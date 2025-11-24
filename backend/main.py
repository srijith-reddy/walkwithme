from fastapi import FastAPI, HTTPException, Query, Request
import requests
import rapidfuzz
import math
# Routing engine
from backend.routing import get_route

# GPX export
from backend.gpx.export_gpx import gpx_response

# Trails
from backend.trails.find_trails import find_nearby_trails
from backend.trails.trail_scorer import score_trails
from backend.trails.osrm_trails import osrm_trail_route

# Elevation analysis
from backend.elevation import analyze_route_elevation

# Geocoding utils
from backend.utils.geo import geocode, reverse_geocode, parse_location
from fastapi.middleware.cors import CORSMiddleware

# =============================================================
# FASTAPI APP
# =============================================================
app = FastAPI(title="Walk With Me API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all local dev frontends
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message": "Walk With Me is running 🚶‍♂️"}


HEADERS = {"User-Agent": "WalkWithMe/1.0 (srijith-github)"}


# =============================================================
# Helper: IP → approximate location
# =============================================================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def ip_bias(request: Request):
    try:
        ip = request.headers.get("x-forwarded-for") or request.client.host
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=2).json()
        return float(r.get("latitude")), float(r.get("longitude"))
    except:
        return None, None


# =============================================================
# /autocomplete — Google Maps–style smart ranking
# =============================================================
@app.get("/autocomplete")
def autocomplete(
    request: Request,
    q: str = Query(..., min_length=1),
    user_lat: float | None = None,
    user_lon: float | None = None,
    limit: int = 7
):

    q = q.strip()

    # -----------------------------------------
    # 1) Determine user anchor point (GPS > IP)
    # -----------------------------------------
    if user_lat is None or user_lon is None:
        user_lat, user_lon = ip_bias(request)

    # If still missing, no geo bias available
    geo_bias_enabled = (user_lat is not None and user_lon is not None)

    # -----------------------------------------
    # 2) Photon + Nominatim Fetch
    # -----------------------------------------
    photon_results = []
    nominatim_results = []

    # Photon
    try:
        params = {"q": q, "limit": limit}
        if geo_bias_enabled:
            params["lat"] = user_lat
            params["lon"] = user_lon

        r = requests.get("https://photon.komoot.io/api/", params=params, timeout=4).json()
        for f in r.get("features", []):
            props = f["properties"]
            label = ", ".join(
                x for x in [
                    props.get("name"),
                    props.get("street"),
                    props.get("city"),
                    props.get("state"),
                    props.get("country")
                ] if x
            )
            lat = f["geometry"]["coordinates"][1]
            lon = f["geometry"]["coordinates"][0]

            photon_results.append({
                "label": label,
                "lat": lat,
                "lon": lon,
                "source": "photon"
            })
    except:
        pass

    # Nominatim Fallback
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "json", "limit": limit, "addressdetails": 1},
            headers={"User-Agent": "WalkWithMe/1.0 (github:srijith)"},
            timeout=4
        ).json()
        for item in r:
            nominatim_results.append({
                "label": item["display_name"],
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
                "source": "nominatim"
            })
    except:
        pass

    # -----------------------------------------
    # 3) Merge + Score + Dynamic Geographic Filter
    # -----------------------------------------
    all_results = photon_results + nominatim_results

    filtered = []

    for o in all_results:
        score = rapidfuzz.fuzz.ratio(q.lower(), o["label"].lower())

        # Geo bias scoring
        if geo_bias_enabled:
            dist = haversine(user_lat, user_lon, o["lat"], o["lon"])
            o["dist_km"] = dist

            # If very far (> 50 km), reject unless very high text match
            if dist > 50 and score < 85:
                continue

            # If < 10 km, boost heavily
            if dist < 10:
                score += 30

            # Add proximity inverse score
            score += max(0, 20 - dist)

        # Photon business priority
        if o["source"] == "photon":
            score += 10

        o["score"] = score
        filtered.append(o)

    # Final ordering
    filtered.sort(key=lambda x: x["score"], reverse=True)

    return [
        {"label": o["label"], "lat": o["lat"], "lon": o["lon"]}
        for o in filtered[:limit]
    ]


# =============================================================
# /route — main routing engine
# =============================================================
@app.get("/route")
def route(
    start: str,
    end: str = None,
    mode: str = "shortest",
    duration: int = 20
):

    lat1, lon1 = parse_location(start)
    end_tuple = None

    if end:
        lat2, lon2 = parse_location(end)
        end_tuple = (lat2, lon2)

    valid_modes = {
        "shortest", "safe", "scenic",
        "explore", "elevation", "best", "loop"
    }

    if mode not in valid_modes:
        raise HTTPException(400, f"Invalid mode '{mode}'")

    try:
        result = get_route((lat1, lon1), end_tuple, mode, duration)
    except Exception as e:
        raise HTTPException(500, f"Routing failed: {e}")

    if not isinstance(result, dict) or "coordinates" not in result:
        raise HTTPException(404, "Route not found")

    result["elevation"] = analyze_route_elevation(result["coordinates"])
    return result


# =============================================================
# /trails — nearby hiking trails
# =============================================================
@app.get("/trails")
def trails(start: str, radius: int = 2000, limit: int = 5):

    lat, lon = parse_location(start)

    raw = find_nearby_trails(lat, lon, radius)
    if not raw:
        raise HTTPException(404, "No trails found nearby")

    scored = score_trails(raw)
    return scored[:limit]


# =============================================================
# /trail_route — OSRM trail routing
# =============================================================
@app.get("/trail_route")
def trail_route(start: str, end: str):

    lat1, lon1 = parse_location(start)
    lat2, lon2 = parse_location(end)

    result = osrm_trail_route(lat1, lon1, lat2, lon2)

    if "error" in result:
        raise HTTPException(500, result["error"])

    return result


# =============================================================
# /reverse_geocode
# =============================================================
@app.get("/reverse_geocode")
def reverse_geocode_endpoint(coords: str):

    try:
        lat, lon = map(float, coords.split(","))
    except:
        raise HTTPException(400, "Invalid coordinate format. Use 'lat,lon'.")

    address = reverse_geocode(lat, lon)
    return {"address": address}


# =============================================================
# /export_gpx
# =============================================================
@app.get("/export_gpx")
def export_gpx(start: str, end: str, mode: str = "shortest"):

    lat1, lon1 = parse_location(start)
    lat2, lon2 = parse_location(end)

    result = get_route((lat1, lon1), (lat2, lon2), mode)

    if "error" in result:
        raise HTTPException(404, result["error"])

    return gpx_response(result["coordinates"])
