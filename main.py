import streamlit as st
import pandas as pd
from src.getHN import get_hn_monitors

# Load data with cache to avoid reloading on every interaction
@st.cache_data(show_spinner="Loading HN data...")
def load_data():
    return get_hn_monitors()

st.set_page_config(page_title="Hypernative Alert Monitor", layout="wide")
st.title("📡 Hypernative Alerts Dashboard")

# Load and sanitize DataFrame
df = load_data()
# Drop rows with essential missing data
#essential_cols = ["Client", "monitorAddress", "monitorSymbol", "monitorLabel", "suitProtocol", monitorSymbol"]
#df = df.dropna(subset=essential_cols)
# df.to_csv("hn_monitors.csv", index=False)  # Save to CSV for debugging

# df = pd.read_csv('hn_monitors.csv')
# Optional: fill NAs in non-essential fields to avoid rendering issues
df.fillna("", inplace=True)

# Group the full DataFrame by monitorAddress to get all monitors per suite
suite_monitors = dict(tuple(df.groupby("fullSuiteName", sort=False)))
# Group original DF by Client for tagging reference
client_groups = dict(tuple(df.groupby("Client", sort=True)))

# Filter out any invalid client names like None or NaN
valid_clients = [c for c in client_groups if pd.notnull(c)]

import ast

for client in valid_clients:
    df_client = client_groups[client]
    client_suites = df_client["fullSuiteName"].unique()

    with st.expander(f"🛡️ {client}", expanded=False):
        for suite_addr in client_suites:
            df_suite = suite_monitors.get(suite_addr)
            if df_suite is None:
                continue

            full_suite_name = df_suite["fullSuiteName"].iloc[0] or "UnknownPosition"
            position_title = f"{full_suite_name}"

            if st.checkbox(f"📍 {position_title}", key=f"{client}_{suite_addr}"):
                for _, row in df_suite.iterrows():
                    alert = row.get("monitorLabel", "Unnamed Alert")
                    monitor_type = row.get("monitorType", "Unknown Type")
                    monitor_symbol = row.get("monitorSymbol", "Unnamed Symbol")
                    monitor_addr = row.get("monitorAddress")
                    monitor_name = row.get("fullMonitorName", "Unnamed Monitor")
                    monitor = row.get("monitor", "Unknown Monitor")
                    monitor_channels = row.get("monitorAlertChannels", [])

                    if isinstance(monitor_channels, str):
                        try:
                            monitor_channels = ast.literal_eval(monitor_channels)
                        except Exception:
                            monitor_channels = []

                    # Check if client name is found in any channel string (case-insensitive)
                    client_clean = client.strip().lower()
                    is_tagged = any(client_clean in channel.lower() for channel in monitor_channels)

                    flag = "✅" if is_tagged else "❌"
                    monitor_link = row.get("monitorLink", "")
                    link_icon = f"[↗️](<{monitor_link}>)" if monitor_link else ""

                    st.markdown(
                        f"- {flag} {monitor}: {monitor_type} - {monitor_name} {link_icon} "
                        f"------> Slack Channels: {monitor_channels}"
                    )
                    #st.write(f"[DEBUG] Client: {client_clean}, Channels: {monitor_channels}")

