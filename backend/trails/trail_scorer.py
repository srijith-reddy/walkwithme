# backend/trails/trail_scorer.py

import numpy as np
from shapely.geometry import LineString
import requests


# ---------------------------------------------------
# 1. Optional elevation API (OpenElevation)
# ---------------------------------------------------
def get_elevation(lat, lon):
    try:
        url = f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}"
        data = requests.get(url).json()
        return data["results"][0]["elevation"]
    except:
        return None


# ---------------------------------------------------
# 2. Compute elevation gain along a Linestring
# ---------------------------------------------------
def compute_elevation_gain(geometry: LineString):
    coords = list(geometry.coords)

    elevations = []
    for lat, lon in coords:
        e = get_elevation(lat, lon)
        elevations.append(e if e is not None else 0)

    gain = 0
    for i in range(1, len(elevations)):
        diff = elevations[i] - elevations[i - 1]
        if diff > 0:
            gain += diff

    return round(gain, 2)


# ---------------------------------------------------
# 3. Difficulty scoring
# ---------------------------------------------------
def score_difficulty(length_m, elevation_gain):
    """
    Naismith-like rule:
    - 1 point per km
    - +1 point per 100m elevation
    """
    difficulty = (length_m / 1000) + (elevation_gain / 100)

    if difficulty < 2:
        level = "Easy"
    elif difficulty < 5:
        level = "Moderate"
    else:
        level = "Hard"

    return level, round(difficulty, 2)


# ---------------------------------------------------
# 4. Scenic scoring
# ---------------------------------------------------
def score_scenic(trail_props):
    scenic = 0

    name = trail_props.get("name", "").lower()
    surface = trail_props.get("surface", "")

    if "park" in name or "lake" in name or "river" in name:
        scenic += 2
    if surface in ["dirt", "gravel", "ground"]:
        scenic += 1
    if surface in ["paved"]:
        scenic -= 1

    return scenic


# ---------------------------------------------------
# 5. Safety scoring
# ---------------------------------------------------
def score_safety(trail_props):
    safety = 0

    surface = trail_props.get("surface", "")

    if surface in ["dirt", "ground"]:
        safety += 1
    if surface == "paved":
        safety += 2
    if surface == "rocky":
        safety -= 1

    return safety


# ---------------------------------------------------
# 6. MASTER FUNCTION → Used by FastAPI
# ---------------------------------------------------
def score_trails(trails):
    """
    trails = list of dicts from find_trails_nearby()
    Each dict must have:
        - 'geometry'
        - 'properties'
        - 'length_m'
    """

    scored = []

    for t in trails:
        geom = t["geometry"]
        props = t["properties"]
        length = t["length_m"]

        # Compute elevation gain
        elevation_gain = compute_elevation_gain(geom)

        # Difficulty
        level, difficulty_score = score_difficulty(length, elevation_gain)

        # Scenic
        scenic_score = score_scenic(props)

        # Safety
        safety_score = score_safety(props)

        scored.append({
            "name": props.get("name", "Unnamed Trail"),
            "length_m": round(length, 2),
            "elevation_gain_m": elevation_gain,
            "difficulty_level": level,
            "difficulty_score": difficulty_score,
            "scenic_score": scenic_score,
            "safety_score": safety_score,
            "geometry_coords": list(geom.coords)
        })

    # Sort by scenic + difficulty (best → top)
    scored.sort(key=lambda x: (x["difficulty_score"], -x["scenic_score"]))

    return scored
