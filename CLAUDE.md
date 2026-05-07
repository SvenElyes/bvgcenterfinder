# BVG Meeting-Point Finder

## Goal
Given **n** people (small, e.g. 2–6) starting at different Berlin public-transit stops, find the **best BVG stop to meet at** — i.e. a stop that minimises travel pain across the group. Uses the public [`v6.bvg.transport.rest`](https://v6.bvg.transport.rest) REST API as the "existing dependency" (no wrapper library; plain HTTP).

## Core algorithm (v1)
1. **Resolve inputs** → each person gives a free-text start (e.g. `"Mehringdamm"`). We call `GET /locations?query=…&poi=false&addresses=false&results=1` to get a stop ID + lat/lon.
2. **Generate candidate meeting stops.** Compute a rough geographic centroid of the n start stops, then call `GET /stops/nearby?latitude=…&longitude=…&distance=2000&results=30` to get ~30 candidate stops around the middle. (Fast, no manual list needed.)
3. **Score each candidate.** For each candidate `C`, for each person `P_i`, call `GET /journeys?from=P_i&to=C&results=1&departure=<now>` and read the journey duration (`arrival - departure` of the first/only journey). That gives a matrix `travel_time[i][C]`.
4. **Pick the winner.** Default objective: **minimise the maximum travel time** across the group (the "fairest" stop — no one gets screwed). Also report: total travel time, per-person times, number of changes.
5. **Output:** top-3 candidate stops with a small table (stop name, per-person minutes, max, sum).

## Planned structure
- Single file: `bvg.py` (already exists, empty).
- Dependencies: `requests` only (stdlib + one pip install).
- CLI entry: `python bvg.py "Mehringdamm" "Alexanderplatz" "Zoologischer Garten"` — each positional arg is one person's start.
- Optional flags later: `--when "tomorrow 2pm"`, `--objective {max,sum}`, `--products subway,tram`, `--top K`.

## Rough code shape
```
resolve_stop(query) -> {id, name, lat, lon}
nearby_stops(lat, lon, radius=2000) -> [stops]
journey_duration(from_id, to_id, when=None) -> minutes
score_candidate(candidate, starts, when) -> {per_person, max, sum}
find_best(starts_text: list[str], top=3) -> ranked list
```

## Open questions for you before I start coding
1. **Objective function** — minimise the **max** travel time (fairest, default) or the **sum** (group-efficient)? I'll default to `max` unless you say otherwise.
2. **Candidate generation** — centroid + `/stops/nearby` (simple, few API calls) vs. a union of nearby stops around *each* person (more candidates, more calls). Default: centroid.
3. **Departure time** — "now" by default, or always let the user pass `--when`?
4. **Input format** — free-text stop names (we fuzzy-resolve via `/locations`) or require stop IDs? Default: free text, we resolve and print what we matched so user can sanity-check.
5. **Output** — just print a ranked table to stdout, or also dump JSON? Default: pretty table + `--json` flag later.
6. **Product filter** — restrict to subway/S-Bahn/tram/bus subset (API supports `subway=false` etc. on `/journeys`)? Default: all modes.
7. **Scope** — is this a one-shot CLI script, or do you eventually want a small web UI / map? v1 assumes CLI.

## API endpoints we'll actually use
- `GET /locations?query=…&poi=false&addresses=false&results=1` — resolve text → stop
- `GET /stops/nearby?latitude=…&longitude=…&distance=…&results=…` — candidate generation
- `GET /journeys?from=…&to=…&results=1&departure=…` — travel time per (person, candidate) pair

## Cost estimate per run
n people × C candidates journey calls + n resolve calls + 1 nearby call. With n=4, C=30 → **121 HTTP calls**. API is free & public but rate-limited; we'll add a small delay / concurrency cap if needed.
