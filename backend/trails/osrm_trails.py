# backend/trails/osrm_trails.py

# backend/trails/osrm_trails.py

import requests


def osrm_trail_route(start_lat, start_lon, end_lat, end_lon):
    """
    Optional: Uses OSRM public server to generate a walking route.
    Good for long trails and off-road routing.
    """

    # OSRM requires lon,lat order
    url = (
        "http://router.project-osrm.org/route/v1/foot/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}"
        "?overview=full&geometries=geojson"
    )

    try:
        res = requests.get(url, timeout=6).json()
    except Exception as e:
        return {"error": f"OSRM request failed: {e}"}

    # --------------------------------------
    # Validate OSRM response
    # --------------------------------------
    if "routes" not in res or len(res["routes"]) == 0:
        return {"error": "No OSRM routes found"}

    route = res["routes"][0]

    # Extract geometry
    try:
        coords = route["geometry"]["coordinates"]
        # Convert OSRM (lon, lat) → (lat, lon)
        route_latlon = [(lat, lon) for lon, lat in coords]
    except Exception:
        return {"error": "OSRM geometry parsing failed"}

    return {
        "distance_m": round(route.get("distance", 0), 2),
        "duration_s": round(route.get("duration", 0), 2),
        "coordinates": route_latlon
    }
