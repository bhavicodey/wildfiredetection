# NASA FIRMS Fire Visualization App

A Streamlit web application for visualizing active fire data from NASA's Fire Information for Resource Management System (FIRMS).

## Features

- 🗺️ Interactive map visualization of fire detections
- 📅 Customizable date range selection
- 📍 Bounding box location selection
- 🛰️ Multiple satellite data sources (VIIRS, MODIS)
- 📊 Statistical summaries and time series charts
- 💾 Download fire data as CSV

## Setup

### 1. Get a FIRMS API Key

Before running the app, you need to obtain a free API key from NASA FIRMS:

1. Visit: https://firms.modaps.eosdis.nasa.gov/api/area/
2. Click on "Request API Key"
3. Fill out the registration form
4. Check your email for the API key

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Application

```bash
streamlit run firms_fire_viz.py
```

The app will open in your default web browser at `http://localhost:8501`

## Usage

1. **Enter API Key**: Paste your FIRMS API key in the sidebar
2. **Select Date Range**: Choose start and end dates for fire data
3. **Define Location**: Set the bounding box coordinates:
   - Min/Max Latitude (range: -90 to 90)
   - Min/Max Longitude (range: -180 to 180)
4. **Choose Satellite Source**: 
   - VIIRS_NOAA20_NRT (recommended for recent data)
   - VIIRS_SNPP_NRT (higher resolution)
   - MODIS_NRT (longer historical record)
5. **Fetch Data**: Click the "Fetch Fire Data" button

## Understanding the Results

- **Map Markers**: 
  - Red: High confidence fires (≥80%)
  - Orange: Medium confidence fires (50-79%)
  - Yellow: Lower confidence fires (<50%)
- **Statistics**: Total fires, high confidence count, average fire radiative power
- **Data Table**: Detailed information about each fire detection
- **Time Series**: Daily fire detection counts

## Example Coordinates

- **Amazon Rainforest**: Min Lat: -10, Min Lon: -70, Max Lat: 5, Max Lon: -50
- **California**: Min Lat: 32, Min Lon: -125, Max Lat: 42, Max Lon: -114
- **Australia**: Min Lat: -44, Min Lon: 113, Max Lat: -10, Max Lon: 154
- **Indonesia**: Min Lat: -11, Min Lon: 95, Max Lat: 6, Max Lon: 141

## Data Sources

The app uses NASA's FIRMS API to access fire detection data from:
- **VIIRS** (Visible Infrared Imaging Radiometer Suite): 375m resolution
- **MODIS** (Moderate Resolution Imaging Spectroradiometer): 1km resolution

Data is near real-time, typically available within 3 hours of satellite observation.

## Limitations

- Maximum 2000 fire markers displayed on map (for performance)
- API may have rate limits depending on your key tier
- Historical data availability varies by satellite (MODIS has longer record)

## Troubleshooting

**"Invalid API Key" error**: 
- Verify your API key is correct
- Ensure you've activated the key via email confirmation

**"No fire detections found"**:
- Try expanding the date range or bounding box
- Check if fires are expected in the selected region
- Try a different satellite source

**Slow loading**:
- Reduce the date range
- Use a smaller bounding box area
- VIIRS data loads faster than MODIS for recent dates

## License

This application uses data from NASA FIRMS, which is freely available for public use.

## Credits

- NASA FIRMS: https://firms.modaps.eosdis.nasa.gov/
- Built with Streamlit, Folium, and Pandas
