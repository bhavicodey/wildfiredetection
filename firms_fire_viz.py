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
st.set_page_config(page_title="🔥 Wildfire Intelligence", layout="wide")
st.title("🔥 Wildfire Intelligence Platform")
st.markdown("Satellite fire detection + **real-time reasoning on Cerebras**")

# =========================
# SESSION STATE KEYS
# =========================
if "firms_api_key" not in st.session_state:
    st.session_state.firms_api_key = ""
if "cerebras_api_key" not in st.session_state:
    st.session_state.cerebras_api_key = ""
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False

# =========================
# SIDEBAR INPUTS
# =========================
st.sidebar.header("Configuration")

# FIRMS API Key
st.session_state.firms_api_key = st.sidebar.text_input(
    "NASA FIRMS API Key",
    value=st.session_state.firms_api_key,
    type="password"
)
# Cerebras API Key
st.session_state.cerebras_api_key = st.sidebar.text_input(
    "Cerebras API Key",
    value=st.session_state.cerebras_api_key,
    type="password"
)

# Status indicators
st.sidebar.markdown("### System Status")
st.sidebar.success("🛰️ FIRMS Ready")
if st.session_state.cerebras_api_key and CEREBRAS_AVAILABLE:
    st.sidebar.success("🧠 Cerebras Connected")
else:
    st.sidebar.warning("🧠 Cerebras Not Connected")

# Date range
st.sidebar.subheader("Date Range")
start_date = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=3))
end_date = st.sidebar.date_input("End Date", datetime.now())

# Bounding box
st.sidebar.subheader("Bounding Box")
min_lat = st.sidebar.number_input("Min Latitude", value=-10.0)
min_lon = st.sidebar.number_input("Min Longitude", value=-80.0)
max_lat = st.sidebar.number_input("Max Latitude", value=10.0)
max_lon = st.sidebar.number_input("Max Longitude", value=-60.0)

# Satellite source
data_source = st.sidebar.selectbox(
    "Satellite Source",
    ["VIIRS_NOAA20_NRT", "VIIRS_SNPP_NRT", "MODIS_NRT"]
)

# =========================
# Fetch Button
# =========================
if st.sidebar.button("🔍 Fetch Fire Data"):
    st.session_state.data_loaded = True
    st.experimental_rerun()  # Immediately rerun so data block executes

# =========================
# FIRMS API FUNCTION
# =========================
def get_firms_data(api_key, source, area, start_date, day_range):
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/{source}/{area}/{day_range}/{start_date}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(StringIO(r.text))

# =========================
# MAP FUNCTION
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
You are a wildfire risk assessment AI.

Analyze the fire event and return ONLY valid JSON:
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
# MAIN APP BLOCK
# =========================
if st.session_state.data_loaded:
    st.write("🧠 Entered main data block")
    
    # Debug info
    st.write({
        "data_loaded": st.session_state.data_loaded,
        "firms_key_present": bool(st.session_state.firms_api_key),
        "cerebras_key_present": bool(st.session_state.cerebras_api_key)
    })

    if not st.session_state.firms_api_key:
        st.error("❌ FIRMS API key required")
    else:
        with st.spinner("Fetching FIRMS data..."):
            try:
                area = f"{min_lon},{min_lat},{max_lon},{max_lat}"
                day_range = (end_date - start_date).days + 1
                st.write(f"📡 Fetching {day_range} days of data from area {area} using {data_source}...")

                df = get_firms_data(
                    st.session_state.firms_api_key,
                    data_source,
                    area,
                    start_date.strftime("%Y-%m-%d"),
                    day_range
                )

                st.write(f"✅ Retrieved {len(df)} rows")

                if len(df) == 0:
                    st.warning("⚠️ FIRMS returned no fire detections for this area/date range")

            except Exception as e:
                st.error("❌ Failed to fetch FIRMS data")
                st.exception(e)
                df = pd.DataFrame()  # ensure df exists

        # Map
        if not df.empty and all(col in df.columns for col in ["latitude", "longitude"]):
            st.subheader("🔥 Fire Map")
            folium_static(create_map(df, [min_lat, min_lon, max_lat, max_lon]), height=600)
        else:
            st.warning("⚠️ Cannot render map: missing latitude/longitude columns")

        # Table
        st.subheader("Fire Data")
        st.dataframe(df.head(100), use_container_width=True)

        # Raw CSV for debug
        st.subheader("📄 Raw FIRMS CSV Preview")
        st.text(df.head(5).to_csv(index=False))

        # Cerebras Analysis
        st.subheader("🧠 Cerebras Wildfire Risk Analysis")
        if st.session_state.cerebras_api_key and CEREBRAS_AVAILABLE:
            client = get_cerebras_client(st.session_state.cerebras_api_key)
            if not df.empty:
                selected = st.selectbox("Select fire index", df.index[:50])

                if st.button("Analyze Fire Risk"):
                    context = build_fire_context(df.loc[selected])
                    st.subheader("📤 Cerebras Input")
                    st.json(context)

                    try:
                        start = time.time()
                        raw_output = analyze_fire(client, context)
                        elapsed = time.time() - start

                        st.subheader("📥 Raw Cerebras Output")
                        st.code(raw_output)

                        analysis = json.loads(raw_output)

                        st.success(f"⚡ Inference completed in {elapsed:.2f} seconds")
                        st.error(f"🔥 Risk Level: {analysis['risk_level']}")
                        st.metric("Spread Probability (12h)", analysis["spread_probability_12h"])

                        st.markdown("### Risk Factors")
                        for f in analysis["primary_risk_factors"]:
                            st.write(f"- {f}")

                        st.markdown("### Recommended Actions")
                        for a in analysis["recommended_actions"]:
                            st.write(f"- {a}")

                    except Exception as e:
                        st.error("❌ Cerebras inference failed")
                        st.exception(e)
        else:
            st.info("Enter a Cerebras API key to enable analysis.")
