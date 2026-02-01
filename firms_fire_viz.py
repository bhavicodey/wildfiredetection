import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta
from cerebras.cloud.sdk import Cerebras
import json

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="🔥 Wildfire Intelligence (Cerebras)", layout="wide")
st.title("🔥 Real-Time Wildfire Intelligence Platform")
st.markdown("Satellite detection + ultra-fast reasoning with **Cerebras WSE**")

# =========================
# SIDEBAR CONFIG
# =========================
st.sidebar.header("Configuration")

firms_api_key = st.sidebar.text_input("NASA FIRMS API Key", type="password")
cerebras_api_key = st.sidebar.text_input("Cerebras API Key", type="password")

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
# FIRMS FETCH
# =========================
def get_firms_data(api_key, source, area, start_date, day_range):
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/{source}/{area}/{day_range}/{start_date}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(pd.compat.StringIO(r.text))

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
def get_cerebras_client(api_key):
    return Cerebras(api_key=api_key)

SYSTEM_PROMPT = """
You are a wildfire risk assessment AI used by emergency response agencies.

Analyze the provided fire event and context.
Return ONLY valid JSON with:
- risk_level (LOW, MEDIUM, HIGH, EXTREME)
- spread_probability_12h (0–1)
- primary_risk_factors (list)
- recommended_actions (list)
"""

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
    return json.loads(response.choices[0].message.content)

# =========================
# MAIN APP
# =========================
if fetch_data:
    if not firms_api_key:
        st.error("Please enter FIRMS API key.")
    else:
        with st.spinner("Fetching satellite fire detections..."):
            area = f"{min_lon},{min_lat},{max_lon},{max_lat}"
            day_range = (end_date - start_date).days + 1
            df = get_firms_data(
                firms_api_key,
                data_source,
                area,
                start_date.strftime("%Y-%m-%d"),
                day_range
            )

        st.success(f"🔥 {len(df)} fire detections found")

        st.subheader("Fire Map")
        folium_static(create_map(df, [min_lat, min_lon, max_lat, max_lon]), height=600)

        st.subheader("Fire Data")
        st.dataframe(df.head(100), use_container_width=True)

        # =========================
        # CEREBRAS ANALYSIS
        # =========================
        st.subheader("🧠 Cerebras Real-Time Risk Analysis")

        if cerebras_api_key:
            client = get_cerebras_client(cerebras_api_key)
            selected = st.selectbox("Select fire index", df.index[:50])

            if st.button("Analyze Fire Risk"):
                with st.spinner("Running ultra-fast inference on Cerebras..."):
                    context = build_fire_context(df.loc[selected])
                    result = analyze_fire(client, context)

                st.error(f"🔥 Risk Level: {result['risk_level']}")
                st.metric("Spread Probability (12h)", result["spread_probability_12h"])

                st.markdown("### Risk Factors")
                for f in result["primary_risk_factors"]:
                    st.write(f"- {f}")

                st.markdown("### Recommended Actions")
                for a in result["recommended_actions"]:
                    st.write(f"- {a}")
        else:
            st.info("Enter a Cerebras API key to enable intelligence analysis.")
