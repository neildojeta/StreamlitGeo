import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
import json
import logging
import numpy as np
from datetime import datetime

# Set up logging
log_filename = f"census_blocks_map_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.info("Application started.")

st.set_page_config(page_title="Census Blocks Map", layout="wide")

# Sidebar inputs
st.sidebar.title("Census Blocks Map - Public APIs Only")
api_key = "49805721fc58f58ce1a40cacf62d6765d8f923ed"
state_fips = st.sidebar.text_input("State FIPS", "44")  # Default: Rhode Island
county_fips = st.sidebar.text_input("County FIPS", "007")
variable = st.sidebar.selectbox("Variable", ["H1_001N"])  # Total population (2020 DHC)
zoom_level = 12
# zoom_level = st.sidebar.slider("Map Zoom", 10, 20, 12)

logging.info(f"State FIPS: {state_fips}, County FIPS: {county_fips}, Variable: {variable}, Zoom Level: {zoom_level}")

if not api_key:
    st.warning("Please provide a Census API Key in the sidebar.") 
    logging.error("API Key not provided.")
    st.stop()

# --- Fetch Tabular Data from Census API ---
base_url = "https://api.census.gov/data/2020/dec/dhc"
for_clause = "block:*"
in_clause = f"state:{state_fips};county:{county_fips}"
url = f"{base_url}?get={variable}&for={for_clause}&in={in_clause}&key={api_key}"
logging.info(f"Census API URL: {url}")

res = requests.get(url)
if res.status_code != 200:
    logging.error(f"Error fetching Census data: {res.status_code} {res.text}")
    st.error(f"Error fetching Census data: {res.status_code} {res.text}")
    st.stop()

try:
    data = res.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    df['GEOID'] = df['state'] + df['county'] + df['tract']
    df[variable] = pd.to_numeric(df[variable], errors='coerce').fillna(0)
    logging.info(f"Successfully fetched and processed Census data. {len(df)} rows retrieved.")
except Exception as e:
    logging.error(f"Error processing Census data: {e}")
    st.error(f"Error processing Census data: {e}")
    st.stop()

# --- Fetch Geometry from TIGERweb ---
tiger_url = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/0/query"
)
geoid_value = str(df['GEOID'].iloc[0]) if not df.empty else None
if geoid_value:
    params = {
        "where": f"GEOID='{geoid_value}'",
        "outFields": "GEOID",
        "f": "geojson"
    }
else:
    st.error("No GEOID value available. DataFrame is empty.")
    st.stop()
logging.info(f"TIGERweb query params: {params}")

geom_res = requests.get(tiger_url, params=params)
if geom_res.status_code != 200:
    logging.error(f"Error fetching geometry: {geom_res.status_code} {geom_res.text}")
    st.error(f"Error fetching geometry: {geom_res.status_code} {geom_res.text}")
    st.stop()

try:
    geojson = geom_res.json()
    logging.info("Successfully fetched geometry data.")
except json.JSONDecodeError as e:
    logging.error("Error decoding GeoJSON response from TIGERweb.")
    st.error("Error decoding GeoJSON response from TIGERweb.")
    st.stop()

# Merge tabular data into the GeoJSON properties
geo_features = {f["properties"]["GEOID"]: f for f in geojson["features"]}

for i, feature in enumerate(geojson["features"]):
    geoid = feature["properties"]["GEOID"]
    row = df.loc[df["GEOID"] == geoid]
    if not row.empty:
        val = row[variable].values[0]
        geojson["features"][i]["properties"][variable] = val
    else:
        geojson["features"][i]["properties"][variable] = 0
logging.info("Merged tabular data into GeoJSON properties.")

# Prepare a color scale function
vals = [f["properties"][variable] for f in geojson["features"]]
min_val, max_val = min(vals), max(vals) if vals else (0, 1)

def color_scale(val):
    if max_val == min_val:
        ratio = 0
    else:
        ratio = (val - min_val) / (max_val - min_val)
    r = int(255 * (1 - ratio))  # Red decreases as value increases
    g = int(255 * ratio)  # Green increases as value increases
    b = int(255 * (1 - ratio))  # Blue decreases as value increases
    return [r, g, b]

for i, feature in enumerate(geojson["features"]):
    val = feature["properties"][variable]
    feature["properties"]["fill_color"] = color_scale(val)
logging.info("Applied color scale to GeoJSON features.")

st.title("Census Block Data (Public APIs Only)")
st.write(f"Variable: {variable}")
st.write("Hover over a block to see its value.")
# Prepare list of coordinates from the GeoJSON features
coordinates = []
for feature in geojson["features"]:
    geom = feature["geometry"]
    if geom["type"] == "Polygon":
        coords = geom["coordinates"][0]  # Polygon coordinates
    elif geom["type"] == "MultiPolygon":
        coords = geom["coordinates"][0][0]  # MultiPolygon coordinates
    else:
        coords = []
    
    # Add all coordinates to the list
    for coord in coords:
        lon, lat = coord
        coordinates.append({"lat": lat, "lon": lon})

# If there are coordinates to plot
if coordinates:
    logging.info(f"Found {len(coordinates)} coordinates to plot.")
    
    # Create the pydeck map
    deck = pdk.Deck(
        initial_view_state=pdk.ViewState(
            latitude=coordinates[0]["lat"],  # Use the first coordinate to center the map
            longitude=coordinates[0]["lon"],
            zoom=zoom_level,
            pitch=0
        ),
        layers=[
            pdk.Layer(
                "ScatterplotLayer",
                data=coordinates,
                get_position=["lon", "lat"],
                get_radius=100,
                get_fill_color=[255, 0, 0],  # Red color for the points
                pickable=True
            )
        ]
    )

    # Render the pydeck map
    st.pydeck_chart(deck)
    logging.info("Visualized all coordinates on the map.")
else:
    logging.error("No coordinates found to plot.")
    st.error("No coordinates found to plot.")

logging.info("Application finished.")
