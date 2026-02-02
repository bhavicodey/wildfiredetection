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
st.caption("Satellite Anomaly Detection × Cerebras Wafer-Scale Inference")

# =========================
# How to Run Box
# =========================
st.info(
    """
### ▶️ How to Run This Demo

This demo combines **live satellite anomaly detections** with **ultra-low-latency Cerebras reasoning**.

**All API keys are preconfigured — no setup required.**

**Steps:**
1. Adjust the **date range** and **bounding box** (or keep defaults)
2. Click **🔍 Fetch Fire Data** to load satellite detections
3. Select an anomaly and click **⚡ Generate Tactical Action Plan**

⚡ Cerebras enables **real-time multi-layer reasoning** on raw satellite data — eliminating traditional processing delays.
"""
)

# =========================
# Session State
# =========================
if "df" not in st.session_state:
    st.session_state.df = None

# =========================
# Sidebar Inputs
# =========================
st.sidebar.header("📅 Date Range")

start_date = st.sidebar.date_input(
    "Start Date",
    datetime.utcnow() - timedelta(days=3)
)

end_date = st.sidebar.date_input(
    "End Date",
    datetime.utcnow()
)

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
# API Keys (Preloaded)
# =========================
firms_api_key = "7a8749d24a541283600ded9b708c220c"
cerebras_api_key = "csk-y2vf6htw5pp3vhwy63x5j2684yn6r2vwykffke4534tdpfyk"

# =========================
# FIRMS Fetch
# =========================
@st.cache_data(ttl=300)
def fetch_firms(api_key, source, area, start_date, days):
    url = (
        f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        f"{api_key}/{source}/{area}/{days}/{start_date}"
    )
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(StringIO(r.text))

# =========================
# Fetch Button
# =========================
if st.sidebar.button("🔍 Fetch Fire Data"):
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

        st.session_state.df = df

    st.success(f"Loaded {len(df)} satellite detections")

# =========================
# Display Data
# =========================
df = st.session_state.df

if df is not None and not df.empty:
    st.subheader("🗺️ Satellite Detection Map")

    if "latitude" not in df.columns or "longitude" not in df.columns:
        st.error(f"Expected latitude/longitude columns not found. Columns: {list(df.columns)}")
        st.stop()

    center_lat = df["latitude"].astype(float).mean()
    center_lon = df["longitude"].astype(float).mean()
    
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=6
    )

    for _, row in df.head(2000).iterrows():
        # Safe handling for confidence and FRP
        try:
            confidence = float(row.get("confidence", 50))
        except (ValueError, TypeError):
            confidence = 50
        try:
            frp = float(row.get("frp", 0))
        except (ValueError, TypeError):
            frp = 0

        # Color by confidence
        if confidence >= 80:
            color = "red"
        elif confidence >= 50:
            color = "orange"
        else:
            color = "yellow"
        
        # Circle size by FRP
        radius = max(3, min(10, frp / 10))

        popup_html = f"""
        <b>Satellite Detection</b><br>
        Latitude: {row.latitude}<br>
        Longitude: {row.longitude}<br>
        Date: {row.acq_date}<br>
        Time: {row.acq_time} UTC<br>
        Brightness: {row.bright_ti4}<br>
        FRP: {frp} MW<br>
        Confidence: {confidence}%
        """

        folium.CircleMarker(
            location=[row.latitude, row.longitude],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=folium.Popup(popup_html, max_width=250)
        ).add_to(m)

    folium_static(m, width=1200, height=500)

    st.subheader("📊 Detection Table")
    st.dataframe(df.head(100), use_container_width=True)

# =========================
# Cerebras Analysis
# =========================
st.subheader("🧠 Cerebras Tactical Reasoning Engine")

if not CEREBRAS_AVAILABLE:
    st.warning("Cerebras SDK not installed")
elif df is None or df.empty:
    st.info("Fetch satellite data first.")
else:
    client = Cerebras(api_key=cerebras_api_key)

    fire_idx = st.selectbox(
        "Select a satellite anomaly",
        df.index[:50]
    )

    def anomaly_context(row):
        return f"""
Satellite observation detected:
Latitude: {row.latitude}
Longitude: {row.longitude}
Date: {row.acq_date}
Time: {row.acq_time}
Thermal Brightness: {row.bright_ti4}
Radiative Power: {row.frp}
"""

    SYSTEM_PROMPT = """
You are the Planetary Operations Core, a high-frequency strategic AI designed to protect critical infrastructure and human life.

INPUT FORMAT
You will receive satellite anomaly data with coordinates, thermal readings, and confidence signals.

ANALYSIS FRAMEWORK
Evaluate these factors internally:
1. Historical patterns and contextual verification
2. Geospatial infrastructure scan (5km radius)
3. Predictive threat modeling (T+1 to T+6 hours)
4. Jurisdictional authority and asset availability

CRITICAL OUTPUT RULES
Your response must be ONLY the JSON object below. Nothing else.

Forbidden elements:
- No <think> tags
- No reasoning exposition
- No markdown (```)
- No explanatory text
- No preamble or postamble
- No internal monologue

Required: Pure JSON only. Start with { and end with }
"""

    if st.button("⚡ Generate Tactical Action Plan"):
        with st.spinner("⚡ Cerebras computing strategy…"):
            response = client.chat.completions.create(
                model="llama3.1-8b",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": anomaly_context(df.loc[fire_idx])}
                ],
                max_completion_tokens=350,
                temperature=0.1
            )
        st.success("Tactical plan generated")
        st.markdown("### 📡 Tactical Action Plan (JSON)")
        st.code(response.choices[0].message.content, language="json")

# =========================
# Footer
# =========================
st.markdown("---")
st.caption("Cerebras Wafer-Scale Engine — Real-time strategic reasoning on live satellite data")
