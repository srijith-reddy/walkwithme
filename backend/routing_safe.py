# backend/routing_safe.py

import osmnx as ox
import networkx as nx
from functools import lru_cache
from datetime import datetime
import requests


# ========================================================
# 1. Load walking graph (cached)
# ========================================================
@lru_cache(maxsize=32)
def load_graph(lat: float, lon: float, dist: int = 2000):
    print(f"Loading OSM graph @ {lat}, {lon} radius={dist}m")
    G = ox.graph_from_point((lat, lon), dist=dist, network_type="walk")
    return G


# ========================================================
# 2. Sun data for automatic mode
# ========================================================
def is_night(lat, lon):
    """
    Uses sunrise/sunset API to determine if current time = night.
    """
    try:
        url = f"https://api.sunrise-sunset.org/json?lat={lat}&lng={lon}&formatted=0"
        data = requests.get(url).json()["results"]
        sunrise = datetime.fromisoformat(data["sunrise"])
        sunset = datetime.fromisoformat(data["sunset"])
        now = datetime.utcnow()
        return not (sunrise <= now <= sunset)
    except:
        # If API fails → assume daytime
        return False


# ========================================================
# 3. Apply DAY safety weights
# ========================================================
def apply_day_safety_weights(G):
    for u, v, k, d in G.edges(keys=True, data=True):
        weight = d.get("length", 1)

        # Major road types – less safe
        if d.get("highway") in ["primary", "secondary"]:
            weight *= 2.0

        # No sidewalk is dangerous
        if d.get("sidewalk") == "no":
            weight *= 2.5

        # Dirt/gravel = low visibility = slightly unsafe
        if d.get("surface") in ["dirt", "gravel"]:
            weight *= 1.5

        d["day_safe_weight"] = weight


# ========================================================
# 4. Apply NIGHT safety weights (stricter)
# ========================================================
def apply_night_safety_weights(G):
    for u, v, k, d in G.edges(keys=True, data=True):
        weight = d.get("length", 1)

        # No lighting at night = big penalty
        if d.get("lit") == "no":
            weight *= 4.0

        # No sidewalk at night = extremely unsafe
        if d.get("sidewalk") == "no":
            weight *= 5.0

        # Avoid parks after dark
        if d.get("highway") == "path":
            weight *= 3.5

        # Avoid alleys/tracks
        if d.get("highway") in ["service", "track"]:
            weight *= 3.0

        # Fast roads = unsafe at night
        if d.get("highway") in ["primary", "secondary"]:
            weight *= 4.0

        d["night_safe_weight"] = weight


# ========================================================
# 5. SAFE ROUTING MAIN FUNCTION
# ========================================================
def get_safe_route(start, end, mode="auto"):
    lat1, lon1 = start
    lat2, lon2 = end

    # Build a graph covering both start & end
    mid_lat = (lat1 + lat2) / 2
    mid_lon = (lon1 + lon2) / 2
    G = load_graph(mid_lat, mid_lon)

    # Determine actual mode
    if mode == "auto":
        mode = "night" if is_night(lat1, lon1) else "day"

    # Apply safety weights
    if mode == "day":
        apply_day_safety_weights(G)
        weight_key = "day_safe_weight"
    elif mode == "night":
        apply_night_safety_weights(G)
        weight_key = "night_safe_weight"

    # Get graph nodes
    orig = ox.nearest_nodes(G, lon1, lat1)
    dest = ox.nearest_nodes(G, lon2, lat2)

    # Compute route
    try:
        route_nodes = nx.shortest_path(G, orig, dest, weight=weight_key)
    except nx.NetworkXNoPath:
        return {"error": "No safe path found"}

    # Convert to coordinates
    coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in route_nodes]

    return {
        "mode": mode,
        "start": start,
        "end": end,
        "coordinates": coords
    }
