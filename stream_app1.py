import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
import json
import logging
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
    
    for coord in coords:
        lon, lat = coord
        coordinates.append({"lat": lat, "lon": lon})

# --- Navigation and Toggle ---
if "current_index" not in st.session_state:
    st.session_state.current_index = 0

if "show_all" not in st.session_state:
    st.session_state.show_all = False

# Toggle button
st.sidebar.markdown("### View Options")
if st.sidebar.button("Toggle View (All / Navigate)"):
    st.session_state.show_all = not st.session_state.show_all

# Navigation buttons are disabled if "Show All" is enabled
if not st.session_state.show_all:
    st.sidebar.markdown("### Navigation")
    prev_disabled = st.session_state.current_index <= 0
    next_disabled = st.session_state.current_index >= len(coordinates) - 1

    prev_button = st.sidebar.button("Previous", disabled=prev_disabled)
    next_button = st.sidebar.button("Next", disabled=next_disabled)

    if prev_button and not prev_disabled:
        st.session_state.current_index -= 1
    elif next_button and not next_disabled:
        st.session_state.current_index += 1

current_index = st.session_state.current_index

# Display map
if st.session_state.show_all:
    # Show all coordinates
    deck = pdk.Deck(
        initial_view_state=pdk.ViewState(
            latitude=coordinates[0]["lat"],
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
                get_fill_color=[255, 0, 0],
                pickable=True
            )
        ]
    )
    st.pydeck_chart(deck)
    st.write(f"Showing all {len(coordinates)} coordinates.")
else:
    # Navigate through coordinates
    if coordinates:
        current_coord = coordinates[current_index]
        lat, lon = current_coord["lat"], current_coord["lon"]

        deck = pdk.Deck(
            initial_view_state=pdk.ViewState(
                latitude=lat,
                longitude=lon,
                zoom=zoom_level,
                pitch=0
            ),
            layers=[
                pdk.Layer(
                    "ScatterplotLayer",
                    data=[current_coord],
                    get_position=["lon", "lat"],
                    get_radius=100,
                    get_fill_color=[255, 0, 0],
                    pickable=True
                )
            ]
        )

        st.pydeck_chart(deck)
        st.write(f"Coordinate {current_index + 1} of {len(coordinates)}")
        st.write(f"Latitude: {lat}, Longitude: {lon}")
    else:
        logging.error("No coordinates found.")
        st.error("No coordinates found.")

logging.info("Application finished.")
