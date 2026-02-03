import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta
from io import StringIO
import time

# =========================
# Cerebras
# =========================
try:
    from cerebras.cloud.sdk import Cerebras
    CEREBRAS_AVAILABLE = True
except:
    CEREBRAS_AVAILABLE = False

# =========================
# OpenAI
# =========================
import openai
openai.api_key = "j89kksk"

# =========================
# Page Config
# =========================
st.set_page_config(
    page_title="🌍 Planetary Operations Core",
    layout="wide"
)

st.title("🌍 Planetary Operations Core")
st.caption("Satellite Anomaly Detection × Cerebras vs Traditional GPU Latency Demo")

# =========================
# Session State
# =========================
if "df" not in st.session_state:
    st.session_state.df = None

# =========================
# Sidebar: Select Anomaly
# =========================
st.sidebar.header("⚡ Tactical Reasoning Demo")
selected_idx = None
if st.session_state.df is not None and not st.session_state.df.empty:
    selected_idx = st.sidebar.selectbox(
        "Select anomaly ID",
        st.session_state.df.index.tolist()
    )

def anomaly_context(row):
    return f"""
Satellite anomaly detected:
Latitude: {row.latitude}
Longitude: {row.longitude}
Timestamp (UTC): {row.get('timestamp_utc', 'N/A')}
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

# =========================
# Side-by-side Comparison
# =========================
st.subheader("🧠 Side-by-Side Inference Comparison")

col1, col2 = st.columns(2)

if selected_idx is not None:
    row = st.session_state.df.loc[selected_idx]

    with col1:
        st.markdown("### 🖥 Traditional GPU (OpenAI) Response")
        if st.button("Generate OpenAI Response"):
            start = time.time()
            response_gpu = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": anomaly_context(row)}
                ],
                max_tokens=400,
                temperature=0.2
            )
            duration_gpu = time.time() - start
            st.markdown(f"*Response time: {duration_gpu:.2f}s*")
            st.markdown(response_gpu.choices[0].message.content)

    with col2:
        st.markdown("### ⚡ Cerebras Wafer-Scale Response")
        if CEREBRAS_AVAILABLE and st.button("Generate Cerebras Response"):
            client = Cerebras(api_key="csk-y2vf6htw5pp3vhwy63x5j2684yn6r2vwykffke4534tdpfyk")
            start = time.time()
            response_cerebras = client.chat.completions.create(
                model="llama-3.1-8b",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": anomaly_context(row)}
                ],
                max_completion_tokens=400,
                temperature=0.1
            )
            duration_cerebras = time.time() - start
            st.markdown(f"*Response time: {duration_cerebras:.2f}s*")
            st.markdown(response_cerebras.choices[0].message.content)

else:
    st.info("Fetch satellite detections first and select an anomaly from the sidebar.")
