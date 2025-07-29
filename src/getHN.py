import requests
import os
import pandas as pd
import logging
import time

from src.login import header
from src.channels import channels

# --- Logging setup ---
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

endpoint = "https://api.hypernative.xyz/security-suit/"
response = requests.get(endpoint, headers=header).json()

def parse_suit_name(name):
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

def parse_watchlist_name(name):
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

def parse_custom_agent_name(name):
    parts = name.split(" ")
    risk_id = parts[0]
    contract_type = parts[1]
    if contract_type in {"[VAULT]", "[EOA]", "[MULTISIG]", "[POOL]", "[OTHER]", "[ORACLE]", "[BRIDGE]", "[TIMELOCK]"}:
        blockchain = parts[2] if len(parts) > 2 else ""
        protocol = parts[3] if len(parts) > 3 else ""
        address = parts[4] if len(parts) > 4 else ""
        symbol = parts[5] if len(parts) > 5 else ""
        label = parts[6] if len(parts) > 6 else ""
    elif contract_type == "[TOKEN]":
        blockchain = parts[2] if len(parts) > 2 else ""
        protocol = ""
        address = parts[3] if len(parts) > 3 else ""
        symbol = parts[4] if len(parts) > 4 else ""
        label = parts[5] if len(parts) > 5 else ""
    else:
        return None
    return risk_id, contract_type, blockchain, protocol, address, symbol, label

def get_hn_monitors(force_refresh=False):
    start_time = time.time()

    logging.info("Fetching fresh data from Hypernative API...")

    channel_dao_map = {
        entry["name"]: entry["dao"] for entry in channels if entry["dao"] != "None"
    }

    flattened_data = []
    suits = response["data"]["results"]
    logging.info(f"Found {len(suits)} suits to process.")

    for i, suit in enumerate(suits, start=1):
        parsed_suit = parse_suit_name(suit["name"])
        if parsed_suit is None:
            continue
        contract_type, blockchain, protocol, address, symbol, label = parsed_suit

        for watchlist in suit.get("watchlists", []):
            try:
                watchlist_endpoint = f"https://api.hypernative.xyz/watchlists/{watchlist['id']}/"
                watchlist_data = requests.get(watchlist_endpoint, headers=header).json()
                monitor_id = watchlist_data["data"]["id"]
                parsed_watchlist = parse_watchlist_name(watchlist_data["data"]["name"])
                if parsed_watchlist is None:
                    continue
                alert_channels = [
                    channel["name"]
                    for channel in watchlist_data["data"]["alertPolicies"][0]["channelsConfigurations"]
                ]
                client_dao = next(
                    (channel_dao_map[name] for name in alert_channels if name in channel_dao_map),
                    "None"
                )
                (
                    risk_id, monitor_contract_type, monitor_blockchain,
                    monitor_protocol, monitor_address, monitor_symbol, monitor_label
                ) = parsed_watchlist
                flattened_data.append({
                    "fullSuiteName": suit['name'], 
                    "suitContractType": contract_type,
                    "suitBlockchain": blockchain,
                    "suitProtocol": protocol,
                    "suitAddress": address,
                    "suitSymbol": symbol,
                    "suitLabel": label,
                    "fullMonitorName": watchlist_data["data"]["name"],
                    "monitorType": "Watchlist",
                    "monitorRiskID": risk_id,
                    "monitorContractType": monitor_contract_type,
                    "monitorBlockchain": monitor_blockchain,
                    "monitorProtocol": monitor_protocol,
                    "monitorAddress": monitor_address,
                    "monitorSymbol": monitor_symbol,
                    "monitorLabel": monitor_label,
                    "monitorAlertChannels": alert_channels,
                    "monitorDescription": watchlist_data["data"]["description"],
                    "monitorLink": f"https://app.hypernative.xyz/watchlist/{monitor_id}",
                    "monitor": "Watchlist",
                    "Client": client_dao
                })
            except Exception as e:
                logging.warning(f"Watchlist failed for suit {suit['name']}: {e}")

        for custom_agent in suit.get("customAgents", []):
            try:
                agent_endpoint = f"https://api.hypernative.xyz/custom-agents/{custom_agent['id']}/"
                agent_data = requests.get(agent_endpoint, headers=header).json()
                agent_id = agent_data["data"]["id"]
                parsed_custom_agent = parse_custom_agent_name(agent_data["data"]["agentName"])
                if parsed_custom_agent is None:
                    continue
                alert_channels = [
                    channel["name"]
                    for channel in agent_data["data"]["alertPolicies"][0]["channelsConfigurations"]
                ]
                agent_type = agent_data["data"]["agentType"]
                client_dao = next(
                    (channel_dao_map[name] for name in alert_channels if name in channel_dao_map),
                    "None"
                )
                (
                    risk_id, monitor_contract_type, monitor_blockchain,
                    monitor_protocol, monitor_address, monitor_symbol, monitor_label
                ) = parsed_custom_agent

                # Try to get ruleString safely
                rule_string = ""
                try:
                    rule_string = agent_data["data"]["rule"]["ruleString"]
                except KeyError as e:
                    logging.warning(f"Missing ruleString in agent {agent_data['data']['agentName']} from suit {suit['name']}: {e}")
                    rule_string = f"⚠️ Incomplete due to missing key: {e}"

                flattened_data.append({
                    "fullSuiteName": suit['name'], 
                    "suitContractType": contract_type,
                    "suitBlockchain": blockchain,
                    "suitProtocol": protocol,
                    "suitAddress": address,
                    "suitSymbol": symbol,
                    "suitLabel": label,
                    "fullMonitorName": agent_data["data"]["agentName"],
                    "monitorType": agent_type,
                    "monitorRiskID": risk_id,
                    "monitorContractType": monitor_contract_type,
                    "monitorBlockchain": monitor_blockchain,
                    "monitorProtocol": monitor_protocol,
                    "monitorAddress": monitor_address,
                    "monitorSymbol": monitor_symbol,
                    "monitorLabel": monitor_label,
                    "monitorAlertChannels": alert_channels,
                    "monitorDescription": rule_string,
                    "monitorLink": f"https://app.hypernative.xyz/custom-agents?agentId={agent_id}",
                    "monitor": "Custom Agent",
                    "Client": client_dao
                })

            except Exception as e:
                logging.warning(f"Custom agent failed for suit {suit['name']}: {e}")


        if i % 10 == 0 or i == len(suits):
            logging.info(f"Processed {i}/{len(suits)} suits...")
    
    

    df = pd.DataFrame(flattened_data)
    try:
        df.to_csv(csv_path, index=False)
        logging.info(f"Saved CSV to {csv_path}")
    except Exception as e:
        logging.warning(f"Failed to save CSV: {e}")

    elapsed = round(time.time() - start_time, 2)
    logging.info(f"Finished in {elapsed}s with {len(df)} monitors.")
    return df