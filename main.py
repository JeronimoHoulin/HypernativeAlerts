import streamlit as st
import pandas as pd
import os
import ast
from src.getHN import get_hn_monitors

from dotenv import load_dotenv
load_dotenv()

# --- Auth setup ---
KPKUSERNAME = os.getenv("KPKUSERNAME")
KPKPASSWORD = os.getenv("KPKPASSWORD")

st.set_page_config(page_title="Hypernative Alert Monitor", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

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
    st.stop()

st.title("📡 Hypernative Alerts Dashboard")

# --- Utility functions ---
@st.cache_data(show_spinner="Loading HN data...")
def load_data():
    return get_hn_monitors()

def parse_channels(raw):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            # Try to parse as a literal list
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        # Fallback: treat as comma-separated string
        return [s.strip() for s in raw.split(",") if s.strip()]
    return []


def is_assigned_to_client(row, client_name):
    channels = parse_channels(row.get("monitorAlertChannels", []))
    return any(client_name.lower() in str(c).lower() for c in channels)

def show_monitor(row, channels, client_name):
    monitor_name = row.get("fullMonitorName", "Unnamed Monitor")
    monitor_type = row.get("monitorType", "Unknown Type")
    monitor = row.get("monitor", "Unknown Monitor")
    monitor_link = row.get("monitorLink", "")
    monitor_desc = row.get("monitorDescription", "")
    monitor_desc = (monitor_desc[:250] + "…") if len(monitor_desc) > 250 else monitor_desc

    is_assigned = any(client_name.lower() in c.lower() for c in channels)
    status_icon = "✅" if is_assigned else "❌"
    link = f"[↗️]({monitor_link})" if monitor_link else ""
    relevant_channels = [c for c in channels if client_name.lower() in c.lower()]

    st.markdown(
        f"- {status_icon} **{monitor}** | *{monitor_type}* | {monitor_name} {link}  \n"
        f"&nbsp;&nbsp;&nbsp;&nbsp;📝 {monitor_desc}  \n"
        f"&nbsp;&nbsp;&nbsp;&nbsp;🔔 Channels: `{', '.join(relevant_channels) or '—'}`"
    )

# --- Data load ---
df = load_data()
df.fillna("", inplace=True)

# --- Sidebar and client selection ---
st.sidebar.title("👤 Select Client")
clients = sorted(df["Client"].dropna().unique())
clients = [c for c in clients if str(c).strip() != ""]
selected_client = st.sidebar.selectbox("Choose a client", clients)

if st.sidebar.button("🔄 Refresh Data"):
    get_hn_monitors(force_refresh=True)  # refetch from API and cache new CSV
    st.cache_data.clear()
    st.rerun()

# --- Client Summary ---
df_client = df[df["Client"] == selected_client]
suite_monitors = dict(tuple(df.groupby("fullSuiteName", sort=False)))
client_suites = df_client["fullSuiteName"].unique()

total_suits = df_client["fullSuiteName"].nunique()

# --- Count assigned monitors before rendering summary ---
total_assigned_monitors = 0
total_unassigned_monitors = 0

for suite in client_suites:
    df_suite_all = suite_monitors.get(suite)
    if df_suite_all is None:
        continue

    for _, row in df_suite_all.iterrows():
        channels = parse_channels(row.get("monitorAlertChannels", []))
        #assigned = any(selected_client.lower() in c.lower() for c in channels)
        assigned = any(selected_client.strip().lower() in str(c).strip().lower() for c in channels)
        if assigned:
            total_assigned_monitors += 1
        else:
            total_unassigned_monitors += 1

st.markdown(f"## 🔎 Monitoring Overview for `{selected_client}`")
st.info(f"**Client Summary:** 🛡️ {total_suits} Suits | ✅ {total_assigned_monitors} Assigned Monitors | ❌ {total_unassigned_monitors} Missing Client Alert")


# --- Display data by suite ---
for suite in client_suites:
    df_suite_all = suite_monitors.get(suite)
    if df_suite_all is None:
        continue

    suite_title = df_suite_all["fullSuiteName"].iloc[0] or "Unnamed Suite"
    if suite_title == "pendle":
        print(suite_title) 

    with st.expander(f"🧱 {suite_title}", expanded=False):
        col1, col2 = st.columns([1, 5])
        with col1:
            st.write("**Blockchain:**", df_suite_all["suitBlockchain"].iloc[0])
            st.write("**Protocol:**", df_suite_all["suitProtocol"].iloc[0])
        with col2:
            st.write("**Label:**", df_suite_all["suitLabel"].iloc[0])
            st.write("**Address:**", df_suite_all["suitAddress"].iloc[0])

        assigned_rows = []
        unassigned_rows = []

        for _, row in df_suite_all.iterrows():
            channels = parse_channels(row.get("monitorAlertChannels", []))
            assigned = any(selected_client.lower() in c.lower() for c in channels)
            (assigned_rows if assigned else unassigned_rows).append((row, channels))

        if assigned_rows:
            st.markdown("#### ✅ Monitors Assigned to This Client")
            for row, channels in assigned_rows:
                show_monitor(row, channels, selected_client)

        if unassigned_rows:
            st.markdown("#### ❌ Monitors Missing Client Channel")
            for row, channels in unassigned_rows:
                show_monitor(row, channels, selected_client)
