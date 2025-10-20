import streamlit as st
import pandas as pd
import os
import ast
from src.performance_optimizer import optimizer

from dotenv import load_dotenv
load_dotenv()

# --- Auth setup ---
KPKUSERNAME = os.getenv("KPKUSERNAME")
KPKPASSWORD = os.getenv("KPKPASSWORD")

st.set_page_config(page_title="kpk Hypernative Monitors", layout="wide", page_icon="🚀")

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

st.title("📡 Hypernative Monitors Dashboard")

# --- Utility functions ---
@st.cache_data(ttl=300, show_spinner=False)  # 5 minute cache - disabled spinner to avoid duplicate loading messages
def load_data(force_refresh=False):
    try:
        # Use limit for testing - set to 5 suits for quick testing
        test_limit = 5 if st.session_state.get('test_mode', False) else None
        df = optimizer.get_hn_monitors_optimized(force_refresh=force_refresh, limit_suits=test_limit)
        
        # Validate that we got actual data
        if df is None or df.empty:
            st.warning("⚠️ No data returned from API. This might be a temporary issue.")
            return pd.DataFrame()
        
        return df
        
    except Exception as e:
        st.error(f"❌ Failed to load data: {str(e)}")
        st.error("The app will continue running. Try refreshing the data.")
        # Log the full error for debugging
        import traceback
        st.error(f"Debug info: {traceback.format_exc()}")
        return pd.DataFrame()

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
    channels = parse_channels(row.get("monitorAlertChannel", []))
    client_lower = client_name.lower().strip()
    return any(client_lower in str(c).lower() for c in channels)

def show_monitor(row, channels, client_name):
    monitor_name = row.get("fullMonitorName", "Unnamed Monitor")
    monitor_type = row.get("monitorType", "Unknown Type")
    monitor = row.get("monitor", "Unknown Monitor")
    monitor_link = row.get("monitorLink", "")
    monitor_desc = row.get("monitorDescription", "")
    monitor_desc = (monitor_desc[:250] + "…") if len(monitor_desc) > 250 else monitor_desc

    is_assigned = any(client_name.lower().strip() in c.lower() for c in channels)
    status_icon = "✅" if is_assigned else "❔"
    link = f"[↗️]({monitor_link})" if monitor_link else ""
    relevant_channels = [c for c in channels if client_name.lower().strip() in c.lower()]

    st.markdown(
        f"- {status_icon} **{monitor}** | *{monitor_type}* | {monitor_name} {link}  \n"
        f"&nbsp;&nbsp;&nbsp;&nbsp;📝 {monitor_desc}  \n"
        f"&nbsp;&nbsp;&nbsp;&nbsp;🔔 Channels: `{', '.join(relevant_channels) or '—'}`"
    )

# --- Data load ---
# Check if we should force refresh
force_refresh = st.session_state.get('force_refresh', False)
if force_refresh:
    st.session_state.force_refresh = False  # Reset the flag

# Check if this is the first time loading data
first_load = st.session_state.get('first_load', True)
if first_load:
    st.session_state.first_load = False
    force_refresh = True  # Force fresh data on first load

# Load data with minimal loading indicators
if force_refresh:
    with st.spinner("Loading data..."):
        df = load_data(force_refresh=force_refresh)
else:
    # Check if we have cached data
    if optimizer.is_cache_valid():
        df = load_data(force_refresh=force_refresh)
    else:
        with st.spinner("Loading data..."):
            df = load_data(force_refresh=True)

if df.empty:
    st.error("No data available. Please check your connection and try refreshing.")
    st.info("The app will continue running. Click the 'Refresh Data' button to retry.")
    # Show a more helpful message and don't create empty DataFrame
    st.warning("⚠️ No data loaded. This could be due to:")
    st.markdown("""
    - Network connectivity issues
    - API authentication problems  
    - API rate limiting
    - Server maintenance
    
    **Try clicking 'Refresh Data' to retry loading.**
    """)
    
    # Show debug info even when no data
    with st.expander("🔍 Debug Information", expanded=True):
        st.write("**DataFrame Info:**")
        st.write(f"- Shape: {df.shape}")
        st.write(f"- Columns: {list(df.columns) if not df.empty else 'No columns'}")
        st.write(f"- Is None: {df is None}")
        st.write(f"- Is Empty: {df.empty}")
        
        # Try to show any cached data
        try:
            cached_data = optimizer.load_from_cache()
            if cached_data is not None and not cached_data.empty:
                st.write(f"**Cached Data Available:** {len(cached_data)} rows")
                st.write("**Cached Columns:**", list(cached_data.columns))
            else:
                st.write("**No Cached Data Available")
        except Exception as e:
            st.write(f"**Cache Error:** {e}")
    
    st.stop()  # Stop the app if no data is available
