# backend/elevation/elevation.py

import requests
import numpy as np


# ============================================================
# 1. Batch elevation fetching (100 coords per request)
# ============================================================
def fetch_batch_elevation(coords):
    """
    coords = [(lat, lon), ...]
    Returns list of elevations (meters).
    Uses OpenElevation API batch endpoint.
    """

    if not coords:
        return []

    # Build the batch string: lat1,lon1|lat2,lon2|...
    locations_param = "|".join([f"{lat},{lon}" for lat, lon in coords])
    url = f"https://api.open-elevation.com/api/v1/lookup?locations={locations_param}"

    try:
        res = requests.get(url, timeout=4).json()
        vals = [item["elevation"] for item in res["results"]]
        return vals
    except Exception:
        # Fallback if API fails
        return [0] * len(coords)


# ============================================================
# 2. Main elevation profile (route → elevation list)
# ============================================================
def get_elevation_profile(coords):
    """
    coords: list[(lat, lon)]
    Batch fetches elevation in chunks of 100.
    """

    batch_size = 100
    elevations = []

    for i in range(0, len(coords), batch_size):
        chunk = coords[i:i + batch_size]
        batch_elev = fetch_batch_elevation(chunk)
        elevations.extend(batch_elev)

    # Replace None with 0
    elevations = [e if e is not None else 0 for e in elevations]

    # Slight smoothing to reduce noise
    return smooth_elevation(elevations)


# ============================================================
# 3. Smooth elevation series (reduces noise)
# ============================================================
def smooth_elevation(elev):
    """
    Apply simple moving average smoothing.
    Makes slopes MUCH more stable.
    """
    elev = np.array(elev, dtype=float)
    kernel = np.array([0.25, 0.5, 0.25])  # smooth but retains shape
    smoothed = np.convolve(elev, kernel, mode="same")
    return smoothed.tolist()


# ============================================================
# 4. Compute elevation gain & loss
# ============================================================
def compute_gain_loss(elevations):
    gain = 0
    loss = 0

    for i in range(1, len(elevations)):
        diff = elevations[i] - elevations[i - 1]
        if diff > 0:
            gain += diff
        else:
            loss += abs(diff)

    return round(gain, 2), round(loss, 2)


# ============================================================
# 5. Compute slopes (grade %) using haversine distance
# ============================================================
def compute_slopes(coords, elevations):

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371000
        p1 = np.radians(lat1)
        p2 = np.radians(lat2)
        dp = np.radians(lat2 - lat1)
        dl = np.radians(lon2 - lon1)

        a = np.sin(dp/2)**2 + np.cos(p1) * np.cos(p2) * np.sin(dl/2)**2
        return 2 * R * np.arcsin(np.sqrt(a))

    slopes = []
    for i in range(1, len(coords)):
        lat1, lon1 = coords[i - 1]
        lat2, lon2 = coords[i]

        dist = haversine(lat1, lon1, lat2, lon2)
        if dist < 1:
            slopes.append(0)
            continue

        elev_diff = elevations[i] - elevations[i - 1]
        slope = (elev_diff / dist) * 100
        slopes.append(round(slope, 3))

    return slopes


# ============================================================
# 6. Difficulty classification
# ============================================================
def classify_difficulty(gain_m, max_slope):
    if gain_m < 50 and max_slope < 6:
        return "Easy"
    if gain_m < 150 and max_slope < 12:
        return "Moderate"
    if gain_m < 300 and max_slope < 18:
        return "Hard"
    return "Very Hard"


# ============================================================
# 7. Full pipeline: analyze elevation profile
# ============================================================
def analyze_route_elevation(coords):
    """
    coords: [(lat, lon)]
    Returns: gain, loss, slopes, difficulty, etc.
    """

    if not coords:
        return {
            "elevations": [],
            "elevation_gain_m": 0,
            "elevation_loss_m": 0,
            "slopes": [],
            "max_slope_percent": 0,
            "difficulty": "Easy"
        }

    elevations = get_elevation_profile(coords)
    gain, loss = compute_gain_loss(elevations)
    slopes = compute_slopes(coords, elevations)
    max_slope = max(slopes) if slopes else 0
    difficulty = classify_difficulty(gain, max_slope)

    return {
        "elevations": elevations,
        "elevation_gain_m": gain,
        "elevation_loss_m": loss,
        "slopes": slopes,
        "max_slope_percent": max_slope,
        "difficulty": difficulty
    }
