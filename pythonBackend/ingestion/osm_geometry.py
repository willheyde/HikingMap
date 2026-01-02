import collections

def build_points_from_relation(relation, elements):
    """
    Builds ordered lat/lon points for a hiking relation by stitching
    ways together geometrically.
    """
    # 1. Create lookup maps for nodes and ways
    node_lookup = {el["id"]: el for el in elements if el["type"] == "node"}
    ways_lookup = {el["id"]: el for el in elements if el["type"] == "way"}
    
    # 2. Extract all 'way' members from the relation
    ways = []
    for member in relation.get("members", []):
        if member["type"] == "way" and member["ref"] in ways_lookup:
            # We explicitly copy the way object because we might modify it (reverse it)
            # and we don't want to break the original data for other relations.
            w = ways_lookup[member["ref"]].copy()
            # We must copy the nodes list too, as we might reverse it
            w["nodes"] = list(w["nodes"]) 
            ways.append(w)

    if not ways:
        return None

    # 3. Sort the ways so they connect end-to-start
    sorted_ways = _sort_ways_geometrically(ways)

    # 4. Extract Lat/Lon/Ele from the sorted nodes
    points = []
    for way in sorted_ways:
        for node_id in way.get("nodes", []):
            node = node_lookup.get(node_id)
            if node:
                ele = float(node.get("tags", {}).get("ele", 0))
                points.append({
                    "lat": node["lat"],
                    "lon": node["lon"],
                    "ele": ele
                })

    return points if len(points) > 1 else None

def _sort_ways_geometrically(ways):
    """
    Takes a list of unordered OSM ways and stitches them into a continuous line.
    Handles cases where a segment might be drawn 'backwards' by reversing it.
    """
    if not ways:
        return []

    # Start the chain with the first available way
    # Use a deque (double-ended queue) to easily add to front or back
    chain = collections.deque([ways.pop(0)])

    # Keep trying to add ways until we can't add any more
    added_something = True
    while added_something and ways:
        added_something = False
        
        # Get the current start and end node IDs of our chain
        chain_start_node = chain[0]["nodes"][0]
        chain_end_node = chain[-1]["nodes"][-1]

        # Look for a way that connects to either end
        for i, way in enumerate(ways):
            way_start = way["nodes"][0]
            way_end = way["nodes"][-1]

            # CHECK: Does this way connect to the END of our chain?
            if way_start == chain_end_node:
                chain.append(way) # Perfect match
                ways.pop(i)
                added_something = True
                break
            elif way_end == chain_end_node:
                way["nodes"].reverse() # Match, but way is drawn backwards
                chain.append(way)
                ways.pop(i)
                added_something = True
                break
            
            # CHECK: Does this way connect to the START of our chain?
            elif way_end == chain_start_node:
                chain.appendleft(way) # Perfect match at the start
                ways.pop(i)
                added_something = True
                break
            elif way_start == chain_start_node:
                way["nodes"].reverse() # Match start-to-start, so reverse way
                chain.appendleft(way)
                ways.pop(i)
                added_something = True
                break
    
    # Warning: If 'ways' is not empty here, the trail has gaps/jumps.
    # We return the longest contiguous chain we managed to build.
    return list(chain)

def to_linestring(points):
    return {
        "type": "LineString",
        "coordinates": [[p["lon"], p["lat"]] for p in points]
    }

def altitude_stats(points):
    elevations = [p["ele"] for p in points if p["ele"] > 0]
    if not elevations:
        return 0, 0
    return min(elevations), max(elevations)