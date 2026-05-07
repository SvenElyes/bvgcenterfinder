"""Centroid strategy: arithmetic mean of start coordinates."""
from __future__ import annotations

from api import Stop, nearby_stops

NAME = "centroid"
DESCRIPTION = "Arithmetic mean of start coordinates — fast baseline, ignores transit topology"


def get_candidates(starts: list[Stop], radius: int = 2000, results: int = 30, **_) -> list[Stop]:
    clat = sum(s.lat for s in starts) / len(starts)
    clon = sum(s.lon for s in starts) / len(starts)
    return nearby_stops(clat, clon, distance=radius, results=results)
