import os
import time
import logging
import requests
import pandas as pd

from src.login import header
from src.channels import channels

# --- Logging setup ---
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)
CSV_FILENAME = "hn_monitors.csv"
CSV_PATH = os.path.join(OUTPUT_DIR, CSV_FILENAME)

SUITS_ENDPOINT = "https://api.hypernative.xyz/security-suit/"


# -----------------------
# Parsing helpers
# -----------------------
def parse_suit_name(name: str):
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


def parse_watchlist_name(name: str):
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


def parse_custom_agent_name(name: str):
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


def extract_channels(alert_policies):
    """
    Collect channel names across ALL alert policies, deduping while preserving order.
    Expected structure:
      alert_policies = [
        {
          "channelsConfigurations": [
            {"name": "..."},
            ...
          ]
        },
        ...
      ]
    """
    out = []
    for p in (alert_policies or []):
        for cc in p.get("channelsConfigurations", []):
            name = cc.get("name")
            if name:
                out.append(name)
    # dedupe preserving order
    return list(dict.fromkeys(out))


# -----------------------
# Main fetcher
# -----------------------
def get_hn_monitors():
    start_time = time.time()
    logging.info("Fetching suits from Hypernative API...")

    # Build channel -> DAO map (ignore channels explicitly mapped to "None")
    channel_dao_map = {
        entry["name"]: entry["dao"]
        for entry in channels
        if entry.get("dao") and entry["dao"] != "None"
    }

    session = requests.Session()
    flattened_rows = []

    try:
        suits_resp = session.get(SUITS_ENDPOINT, headers=header, timeout=30).json()
        suits = suits_resp.get("data", {}).get("results", [])
        logging.info(f"Found {len(suits)} suits to process.")
    except Exception as e:
        logging.error(f"Failed to fetch suits: {e}")
        return pd.DataFrame()

    for i, suit in enumerate(suits, start=1):
        parsed_suit = parse_suit_name(suit.get("name", ""))
        if parsed_suit is None:
            continue

        (
            suit_contract_type,
            suit_blockchain,
            suit_protocol,
            suit_address,
            suit_symbol,
            suit_label,
        ) = parsed_suit

        # ---------- Watchlists ----------
        for watchlist in suit.get("watchlists", []):
            try:
                wl_endpoint = f"https://api.hypernative.xyz/watchlists/{watchlist['id']}/"
                wl_data = session.get(wl_endpoint, headers=header, timeout=30).json().get("data", {})
                wl_id = wl_data.get("id")
                wl_name = wl_data.get("name", "")

                parsed_watchlist = parse_watchlist_name(wl_name)
                if parsed_watchlist is None:
                    continue

                alert_channels = extract_channels(wl_data.get("alertPolicies"))
                # If there are no channels, still create one row with "None"
                channels_for_rows = alert_channels or ["None"]

                (
                    risk_id,
                    mon_contract_type,
                    mon_blockchain,
                    mon_protocol,
                    mon_address,
                    mon_symbol,
                    mon_label,
                ) = parsed_watchlist

                for ch in channels_for_rows:
                    client_dao = channel_dao_map.get(ch, "None") if ch != "None" else "None"
                    flattened_rows.append({
                        "fullSuiteName": suit.get("name", ""),
                        "suitContractType": suit_contract_type,
                        "suitBlockchain": suit_blockchain,
                        "suitProtocol": suit_protocol,
                        "suitAddress": suit_address,
                        "suitSymbol": suit_symbol,
                        "suitLabel": suit_label,
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
                        "monitorLink": f"https://app.hypernative.xyz/watchlist/{wl_id}" if wl_id else "",
                        "monitor": "Watchlist",
                        "Client": client_dao,
                    })
            except Exception as e:
                logging.warning(f"Watchlist failed for suit {suit.get('name','(unknown)')}: {e}")

        # ---------- Custom Agents ----------
        for custom_agent in suit.get("customAgents", []):
            try:
                agent_endpoint = f"https://api.hypernative.xyz/custom-agents/{custom_agent['id']}/"
                agent_resp = session.get(agent_endpoint, headers=header, timeout=30).json()
                agent_data = agent_resp.get("data", {})
                agent_id = agent_data.get("id")
                agent_name = agent_data.get("agentName", "")
                agent_type = agent_data.get("agentType", "Custom Agent")

                parsed_agent = parse_custom_agent_name(agent_name)
                if parsed_agent is None:
                    continue

                alert_channels = extract_channels(agent_data.get("alertPolicies"))
                channels_for_rows = alert_channels or ["None"]

                # Try to get ruleString safely
                rule_string = ""
                try:
                    rule_string = agent_data["rule"]["ruleString"]
                except Exception as e:
                    logging.warning(
                        f"Missing ruleString in agent '{agent_name}' from suit '{suit.get('name','(unknown)')}': {e}"
                    )
                    rule_string = f"⚠️ Incomplete due to missing ruleString"

                (
                    risk_id,
                    mon_contract_type,
                    mon_blockchain,
                    mon_protocol,
                    mon_address,
                    mon_symbol,
                    mon_label,
                ) = parsed_agent

                for ch in channels_for_rows:
                    client_dao = channel_dao_map.get(ch, "None") if ch != "None" else "None"
                    flattened_rows.append({
                        "fullSuiteName": suit.get("name", ""),
                        "suitContractType": suit_contract_type,
                        "suitBlockchain": suit_blockchain,
                        "suitProtocol": suit_protocol,
                        "suitAddress": suit_address,
                        "suitSymbol": suit_symbol,
                        "suitLabel": suit_label,
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
                        "monitorLink": f"https://app.hypernative.xyz/custom-agents?agentId={agent_id}" if agent_id else "",
                        "monitor": "Custom Agent",
                        "Client": client_dao,
                    })

            except Exception as e:
                logging.warning(f"Custom agent failed for suit {suit.get('name','(unknown)')}: {e}")

        if i % 10 == 0 or i == len(suits):
            logging.info(f"Processed {i}/{len(suits)} suits...")

    df = pd.DataFrame(flattened_rows)

    elapsed = round(time.time() - start_time, 2)
    logging.info(f"Finished in {elapsed}s with {len(df)} rows.")
    return df
