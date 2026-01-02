import requests

# CHANGED: We are switching to the Kumi Systems mirror which is often more reliable
# Old URL: "https://overpass-api.de/api/interpreter"
OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"

def fetch_hiking_routes(bbox):
    # Added [timeout:60] because Kumi sometimes takes a moment to spin up
    query = f"""
    [out:json][timeout:60];
    relation["route"="hiking"]["type"="route"]({bbox});
    out body;
    >;
    out skel qt;
    """
    
    # Added a specific User-Agent header (Good practice, prevents 403 Forbidden errors)
    headers = {
        "User-Agent": "HikingMapIngestor/1.0 (contact@example.com)",
        "Referer": "http://localhost"
    }

    try:
        response = requests.post(OVERPASS_URL, data=query, headers=headers)
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.ConnectionError as e:
        print(f"\nCRITICAL NETWORK ERROR: Could not connect to {OVERPASS_URL}")
        print("Please check your internet connection or try a different URL.")
        print(f"Details: {e}\n")
        raise