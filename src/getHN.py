from login import header
import requests
import json
import os
import pandas as pd
# Ensure the output directory exists
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)
endpoint = f"https://api.hypernative.xyz/security-suit/"
response = requests.get(endpoint, headers=header).json()

# Function to remove 'alertPolicies' key from data
def remove_alert_policies(data):
    if "alertPolicies" in data:
        del data["alertPolicies"]
    return data
# Function to parse suit name and extract contractType, blockchain, protocol, address, and label
def parse_suit_name(name):
    parts = name.split(" ")
    contract_type = parts[0]  # Either "TOKEN", "POOL", "VAULT", or "BRIDGE"
    symbol = ""
    # Skip suit if the type is not one of the specified ones
    if contract_type not in {"[TOKEN]", "[POOL]", "[VAULT]", "[BRIDGE]"}:
        return None  # Indicate to skip this suit
    blockchain = parts[1]
    if contract_type == "[TOKEN]":
        address = parts[2]
        symbol = parts[3]
        label = " ".join(parts[4:])  # Join the rest as label
        protocol = ""  # No protocol for TOKEN, VAULT, or BRIDGE suits
    else:
        protocol = parts[2]
        address = parts[3]
        label = " ".join(parts[4:])  # Join the rest as label
    return contract_type, blockchain, protocol, address, symbol, label
# Function to parse watchlist names based on specific contractType formats
def parse_watchlist_name(name):
    parts = name.split(" ")
    risk_id = parts[0]
    contract_type = parts[1]
    if contract_type == "[PROTOCOL]":
        # Format: "[riskId] [PROTOCOL] chain protocolname"
        blockchain = parts[2]
        protocol = parts[3]
        address = ""
        label = protocol
    elif contract_type == "[TOKEN]":
        # Format: "[riskId] [TOKEN] chain address label"
        blockchain = parts[2]
        address = parts[3]
        label = " ".join(parts[4:])
        protocol = ""
    elif contract_type == "[CONSENSUSLAYER]":
        # Format: "[riskId] [CONSENSUSLAYER] chain label"
        blockchain = parts[2]
        address = ""
        protocol = ""
        label = " ".join(parts[3:])
    elif contract_type == "[MULTISIG]" or contract_type == "[POOL]":
        # Format: "[riskId] [MULTISIG/POOL] chain protocol address label"
        blockchain = parts[2]
        protocol = parts[3]
        address = parts[4]
        label = " ".join(parts[5:])
    elif contract_type == "[L2]":
        # Format: "[riskId] [L2] label"
        address = ""
        blockchain = ""
        protocol = ""
        label = " ".join(parts[2:])
    else:
        return None  # Skip if not matching the specified types
    return risk_id, contract_type, blockchain, protocol, address, symbol, label
# Function to parse custom agent names based on specific contractType formats
def parse_custom_agent_name(name):
    parts = name.split(" ")
    risk_id = parts[0]
    contract_type = parts[1]
    if contract_type in {"[VAULT]", "[EOA]", "[MULTISIG]", "[POOL]", "[OTHER]", "[ORACLE]", "[BRIDGE]", "[TIMELOCK]"}:
        # Common structure for these types
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
        return None  # Skip if not matching the specified types
    return risk_id, contract_type, blockchain, protocol, address, symbol, label

def get_hn_monitors():

    flattened_data = []
    # Process each suit and extract its details and associated monitors
    for suit in response["data"]["results"]:
        print(f"Processing suit: {suit['name']}")
        # Parse the suit name to get required fields
        parsed_suit = parse_suit_name(suit["name"])
        if parsed_suit is None:
            continue  # Skip suits that do not match TOKEN, POOL, VAULT, or BRIDGE
        contract_type, blockchain, protocol, address, symbol, label = parsed_suit
        # Extract monitors from watchlists
        for watchlist in suit.get("watchlists", []):
            try:
                watchlist_endpoint = f"https://api.hypernative.xyz/watchlists/{watchlist['id']}/"
                watchlist_data = requests.get(watchlist_endpoint, headers=header).json()
                print(f"Processing watchlist: {watchlist_data['data']['name']} for suit: {suit['name']}")
                parsed_watchlist = parse_watchlist_name(watchlist_data["data"]["name"])
                if parsed_watchlist is None:
                    continue  # Skip if not a specified watchlist type
                alert_channels = []
                alert_channels_config = watchlist_data["data"]["alertPolicies"][0]
                for channel in alert_channels_config["channelsConfigurations"]:
                    alert_channels.append(channel["name"])
                (
                    risk_id,
                    monitor_contract_type,
                    monitor_blockchain,
                    monitor_protocol,
                    monitor_address,
                    monitor_symbol,
                    monitor_label,
                ) = parsed_watchlist
                # Flatten the monitor data
                flattened_data.append(
                    {
                        "suitContractType": contract_type,
                        "suitBlockchain": blockchain,
                        "suitProtocol": protocol,
                        "suitAddress": address,
                        "suitSymbol": symbol,
                        "suitLabel": label,
                        "monitorRiskID": risk_id,
                        "monitorContractType": monitor_contract_type,
                        "monitorBlockchain": monitor_blockchain,
                        "monitorProtocol": monitor_protocol,
                        "monitorAddress": monitor_address,
                        "monitorSymbol": monitor_symbol,
                        "monitorLabel": monitor_label,
                        "monitorAlertChannels": alert_channels,
                        "monitorType": "Watchlist",
                    }
                )
            except Exception as e:
                print(f"Error processing watchlist {watchlist['id']} for suit {suit['name']}: {e}")
                continue
        # Extract monitors from custom agents
        for custom_agent in suit.get("customAgents", []):
            try:
                agent_endpoint = f"https://api.hypernative.xyz/custom-agents/{custom_agent['id']}/"
                agent_data = requests.get(agent_endpoint, headers=header).json()
                print(f"Processing custom agent: {agent_data['data']['agentName']} for suit: {suit['name']}")
                parsed_custom_agent = parse_custom_agent_name(agent_data["data"]["agentName"])
                if parsed_custom_agent is None:
                    continue  # Skip if not a specified custom agent type
                alert_channels = []
                alert_channels_config = agent_data["data"]["alertPolicies"][0]
                for channel in alert_channels_config["channelsConfigurations"]:
                    alert_channels.append(channel["name"])
                (
                    risk_id,
                    monitor_contract_type,
                    monitor_blockchain,
                    monitor_protocol,
                    monitor_address,
                    monitor_symbol,
                    monitor_label,
                ) = parsed_custom_agent
                # Flatten the monitor data
                flattened_data.append(
                    {
                        "suitContractType": contract_type,
                        "suitBlockchain": blockchain,
                        "suitProtocol": protocol,
                        "suitAddress": address,
                        "suitSymbol": symbol,
                        "suitLabel": label,
                        "monitorRiskID": risk_id,
                        "monitorContractType": monitor_contract_type,
                        "monitorBlockchain": monitor_blockchain,
                        "monitorProtocol": monitor_protocol,
                        "monitorAddress": monitor_address,
                        "monitorSymbol": monitor_symbol,
                        "monitorLabel": monitor_label,
                        "monitorAlertChannels": alert_channels,
                        "monitorType": "Custom Agent",
                    }
                )
            except Exception as e:
                print(f"Error processing custom agent {custom_agent['id']} for suit {suit['name']}: {e}")
                continue
    # Create DataFrame from the flattened data
    df = pd.DataFrame(flattened_data)
    print(f"Processing complete.")
    return df