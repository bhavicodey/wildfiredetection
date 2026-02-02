import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta
from io import StringIO

# =========================
# Cerebras
# =========================
try:
    from cerebras.cloud.sdk import Cerebras
    CEREBRAS_AVAILABLE = True
except:
    CEREBRAS_AVAILABLE = False

# =========================
# Page Config
# =========================
st.set_page_config(
    page_title="🌍 Planetary Operations Core",
    layout="wide"
)

st.title("🌍 Planetary Operations Core")
st.caption("Satellite Anomaly Detection × Cerebras Wafer-Scale Reasoning")

# =========================
# What Cerebras Does
# =========================
st.warning(
    """
### 🧠 Why Cerebras Is Used Here

Satellite systems already **detect anomalies** — the bottleneck is **reasoning speed**.

Cerebras performs **multi-step geospatial, legal, and operational reasoning**
**while the satellite is still overhead**, answering:
- *Is this real or a false positive?*
- *Who owns jurisdiction?*
- *What assets should respond — right now?*

This turns satellite imagery into **instant tactical decisions**, not delayed reports.
"""
)

# =========================
# How to Run
# =========================
st.info(
    """
### ▶️ How to Run

1. Keep defaults or adjust **date & region**
2. Click **🔍 Fetch Satellite Detections**
3. Click a point on the map or select it below
4. Click **⚡ Generate Tactical Action Plan**

All API keys are preconfigured.
"""
)

# =========================
# Session State
# =========================
if "df" not in st.session_state:
    st.session_state.df = None

# =========================
# Sidebar Controls
# =========================
st.sidebar.header("📅 Date Range")
start_date = st.sidebar.date_input("Start Date", datetime.utcnow() - timedelta(days=3))
end_date = st.sidebar.date_input("End Date", datetime.utcnow())

st.sidebar.header("📍 Bounding Box")
min_lat = st.sidebar.number_input("Min Latitude", value=34.0)
min_lon = st.sidebar.number_input("Min Longitude", value=-120.0)
max_lat = st.sidebar.number_input("Max Latitude", value=38.0)
max_lon = st.sidebar.number_input("Max Longitude", value=-115.0)

satellite = st.sidebar.selectbox(
    "Satellite Source",
    ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "MODIS_NRT"]
)

# =========================
# API Keys
# =========================
firms_api_key = "7a8749d24a541283600ded9b708c220c"
cerebras_api_key = "csk-y2vf6htw5pp3vhwy63x5j2684yn6r2vwykffke4534tdpfyk"

# =========================
# FIRMS Fetch
# =========================
@st.cache_data(ttl=300)
def fetch_firms(api_key, source, area, start_date, days):
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/{source}/{area}/{days}/{start_date}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(StringIO(r.text))

# =========================
# Fetch Button
# =========================
if st.sidebar.button("🔍 Fetch Satellite Detections"):
    with st.spinner("Fetching satellite detections…"):
        area = f"{min_lon},{min_lat},{max_lon},{max_lat}"
        days = (end_date - start_date).days + 1

        df = fetch_firms(
            firms_api_key,
            satellite,
            area,
            start_date.strftime("%Y-%m-%d"),
            days
        )

        # UTC timestamp formatting
        df["acq_time_utc"] = df["acq_time"].astype(str).str.zfill(4)
        df["acq_time_utc"] = df["acq_time_utc"].str[:2] + ":" + df["acq_time_utc"].str[2:]
        df["timestamp_utc"] = df["acq_date"] + " " + df["acq_time_utc"] + " UTC"

        st.session_state.df = df

    st.success(f"Loaded {len(df)} satellite detections")

# =========================
# Map Visualization
# =========================
df = st.session_state.df

if df
