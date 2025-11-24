import osmnx as ox
from functools import lru_cache
from shapely.geometry import LineString, Point


# ------------------------------------------------------
# Cache trail graph to avoid multiple downloads
# ------------------------------------------------------
@lru_cache(maxsize=16)
def load_trail_graph(lat, lon, dist=4000):
    """
    Load OSM graph including hiking paths, footways, trails.
    """
    print(f"[TRAIL] Loading trail graph @ {lat},{lon} dist={dist}m")

    G = ox.graph_from_point(
        (lat, lon),
        dist=dist,
        network_type="walk",
        custom_filter='["highway"~"path|footway|track|bridleway"]'
    )
    return G


# ------------------------------------------------------
# Extract trail segments (LineString geometry)
# ------------------------------------------------------
def extract_trail_segments(G):
    trails = []

    for u, v, k, d in G.edges(keys=True, data=True):
        if "geometry" not in d:
            continue

        geom = d["geometry"]
        if not isinstance(geom, LineString):
            continue

        # Only keep paths
        hwy = d.get("highway", "")
        if hwy not in ["path", "footway", "track", "bridleway"]:
            continue

        # Package into "properties" for the scorer
        props = {
            "name": d.get("name", "Unnamed Trail"),
            "surface": d.get("surface", "unknown"),
            "highway": hwy,
        }

        trails.append({
            "geometry": geom,
            "properties": props,
            "length_m": d.get("length", 0)
        })

    return trails


# ------------------------------------------------------
# Find trails within radius of user
# ------------------------------------------------------
def find_nearby_trails(lat, lon, max_distance_m=1500):
    """
    For FastAPI /trails endpoint.
    Returns:
        list of trail dicts with geometry + properties
    """
    G = load_trail_graph(lat, lon)
    trails = extract_trail_segments(G)

    user_point = Point(lon, lat)
    result = []

    for t in trails:
        # Distance from user → start of trail segment
        first_coord = t["geometry"].coords[0]
        seg_point = Point(first_coord[0], first_coord[1])

        # Convert degrees → meters
        distance_m = user_point.distance(seg_point) * 111000  

        if distance_m <= max_distance_m:
            t["distance_from_user_m"] = round(distance_m, 2)
            result.append(t)

    return result
