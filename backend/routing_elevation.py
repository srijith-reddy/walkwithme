# backend/routing/routing_elevation.py

import osmnx as ox
import networkx as nx
from functools import lru_cache
import requests


# -------------------------------------------------------------
# 1. Cached graph loader
# -------------------------------------------------------------
@lru_cache(maxsize=16)
def load_graph(lat, lon, dist=2500):
    """
    Load a walking graph around a midpoint.
    Cached so multiple calls don’t rebuild the map.
    """
    return ox.graph_from_point((lat, lon), dist=dist, network_type="walk")


# -------------------------------------------------------------
# 2. Elevation for a single point
# -------------------------------------------------------------
def get_node_elevation(lat, lon):
    """
    Fetch elevation from OpenElevation API.
    """
    try:
        url = f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}"
        data = requests.get(url, timeout=3).json()
        return data["results"][0]["elevation"]
    except:
        return 0  # fallback


# -------------------------------------------------------------
# 3. Attach elevation to each graph node
# -------------------------------------------------------------
def add_elevation_to_graph(G):
    for node, data in G.nodes(data=True):
        lat = data["y"]
        lon = data["x"]
        elev = get_node_elevation(lat, lon)
        data["elevation"] = elev


# -------------------------------------------------------------
# 4. Apply slope-aware weights for each edge
# -------------------------------------------------------------
def apply_slope_weights(G):
    """
    Compute elevation-aware weights:
    - Uphill is heavily penalized
    - Downhill slightly penalized
    """

    for u, v, k, d in G.edges(keys=True, data=True):

        dist = d.get("length", 1)

        elev_u = G.nodes[u].get("elevation", 0)
        elev_v = G.nodes[v].get("elevation", 0)

        rise = elev_v - elev_u
        slope = rise / dist if dist > 0 else 0

        if slope > 0:
            # Uphill penalty
            d["slope_weight"] = dist * (1 + slope * 15)
        else:
            # Slight downhill penalty
            d["slope_weight"] = dist * (1 + abs(slope) * 5)


# -------------------------------------------------------------
# 5. MAIN: Elevation-aware routing
# -------------------------------------------------------------
def get_elevation_route(start, end):
    """
    start = (lat1, lon1)
    end   = (lat2, lon2)
    """
    lat1, lon1 = start
    lat2, lon2 = end

    mid_lat = (lat1 + lat2) / 2
    mid_lon = (lon1 + lon2) / 2

    # Load walking graph
    G = load_graph(mid_lat, mid_lon)

    # Add elevation metadata
    add_elevation_to_graph(G)
    apply_slope_weights(G)

    # Nearest map nodes
    orig = ox.nearest_nodes(G, lon1, lat1)
    dest = ox.nearest_nodes(G, lon2, lat2)

    try:
        node_path = nx.shortest_path(G, orig, dest, weight="slope_weight")
    except nx.NetworkXNoPath:
        return {"error": "No hill-friendly route found"}

    coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in node_path]

    return {
        "mode": "elevation",
        "start": start,
        "end": end,
        "coordinates": coords
    }
