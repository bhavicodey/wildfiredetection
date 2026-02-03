import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta
from io import StringIO
import time  # For real-time counter

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

        # Limit days to 5 per API restrictions
        if days > 5:
            st.warning("NASA FIRMS API only allows 5-day segments. Using last 5 days.")
            days = 5

        df = fetch_firms(
            firms_api_key,
            satellite,
            area,
            start_date.strftime("%Y-%m-%d"),
            days
        )

        # UTC timestamp formatting
        if "acq_time" in df.columns and "acq_date" in df.columns:
            df["acq_time_utc"] = df["acq_time"].astype(str).str.zfill(4)
            df["acq_time_utc"] = df["acq_time_utc"].str[:2] + ":" + df["acq_time_utc"].str[2:]
            df["timestamp_utc"] = df["acq_date"] + " " + df["acq_time_utc"] + " UTC"

        st.session_state.df = df

    st.success(f"Loaded {len(df)} satellite detections")

# =========================
# Map Visualization
# =========================
df = st.session_state.df

if df is not None and not df.empty:
    st.subheader("🗺️ Interactive Satellite Detection Map")

    center_lat = df["latitude"].mean()
    center_lon = df["longitude"].mean()

    m = folium.Map(location=[center_lat, center_lon], zoom_start=6)

    for idx, row in df.iterrows():
        color = "green" if row.frp < 10 else "orange" if row.frp < 50 else "red"
        radius = min(12, max(4, row.frp / 5))

        popup = folium.Popup(
            f"""
<b>ID:</b> {idx}<br>
<b>Lat/Lon:</b> {row.latitude}, {row.longitude}<br>
<b>Time:</b> {row.timestamp_utc}<br>
<b>FRP:</b> {row.frp}<br>
<b>Brightness:</b> {row.bright_ti4}<br>
<b>Note:</b> Possible false positives near landfills or solar facilities
""",
            max_width=300
        )

        folium.CircleMarker(
            location=[row.latitude, row.longitude],
            radius=radius,
            color=color,
            fill=True,
            fill_opacity=0.75,
            popup=popup
        ).add_to(m)

    folium_static(m, width=1200, height=420)

    with st.expander("ℹ️ Column Meanings"):
        st.markdown(
            """
- **latitude / longitude** — Satellite-detected anomaly location  
- **acq_date / acq_time** — Acquisition time (UTC)  
- **bright_ti4** — Thermal brightness (Kelvin)  
- **frp** — Fire Radiative Power (proxy for intensity)  
- **Lower FRP ≠ safe** — context matters (location, infrastructure, wind)
"""
        )

    st.divider()
    st.subheader("📋 Satellite Detection Table")

    table_columns = [
        "latitude",
        "longitude",
        "timestamp_utc",
        "bright_ti4",
        "frp",
        "confidence"
    ]
    existing_columns = [c for c in table_columns if c in df.columns]

    st.dataframe(
        df[existing_columns].sort_values("frp", ascending=False),
        use_container_width=True,
        height=350
    )

# =========================
# Cerebras Tactical Reasoning
# =========================
st.subheader("🧠 Cerebras Tactical Reasoning Engine")

if df is not None and not df.empty and CEREBRAS_AVAILABLE:
    client = Cerebras(api_key=cerebras_api_key)

    fire_idx = st.selectbox(
        "Select anomaly ID (map + table aligned)",
        df.index.tolist()
    )

    def anomaly_context(row):
        return f"""
Satellite anomaly detected:
Latitude: {row.latitude}
Longitude: {row.longitude}
Timestamp (UTC): {row.timestamp_utc}
Thermal Brightness: {row.bright_ti4}
Radiative Power: {row.frp}
"""

    SYSTEM_PROMPT = """
You are the Planetary Operations Core — a real-time strategic AI for satellite anomaly response.

Your task is to instantly reason over:
• Geospatial context
• Infrastructure proximity
• Jurisdictional authority
• Likelihood of false positives
• Immediate operational response

Always end with a complete final recommendation.
"""

    if st.button("⚡ Generate Tactical Action Plan"):
        # Placeholder for real-time burned acres counter
        burned_placeholder = st.empty()
        with st.spinner("⚡ Cerebras reasoning in real time…"):
            start_time = time.time()
            acres_burned = 0
            # Simulate GPU/model processing while updating counter
            while True:
                elapsed = time.time() - start_time
                acres_burned = int(elapsed * 2)  # 2 acres per second
                burned_placeholder.markdown(f"🔥 Acres burned while reasoning: **{acres_burned}**")
                time.sleep(0.5)
                if elapsed > 10:  # Replace 10 with actual GPU wait time if known
                    break

            # Call Cerebras model
            response = client.chat.completions.create(
                model="llama-3.1-8b",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": anomaly_context(df.loc[fire_idx])}
                ],
                max_completion_tokens=500,
                temperature=0.1
            )

        burned_placeholder.empty()  # Clear counter
        st.success("Tactical plan generated")
        st.markdown("### 📡 Tactical Assessment")
        st.markdown(response.choices[0].message.content)

# =========================
# Footer
# =========================
st.markdown("---")
st.caption("Cerebras Wafer-Scale Engine — Turning satellite pixels into decisions, instantly")
