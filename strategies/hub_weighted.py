"""Hub-weighted strategy: keep only the most connected stops near the centroid."""
from __future__ import annotations

from api import Stop, nearby_stops

NAME = "hub_weighted"
DESCRIPTION = "Centroid pool filtered by transit-hub score (number of active product types)"


def _hub_score(stop: Stop) -> int:
    return sum(1 for v in stop.products.values() if v)


def get_candidates(
    starts: list[Stop], radius: int = 2000, results: int = 30, top_k: int = 20, **_
) -> list[Stop]:
    clat = sum(s.lat for s in starts) / len(starts)
    clon = sum(s.lon for s in starts) / len(starts)
    cands = nearby_stops(clat, clon, distance=radius, results=results)
    return sorted(cands, key=_hub_score, reverse=True)[:top_k]
