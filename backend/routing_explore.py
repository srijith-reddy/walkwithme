import osmnx as ox
import networkx as nx
from functools import lru_cache


# ============================================================
# 1. Load graph (cached)
# ============================================================
@lru_cache(maxsize=32)
def load_graph(lat: float, lon: float, dist: int = 2000):
    print(f"[EXPLORE] Loading graph around {lat},{lon}")
    G = ox.graph_from_point((lat, lon), dist=dist, network_type="walk")
    return G


# ============================================================
# 2. Explore scoring (pleasant, lively, pretty streets)
# ============================================================
def apply_explore_weights(G):
    """
    Assign "explore-friendly" weights to each edge.
    Lower weight = more desirable.
    """

    for u, v, k, d in G.edges(keys=True, data=True):

        base = d.get("length", 1.0)
        weight = base

        highway = d.get("highway", "")
        surface = d.get("surface", "")
        lit_val = d.get("lit", "")
        name = d.get("name", "").lower() if d.get("name") else ""
        amenity = d.get("amenity", "")

        # -----------------------------------------
        # 🌳 1. Pleasant paths (bonus)
        # -----------------------------------------
        if highway in ["path", "footway", "living_street"]:
            weight *= 0.7

        if "park" in name or "garden" in name:
            weight *= 0.6

        if "river" in name or "water" in name or "lake" in name:
            weight *= 0.55

        # -----------------------------------------
        # ☕ 2. Explore = lively streets
        # -----------------------------------------
        if amenity in ["cafe", "restaurant", "bar", "pub", "ice_cream"]:
            weight *= 0.7

        # -----------------------------------------
        # 🎨 3. Charming elements
        # -----------------------------------------
        if "mural" in name or "art" in name or "historic" in name:
            weight *= 0.75

        # -----------------------------------------
        # 🚫 4. Avoid boring or stressful zones
        # -----------------------------------------
        if highway in ["primary", "secondary", "trunk"]:
            weight *= 2.0

        if highway in ["service", "track"]:
            weight *= 2.3

        if surface in ["gravel", "dirt"]:
            weight *= 1.8

        # Dark streets = less “explore-friendly”
        if lit_val == "no":
            weight *= 1.5

        d["explore_weight"] = weight


# ============================================================
# 3. Main EXPLORE route function
# ============================================================
def get_explore_route(start, end):
    lat1, lon1 = start
    lat2, lon2 = end

    mid_lat = (lat1 + lat2) / 2
    mid_lon = (lon1 + lon2) / 2

    G = load_graph(mid_lat, mid_lon)

    # Assign explore weights
    apply_explore_weights(G)

    try:
        orig = ox.nearest_nodes(G, lon1, lat1)
        dest = ox.nearest_nodes(G, lon2, lat2)
    except Exception:
        return {"error": "Could not find map nodes"}

    try:
        route_nodes = nx.shortest_path(G, orig, dest, weight="explore_weight")
    except nx.NetworkXNoPath:
        return {"error": "No explore-friendly path found"}

    coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in route_nodes]

    return {
        "mode": "explore",
        "start": start,
        "end": end,
        "coordinates": coords
    }
