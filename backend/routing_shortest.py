# backend/routing_shortest.py

import osmnx as ox
import networkx as nx
from haversine import haversine
from functools import lru_cache


# ============================================================
# 0. Safety Utils
# ============================================================
def graph_is_empty(G):
    return (G is None) or (len(G.nodes) == 0) or (len(G.edges) == 0)


# ============================================================
# Bounding Box Calculation
# ============================================================
def compute_bbox(lat1, lon1, lat2, lon2, buffer_m=2500):
    lat_buffer = buffer_m / 111111
    lon_buffer = buffer_m / 85000

    north = max(lat1, lat2) + lat_buffer
    south = min(lat1, lat2) - lat_buffer
    east  = max(lon1, lon2) + lon_buffer
    west  = min(lon1, lon2) - lon_buffer

    return north, south, east, west


# ============================================================
# Cached Loaders
# ============================================================
@lru_cache(maxsize=32)
def load_graph_point(center_lat, center_lon, radius):
    print(f"[LOADER] Point-radius loader: center=({center_lat}, {center_lon}), r={radius}m")
    try:
        return ox.graph_from_point((center_lat, center_lon),
                                   dist=radius,
                                   network_type="walk",
                                   simplify=False)
    except Exception:
        return None


@lru_cache(maxsize=32)
def load_graph_bbox(n, s, e, w):
    print(f"[LOADER] Bounding-box loader: N={n}, S={s}, E={e}, W={w}")
    try:
        return ox.graph_from_bbox(north=n, south=s, east=e, west=w,
                                  network_type="walk",
                                  simplify=False)
    except Exception:
        return None


# ============================================================
# Hybrid Graph Loader
# ============================================================
def smart_load_graph(start, end):
    lat1, lon1 = start
    lat2, lon2 = end

    dist_m = haversine(start, end) * 1000

    # SHORT DISTANCES (< 5 km)
    if dist_m < 5000:
        radius = max(3000, dist_m/2 + 3000)
        mid_lat = (lat1 + lat2) / 2
        mid_lon = (lon1 + lon2) / 2
        G = load_graph_point(mid_lat, mid_lon, radius)
        if not graph_is_empty(G):
            return G

    # LONG DISTANCES (>= 5 km)
    n, s, e, w = compute_bbox(lat1, lon1, lat2, lon2, buffer_m=3000)
    G = load_graph_bbox(n, s, e, w)

    return G


# ============================================================
# Shortest Route
# ============================================================
def get_shortest_route(start, end):
    lat1, lon1 = start
    lat2, lon2 = end

    # --- Load graph ---
    G = smart_load_graph(start, end)

    if graph_is_empty(G):
        return {
            "error": "Walking network not available for this area.",
            "suggest": [
                "Try a closer start/end point.",
                "Try transit (PATH, subway, ferry).",
                "Try cycling mode."
            ]
        }

    # --- Nearest nodes ---
    try:
        orig = ox.nearest_nodes(G, lon1, lat1)
        dest = ox.nearest_nodes(G, lon2, lat2)
    except Exception as e:
        return {
            "error": f"Could not find walking nodes: {e}",
            "suggest": [
                "Try tapping a different spot.",
                "Walking network may not exist here."
            ]
        }

    # --- Compute route ---
    try:
        route_nodes = nx.shortest_path(G, orig, dest, weight="length")
    except nx.NetworkXNoPath:
        return {
            "error": "No walking path available.",
            "suggest": [
                "This route may cross water or highways.",
                "For NYC ↔ NJ: Use PATH train or Ferry.",
                "Choose a route near a walkable bridge."
            ]
        }

    # --- Convert nodes to coordinates ---
    coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in route_nodes]

    return {
        "mode": "shortest",
        "start": start,
        "end": end,
        "distance_m": compute_route_length(G, route_nodes),
        "coordinates": coords
    }


# ============================================================
# Distance Calculation
# ============================================================
def compute_route_length(G, route_nodes):
    dist = 0.0

    for i in range(len(route_nodes) - 1):
        u = route_nodes[i]
        v = route_nodes[i + 1]

        try:
            edge = G[u][v][0]
        except Exception:
            k = list(G[u][v].keys())[0]
            edge = G[u][v][k]

        dist += edge.get("length", 0)

    return round(dist, 2)
