import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta
from io import StringIO
import os

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
    page_title="🔥 Wildfire Detection + Cerebras AI",
    layout="wide"
)

st.title("🔥 Wildfire Detection & Risk Analysis")
st.caption("NASA FIRMS × Cerebras Wafer-Scale Inference")

# =========================
# Session State
# =========================
if "df" not in st.session_state:
    st.session_state.df = None

# =========================
# Sidebar Inputs
# =========================
st.sidebar.header("🔑 API Keys")

firms_api_key = "7a8749d24a541283600ded9b708c220c"

cerebras_api_key = "csk-y2vf6htw5pp3vhwy63x5j2684yn6r2vwykffke4534tdpfyk"

# =========================
# Date + Area
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

min_lat = st.sidebar.number_input("Min Lat", value=34.0)
min_lon = st.sidebar.number_input("Min Lon", value=-120.0)
max_lat = st.sidebar.number_input("Max Lat", value=38.0)
max_lon = st.sidebar.number_input("Max Lon", value=-115.0)

satellite = st.sidebar.selectbox(
    "Satellite Source",
    ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "MODIS_NRT"]
)

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
    if not firms_api_key:
        st.error("Enter FIRMS API key")
        st.stop()

    with st.spinner("Fetching wildfire data…"):
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

    st.success(f"Loaded {len(df)} fire detections")

# =========================
# Display Data
# =========================
df = st.session_state.df

if df is not None and not df.empty:
    st.subheader("🗺️ Fire Map")

    m = folium.Map(
        location=[df.latitude.mean(), df.longitude.mean()],
        zoom_start=6
    )

    for _, row in df.head(2000).iterrows():
        folium.CircleMarker(
            location=[row.latitude, row.longitude],
            radius=4,
            color="red",
            fill=True,
            fill_opacity=0.7
        ).add_to(m)

    folium_static(m, width=1200, height=500)

    st.subheader("📊 Fire Table")
    st.dataframe(df.head(100), use_container_width=True)

# =========================
# Cerebras Analysis
# =========================
st.subheader("🧠 Cerebras Fire Risk Analysis")

if not CEREBRAS_AVAILABLE:
    st.warning("Cerebras SDK not installed")
elif not cerebras_api_key:
    st.info("Enter a Cerebras API key to enable analysis.")
elif df is None or df.empty:
    st.info("Fetch fire data first.")
else:
    client = Cerebras(api_key=cerebras_api_key)

    fire_idx = st.selectbox(
        "Select a fire to analyze",
        df.index[:50]
    )

    def fire_context(row):
        return f"""
Wildfire detected:
Latitude: {row.latitude}
Longitude: {row.longitude}
Date: {row.acq_date}
Time: {row.acq_time}
Brightness: {row.bright_ti4}
Fire Radiative Power: {row.frp}

Analyze:
- Likelihood of spread
- Risk to population
- Environmental factors
- Urgency level
- Recommended actions
"""

    if st.button("⚡ Analyze Fire Risk"):
        st.write("🚀 Running Cerebras inference…")

        with st.spinner("Ultra-fast reasoning on WSE…"):
            response = client.chat.completions.create(
                model="qwen-3-32b",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an emergency wildfire risk assessment AI. "
                            "Be concise, actionable, and structured."
                        )
                    },
                    {
                        "role": "user",
                        "content": fire_context(df.loc[fire_idx])
                    }
                ],
                max_completion_tokens=300,
                temperature=0.2
            )

        st.success("Analysis complete")
        st.markdown("### 🔥 Risk Assessment")
        st.markdown(response.choices[0].message.content)

# =========================
# Footer
# =========================
st.markdown("---")
st.caption("NASA FIRMS × Cerebras Wafer-Scale Engine")
