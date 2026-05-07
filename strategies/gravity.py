"""Gravity strategy: pull the search center toward transit-sparse start points."""
from __future__ import annotations

from api import Stop, nearby_stops

NAME = "gravity"
DESCRIPTION = "Inverse-density weighting — pulls center toward people in transit-sparse areas"


def get_candidates(starts: list[Stop], radius: int = 2000, results: int = 30, **_) -> list[Stop]:
    # Measure local stop density around each person (small fixed radius)
    densities: list[int] = []
    for start in starts:
        nearby = nearby_stops(start.lat, start.lon, distance=500, results=30)
        densities.append(len(nearby) or 1)

    # Weight: sparse areas (low count) get higher pull
    weights = [1.0 / d for d in densities]
    w_sum = sum(weights)
    glat = sum(w * s.lat for w, s in zip(weights, starts)) / w_sum
    glon = sum(w * s.lon for w, s in zip(weights, starts)) / w_sum
    return nearby_stops(glat, glon, distance=radius, results=results)
