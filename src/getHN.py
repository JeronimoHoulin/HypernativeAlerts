from src.login import header
from src.channels import channels
import requests
import json
import os
import pandas as pd

output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

endpoint = "https://api.hypernative.xyz/security-suit/"
response = requests.get(endpoint, headers=header).json()

def remove_alert_policies(data):
    if "alertPolicies" in data:
        del data["alertPolicies"]
    return data

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

def get_hn_monitors():
    # DAO lookup map
    channel_dao_map = {
        entry["name"]: entry["dao"] for entry in channels if entry["dao"] != "None"
    }

    flattened_data = []

    for suit in response["data"]["results"]:
        print(f"Processing suit: {suit['name']}")
        parsed_suit = parse_suit_name(suit["name"])
        if parsed_suit is None:
            continue
        contract_type, blockchain, protocol, address, symbol, label = parsed_suit

        for watchlist in suit.get("watchlists", []):
            try:
                watchlist_endpoint = f"https://api.hypernative.xyz/watchlists/{watchlist['id']}/"
                watchlist_data = requests.get(watchlist_endpoint, headers=header).json()
                print(f"Processing watchlist: {watchlist_data['data']['name']} for suit: {suit['name']}")
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
                    "monitor": "Watchlist",
                    "Client": client_dao
                })
            except Exception as e:
                print(f"Error processing watchlist {watchlist['id']} for suit {suit['name']}: {e}")
                continue

        for custom_agent in suit.get("customAgents", []):
            try:
                agent_endpoint = f"https://api.hypernative.xyz/custom-agents/{custom_agent['id']}/"
                agent_data = requests.get(agent_endpoint, headers=header).json()
                print(f"Processing custom agent: {agent_data['data']['agentName']} for suit: {suit['name']}")
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
                    "monitor": "Custom Agent",
                    "Client": client_dao
                })
            except Exception as e:
                print(f"Error processing custom agent {custom_agent['id']} for suit {suit['name']}: {e}")
                continue

    df = pd.DataFrame(flattened_data)
    print("Processing complete.")
    return df