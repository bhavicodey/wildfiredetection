import os
import json
import time
import requests
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta
from io import StringIO

# =============================
# CEREBRAS IMPORT (SAFE)
# =============================
try:
    from cerebras.cloud.sdk import Cerebras
    CEREBRAS_AVAILABLE = True
except ImportError:
    CEREBRAS_AVAILABLE = False

# =============================
# PAGE CONFIG
# =============================
st.set_page_config(page_title="🔥 Wildfire Intelligence", layout="wide")
st.title("🔥 Wildfire Intelligence")
st.caption("NASA FIRMS + Real-Time Reasoning on Cerebras")

# =============================
# SIDEBAR CONTROLS
# =============================
st.sidebar.header("Configuration")

firms_api_key = st.sidebar.text_input(
    "NASA FIRMS API Key",
    type="password"
)

start_date = st.sidebar.date_input(
    "Start Date",
    value=datetime.utcnow() - timedelta(days=3)
)
end_date = st.sidebar.date_input(
    "End Date",
    value=datetime.utcnow()
)

st.sidebar.subheader("Bounding Box")
min_lat = st.sidebar.number_input("Min Latitude", value=-10.0)
min_lon = st.sidebar.number_input("Min Longitude", value=-80.0)
max_lat = st.sidebar.number_input("Max Latitude", value=10.0)
max_lon = st.sidebar.number_input("Max Longitude", value=-60.0)

satellite = st.sidebar.selectbox(
    "Satellite Source",
    ["VIIRS_NOAA20_NRT", "VIIRS_SNPP_NRT", "MODIS_NRT"]
)

fetch = st.sidebar.button("🔍 Fetch Fire Data")

# =============================
# FIRMS FETCH
# =============================
def fetch_firms(api_key, source, area, start_date, days):
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/{source}/{area}/{days}/{start_date}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(StringIO(r.text))

# =============================
# MAP
# =============================
def render_map(df, bbox):
    center = [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]
    m = folium.Map(location=center, zoom_start=6)
    for _, r in df.iterrows():
        folium.CircleMarker(
            [r["latitude"], r["longitude"]],
            radius=4,
            color="red",
            fill=True,
            fill_opacity=0.7
        ).add_to(m)
    return m

# =============================
# CEREBRAS PROMPT
# =============================
SYSTEM_PROMPT = """
You are a real-time wildfire risk assessment AI.

Return ONLY valid JSON:
{
  "risk_level": "LOW | MEDIUM | HIGH | EXTREME",
  "spread_probability_12h": number between 0 and 1,
  "primary_risk_factors": [strings],
  "recommended_actions": [strings]
}
"""

def cerebras_client():
    key = "csk-y2vf6htw5pp3vhwy63x5j2684yn6r2vwykffke4534tdpfyk"
    if not key:
        return None
    return Cerebras(api_key=key)

def fire_context(row):
    return {
        "fire": {
            "lat": float(row["latitude"]),
            "lon": float(row["longitude"]),
            "confidence": row.get("confidence"),
            "frp_mw": row.get("frp"),
            "brightness": row.get("bright_ti4"),
            "date": row.get("acq_date"),
            "time": row.get("acq_time")
        },
        "assumptions": {
            "wind_kmh": 30,
            "humidity_percent": 20,
            "terrain": "vegetation",
            "distance_to_population_km": 5
        }
    }

def analyze_fire(client, context):
    res = client.chat.completions.create(
        model="llama-3.1-8b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(context)}
        ],
        temperature=0.2,
        max_completion_tokens=400
    )
    return res.choices[0].message.content

# =============================
# MAIN FLOW
# =============================
if fetch:
    if not firms_api_key:
        st.error("Please enter a FIRMS API key.")
        st.stop()

    with st.spinner("Fetching FIRMS data…"):
        try:
            area = f"{min_lon},{min_lat},{max_lon},{max_lat}"
            days = (end_date - start_date).days + 1
            df = fetch_firms(
                firms_api_key,
                satellite,
                area,
                start_date.strftime("%Y-%m-%d"),
                days
            )
        except Exception as e:
            st.error("Failed to fetch FIRMS data")
            st.exception(e)
            st.stop()

    st.success(f"Loaded {len(df)} fire detections")

    if df.empty:
        st.warning("No fires detected for this region/time.")
        st.stop()

    # MAP
    st.subheader("🔥 Fire Map")
    folium_static(
        render_map(df, [min_lat, min_lon, max_lat, max_lon]),
        height=600
    )

    # TABLE
    st.subheader("📊 Fire Data")
    st.dataframe(df.head(100), use_container_width=True)

    # =============================
    # CEREBRAS ANALYSIS
    # =============================
    st.subheader("🧠 Cerebras Real-Time Risk Analysis")

    if not CEREBRAS_AVAILABLE:
        st.warning("Cerebras SDK not installed.")
        st.stop()

    client = cerebras_client()
    if client is None:
        st.info("Set CEREBRAS_API_KEY to enable analysis.")
        st.stop()

    fire_idx = st.selectbox("Select fire", df.index[:50])

    if st.button("⚡ Analyze Fire Risk"):
        ctx = fire_context(df.loc[fire_idx])

        with st.spinner("Running ultra-fast inference on Cerebras…"):
            start = time.time()
            raw = analyze_fire(client, ctx)
            latency = time.time() - start

        st.success(f"Inference completed in {latency:.2f}s")

        try:
            result = json.loads(raw)

            st.error(f"🔥 Risk Level: {result['risk_level']}")
            st.metric("Spread Probability (12h)", result["spread_probability_12h"])

            st.markdown("### Risk Factors")
            for r in result["primary_risk_factors"]:
                st.write(f"- {r}")

            st.markdown("### Recommended Actions")
            for a in result["recommended_actions"]:
                st.write(f"- {a}")

        except Exception:
            st.code(raw)
