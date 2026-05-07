# BVG Meeting-Point Finder

Given **n** people (2–6) starting at different Berlin public-transit stops, find the **fairest stop to meet at** — the one that minimises travel pain across the group.

Uses the public [`v6.bvg.transport.rest`](https://v6.bvg.transport.rest) REST API. No BVG account or API key required.

---

## How it works

The core loop is three steps:

1. **Resolve** each person's free-text input (e.g. `"Mehringdamm"`) to a BVG stop ID + coordinates via `/locations`.
2. **Generate candidates** — a set of stops that might be good meeting points — using one of the strategies described below.
3. **Score candidates** — for every `(person, candidate)` pair, fetch the fastest journey time via `/journeys`. Build a matrix of travel times, then rank candidates by their **maximum** travel time across the group (fairest: no one gets a terrible commute).

The top-K results are printed as a table (CLI) or rendered in the browser (web UI).

---

## Usage

### CLI

```bash
python bvg.py "Mehringdamm" "Alexanderplatz" "Zoologischer Garten"
python bvg.py "Mehringdamm" "Alexanderplatz" --strategy two_pass --top 5
python bvg.py -f stops.txt --strategy union
```

**Flags:**

| Flag | Default | Description |
|---|---|---|
| `--strategy` | `union` | Candidate-generation strategy (see below) |
| `--top` | `3` | How many top stops to show |
| `--radius` | `2000` | Candidate search radius in metres |
| `--candidates` | `30` | Max stops to fetch per strategy query |
| `--when` | now | Departure time, e.g. `"tomorrow 2pm"` |
| `-f FILE` | — | Text file with one address per line |

### Web UI

```bash
python app.py
# open http://localhost:5000
```

The web UI lets you add addresses, pick a strategy, and see results in a table alongside a map. The **Compare All** button runs every strategy in parallel via Server-Sent Events and shows results as they arrive.

---

## API endpoints used

| Endpoint | Purpose |
|---|---|
| `GET /locations?query=…` | Resolve free-text → stop ID + coordinates |
| `GET /locations/nearby?latitude=…&longitude=…` | Find stops near a point |
| `GET /journeys?from=…&to=…&results=1` | Fastest journey time between two stops |

Journey scoring runs all `n × C` API calls concurrently via `ThreadPoolExecutor` (12 workers by default).

---

## Candidate-generation strategies

The strategies differ only in **which stops they nominate as candidates** before the scoring step. Scoring is always the same: real journey times from the BVG API, ranked by worst-case travel time.

---

### `centroid` — Arithmetic mean

**The simplest baseline.**

Computes the arithmetic mean of all start coordinates, then fetches the `--candidates` nearest stops around that point.

```
center = (mean(lats), mean(lons))
candidates = nearby_stops(center, radius)
```

**Pros:** One API call. Fast.  
**Cons:** Purely geometric — ignores transit topology entirely. The centroid of two S-Bahn stations might land in a neighbourhood with only buses. A group with one outlier will have the center pulled toward them, potentially shortchanging the majority.

---

### `median` — Geographic median (Weiszfeld algorithm)

**Outlier-robust version of centroid.**

Instead of the arithmetic mean, computes the [geometric median](https://en.wikipedia.org/wiki/Geometric_median) — the point that minimises the *sum of distances* to all start points. The arithmetic mean is pulled hard by outliers; the geometric median resists them.

The algorithm used is **Weiszfeld's iterative method**:

```
initialise: (lat, lon) = arithmetic mean
repeat up to 200 times:
    distances[i] = euclidean distance from (lat, lon) to start[i]
    weights[i]   = 1 / distances[i]          # closer points get less pull
    (lat, lon)   = weighted mean of starts   # pull toward all, proportionally
    stop if change < 1e-9
candidates = nearby_stops((lat, lon), radius)
```

Each iteration pulls the estimate toward all starts, weighted inversely by distance — far starts pull harder, so the result stays near the dense cluster while resisting the isolated outlier.

**Pros:** More robust than centroid when one person is far from the group.  
**Cons:** Still a single geometric point — one API call for candidates. No transit awareness.

---

### `union` — Per-person neighbourhood union

**Collects candidates from around each person, not just the centre.**

For every start stop, fetches nearby stops within `--radius`. Merges all results (deduplicates by stop ID).

```
candidates = {}
for each start S:
    candidates |= nearby_stops(S.lat, S.lon, radius)
```

**Pros:** Never misses a stop that is close to one person and reachable by others. Catches good meeting points that lie off-centre — for example, a major hub near one person that everyone else can reach via a direct line.  
**Cons:** `n` API calls instead of 1. For n=4 and 30 results each, you may get up to 120 raw candidates (many will be filtered as start stops), which then need `n × C` journey calls to score. Slower overall.

**This is the default strategy.**

---

### `hub_weighted` — Centroid pool filtered by transit connectivity

**Takes the centroid candidate pool and keeps only the best-connected stops.**

First fetches candidates around the centroid (like `centroid`), then sorts them by **hub score** — the number of distinct transport modes available at the stop (subway, S-Bahn, tram, bus, ferry, etc.) — and keeps the top K.

```
hub_score(stop) = count of active product types (subway, tram, bus, …)
candidates = centroid_candidates sorted by hub_score DESC, top 20
```

**Pros:** Biases toward major interchange stations, which tend to have frequent service from many directions.  
**Cons:** Hub score is a crude proxy. A stop with many product types isn't necessarily easy to reach from every start. Still centroid-based, so shares its geometric blind spots.

---

### `steiner` — Iterative centre shift toward transit hubs

**Inspired by the Steiner point / Weber problem: iteratively move the search centre toward the "best" hub found so far.**

Runs multiple rounds. Each round:
1. Fetch nearby stops around the current centre.
2. Find the stop with the highest hub score.
3. Shift the centre **50% toward** that stop.
4. Repeat.

```
(lat, lon) = centroid of starts
for i in 1..iterations:
    batch = nearby_stops((lat, lon), radius)
    best  = argmax(hub_score, batch)
    (lat, lon) = midpoint((lat, lon), best)
    collect all seen stops as candidates
```

All stops seen across all iterations are collected as candidates (union of batches).

**Pros:** Gravitates toward transit hubs through an exploratory search, rather than committing to a fixed point. Can discover hubs that the centroid alone would miss.  
**Cons:** The 50% shift is a heuristic — it can overshoot or oscillate. Makes `iterations` API calls (default 3). The hub-score proxy applies here too.

---

### `gravity` — Inverse-density weighting

**Compensates for people in transit-sparse areas by pulling the search centre toward them.**

The intuition: if one person is in a neighbourhood with few stops, they likely have bad transit options. The search centre should lean toward them to find stops that are actually reachable for them, not just convenient for people already near a hub.

```
for each start S:
    density[S] = count of stops within 500m of S
    weight[S]  = 1 / density[S]     # fewer stops → higher weight

center = weighted mean of starts, weighted by 1/density
candidates = nearby_stops(center, radius)
```

**Pros:** Accounts for transit inequality. A person in Marzahn gets more pull than a person at Alexanderplatz.  
**Cons:** Extra API calls (one small `nearby` query per person to measure density). Still produces a single search point, so it can overshoot the sparse area if the density difference is extreme.

---

### `two_pass` — Wide union pre-filtered by hub score *(recommended)*

**Combines the coverage of `union` with the quality filter of `hub_weighted`.**

Two passes:

- **Pass 1a:** Wide centroid pool at `1.5×` the normal radius.
- **Pass 1b:** Tight per-person pools at `0.5×` the normal radius around each start.
- **Pass 2:** Merge everything, sort by hub score, keep top K.

```
candidates = {}
candidates |= nearby_stops(centroid, radius * 1.5)   # wide sweep
for each start S:
    candidates |= nearby_stops(S, radius * 0.5)       # local sweep
return top_K by hub_score
```

**Pros:** Gets broad geographic coverage (centroid sweep) plus local reachability candidates (per-person sweep), then filters to well-connected stops. Avoids scoring hundreds of bus-only stops that will never win.  
**Cons:** `n + 1` API calls to build the pool. Hub-score filter may exclude a stop that is geometrically ideal but happens to serve fewer modes.

**This is the recommended strategy for most use cases.**

---

## Scoring and ranking

Once candidates are collected, every strategy feeds into the same scoring step:

1. For each `(person i, candidate C)` pair, call `GET /journeys?from=P_i&to=C&results=1` and extract `arrival − departure` of the first journey.
2. Build a matrix `travel_time[person][candidate]`.
3. Drop any candidate where at least one person has no journey (unreachable stop, no service).
4. Rank survivors by **max travel time** (default) — the fairest metric: minimise how bad the worst commute is.
5. Secondary sort by **sum** (total group travel time).

All journey calls run concurrently (12 threads).

---

## Evaluate all strategies

```bash
python evaluate.py "Mehringdamm" "Alexanderplatz" "Zoologischer Garten"
```

Runs every strategy on the same inputs and prints a side-by-side comparison table, showing the top-1 result per strategy along with its per-person and max travel times.

---

## Project structure

```
bvg.py            CLI entry point
app.py            Flask web server (UI + REST API + SSE)
api.py            BVG API client, data types, scoring, table output
evaluate.py       Side-by-side strategy comparison runner
strategies/
  __init__.py     Auto-discovers and registers strategy modules
  centroid.py
  median.py
  union.py
  hub_weighted.py
  steiner.py
  gravity.py
  two_pass.py
templates/
  index.html      Web UI
```

## Dependencies

```
requests
flask
staticmap
```

Install with `pip install requests flask staticmap`.
