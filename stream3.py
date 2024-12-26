import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
import json
from urllib.parse import urlencode, urlunparse

st.set_page_config(page_title="Census Blocks Map", layout="wide")

# Sidebar inputs
st.sidebar.title("Census Blocks Map - Public APIs Only")
api_key = st.sidebar.text_input("Census API Key", "YOUR_CENSUS_API_KEY_HERE")
state_fips = st.sidebar.text_input("State FIPS", "44")    # Default: Rhode Island
county_fips = st.sidebar.text_input("County FIPS", "007")
variable = st.sidebar.selectbox("Variable", ["H1_001N"])  # Total population (2020 DHC)
zoom_level = st.sidebar.slider("Map Zoom", 5, 20, 12)

if not api_key:
    st.warning("Please provide a Census API Key in the sidebar.")
    st.stop()

# --- Fetch Tabular Data from Census API ---
base_url = "https://api.census.gov/data/2020/dec/dhc"
for_clause = "block:*"
in_clause = f"state:{state_fips};county:{county_fips}"
url = f"{base_url}?get={variable}&for={for_clause}&in={in_clause}&key={api_key}"
res = requests.get(url)

if res.status_code != 200:
    st.error(f"Error fetching Census data: {res.status_code} {res.text}")
    st.stop()

try:
    data = res.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    # Create GEOID for blocks (state+county+tract+block)
    df['GEOID'] = df['state'] + df['county'] + df['tract'] + df['block']
    df[variable] = pd.to_numeric(df[variable], errors='coerce').fillna(0)
    # st.write(df[variable])
    st.write(df)
except Exception as e:
    st.error(f"Error processing Census data: {e}")
    st.stop()

# Base URL for TIGERweb API
tigerweb_url = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/14/query"

# params = {
    #     "where": f"GEOID='{geoid}'",
    #     "outFields": "*",
    #     "f": "json"
    # }
params = {
        "where": f"STATE='{state_fips}'",
        "outFields": "*",
        "geometryType": "esriGeometryEnvelope",
        "outSR": "4326",
        "spatialRel": "esriSpatialRelItersects",
        "returnGeometry": "true",
        "f": "json",
        "key": api_key,
}
final_url = urlunparse((
    'https',  # Scheme 
    'tigerweb.geo.census.gov',  # Netloc
    '/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/14/query',  # Path
    '',  # Params
    urlencode(params),  # Query (encoded parameters)
    '',  # Fragment
))

# Display the final URL in the Streamlit app
st.write(f"Final URL: {final_url}")
# response = requests.get(tigerweb_url, params=params)
geo_res = requests.get(final_url)
geo_res.raise_for_status() 
if geo_res.status_code == 200:
    try:
        # st.write(f"JSON Response: {response.json()}")
        geojson = geo_res.json()  # Try parsing the JSON response
            
    except requests.exceptions.JSONDecodeError as e:
        st.error(f"Error decoding JSON for GEOID {state_fips}: {e}")
else:
    st.error(f"Error fetching TIGERweb data for GEOID {state_fips}: {geo_res.status_code}")
    
# The features have properties including GEOID. We'll join on GEOID.
# Convert the GeoJSON 'features' into a dictionary keyed by GEOID for easy merging.
# geo_features = {f["properties"]["GEOID"]: f for f in geojson["features"]}
geo_features = {f["attributes"]["GEOID"]: f for f in geojson["features"] if "GEOID" in f["STATE"]}

# Merge tabular data into the GeoJSON attributes
for i, feature in enumerate(geojson["features"]):
    geoid = feature["attributes"]["GEOID"]  # Adjusted for `STATE`
    row = df.loc[df["GEOID"] == geoid]  # Match with `GEOID` in the DataFrame
    if not row.empty:
        val = row[variable].values[0]
        geojson["features"][i]["attributes"][variable] = val
    else:
        # No data found for this geoid (should not typically happen), set to 0
        geojson["features"][i]["attributes"][variable] = 0

# Prepare a color scale function
# Extract values of the variable from attributes
vals = [f["attributes"].get(variable) for f in geojson["features"] if f["attributes"].get(variable) is not None]

# Check if vals is empty and set default values if so
if not vals:
    min_val, max_val = 0, 1  # Handle the case where there are no valid values
else:
    min_val, max_val = min(vals), max(vals)

def color_scale(val):
    if max_val == min_val:
        ratio = 0
    else:
        ratio = (val - min_val) / (max_val - min_val)
    r = int(255 * ratio)
    g = int(255 * (1 - ratio))
    b = 0
    return [r, g, b]

# Add a fill color attribute to each feature
for i, feature in enumerate(geojson["features"]):
    val = feature["attributes"][variable]
    feature["attributes"]["fill_color"] = color_scale(val)

# Compute the centroid for initial map view
# Compute the centroid for initial map view
if geojson["features"]:
    lons = []
    lats = []
    for f in geojson["features"]:
        geom = f["geometry"]
        
        # Ensure that the geometry contains "rings" for polygons
        if "rings" not in geom:
            st.warning(f"Missing 'rings' in geometry: {geom}")
            continue
        
        # Process the geometry assuming it's a polygon with 'rings'
        coords = geom["rings"][0]  # Extract the first ring (polygon coordinates)

        # Collect coordinates
        for c in coords:
            if len(c) >= 2:  # Ensure the coordinate is valid (should be a pair of lat/lon)
                lons.append(c[0])
                lats.append(c[1])

    # Calculate the center of the map
    if lons and lats:
        center_lon = sum(lons) / len(lons)
        center_lat = sum(lats) / len(lats)
    else:
        center_lon, center_lat = -71.5, 41.7  # Default Rhode Island center
