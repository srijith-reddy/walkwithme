# backend/routing.py

from .routing_shortest import get_shortest_route
from .routing_safe import get_safe_route
from .routing_scenic import get_scenic_route
from .routing_explore import get_explore_route
from .routing_ai import get_ai_best_route, get_ai_loop_route
from .routing_elevation import get_elevation_route


def get_route(start, end=None, mode="shortest", duration_minutes=20):
    """
    Route dispatcher.

    Modes:
        - shortest  : shortest walking path
        - safe      : day/night aware safe routing
        - scenic    : park/water/greenery routing
        - explore   : pleasant lively cozy streets
        - elevation : hill-friendly or hill-avoiding route
        - best      : AI combined safest + scenic + explore + short
        - loop      : AI loop walk (A → A, no destination)
    """

    # ==========================================
    # SHORTEST
    # ==========================================
    if mode == "shortest":
        return get_shortest_route(start, end)

    # ==========================================
    # SAFE
    # ==========================================
    elif mode == "safe":
        return get_safe_route(start, end, mode="auto")

    # ==========================================
    # SCENIC
    # ==========================================
    elif mode == "scenic":
        return get_scenic_route(start, end)

    # ==========================================
    # EXPLORE
    # ==========================================
    elif mode == "explore":
        return get_explore_route(start, end)

    # ==========================================
    # ELEVATION-AWARE ROUTE (NEW)
    # ==========================================
    elif mode == "elevation":
        return get_elevation_route(start, end)

    # ==========================================
    # AI BEST ROUTE (A → B)
    # ==========================================
    elif mode == "best":
        return get_ai_best_route(start, end)

    # ==========================================
    # AI LOOP ROUTE (A → A)
    # ==========================================
    elif mode == "loop":
        return get_ai_loop_route(start, duration_minutes)

    # ==========================================
    # INVALID MODE
    # ==========================================
    else:
        return {
            "error": f"Invalid mode: {mode}. Choose from "
                     f"shortest, safe, scenic, explore, elevation, best, loop."
        }
