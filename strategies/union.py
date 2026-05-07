"""Union strategy: merge per-person neighborhood lookups."""
from __future__ import annotations

from api import Stop, nearby_stops

NAME = "union"
DESCRIPTION = "Union of per-person neighborhoods — catches off-center hubs reachable by all"


def get_candidates(starts: list[Stop], radius: int = 2000, results: int = 30, **_) -> list[Stop]:
    seen: dict[str, Stop] = {}
    for start in starts:
        for stop in nearby_stops(start.lat, start.lon, distance=radius, results=results):
            seen[stop.id] = stop
    return list(seen.values())
