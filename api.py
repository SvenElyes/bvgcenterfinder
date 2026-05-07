"""Shared BVG API utilities: data types, HTTP helpers, scoring, output."""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime

import requests

API = "https://v6.bvg.transport.rest"
TIMEOUT = 15


@dataclass
class Stop:
    id: str
    name: str
    lat: float
    lon: float
    products: dict = field(default_factory=dict)


@dataclass
class Score:
    candidate: Stop
    per_person_min: list[float]
    max_min: float
    sum_min: float


def _get(path: str, params: dict) -> object:
    r = requests.get(f"{API}{path}", params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def resolve_stop(query: str) -> Stop:
    results = _get("/locations", {"query": query, "results": 1, "poi": "false", "addresses": "true"})
    if not results:
        raise ValueError(f"No result for: {query!r}")
    hit = results[0]
    if hit.get("type") == "stop":
        loc = hit["location"]
        return Stop(
            id=hit["id"], name=hit["name"],
            lat=loc["latitude"], lon=loc["longitude"],
            products=hit.get("products") or {},
        )
    lat, lon = hit["latitude"], hit["longitude"]
    nearby = _get("/locations/nearby", {"latitude": lat, "longitude": lon, "results": 1})
    nearby = [s for s in nearby if s.get("type") == "stop"]
    if not nearby:
        raise ValueError(f"No nearby stop for address: {query!r}")
    s = nearby[0]
    loc = s["location"]
    return Stop(
        id=s["id"], name=s["name"],
        lat=loc["latitude"], lon=loc["longitude"],
        products=s.get("products") or {},
    )


def nearby_stops(lat: float, lon: float, distance: int = 2000, results: int = 30) -> list[Stop]:
    data = _get(
        "/locations/nearby",
        {"latitude": lat, "longitude": lon, "distance": distance, "results": results},
    )
    out: list[Stop] = []
    for s in data:
        if s.get("type") != "stop":
            continue
        loc = s.get("location") or {}
        if "latitude" not in loc or "longitude" not in loc:
            continue
        out.append(Stop(
            id=s["id"], name=s["name"],
            lat=loc["latitude"], lon=loc["longitude"],
            products=s.get("products") or {},
        ))
    return out


def journey_minutes(from_id: str, to_id: str, when: str | None = None) -> float | None:
    params: dict = {"from": from_id, "to": to_id, "results": 1, "stopovers": "false"}
    if when:
        params["departure"] = when
    try:
        data = _get("/journeys", params)
    except requests.HTTPError:
        return None
    journeys = data.get("journeys") if isinstance(data, dict) else None
    if not journeys:
        return None
    legs = journeys[0].get("legs") or []
    if not legs:
        return None
    dep = legs[0].get("plannedDeparture") or legs[0].get("departure")
    arr = legs[-1].get("plannedArrival") or legs[-1].get("arrival")
    if not dep or not arr:
        return None
    d = datetime.fromisoformat(dep)
    a = datetime.fromisoformat(arr)
    return (a - d).total_seconds() / 60.0


def score_candidates(
    starts: list[Stop], candidates: list[Stop], when: str | None, workers: int = 12
) -> list[Score]:
    if not candidates:
        return []
    tasks = [(ci, pi) for ci in range(len(candidates)) for pi in range(len(starts))]
    matrix: list[list[float | None]] = [[None] * len(starts) for _ in candidates]

    def work(ci: int, pi: int) -> tuple[int, int, float | None]:
        return ci, pi, journey_minutes(starts[pi].id, candidates[ci].id, when)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(work, ci, pi) for ci, pi in tasks]
        for f in as_completed(futs):
            ci, pi, m = f.result()
            matrix[ci][pi] = m

    scores: list[Score] = []
    for ci, cand in enumerate(candidates):
        row = matrix[ci]
        if any(v is None for v in row):
            continue
        per = [float(v) for v in row]  # type: ignore[arg-type]
        scores.append(
            Score(candidate=cand, per_person_min=per, max_min=max(per), sum_min=sum(per))
        )
    return sorted(scores, key=lambda s: (s.max_min, s.sum_min))


def print_table(top: list[Score], starts: list[Stop]) -> None:
    name_w = max((len(s.candidate.name) for s in top), default=10)
    name_w = min(max(name_w, 20), 40)
    headers = ["#", "stop".ljust(name_w), "  max", "  sum"] + [
        f"  P{i+1}" for i in range(len(starts))
    ]
    print(" ".join(headers))
    print("-" * (sum(len(h) for h in headers) + len(headers)))
    for rank, s in enumerate(top, 1):
        cells = [
            str(rank),
            s.candidate.name.ljust(name_w)[:name_w],
            f"{s.max_min:5.1f}",
            f"{s.sum_min:5.1f}",
        ] + [f"{m:5.1f}" for m in s.per_person_min]
        print(" ".join(cells))
    print()
    print("Legend:")
    for i, st in enumerate(starts, 1):
        print(f"  P{i} = {st.name} ({st.id})")
