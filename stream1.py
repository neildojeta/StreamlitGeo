   


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
state_fips = st.sidebar.text_input("State FIPS", "44")   # Default: Rhode Island
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
except Exception as e:
    st.error(f"Error processing Census data: {e}")
    st.stop()

# --- Fetch Geometry from TIGERweb ---
# We'll use the TIGERweb Census 2020 ArcGIS REST service:
# Census Blocks (2020) layer is layer=14 in: 
# https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/14
#
# We can query by STATE and COUNTY fields. The output will be GeoJSON.
# Example:
# https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/14/query
# ?where=STATE='44'%20AND%20COUNTY='007'
# &outFields=GEOID,STATE,COUNTY,TRACT,BLOCK
# &outSR=4326
# &f=geojson



# params = {
#     "where": f"STATE='{state_fips}' AND COUNTY='{county_fips}'",
#     "outFields": "GEOID,STATE,COUNTY,TRACT,BLOCK",
#     "outSR": "4326",
#     "f": "geojson"
# }

# params = {"where": f"STATE={state_fips}"}
# geom_res = requests.get(tiger_url, params=params)
tiger_url = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/14/query"
)
# params = {
#     "where": f"STATE='{state_fips}'",  # Ensure proper formatting for string comparison
#     "geometryType": "esriGeometryEnvelope",
#     "spatialRel": "esriSpatialRelIntersects",
#     "distance": "",
#     "units": "esriSRUnit_Foot",
#     "returnGeometry": "true",
#     "returnTrueCurves": "false",
#     "returnIdsOnly": "false",
#     "returnCountOnly": "false",
#     "orderByFields": "",
#     "groupByFieldsForStatistics": "",
#     "outStatistics": "",
#     "returnZ": "false",
#     "returnM": "false",
#     "sqlFormat": "none",
#     "featureEncoding": "esriDefault",
#     "outFields": "*",  # Use "*" to return all fields
#     "outSR": "",
#     "resultRecordCount": "1000",  # Limit the number of records returned if needed
#     "f": "json",  # Ensure the response is in JSON format
# }
params = {
    "where": f"STATE='{state_fips}'",  # Same as before
    "text": "",
    "objectIds": "",
    "time": "",
    "timeRelation": "esriTimeRelationOverlaps",
    "geometry": "",
    "geometryType": "esriGeometryEnvelope",
    "inSR": "",
    "spatialRel": "esriSpatialRelIntersects",
    "distance": "",
    "units": "esriSRUnit_Foot",
    "relationParam": "",
    "outFields": "",  # Return all fields
    "returnGeometry": "true",
    "returnTrueCurves": "false",
    "maxAllowableOffset": "",
    "geometryPrecision": "",
    "outSR": "",
    "havingClause": "",
    "returnIdsOnly": "false",
    "returnCountOnly": "false",
    "orderByFields": "",
    "groupByFieldsForStatistics": "",
    "outStatistics": "",
    "returnZ": "false",
    "returnM": "false",
    "gdbVersion": "",
    "historicMoment": "",
    "returnDistinctValues": "false",
    "resultOffset": "",
    "resultRecordCount": "",  # Same as before
    "returnExtentOnly": "false",
    "sqlFormat": "none",
    "datumTransformation": "",
    "parameterValues": "",
    "rangeValues": "",
    "quantizationParameters": "",
    "featureEncoding": "esriDefault",
    "f": "pjson",  # Added this
}

headers = {
    "Accept": "application/json",  # Accept JSON response
}

geom_res = requests.get(url, params=params, headers=headers)


headers = {
    "Accept": "application/json",
}
# Build the full URL with parameters
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

geom_res = requests.get(final_url)

if geom_res.status_code != 200:
    st.error(f"Error fetching geometry: {geom_res.status_code} {geom_res.text}")
    st.stop()
# Attempt to parse the GeoJSON
try:
    geojson = geom_res.json()
except json.JSONDecodeError as e:
    st.error(f"Error decoding GeoJSON response from TIGERweb: {e}")
    st.stop()

# Check for content type and ensure it's JSON
# if 'application/json' not in geom_res.headers.get('Content-Type', ''):
# if 'application/json' not in geojson:
#     st.error(f"Expected JSON response but got {geom_res.headers.get('Content-Type')}. Response content:\n{geom_res.text}")
#     st.stop()

# Continue processing the GeoJSON if it's valid
if "features" not in geojson:
    st.error("No 'features' found in the GeoJSON response.")
    st.stop()


# The features have properties including GEOID. We'll join on GEOID.
# Convert the GeoJSON 'features' into a dictionary keyed by GEOID for easy merging.
geo_features = {f["properties"]["GEOID"]: f for f in geojson["features"]}

# Merge tabular data into the GeoJSON properties
for i, feature in enumerate(geojson["features"]):
    geoid = feature["properties"]["GEOID"]
    row = df.loc[df["GEOID"] == geoid]
    if not row.empty:
        val = row[variable].values[0]
        geojson["features"][i]["properties"][variable] = val
    else:
        # No data found for this geoid (should not typically happen), set to 0
        geojson["features"][i]["properties"][variable] = 0

# Prepare a color scale function
vals = [f["properties"][variable] for f in geojson["features"]]
min_val, max_val = min(vals), max(vals) if vals else (0, 1)

def color_scale(val):
    if max_val == min_val:
        ratio = 0
    else:
        ratio = (val - min_val) / (max_val - min_val)
    r = int(255 * ratio)
    g = int(255 * (1 - ratio))
    b = 0
    return [r, g, b]

# Add a fill color property to each feature
for i, feature in enumerate(geojson["features"]):
    val = feature["properties"][variable]
    feature["properties"]["fill_color"] = color_scale(val)

# Compute the centroid for initial map view
# We'll just average coordinates of bounding box. Alternatively, 
# we could find the centroid of all polygons by a quick bounding approach.
if geojson["features"]:
    # Collect all coordinates to approximate center
    lons = []
    lats = []
    for f in geojson["features"]:
        geom = f["geometry"]
        if geom["type"] == "Polygon":
            coords = geom["coordinates"][0]
        elif geom["type"] == "MultiPolygon":
            # Just take first polygon of multipolygon for center calc
            coords = geom["coordinates"][0][0]
        else:
            coords = []
        for c in coords:
            lons.append(c[0])
            lats.append(c[1])
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
    get_fill_color="properties.fill_color",
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
        tooltip={"text": f"{variable}: {{ {variable} }}"}
    )
)


