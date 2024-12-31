import requests
import matplotlib.pyplot as plt

def plot_state_geometry(state_name, api_key):
    try:
        # URL for the Census Bureau TigerWeb API
        base_url = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/40/query"
        
        # Parameters to get the state's geometry
        params = {
            "where": f"NAME='{state_name}'",
            "outFields": "NAME",
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects",
            "returnGeometry": "true",
            "f": "json",
            "key": api_key,
        }
        
        # Make the API request
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        print (data)
        
        # Check if the response contains geometries
        if 'features' not in data or not data['features']:
            print(f"Geometry for state '{state_name}' not found.")
            return
        
        # Extract the geometry
        geometry = data['features'][0]['geometry']
        
        # Plot the state geometry
        plt.figure(figsize=(10, 8))
        
        # If geometry is a polygon (multiple rings)
        if "rings" in geometry:
            for ring in geometry["rings"]:
                x, y = zip(*ring)
                plt.plot(x, y, 'k', linewidth=1)
        else:
            print(f"Unexpected geometry format for state '{state_name}'.")
            return
        
        plt.title(f"Representation of {state_name}", fontsize=16)
        plt.xlabel("Longitude")
        plt.ylabel("Latitude")
        plt.axis("equal")
        # plt.grid(True)
        plt.show()
    
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
state_name = input("Enter the name of a U.S. state: ")
api_key = input("Enter your Census API key: ")
plot_state_geometry(state_name, api_key)
# 49805721fc58f58ce1a40cacf62d6765d8f923ed
