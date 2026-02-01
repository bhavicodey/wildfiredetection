import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="FIRMS Fire Visualization", layout="wide")

st.title("🔥 NASA FIRMS Fire Data Visualization (Update)")
st.markdown("Visualize active fire data from NASA's Fire Information for Resource Management System")

# Sidebar for inputs
st.sidebar.header("Configuration")

# API Key input
api_key = st.sidebar.text_input("Enter your FIRMS API Key:", type="password")

# Date selection
st.sidebar.subheader("Date Range")
col1, col2 = st.sidebar.columns(2)
with col1:
    start_date = st.date_input(
        "Start Date",
        value=datetime.now() - timedelta(days=7),
        max_value=datetime.now()
    )
with col2:
    end_date = st.date_input(
        "End Date",
        value=datetime.now(),
        max_value=datetime.now()
    )

# Location input
st.sidebar.subheader("Location (Bounding Box)")
st.sidebar.markdown("Enter coordinates for the bounding box:")

col3, col4 = st.sidebar.columns(2)
with col3:
    min_lat = st.number_input("Min Latitude", value=-10.0, min_value=-90.0, max_value=90.0, step=0.1)
    min_lon = st.number_input("Min Longitude", value=-80.0, min_value=-180.0, max_value=180.0, step=0.1)
with col4:
    max_lat = st.number_input("Max Latitude", value=10.0, min_value=-90.0, max_value=90.0, step=0.1)
    max_lon = st.number_input("Max Longitude", value=-60.0, min_value=-180.0, max_value=180.0, step=0.1)

# Data source selection
data_source = st.sidebar.selectbox(
    "Satellite Source",
    ["VIIRS_NOAA20_NRT", "VIIRS_SNPP_NRT", "MODIS_NRT"],
    help="VIIRS has higher resolution, MODIS has longer historical record"
)

# Fetch button
fetch_data = st.sidebar.button("🔍 Fetch Fire Data", type="primary")


def get_firms_data(api_key, source, area, date_range):
    """
    Fetch fire data from NASA FIRMS API
    API Format: /api/area/csv/{MAP_KEY}/{source}/{area}/{dayrange}/{date}
    Returns data for [DATE] to [DATE + DAY_RANGE - 1]
    """
    # Format start date - FIRMS expects YYYY-MM-DD format
    start_date = date_range[0].strftime("%Y-%m-%d")
    day_range = date_range[2]
    
    # Build URL for area request
    base_url = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
    
    # The DATE parameter is just the start date
    # The API returns data from start_date to start_date + day_range - 1
    url = f"{base_url}/{api_key}/{source}/{area}/{day_range}/{start_date}"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Check if response is valid
        if "Invalid" in response.text or "error" in response.text.lower():
            return None, response.text
        
        # Parse CSV data
        from io import StringIO
        df = pd.read_csv(StringIO(response.text))
        
        # Convert data types - FIRMS sometimes returns confidence as string ('l', 'n', 'h') or numeric
        # Handle both cases
        if 'confidence' in df.columns:
            # If confidence is categorical (l/n/h), convert to numeric
            if df['confidence'].dtype == 'object':
                confidence_map = {'l': 30, 'n': 50, 'h': 80, 'low': 30, 'nominal': 50, 'high': 80}
                df['confidence'] = df['confidence'].map(lambda x: confidence_map.get(str(x).lower(), 50))
            # Convert to numeric, handling any errors
            df['confidence'] = pd.to_numeric(df['confidence'], errors='coerce').fillna(50)
        
        # Convert other numeric columns
        numeric_cols = ['latitude', 'longitude', 'bright_ti4', 'frp']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df, None
    except requests.exceptions.RequestException as e:
        return None, str(e)


