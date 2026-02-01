import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta
from io import StringIO
import json
import time

# =========================
# SAFE CEREBRAS IMPORT
# =========================
try:
    from cerebras.cloud import Cerebras
    CEREBRAS_AVAILABLE = True
except ImportError:
    CEREBRAS_AVAILABLE = False

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="🔥 Wildfire Intelligence (Cerebras)", layout="wide")
st.title("🔥 Wildfire Intelligence Platform")
st.markdown("Satellite fire detection + **real-time reasoning on Cerebras**")

# =========================
# SIDEBAR
# =========================
st.sidebar.header("Configuration")

firms_api_key = st.sidebar.text_input("NASA FIRMS API Key", type="password")
cerebras_api_key = st.sidebar.text_input("Cerebras API Key", type="password")

st.sidebar.markdown("### System Status")
st.sidebar.success("🛰️ FIRMS Ready")
if cerebras_api_key and CEREBRAS_AVAILABLE:
    st.sidebar.success("🧠 Cerebras Connected")
else:
    st.sidebar.warning("🧠 Cerebras Not Connected")

st.sidebar.subheader("Date Range")
start_date = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=3))
end_date = st.sidebar.date_input("End Date", datetime.now())

st.sidebar.subheader("Bounding Box")
min_lat = st.sidebar.number_input("Min Latitude", value=-10.0)
min_lon = st.sidebar.number_input("Min Longitude", value=-80.0)
max_lat = st.sidebar.number_input("Max Latitude", value=10.0)
max_lon = st.sidebar.number_input("Max Longitude", value=-60.0)

data_source = st.sidebar.selectbox(
    "Satellite Source",
    ["VIIRS_NOAA20_NRT", "VIIRS_SNPP_NRT", "MODIS_NRT"]
)

fetch_data = st.sidebar.button("🔍 Fetch Fire Data")

# =========================
# FIRMS API
# =========================
def get_firms_data(api_key, source, area, start_date, day_range):
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/{source}/{area}/{day_range}/{start_date}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(StringIO(r.text))

# =========================
# MAP
# =========================
def create_map(df, bbox):
    center = [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]
    m = folium.Map(location=center, zoom_start=6)

    for _, r in df.iterrows():
        folium.CircleMarker(
            location=[r["latitude"], r["longitude"]],
            radius=4,
            color="red",
            fill=True,
            fill_opacity=0.7
        ).add_to(m)
    return m

# =========================
# CEREBRAS SETUP
# =========================
SYSTEM_PROMPT = """
You are a wildfire risk assessment AI used by emergency response agencies.

Analyze the fire event and return ONLY valid JSON with:
- risk_level (LOW, MEDIUM, HIGH, EXTREME)
- spread_probability_12h (0–1)
- primary_risk_factors (list)
- recommended_actions (list)
"""

def get_cerebras_client(api_key):
    return Cerebras(api_key=api_key)

def build_fire_context(row):
    return {
        "fire_event": {
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "confidence": row["confidence"],
            "frp_mw": row.get("frp"),
            "date": row["acq_date"],
            "time": row["acq_time"]
        },
        "weather": {
            "wind_speed_kmh": 30,
            "wind_direction": "NE",
            "humidity_percent": 20,
            "temperature_c": 36
        },
        "terrain": {
            "land_cover": "forest"
        },
        "human_context": {
            "distance_to_city_km": 6,
            "population_estimate": 12000
        }
    }

def analyze_fire(client, context):
    response = client.chat.completions.create(
        model="llama-3.1-8b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(context)}
        ],
        temperature=0.2,
        max_completion_tokens=600
    )
    return response.choices[0].message.content

# =========================
# MAIN APP
# =========================
if fetch_data:
    if not firms_api_key:
        st.error("❌ FIRMS API key required")
        st.stop()

    with st.status("🛰️ Fetching FIRMS satellite data...", expanded=True) as status:
        area = f"{min_lon},{min_lat},{max_lon},{max_lat}"
        day_range = (end_date - start_date).days + 1
