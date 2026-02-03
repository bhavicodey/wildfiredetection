import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta
from io import StringIO
import geopandas as gpd
from shapely.geometry import Point

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
firms_api_key = "YOUR_FIRMS_API_KEY"
cerebras_api_key = "YOUR_CEREBRAS_API_KEY"

# =========================
# Load Infrastructure GeoJSON
# =========================
@st.cache_data(ttl=86400)
def load_infrastructure_data():
    # Example GeoJSON with points for solar, roads, airports, landfills
    infra = gpd.read_file("data/infrastructure.geojson")
    infra = infra.to_crs(epsg=4326)
    return infra

infrastructure_gdf = load_infrastructure_data()

# =========================
# FIRMS Fetch (5-day chunking)
# =========================
@st.cache_data(ttl=300)
def fetch_firms(api_key, source, area, start_date, days):
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/{source}/{area}/{days}/{start_date}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(StringIO(r.text))

# =========================
# Nearby Infrastructure Function
# =========================
def get_nearby_infra(lat, lon, radius_km=20):
    point = Point(lon, lat)
    buffer = point.buffer(radius_km / 111)  # 1 degree ≈ 111 km
    nearby = infrastructure_gdf[infrastructure_gdf.geometry.intersects(buffer)]
    nearby_list = []
    for _, r in nearby.iterrows():
        dist_km = r.geometry.distance(point) * 111
        nearby_list.append(f"• {r.get('name', 'Unknown')} ({r.get('type', 'N/A')}, {dist_km:.1f} km)")
    if not nearby_list:
        nearby_list.append("• No significant infrastructure within radius.")
    return "\n".join(nearby_list)

# =========================
# Fetch Button
# =========================
if st.sidebar.button("🔍 Fetch Satellite Detections"):
    with st.spinner("Fetching satellite detections…"):
        delta = end_date - start_date
        dfs = []

        for i in range(0, delta.days + 1, 5):
            chunk_start = start_date + timedelta(days=i)
            chunk_end = min(start_date + timedelta(days=i+4), end_date)
            chunk_days = (chunk_end - chunk_start).days + 1

            area = f"{min_lon},{min_lat},{max_lon},{max_lat}"
            df_chunk = fetch_firms(
                firms_api_key,
                satellite,
                area,
                chunk_start.strftime("%Y-%m-%d"),
                chunk_days
            )
            dfs.append(df_chunk)

        df = pd.concat(dfs, ignore_index=True)

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
            f"<b>ID:</b> {idx}<br>"
            f"<b>Lat/Lon:</b> {row.latitude}, {row.longitude}<br>"
            f"<b>Time:</b> {row.get('timestamp_utc','N/A')}<br>"
            f"<b>FRP:</b> {row.frp}<br>"
            f"<b>Brightness:</b> {row.bright_ti4}",
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
        nearby_infra = get_nearby_infra(row.latitude, row.longitude)
        return f"""
Satellite anomaly detected:
Latitude: {row.latitude}
Longitude: {row.longitude}
Timestamp (UTC): {row.get('timestamp_utc', 'N/A')}
Thermal Brightness: {row.bright_ti4}
Radiative Power: {row.frp}

Nearby infrastructure (within 20 km):
{nearby_infra}
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
        with st.spinner("⚡ Cerebras reasoning in real time…"):
            response = client.chat.completions.create(
                model="llama-3.1-8b",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": anomaly_context(df.loc[fire_idx])}
                ],
                max_completion_tokens=500,
                temperature=0.1
            )

        st.success("Tactical plan generated")
        st.markdown("### 📡 Tactical Assessment")
        st.markdown(response.choices[0].message.content)

# =========================
# Footer
# =========================
st.markdown("---")
st.caption("Cerebras Wafer-Scale Engine — Turning satellite pixels into decisions, instantly")