def create_fire_map(df, bbox):
    """
    Create a Folium map with fire markers
    """
    # Calculate center of bounding box
    center_lat = (bbox[0] + bbox[2]) / 2
    center_lon = (bbox[1] + bbox[3]) / 2
    
    # Create map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=6,
        tiles="OpenStreetMap"
    )
    
    # Add bounding box rectangle
    folium.Rectangle(
        bounds=[[bbox[0], bbox[1]], [bbox[2], bbox[3]]],
        color="blue",
        fill=False,
        weight=2,
        popup="Search Area"
    ).add_to(m)
    
    # Add fire markers
    if len(df) > 0:
        # Color coding by confidence level
        def get_color(confidence):
            # Handle both numeric and string confidence values
            try:
                if isinstance(confidence, str):
                    conf_lower = confidence.lower()
                    if conf_lower in ['h', 'high']:
                        return 'red'
                    elif conf_lower in ['n', 'nominal']:
                        return 'orange'
                    else:
                        return 'yellow'
                else:
                    # Numeric confidence
                    conf_num = float(confidence)
                    if conf_num >= 80:
                        return 'red'
                    elif conf_num >= 50:
                        return 'orange'
                    else:
                        return 'yellow'
            except:
                return 'yellow'  # Default color if we can't parse
        
        # Add markers (limit to 2000 for performance)
        sample_df = df.head(2000) if len(df) > 2000 else df
        
        for idx, row in sample_df.iterrows():
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=4,
                popup=folium.Popup(
                    f"""
                    <b>Fire Detection</b><br>
                    Date: {row['acq_date']}<br>
                    Time: {row['acq_time']}<br>
                    Confidence: {row['confidence']}<br>
                    Brightness: {row['bright_ti4']} K<br>
                    FRP: {row['frp']} MW
                    """,
                    max_width=200
                ),
                color=get_color(row['confidence']),
                fill=True,
                fillColor=get_color(row['confidence']),
                fillOpacity=0.7
            ).add_to(m)
    
    return m


# Main content
if not api_key:
    st.info("👈 Please enter your FIRMS API key in the sidebar to get started.")
    st.markdown("""
    ### How to get a FIRMS API Key:
    1. Visit [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/api/area/)
    2. Register for a free API key
    3. Enter the key in the sidebar
    
    ### About the Data Sources:
    - **VIIRS NOAA-20**: High resolution, near real-time data
    - **VIIRS S-NPP**: High resolution, near real-time data  
    - **MODIS**: Moderate resolution, longer historical record
    """)
elif fetch_data:
    if start_date > end_date:
        st.error("Start date must be before end date!")
    else:
        # Validate bounding box
        if min_lat >= max_lat or min_lon >= max_lon:
            st.error("Invalid bounding box! Ensure min values are less than max values.")
        else:
            with st.spinner("Fetching fire data from NASA FIRMS..."):
                # Format area string
                area = f"{min_lon},{min_lat},{max_lon},{max_lat}"
                
                # Calculate day range
                day_range = (end_date - start_date).days + 1
                
                # Fetch data
                df, error = get_firms_data(
                    api_key, 
                    data_source, 
                    area, 
                    (start_date, end_date, day_range)
                )
                
                if error:
                    st.error(f"Error fetching data: {error}")
                elif df is None or len(df) == 0:
                    st.warning("No fire detections found for the specified area and time range.")
                else:
                    st.success(f"Found {len(df)} fire detections!")
                    
                    # Display statistics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Fires", len(df))
                    with col2:
                        try:
                            high_conf = len(df[df['confidence'] >= 80])
                        except:
                            high_conf = 0
                        st.metric("High Confidence", high_conf)
                    with col3:
                        try:
                            avg_frp = df['frp'].mean()
                            st.metric("Avg Fire Power", f"{avg_frp:.1f} MW")
                        except:
                            st.metric("Avg Fire Power", "N/A")
                    with col4:
                        unique_days = df['acq_date'].nunique()
                        st.metric("Days with Fires", unique_days)
                    
                    # Create and display map
                    st.subheader("Fire Location Map")
                    bbox = [min_lat, min_lon, max_lat, max_lon]
                    fire_map = create_fire_map(df, bbox)
                    folium_static(fire_map, width=1200, height=600)
                    
                    # Display data table
                    st.subheader("Fire Detection Data")
                    st.dataframe(
                        df[['latitude', 'longitude', 'acq_date', 'acq_time', 
                            'confidence', 'bright_ti4', 'frp']].head(100),
                        use_container_width=True
                    )
                    
                    # Download option
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Full Dataset (CSV)",
                        data=csv,
                        file_name=f"firms_fire_data_{start_date}_{end_date}.csv",
                        mime="text/csv"
                    )
                    
                    # Time series chart
                    if len(df) > 0:
                        st.subheader("Fire Detections Over Time")
                        daily_counts = df.groupby('acq_date').size().reset_index(name='count')
                        st.line_chart(daily_counts.set_index('acq_date'))

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("### About")
st.sidebar.info("""
This app uses NASA's FIRMS (Fire Information for Resource Management System) 
to visualize active fire data detected by satellites.

Data is near real-time (within 3 hours of satellite observation).
""")
