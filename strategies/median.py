"""Median strategy: geographic median via the Weiszfeld algorithm."""
from __future__ import annotations

import math

from api import Stop, nearby_stops

NAME = "median"
DESCRIPTION = "Geographic median (Weiszfeld) — outlier-robust; resists one person being far away"


def get_candidates(starts: list[Stop], radius: int = 2000, results: int = 30, **_) -> list[Stop]:
    lat = sum(s.lat for s in starts) / len(starts)
    lon = sum(s.lon for s in starts) / len(starts)
    for _ in range(200):
        dists = [math.hypot(s.lat - lat, s.lon - lon) for s in starts]
        weights = [1.0 / max(d, 1e-10) for d in dists]
        w_sum = sum(weights)
        new_lat = sum(w * s.lat for w, s in zip(weights, starts)) / w_sum
        new_lon = sum(w * s.lon for w, s in zip(weights, starts)) / w_sum
        if abs(new_lat - lat) < 1e-9 and abs(new_lon - lon) < 1e-9:
            break
        lat, lon = new_lat, new_lon
    return nearby_stops(lat, lon, distance=radius, results=results)
