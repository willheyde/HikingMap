"""
pbf_hiking_extractor.py

Extracts hiking route relations from a local .osm.pbf file and returns them
in the same "elements" list shape that the Overpass API returns for:

    [out:json][timeout:180];
    ( relation["route"="hiking"]({bbox}); );
    out body;
    >;
    out skel qt;

Drop-in replacement for fetch_hiking_routes(bbox) — build_points_from_relation
and everything downstream in run_ingestion.py needs no changes.

Install: pip install osmium
"""

import osmium


class _RelationPass(osmium.SimpleHandler):
    """Pass 1: find hiking route relations, note which ways they need."""
    def __init__(self):
        super().__init__()
        self.relations = []
        self.needed_way_ids = set()

    def relation(self, r):
        if r.tags.get("route") != "hiking":
            return
        members = []
        for m in r.members:
            if m.type == "w":
                self.needed_way_ids.add(m.ref)
            members.append({
                "type": {"n": "node", "w": "way", "r": "relation"}[m.type],
                "ref": m.ref,
                "role": m.role,
            })
        self.relations.append({
            "type": "relation",
            "id": r.id,
            "tags": dict(r.tags),
            "members": members,
        })


class _WayPass(osmium.SimpleHandler):
    """Pass 2: pull ordered node-id lists for the ways those relations need."""
    def __init__(self, needed_way_ids):
        super().__init__()
        self.needed_way_ids = needed_way_ids
        self.ways = []
        self.needed_node_ids = set()

    def way(self, w):
        if w.id not in self.needed_way_ids:
            return
        node_ids = [n.ref for n in w.nodes]
        self.needed_node_ids.update(node_ids)
        self.ways.append({
            "type": "way",
            "id": w.id,
            "tags": dict(w.tags),
            "nodes": node_ids,
        })


class _NodePass(osmium.SimpleHandler):
    """Pass 3: pull lat/lon for every node those ways reference."""
    def __init__(self, needed_node_ids):
        super().__init__()
        self.needed_node_ids = needed_node_ids
        self.nodes = []

    def node(self, n):
        if n.id not in self.needed_node_ids:
            return
        self.nodes.append({
            "type": "node",
            "id": n.id,
            "lat": n.location.lat,
            "lon": n.location.lon,
        })


def fetch_hiking_routes_from_pbf(pbf_path):
    """
    Drop-in replacement for fetch_hiking_routes(bbox).

    Returns {"elements": [...]} in the same shape Overpass returns, so
    run_ingestion.py, build_points_from_relation, and parse_hike need
    zero modification.
    """
    rel_pass = _RelationPass()
    rel_pass.apply_file(pbf_path)

    way_pass = _WayPass(rel_pass.needed_way_ids)
    way_pass.apply_file(pbf_path)

    node_pass = _NodePass(way_pass.needed_node_ids)
    node_pass.apply_file(pbf_path)

    elements = rel_pass.relations + way_pass.ways + node_pass.nodes
    return {"elements": elements}


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "rhode-island-260101.osm.pbf"
    data = fetch_hiking_routes_from_pbf(path)
    print(f"Extracted {len(data['elements'])} elements from {path}")
    rel_count = sum(1 for e in data["elements"] if e["type"] == "relation")
    print(f"  of which {rel_count} are hiking-route relations")