"""Steiner strategy: iteratively shift the search center toward the best transit hub."""
from __future__ import annotations

import sys

from api import Stop, nearby_stops

NAME = "steiner"
DESCRIPTION = "Iterative center shift toward highest-hub stop — converges on transit topology"


def _hub_score(stop: Stop) -> int:
    return sum(1 for v in stop.products.values() if v)


def get_candidates(
    starts: list[Stop],
    radius: int = 2000,
    results: int = 30,
    iterations: int = 3,
    **_,
) -> list[Stop]:
    lat = sum(s.lat for s in starts) / len(starts)
    lon = sum(s.lon for s in starts) / len(starts)
    all_cands: dict[str, Stop] = {}
    for i in range(iterations):
        batch = nearby_stops(lat, lon, distance=radius, results=results)
        for c in batch:
            all_cands[c.id] = c
        best = max(batch, key=_hub_score, default=None)
        if best is None:
            break
        # Shift center 50% toward the best-connected hub
        new_lat = (lat + best.lat) / 2
        new_lon = (lon + best.lon) / 2
        print(
            f"  [steiner iter {i + 1}] shifted to {best.name} "
            f"(score {_hub_score(best)}, Δlat={new_lat - lat:+.5f})",
            file=sys.stderr,
        )
        lat, lon = new_lat, new_lon
    return list(all_cands.values())
