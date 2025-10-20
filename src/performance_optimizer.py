import os
import time
import logging
import requests
import pandas as pd
import json
import hashlib
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, List, Optional, Tuple
import threading

from src.login import header
from src.channels import channels

# --- Logging setup ---
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

class PerformanceOptimizer:
    def __init__(self):
        self.cache_dir = "cache"
        self.cache_file = os.path.join(self.cache_dir, "hn_data.json")
        self.cache_metadata_file = os.path.join(self.cache_dir, "cache_metadata.json")
        self.cache_duration = 300  # 5 minutes cache
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Thread-safe lock for cache operations
        self.cache_lock = threading.Lock()
        
    def _get_cache_metadata(self) -> Dict:
        """Get cache metadata safely"""
        try:
            if os.path.exists(self.cache_metadata_file):
                with open(self.cache_metadata_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logging.warning(f"Failed to read cache metadata: {e}")
        return {}
    
    def _set_cache_metadata(self, metadata: Dict):
        """Set cache metadata safely"""
        try:
            with open(self.cache_metadata_file, 'w') as f:
                json.dump(metadata, f)
        except Exception as e:
            logging.warning(f"Failed to write cache metadata: {e}")
    
    def is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        try:
            metadata = self._get_cache_metadata()
            if not metadata:
                return False
                
            cache_time = datetime.fromisoformat(metadata.get('timestamp', ''))
            return datetime.now() - cache_time < timedelta(seconds=self.cache_duration)
        except Exception:
            return False
    
    def load_from_cache(self) -> Optional[pd.DataFrame]:
        """Load data from cache if valid"""
        with self.cache_lock:
            if not self.is_cache_valid():
                return None
                
            try:
                if os.path.exists(self.cache_file):
                    with open(self.cache_file, 'r') as f:
                        data = json.load(f)
                    df = pd.DataFrame(data)
                    logging.info(f"Loaded {len(df)} rows from cache")
                    return df
            except Exception as e:
                logging.warning(f"Failed to load from cache: {e}")
        return None
    
    def save_to_cache(self, df: pd.DataFrame):
        """Save data to cache"""
        with self.cache_lock:
            try:
                # Save data
                df.to_json(self.cache_file, orient='records', date_format='iso')
                
                # Save metadata
                metadata = {
                    'timestamp': datetime.now().isoformat(),
                    'row_count': len(df),
                    'cache_version': '1.0'
                }
                self._set_cache_metadata(metadata)
                logging.info(f"Cached {len(df)} rows")
            except Exception as e:
                logging.warning(f"Failed to save to cache: {e}")
    
    def create_session(self) -> requests.Session:
        """Create optimized session with retry strategy"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,  # Reduced backoff
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    def fetch_suit_data(self, suit: Dict, session: requests.Session) -> List[Dict]:
        """Fetch all data for a single suit (watchlists + agents) in parallel"""
        suit_name = suit.get("name", "")
        parsed_suit = self.parse_suit_name(suit_name)
        if parsed_suit is None:
            return []
        
        (suit_contract_type, suit_blockchain, suit_protocol, 
         suit_address, suit_symbol, suit_label) = parsed_suit
        
        # Prepare tasks for parallel execution
        tasks = []
        
        # Add watchlist tasks
        for watchlist in suit.get("watchlists", []):
            tasks.append(('watchlist', watchlist, suit, parsed_suit))
        
        # Add custom agent tasks  
        for custom_agent in suit.get("customAgents", []):
            tasks.append(('agent', custom_agent, suit, parsed_suit))
        
        # Execute tasks in parallel
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:  # Limit concurrent requests
            future_to_task = {
                executor.submit(self._fetch_monitor_data, task_type, monitor, suit, parsed_suit, session): task_type
                for task_type, monitor, suit, parsed_suit in tasks
            }
            
            for future in as_completed(future_to_task):
                try:
                    result = future.result()
                    if result:
                        results.extend(result)
                except Exception as e:
                    task_type = future_to_task[future]
                    logging.warning(f"Failed to fetch {task_type}: {e}")
        
        return results
    
    def _fetch_monitor_data(self, task_type: str, monitor: Dict, suit: Dict, 
                           parsed_suit: Tuple, session: requests.Session) -> List[Dict]:
        """Fetch data for a single monitor (watchlist or agent)"""
        try:
            if task_type == 'watchlist':
                return self._fetch_watchlist_data(monitor, suit, parsed_suit, session)
            elif task_type == 'agent':
                return self._fetch_agent_data(monitor, suit, parsed_suit, session)
        except Exception as e:
            logging.warning(f"Failed to fetch {task_type} {monitor.get('id', 'unknown')}: {e}")
        return []
    
    def _fetch_watchlist_data(self, watchlist: Dict, suit: Dict, 
                             parsed_suit: Tuple, session: requests.Session) -> List[Dict]:
        """Fetch watchlist data"""
        wl_endpoint = f"https://api.hypernative.xyz/watchlists/{watchlist['id']}/"
        wl_data = session.get(wl_endpoint, headers=header, timeout=5).json().get("data", {})
        
        wl_name = wl_data.get("name", "")
        parsed_watchlist = self.parse_watchlist_name(wl_name)
        if parsed_watchlist is None:
            return []
        
        alert_channels = self.extract_channels(wl_data.get("alertPolicies"))
        channels_for_rows = alert_channels or ["None"]
        
        (risk_id, mon_contract_type, mon_blockchain, mon_protocol, 
         mon_address, mon_symbol, mon_label) = parsed_watchlist
        
        results = []
        for ch in channels_for_rows:
            client_dao = self.get_client_dao(ch)
            results.append({
                "fullSuiteName": suit.get("name", ""),
                "suitContractType": parsed_suit[0],
                "suitBlockchain": parsed_suit[1],
                "suitProtocol": parsed_suit[2],
                "suitAddress": parsed_suit[3],
                "suitSymbol": parsed_suit[4],
                "suitLabel": parsed_suit[5],
                "fullMonitorName": wl_name,
                "monitorType": "Watchlist",
                "monitorRiskID": risk_id,
                "monitorContractType": mon_contract_type,
                "monitorBlockchain": mon_blockchain,
                "monitorProtocol": mon_protocol,
                "monitorAddress": mon_address,
                "monitorSymbol": mon_symbol,
                "monitorLabel": mon_label,
                "monitorAlertChannel": ch,
                "monitorDescription": wl_data.get("description", ""),
                "monitorLink": f"https://app.hypernative.xyz/watchlist/{wl_data.get('id')}" if wl_data.get('id') else "",
                "monitor": "Watchlist",
                "Client": client_dao,
            })
        return results
    
    def _fetch_agent_data(self, custom_agent: Dict, suit: Dict, 
                          parsed_suit: Tuple, session: requests.Session) -> List[Dict]:
        """Fetch custom agent data"""
        agent_endpoint = f"https://api.hypernative.xyz/custom-agents/{custom_agent['id']}/"
        agent_resp = session.get(agent_endpoint, headers=header, timeout=5).json()
        agent_data = agent_resp.get("data", {})
        
        agent_name = agent_data.get("agentName", "")
        agent_type = agent_data.get("agentType", "Custom Agent")
        
        parsed_agent = self.parse_custom_agent_name(agent_name)
        if parsed_agent is None:
            return []
        
        alert_channels = self.extract_channels(agent_data.get("alertPolicies"))
        channels_for_rows = alert_channels or ["None"]
        
        rule_string = ""
        try:
            rule_string = agent_data["rule"]["ruleString"]
        except Exception:
            rule_string = agent_name
        
        (risk_id, mon_contract_type, mon_blockchain, mon_protocol, 
         mon_address, mon_symbol, mon_label) = parsed_agent
        
        results = []
        for ch in channels_for_rows:
            client_dao = self.get_client_dao(ch)
            results.append({
                "fullSuiteName": suit.get("name", ""),
                "suitContractType": parsed_suit[0],
                "suitBlockchain": parsed_suit[1],
                "suitProtocol": parsed_suit[2],
                "suitAddress": parsed_suit[3],
                "suitSymbol": parsed_suit[4],
                "suitLabel": parsed_suit[5],
                "fullMonitorName": agent_name,
                "monitorType": agent_type,
                "monitorRiskID": risk_id,
                "monitorContractType": mon_contract_type,
                "monitorBlockchain": mon_blockchain,
                "monitorProtocol": mon_protocol,
                "monitorAddress": mon_address,
                "monitorSymbol": mon_symbol,
                "monitorLabel": mon_label,
                "monitorAlertChannel": ch,
                "monitorDescription": rule_string,
                "monitorLink": f"https://app.hypernative.xyz/custom-agents?agentId={agent_data.get('id')}" if agent_data.get('id') else "",
                "monitor": "Custom Agent",
                "Client": client_dao,
            })
        return results
    
    def get_client_dao(self, channel: str) -> str:
        """Get client DAO for a channel"""
        channel_dao_map = {
            entry["name"]: entry["dao"]
            for entry in channels
            if entry.get("dao") and entry["dao"] != "None"
        }
        return channel_dao_map.get(channel, "None") if channel != "None" else "None"
    
    # Import parsing methods from original getHN.py
    def parse_suit_name(self, name: str):
        parts = name.split(" ")
        contract_type = parts[0]
        symbol = ""
        if contract_type not in {"[TOKEN]", "[POOL]", "[VAULT]", "[BRIDGE]"}:
            return None
        blockchain = parts[1]
        if contract_type == "[TOKEN]":
            address = parts[2]
            symbol = parts[3]
            label = " ".join(parts[4:])
            protocol = ""
        else:
            protocol = parts[2]
            address = parts[3]
            label = " ".join(parts[4:])
        return contract_type, blockchain, protocol, address, symbol, label

    def parse_watchlist_name(self, name: str):
        parts = name.split(" ")
        risk_id = parts[0]
        contract_type = parts[1]
        if contract_type == "[PROTOCOL]":
            blockchain = parts[2]
            protocol = parts[3]
            address = ""
            label = protocol
        elif contract_type == "[TOKEN]":
            blockchain = parts[2]
            address = parts[3]
            label = " ".join(parts[4:])
            protocol = ""
        elif contract_type == "[CONSENSUSLAYER]":
            blockchain = parts[2]
            address = ""
            protocol = ""
            label = " ".join(parts[3:])
        elif contract_type in {"[MULTISIG]", "[POOL]"}:
            blockchain = parts[2]
            protocol = parts[3]
            address = parts[4]
            label = " ".join(parts[5:])
        elif contract_type == "[L2]":
            address = ""
            blockchain = ""
            protocol = ""
            label = " ".join(parts[2:])
        else:
            return None
        return risk_id, contract_type, blockchain, protocol, address, "", label

    def parse_custom_agent_name(self, name: str):
        parts = name.split(" ")
        
        if len(parts) < 2:
            if len(parts) == 1:
                return parts[0], "[OTHER]", "", "", "", "", ""
            else:
                return None
        
        risk_id = parts[0]
        contract_type = parts[1]
        contract_type_upper = contract_type.upper()
        
        if contract_type_upper in {"[VAULT]", "[EOA]", "[MULTISIG]", "[POOL]", "[OTHER]", "[ORACLE]", "[BRIDGE]", "[TIMELOCK]"}:
            blockchain = parts[2] if len(parts) > 2 else ""
            protocol = parts[3] if len(parts) > 3 else ""
            address = parts[4] if len(parts) > 4 else ""
            symbol = parts[5] if len(parts) > 5 else ""
            label = " ".join(parts[6:]) if len(parts) > 6 else ""
        elif contract_type_upper == "[TOKEN]":
            blockchain = parts[2] if len(parts) > 2 else ""
            protocol = ""
            address = parts[3] if len(parts) > 3 else ""
            symbol = parts[4] if len(parts) > 4 else ""
            label = " ".join(parts[5:]) if len(parts) > 5 else ""
        else:
            if len(parts) >= 4:
                blockchain = parts[1] if len(parts) > 1 else ""
                protocol = parts[2] if len(parts) > 2 else ""
                address = parts[3] if len(parts) > 3 else ""
                symbol = parts[4] if len(parts) > 4 else ""
                label = " ".join(parts[5:]) if len(parts) > 5 else ""
                contract_type = "[OTHER]"
            else:
                return None
        return risk_id, contract_type, blockchain, protocol, address, symbol, label

    def extract_channels(self, alert_policies):
        """Extract channel names from alert policies"""
        out = []
        for p in (alert_policies or []):
            for cc in p.get("channelsConfigurations", []):
                name = cc.get("name")
                if name:
                    out.append(name)
        return list(dict.fromkeys(out))

    def get_hn_monitors_optimized(self, force_refresh: bool = False, limit_suits: int = None) -> pd.DataFrame:
        """Optimized version of get_hn_monitors with caching and parallel processing"""
        start_time = time.time()
        
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_data = self.load_from_cache()
            if cached_data is not None:
                logging.info(f"Using cached data ({len(cached_data)} rows)")
                return cached_data
        
        logging.info("Fetching fresh data from Hypernative API...")
        
        session = self.create_session()
        flattened_rows = []
        
        try:
            # Fetch suits
            suits_resp = session.get("https://api.hypernative.xyz/security-suit/", 
                                   headers=header, timeout=10).json()
            suits = suits_resp.get("data", {}).get("results", [])
            logging.info(f"Found {len(suits)} suits to process.")
            
            # Apply limit for testing if specified
            if limit_suits and limit_suits > 0:
                suits = suits[:limit_suits]
                logging.info(f"Limited to {len(suits)} suits for testing.")
            
            # Process suits in parallel batches
            batch_size = 5  # Process 5 suits at a time
            for i in range(0, len(suits), batch_size):
                batch = suits[i:i + batch_size]
                
                with ThreadPoolExecutor(max_workers=3) as executor:  # Limit concurrent suits
                    future_to_suit = {
                        executor.submit(self.fetch_suit_data, suit, session): suit
                        for suit in batch
                    }
                    
                    for future in as_completed(future_to_suit):
                        try:
                            suit_results = future.result()
                            flattened_rows.extend(suit_results)
                        except Exception as e:
                            suit = future_to_suit[future]
                            logging.warning(f"Failed to process suit {suit.get('name', 'unknown')}: {e}")
                
                # Progress update
                processed = min(i + batch_size, len(suits))
                logging.info(f"Processed {processed}/{len(suits)} suits...")
                
                # Small delay between batches to be respectful to the API
                if processed < len(suits):
                    time.sleep(0.2)
        
        except Exception as e:
            logging.error(f"Failed to fetch suits: {e}")
            return pd.DataFrame()
        
        df = pd.DataFrame(flattened_rows)
        
        # Save to cache
        if not df.empty:
            self.save_to_cache(df)
        
        elapsed = round(time.time() - start_time, 2)
        logging.info(f"Finished in {elapsed}s with {len(df)} rows.")
        return df

# Global optimizer instance
optimizer = PerformanceOptimizer()
