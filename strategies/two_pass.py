"""Two-pass strategy: large union pool pre-filtered by hub score before journey scoring."""
from __future__ import annotations

from api import Stop, nearby_stops

NAME = "two_pass"
DESCRIPTION = "Large union pool pre-filtered by hub score — combines coverage of union with speed of hub_weighted"


def _hub_score(stop: Stop) -> int:
    return sum(1 for v in stop.products.values() if v)


def get_candidates(
    starts: list[Stop],
    radius: int = 2000,
    results: int = 30,
    top_k: int = 30,
    **_,
) -> list[Stop]:
    seen: dict[str, Stop] = {}

    # Pass 1: wide centroid pool
    clat = sum(s.lat for s in starts) / len(starts)
    clon = sum(s.lon for s in starts) / len(starts)
    for stop in nearby_stops(clat, clon, distance=int(radius * 1.5), results=results):
        seen[stop.id] = stop

    # Pass 1b: tight per-person pools
    for start in starts:
        for stop in nearby_stops(start.lat, start.lon, distance=radius // 2, results=20):
            seen[stop.id] = stop

    # Pass 2: keep only the top-K most connected hubs
    return sorted(seen.values(), key=_hub_score, reverse=True)[:top_k]
