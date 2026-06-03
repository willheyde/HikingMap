# ingestion/osm_client.py
import time
import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Fetches named hiking relations and all their member nodes/ways.
# "out body; >; out skel qt;" means: give me the relations,
# then recurse down to get the ways and nodes they reference.
QUERY = """
[out:json][timeout:120];
(
  relation["route"="hiking"]["name"]({bbox});
  relation["route"="foot"]["name"]({bbox});
);
out body;
>;
out skel qt;
"""

def fetch_hiking_routes(bbox: str, retries: int = 3) -> dict:
    """
    bbox: "lat_min,lon_min,lat_max,lon_max"
    e.g. "35.4, -84.0, 35.8, -83.2" for a chunk of the Smokies
    """
    query = QUERY.format(bbox=bbox)

    for attempt in range(retries):
        try:
            resp = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=130,
            )
            resp.raise_for_status()
            data = resp.json()
            if "elements" not in data:
                raise ValueError("Overpass returned no elements")
            return data

        except Exception as e:
            if attempt < retries - 1:
                wait = 5 * (2 ** attempt)   # 5s → 10s → 20s
                print(f"  Overpass failed ({e}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise RuntimeError(f"Overpass API failed after {retries} attempts: {e}") from e