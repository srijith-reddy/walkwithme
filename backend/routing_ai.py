import osmnx as ox
import networkx as nx
from datetime import datetime
import requests
import random

# ⭐ Import intelligent loaders from routing_shortest.py
from .routing_shortest import (
    smart_load_graph,
    load_graph_point,
    graph_is_empty
)


# ============================================================
# WEATHER (Open-Meteo – keyless)
# ============================================================
def get_weather(lat, lon):
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&current_weather=true"
        )
        j = requests.get(url, timeout=5).json()
        w = j["current_weather"]
        code = int(w["weathercode"])
        temp = float(w["temperature"])

        if code in [61, 63, 65]: return "rain"
        if code in [71, 73, 75]: return "snow"
        if temp > 30:           return "hot"
        if temp < 5:            return "cold"
        return "clear"

    except Exception:
        return "clear"


# ============================================================
# NIGHT CHECK
# ============================================================
def is_night(lat, lon):
    try:
        url = f"https://api.sunrise-sunset.org/json?lat={lat}&lng={lon}&formatted=0"
        data = requests.get(url, timeout=5).json()["results"]
        sunrise = datetime.fromisoformat(data["sunrise"])
        sunset  = datetime.fromisoformat(data["sunset"])
        now = datetime.utcnow()
        return not (sunrise <= now <= sunset)
    except Exception:
        return False


# ============================================================
# APPLY SAFE / SCENIC / EXPLORE RAW WEIGHTS
# ============================================================
def apply_all_weights(G):
    if graph_is_empty(G):
        return

    for _, _, _, d in G.edges(keys=True, data=True):
        base = d.get("length", 1)
        highway = d.get("highway", "")
        surface = d.get("surface", "")
        lit     = d.get("lit", "")
        name    = (d.get("name", "") or "").lower()
        amenity = d.get("amenity", "")

        # SAFE
        safe = base
        if highway in ["primary", "secondary"]: safe *= 2
        if d.get("sidewalk") == "no":           safe *= 3
        if lit == "no":                         safe *= 2
        d["safe_w"] = safe

        # SCENIC
        scenic = base
        if any(k in name for k in ["park", "garden"]): scenic *= 0.7
        if any(k in name for k in ["river", "lake", "water"]): scenic *= 0.6
        if surface in ["dirt", "gravel"]: scenic *= 1.3
        d["scenic_w"] = scenic

        # EXPLORE
        explore = base
        if highway in ["path", "footway", "living_street"]: explore *= 0.7
        if amenity in ["cafe", "restaurant", "bar", "ice_cream"]: explore *= 0.7
        d["explore_w"] = explore


# ============================================================
# AI WEIGHTS (weather + night)
# ============================================================
def get_ai_weights(lat, lon):
    w = get_weather(lat, lon)
    night = is_night(lat, lon)

    if night:      return dict(short=1.0, safe=3.0, scenic=0.4, explore=0.6)
    if w=="rain":  return dict(short=1.0, safe=2.0, scenic=0.2, explore=0.7)
    if w=="snow":  return dict(short=1.0, safe=2.5, scenic=0.4, explore=0.6)
    if w=="hot":   return dict(short=1.2, safe=1.0, scenic=1.0, explore=0.6)
    if w=="cold":  return dict(short=1.0, safe=1.7, scenic=1.0, explore=0.8)

    # perfect day
    return dict(short=0.6, safe=1.0, scenic=2.0, explore=1.5)


# ============================================================
# APPLY AI MIXED WEIGHT
# ============================================================
def apply_ai_combined_weight(G, W):
    if graph_is_empty(G):
        return

    for _, _, _, d in G.edges(keys=True, data=True):
        d["ai_weight"] = (
            W["short"]   * d.get("length", 1) +
            W["safe"]    * d.get("safe_w", 1) +
            W["scenic"]  * d.get("scenic_w", 1) +
            W["explore"] * d.get("explore_w", 1)
        )


# ============================================================
# AI BEST ROUTE (A → B)
# ============================================================
def get_ai_best_route(start, end):
    if start is None or end is None:
        return {"error": "Missing start or end."}

    # ⭐ FIX: use robust hybrid loader
    G = smart_load_graph(start, end)

    if graph_is_empty(G):
        return {"error": "Could not load walking network."}

    apply_all_weights(G)
    W = get_ai_weights(*start)
    apply_ai_combined_weight(G, W)

    try:
        orig = ox.nearest_nodes(G, start[1], start[0])
        dest = ox.nearest_nodes(G, end[1], end[0])
    except Exception:
        return {"error": "Could not snap to walking network."}

    try:
        route_nodes = nx.shortest_path(G, orig, dest, weight="ai_weight")
    except Exception:
        return {"error": "No AI route found."}

    coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in route_nodes]

    return {
        "mode": "ai_best",
        "start": start,
        "end": end,
        "weights": W,
        "coordinates": coords
    }


# ============================================================
# AI LOOP ROUTE (A → A)
# ============================================================
def get_ai_loop_route(start, duration_minutes=20):
    if start is None:
        return {"error": "Missing start coordinates."}

    lat, lon = start

    # ⭐ FIX: loop = local walking only
    G = load_graph_point(lat, lon, 3000)

    if graph_is_empty(G):
        return {"error": "Could not load walking network."}

    apply_all_weights(G)
    W = get_ai_weights(lat, lon)
    apply_ai_combined_weight(G, W)

    try:
        orig = ox.nearest_nodes(G, lon, lat)
    except Exception:
        return {"error": "Could not snap to walking network."}

    nodes = list(G.nodes())
    if not nodes:
        return {"error": "Empty walking graph."}

    mid = random.choice(nodes)

    try:
        out = nx.shortest_path(G, orig, mid, weight="ai_weight")
        back = nx.shortest_path(G, mid, orig, weight="ai_weight")
    except Exception:
        return {"error": "Loop route failed."}

    loop = out + back[::-1]
    coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in loop]

    return {
        "mode": "ai_loop",
        "start": start,
        "duration_minutes": duration_minutes,
        "weights": W,
        "coordinates": coords
    }
