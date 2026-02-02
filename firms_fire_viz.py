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
# How to Run
# =========================
st.info(
"""
### ▶️ How to Run This Demo

This system combines **live satellite detections** with **ultra-low-latency Cerebras reasoning**.

**No setup required — API keys are preloaded.**

**Steps**
1. Choose a date range & bounding box (or keep defaults)
2. Click **🔍 Fetch Fire Data**
3. Click a detection on the map or select one below
4. Click **⚡ Generate Tactical Action Plan**

🧠 **Cerebras’ role:**  
Instantly transforms raw satellite signals into **validated, jurisdiction-aware response recommendations** — in seconds, not hours.
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
# API Keys (Preloaded)
# =========================
firms_api_key = "7a8749d24a541283600ded9b708c220c"
cerebras_api_key = "csk-y2vf6htw5pp3vhwy63x5j2684yn6r2vwykffke4534tdpfyk"

# =========================
# Helpers
# =========================
def normalize_confidence(conf):
    if pd.isna(conf):
        return 50
    if isinstance(conf, str):
        return {"l": 30, "n": 60, "h": 90}.get(conf.lower(), 50)
    try:
        return float(conf)
    except:
        return 50

def color_by_conf(conf):
    conf = normalize_confidence(conf)
    if conf >= 80:
        return "red"
    elif conf >= 50:
        return "orange"
    return "yellow"

# =========================
# FIRMS Fetch
# =========================
@st.cache_data(ttl=300)
def fetch_firms(api_key, source, area, start_date, days):
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/{source}/{area}/{days}/{start_date}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(StringIO(r.text))
    return df

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

        if "latitude" not in df.columns or "longitude" not in df.columns:
            st.error("Invalid bounding box or no detections returned.")
            st.stop()

        # Format UTC timestamp
        df["timestamp_utc"] = pd.to_datetime(
            df["acq_date"] + " " + df["acq_time"].astype(str).str.zfill(4),
            format="%Y-%m-%d %H%M",
            utc=True
        )

        st.session_state.df = df

    st.success(f"Loaded {len(df)} satellite detections")

# =========================
# Display Data
# =========================
df = st.session_state.df

if df is not None and not df.empty:
    st.subheader("🗺️ Satellite Detection Map")

    center_lat = df.latitude.astype(float).mean()
    center_lon = df.longitude.astype(float).mean()

    m = folium.Map(location=[center_lat, center_lon], zoom_start=6)

    for idx, row in df.iterrows():
        conf = normalize_confidence(row.get("confidence", 50))

        folium.CircleMarker(
            location=[row.latitude, row.longitude],
            radius=4 + (row.frp / 10 if not pd.isna(row.frp) else 3),
            color=color_by_conf(conf),
            fill=True,
            fill_opacity=0.75,
            popup=f"""
            <b>Satellite Detection</b><br>
            UTC Time: {row.timestamp_utc}<br>
            Confidence: {conf}<br>
            Brightness: {row.bright_ti4} K<br>
            FRP: {row.frp} MW
            """
        ).add_to(m)

    folium_static(m, width=1200, height=500)

    # =========================
    # Table
    # =========================
    with st.expander("📊 View Raw Detection Table & Column Meanings"):
        st.markdown("""
**Column Guide**
- **latitude / longitude**: Detection coordinates  
- **timestamp_utc**: Acquisition time (UTC)  
- **bright_ti4**: Thermal brightness (Kelvin)  
- **frp**: Fire Radiative Power (MW) — intensity proxy  
- **confidence**: Detection reliability  
""")
        st.dataframe(
            df[["latitude", "longitude", "timestamp_utc", "bright_ti4", "frp", "confidence"]],
            use_container_width=True
        )

# =========================
# Cerebras Analysis
# =========================
st.subheader("🧠 Cerebras Tactical Reasoning Engine")

st.caption(
"""
Cerebras performs **instant multi-layer reasoning**:
historical context → infrastructure exposure → predictive spread → jurisdiction → response assets.
"""
)

if not CEREBRAS_AVAILABLE:
    st.warning("Cerebras SDK not installed.")
elif df is None or df.empty:
    st.info("Fetch satellite data first.")
else:
    client = Cerebras(api_key=cerebras_api_key)

    fire_idx = st.selectbox(
        "Select a satellite anomaly",
        df.index.tolist()
    )

    def anomaly_context(row):
        return f"""
Satellite observation:
Latitude: {row.latitude}
Longitude: {row.longitude}
UTC Time: {row.timestamp_utc}
Brightness: {row.bright_ti4} K
Radiative Power: {row.frp} MW
"""

    SYSTEM_PROMPT = """
You are the Planetary Operations Core — a strategic AI for time-critical satellite anomalies.
Instantly validate risk, infrastructure exposure, jurisdiction, and recommend actions.
Respond concisely and operationally.
"""

    if st.button("⚡ Generate Tactical Action Plan"):
        with st.spinner("⚡ Cerebras computing response…"):
            response = client.chat.completions.create(
                model="llama3.1-8b",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": anomaly_context(df.loc[fire_idx])}
                ],
                max_completion_tokens=500,
                temperature=0.1
            )

        st.success("Tactical plan generated")

        st.text_area(
            "📡 Cerebras Tactical Output",
            response.choices[0].message.content,
            height=450
        )

# =========================
# Footer
# =========================
st.markdown("---")
st.caption("Cerebras Wafer-Scale Engine — Real-time strategic reasoning on live satellite data")