else:
    center_lon, center_lat = -71.5, 41.7


# Create a pydeck layer for GeoJSON
layer = pdk.Layer(
    "GeoJsonLayer",
    geojson,
    pickable=True,
    opacity=0.6,
    stroked=True,
    filled=True,
    get_fill_color=[255, 0, 0],
    # get_fill_color="attributes.fill_color",  # Adjusted for `attributes`
    get_line_color=[0, 0, 0],
    line_width_min_pixels=1
)

initial_view_state = pdk.ViewState(
    longitude=center_lon,
    latitude=center_lat,
    zoom=zoom_level,
    pitch=0
)

st.title("Census Block Data (Public APIs Only)")
st.write(f"Variable: {variable}")
st.write("Hover over a block to see its value.")

st.pydeck_chart(
    pdk.Deck(
        layers=[layer],
        initial_view_state=initial_view_state,
        tooltip={"text": f"{variable}: {{attributes.{variable}}}"}  # Adjusted for `attributes`
    )
)


# Merge tabular data into the GeoJSON properties
# geo_features = {f["properties"]["GEOID"]: f for f in geojson["features"]}
# for i, feature in enumerate(geojson["features"]):
#     geoid = feature["properties"]["GEOID"]
#     row = df.loc[df["GEOID"] == geoid]
#     if not row.empty:
#         val = row[variable].values[0]
#         geojson["features"][i]["properties"][variable] = val
#     else:
#         # No data found for this geoid (should not typically happen), set to 0
#         geojson["features"][i]["properties"][variable] = 0

# # Prepare a color scale function
# # vals = [f["properties"][variable] for f in geojson["features"]]
# # Filter out None or invalid values before calculating min and max
# # Filter out None or invalid values before calculating min and max
# vals = [f["properties"].get(variable) for f in geojson["features"] if f["properties"].get(variable) is not None]

# Check if vals is empty and set default values if so
# if not vals:
#     # Handle the case where there are no valid values
#     min_val, max_val = 0, 1
# else:
#     min_val, max_val = min(vals), max(vals)

# # min_val, max_val = min(vals), max(vals) if vals else (0, 1)

# def color_scale(val):
#     if max_val == min_val:
#         ratio = 0
#     else:
#         ratio = (val - min_val) / (max_val - min_val)
#     r = int(255 * ratio)
#     g = int(255 * (1 - ratio))
#     b = 0
#     return [r, g, b]

# # Add a fill color property to each feature
# for i, feature in enumerate(geojson["features"]):
#     val = feature["properties"][variable]
#     feature["properties"]["fill_color"] = color_scale(val)

# # Compute the centroid for initial map view
# # We'll just average coordinates of bounding box. Alternatively, 
# # we could find the centroid of all polygons by a quick bounding approach.
# if geojson["features"]:
#     # Collect all coordinates to approximate center
#     lons = []
#     lats = []
#     for f in geojson["features"]:
#         geom = f["geometry"]
#         if geom["type"] == "Polygon":
#             coords = geom["coordinates"][0]
#         elif geom["type"] == "MultiPolygon":
#             # Just take first polygon of multipolygon for center calc
#             coords = geom["coordinates"][0][0]
#         else:
#             coords = []
#         for c in coords:
#             lons.append(c[0])
#             lats.append(c[1])
#     if lons and lats:
#         center_lon = sum(lons) / len(lons)
#         center_lat = sum(lats) / len(lats)
#     else:
#         center_lon, center_lat = -71.5, 41.7  # Default Rhode Island center
# else:
#     center_lon, center_lat = -71.5, 41.7

# Create a pydeck layer for GeoJSON
# layer = pdk.Layer(
#     "GeoJsonLayer",
#     geojson,
#     pickable=True,
#     opacity=0.6,
#     stroked=True,
#     filled=True,
#     get_fill_color="properties.fill_color",
#     get_line_color=[0, 0, 0],
#     line_width_min_pixels=1
# )

# initial_view_state = pdk.ViewState(
#     longitude=center_lon,
#     latitude=center_lat,
#     zoom=zoom_level,
#     pitch=0 
# )

# st.title("Census Block Data (Public APIs Only)")
# st.write(f"Variable: {variable}")
# st.write("Hover over a block to see its value.")

# st.pydeck_chart(
#     pdk.Deck(
#         layers=[layer],
#         initial_view_state=initial_view_state,
#         tooltip={"text": f"{variable}: {{ {variable} }}"}
#     )
# )
    
# Query TIGERweb for each GEOID in the DataFrame
# results = []
# for _, row in df.iterrows():
#     geoid = row["GEOID"]
#     tigerweb_data = query_tigerweb(geoid)
#     if tigerweb_data:
#         results.append(tigerweb_data)
    

# # Display results (or process further)
# st.write("TIGERweb API Results", results)