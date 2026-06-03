import collections


def build_points_from_relation(relation: dict, elements: list) -> list | None:
    """
    Builds an ordered list of {lat, lon, ele} points for a hiking relation
    by stitching its ways together geometrically.

    ele is None when the OSM node carries no elevation tag — callers should
    treat None as "no data" rather than "sea level".
    """
    node_lookup = {el["id"]: el for el in elements if el["type"] == "node"}
    ways_lookup = {el["id"]: el for el in elements if el["type"] == "way"}

    ways = []
    for member in relation.get("members", []):
        if member["type"] == "way" and member["ref"] in ways_lookup:
            w = ways_lookup[member["ref"]].copy()
            w["nodes"] = list(w["nodes"])
            ways.append(w)

    if not ways:
        return None

    sorted_ways = _sort_ways_geometrically(ways)

    points = []
    for way_index, way in enumerate(sorted_ways):
        nodes = way.get("nodes", [])

        # FIX: skip the first node of every way after the first one —
        # it is the junction node already appended as the last point of
        # the previous way, so including it again inflates distance.
        start = 1 if way_index > 0 else 0

        for node_id in nodes[start:]:
            node = node_lookup.get(node_id)
            if node:
                ele_raw = node.get("tags", {}).get("ele")
                ele = float(ele_raw) if ele_raw is not None else None  # None = no data
                points.append({
                    "lat": node["lat"],
                    "lon": node["lon"],
                    "ele": ele,
                })

    return points if len(points) > 1 else None


def _sort_ways_geometrically(ways: list) -> list:
    """
    Takes an unordered list of OSM ways and stitches them into a continuous
    chain.  Reverses individual ways as needed to make them connect.
    If gaps exist the longest contiguous chain found so far is returned.
    """
    if not ways:
        return []

    chain = collections.deque([ways.pop(0)])

    added = True
    while added and ways:
        added = False
        chain_start = chain[0]["nodes"][0]
        chain_end   = chain[-1]["nodes"][-1]

        for i, way in enumerate(ways):
            w_start = way["nodes"][0]
            w_end   = way["nodes"][-1]

            if w_start == chain_end:
                chain.append(way)
            elif w_end == chain_end:
                way["nodes"].reverse()
                chain.append(way)
            elif w_end == chain_start:
                chain.appendleft(way)
            elif w_start == chain_start:
                way["nodes"].reverse()
                chain.appendleft(way)
            else:
                continue

            ways.pop(i)
            added = True
            break

    if ways:
        # Remaining ways couldn't be connected — trail has geometry gaps in OSM.
        print(f"  Warning: {len(ways)} disconnected way(s) dropped — trail has gaps in OSM data.")

    return list(chain)


def to_linestring(points: list) -> dict:
    return {
        "type": "LineString",
        "coordinates": [[p["lon"], p["lat"]] for p in points],
    }


def altitude_stats(points: list) -> tuple[float | None, float | None]:
    """Returns (min_ele, max_ele), or (None, None) if no elevation data exists."""
    elevations = [p["ele"] for p in points if p["ele"] is not None]
    if not elevations:
        return None, None
    return min(elevations), max(elevations)