else:
    df.fillna("", inplace=True)
    
    # Data loaded successfully - no status messages needed

# --- Sidebar and client selection ---
st.sidebar.title("👤 Select Client")
clients = sorted(df["Client"].dropna().unique())
clients = [c for c in clients if str(c).strip() != ""]

if not clients:
    st.warning("No clients available. Please refresh the data.")
    selected_client = None
else:
    selected_client = st.sidebar.selectbox("Choose a client", clients)

if st.sidebar.button("🔄 Refresh Data"):
    # Set flag to force refresh and clear cache
    st.session_state.force_refresh = True
    st.cache_data.clear()
    st.success("Cache cleared. Refreshing data...")
    st.rerun()

# Add cache status indicator
if not df.empty:
    if optimizer.is_cache_valid():
        st.sidebar.success("✅ Using cached data")
    else:
        st.sidebar.info("🔄 Fresh data loaded")
else:
    st.sidebar.warning("⚠️ No data available")

# Add debug information in sidebar
with st.sidebar.expander("🔧 Debug Info", expanded=False):
    st.write(f"**Data Rows:** {len(df)}")
    st.write(f"**Cache Valid:** {optimizer.is_cache_valid()}")
    st.write(f"**Force Refresh:** {force_refresh}")
    st.write(f"**Test Mode:** {st.session_state.get('test_mode', False)}")
    
    if not df.empty:
        st.write(f"**Clients Found:** {len(clients)}")
        st.write(f"**Sample Client:** {clients[0] if clients else 'None'}")
    
    # Test mode toggle
    test_mode = st.checkbox("Test Mode (5 suits only)", value=st.session_state.get('test_mode', False))
    if test_mode != st.session_state.get('test_mode', False):
        st.session_state.test_mode = test_mode
        st.rerun()
    
    if st.button("🗑️ Clear Cache"):
        st.cache_data.clear()
        st.success("Cache cleared!")
        st.rerun()

# --- Client Summary ---
if selected_client is None:
    st.info("Please select a client from the sidebar to view their monitors.")
    st.stop()

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
        channels = parse_channels(row.get("monitorAlertChannel", []))
        #assigned = any(selected_client.lower() in c.lower() for c in channels)
        assigned = any(selected_client.lower().strip() in str(c).lower() for c in channels)
        if assigned:
            total_assigned_monitors += 1
        else:
            total_unassigned_monitors += 1

st.markdown(f"## 🔎 Overview for `{selected_client}`")
st.info(f"**Client Summary:** 🛡️ {total_suits} Suits | ✅ {total_assigned_monitors} Assigned Monitors | ❔ {total_unassigned_monitors} Unassigned Monitors")


# --- Display data by suite ---
for suite in client_suites:
    df_suite_all = suite_monitors.get(suite)
    if df_suite_all is None:
        continue

    suite_title = df_suite_all["fullSuiteName"].iloc[0] or "Unnamed Suite"

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
            channels = parse_channels(row.get("monitorAlertChannel", []))
                
            assigned = any(selected_client.lower().strip() in c.lower() for c in channels)
            (assigned_rows if assigned else unassigned_rows).append((row, channels))

        if assigned_rows:
            st.markdown("#### ✅ Assigned Monitors")
            for row, channels in assigned_rows:
                show_monitor(row, channels, selected_client)

        if unassigned_rows:
            st.markdown("#### ❔ Unassigned Monitors")
            for row, channels in unassigned_rows:
                show_monitor(row, channels, selected_client)
