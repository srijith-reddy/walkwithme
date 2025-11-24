# backend/routing_scenic.py

import osmnx as ox
import networkx as nx
from functools import lru_cache


# ============================================================
# CACHED GRAPH LOADER (same as other modules)
# ============================================================
@lru_cache(maxsize=32)
def load_graph(lat, lon, dist=2500):
    print(f"[SCENIC] Loading graph @ ({lat}, {lon}) radius={dist}m")
    return ox.graph_from_point((lat, lon), dist=dist, network_type="walk")


# ============================================================
# APPLY SCENIC WEIGHTS
# ============================================================
def apply_scenic_weights(G):
    """
    Scenic routing rewards parks, waterfront, greenery, and quiet areas.
    Penalizes traffic-heavy, industrial, or boring streets.
    """
    for u, v, k, d in G.edges(keys=True, data=True):

        # Base weight = distance
        weight = d.get("length", 1)

        highway = d.get("highway", "")
        surface = d.get("surface", "")
        landuse = d.get("landuse", "")
        natural = d.get("natural", "")
        leisure = d.get("leisure", "")

        # --------------------------------------------------------
        # 1. Positive scenic bonuses (REDUCE weight)
        # --------------------------------------------------------

        # Parks, gardens, green zones
        if landuse in ["grass", "meadow", "forest"]:
            weight *= 0.5     # very scenic

        if leisure in ["park", "garden", "nature_reserve"]:
            weight *= 0.4     # extremely scenic

        # Waterfront / riversides
        if natural in ["water", "wetland"]:
            weight *= 0.5

        # Footpaths in natural areas
        if highway in ["footway", "path"]:
            weight *= 0.6

        # Tree-lined streets (OSM tags sometimes include this)
        if "tree" in str(d):
            weight *= 0.7

        # --------------------------------------------------------
        # 2. Negative scenic penalties (INCREASE weight)
        # --------------------------------------------------------

        # Industrial area → avoid
        if landuse in ["industrial", "commercial"]:
            weight *= 2.0

        # Busy highways
        if highway in ["primary", "secondary", "tertiary"]:
            weight *= 2.0

        # Ugly/rough surfaces
        if surface in ["asphalt", "concrete"]:
            weight *= 1.3  # slightly penalize
        if surface in ["paving_stones"]:
            weight *= 1.1
        if surface in ["dirt", "gravel"]:
            weight *= 1.5  # less scenic typically

        d["scenic_weight"] = weight


# ============================================================
# MAIN SCENIC ROUTING FUNCTION
# ============================================================
def get_scenic_route(start, end):
    lat1, lon1 = start
    lat2, lon2 = end

    # Build a graph covering both
    mid_lat = (lat1 + lat2) / 2
    mid_lon = (lon1 + lon2) / 2
    G = load_graph(mid_lat, mid_lon)

    # Apply scenic weights
    apply_scenic_weights(G)

    # Locate nodes
    orig = ox.nearest_nodes(G, lon1, lat1)
    dest = ox.nearest_nodes(G, lon2, lat2)

    # Compute scenic path
    try:
        route_nodes = nx.shortest_path(G, orig, dest, weight="scenic_weight")
    except nx.NetworkXNoPath:
        return {"error": "No scenic path found"}

    # Convert to coordinates
    coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in route_nodes]

    return {
        "mode": "scenic",
        "start": start,
        "end": end,
        "coordinates": coords
    }
