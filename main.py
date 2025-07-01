import streamlit as st
import pandas as pd
from src.getHN import get_hn_monitors
from dotenv import load_dotenv
import os
import ast

# Must be the very first Streamlit command
st.set_page_config(page_title="Hypernative Alert Monitor", layout="wide")

# Load environment variables
load_dotenv()
KPKUSERNAME = os.getenv("KPKUSERNAME")
KPKPASSWORD = os.getenv("KPKPASSWORD")

# Session state login check
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# One-time login form
if not st.session_state.authenticated:
    with st.form("login_form"):
        input_username = st.text_input("Username", type="password")
        input_password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            if input_username == KPKUSERNAME and input_password == KPKPASSWORD:
                st.session_state.authenticated = True
                st.success("Login successful. Loading app...")
                st.rerun()
            else:
                st.error("Invalid username or password.")
    st.stop()  # Stop further execution until authenticated

# --- Authenticated User Flow ---
st.title("📡 Hypernative Alerts Dashboard")

@st.cache_data(show_spinner="Loading HN data...")
def load_data():
    return get_hn_monitors()

df = load_data()
df.fillna("", inplace=True)

suite_monitors = dict(tuple(df.groupby("fullSuiteName", sort=False)))
client_groups = dict(tuple(df.groupby("Client", sort=True)))
valid_clients = [c for c in client_groups if pd.notnull(c)]

for client in valid_clients:
    df_client = client_groups[client]
    client_suites = df_client["fullSuiteName"].unique()

    with st.expander(f"🛡️ {client}", expanded=False):
        for suite_addr in client_suites:
            df_suite = suite_monitors.get(suite_addr)
            if df_suite is None:
                continue

            position_title = df_suite["fullSuiteName"].iloc[0] or "UnknownPosition"
            if st.checkbox(f"📍 {position_title}", key=f"{client}_{suite_addr}"):
                for _, row in df_suite.iterrows():
                    alert = row.get("monitorLabel", "Unnamed Alert")
                    monitor_type = row.get("monitorType", "Unknown Type")
                    monitor_symbol = row.get("monitorSymbol", "Unnamed Symbol")
                    monitor_addr = row.get("monitorAddress")
                    monitor_name = row.get("fullMonitorName", "Unnamed Monitor")
                    monitor = row.get("monitor", "Unknown Monitor")
                    
                    monitor_channels_raw = row.get("monitorAlertChannels", [])
                    if isinstance(monitor_channels_raw, str):
                        try:
                            monitor_channels = ast.literal_eval(monitor_channels_raw)
                        except Exception:
                            monitor_channels = []
                    else:
                        monitor_channels = monitor_channels_raw

                    client_clean = client.strip().lower()
                    is_tagged = any(client_clean in channel.lower() for channel in monitor_channels)

                    flag = "✅" if is_tagged else "❌"
                    monitor_link = row.get("monitorLink", "")
                    link_icon = f"[↗️](<{monitor_link}>)" if monitor_link else ""

                    st.markdown(
                        f"- {flag} {monitor}: {monitor_type} - {monitor_name} {link_icon} "
                        f"------> Slack Channels: {monitor_channels}"
                    )

# Refresh button
if st.button("🔄 Refresh Data (5min..)"):
    st.cache_data.clear()
    st.rerun()
