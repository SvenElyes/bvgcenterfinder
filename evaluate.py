"""Compare every candidate-generation strategy on the same set of start stops.

All unique candidates across all strategies are scored exactly once, so the
journey-API call count equals (unique_candidates × n_people), not multiplied
by the number of strategies.
source ~/Desktop/bvg/.venv/bin/activate

Usage:
    python evaluate.py "Mehringdamm" "Alexanderplatz" "Zoologischer Garten"
    python3 evaluate.py -f stops.txt --radius 2500 --candidates 40
"""
from __future__ import annotations

import argparse
import sys
import time

from api import Score, Stop, resolve_stop, score_candidates
from strategies import REGISTRY


def _resolve_starts(queries: list[str]) -> list[Stop]:
    print(f"Resolving {len(queries)} start locations…", file=sys.stderr)
    starts: list[Stop] = []
    for q in queries:
        s = resolve_stop(q)
        print(f"  {q!r} -> {s.name} ({s.id})", file=sys.stderr)
        starts.append(s)
    return starts


def _collect_candidates(
    starts: list[Stop], radius: int, results: int
) -> tuple[dict[str, list[Stop]], dict[str, Stop]]:
    """Run every strategy and return per-strategy lists + a unified id→Stop map."""
    start_ids = {s.id for s in starts}
    strategy_cands: dict[str, list[Stop]] = {}
    all_stops: dict[str, Stop] = {}

    for name, mod in sorted(REGISTRY.items()):
        t0 = time.time()
        print(f"  [{name}] generating candidates…", file=sys.stderr)
        try:
            cands = mod.get_candidates(starts, radius=radius, results=results)
        except Exception as exc:
            print(f"  [{name}] FAILED: {exc}", file=sys.stderr)
            strategy_cands[name] = []
            continue
        cands = [c for c in cands if c.id not in start_ids]
        strategy_cands[name] = cands
        for c in cands:
            all_stops[c.id] = c
        print(
            f"  [{name}] {len(cands)} candidates in {time.time() - t0:.1f}s",
            file=sys.stderr,
        )

    return strategy_cands, all_stops


def _print_comparison(
    strategy_cands: dict[str, list[Stop]],
    score_map: dict[str, Score],
    starts: list[Stop],
    elapsed: float,
) -> None:
    NAME_W = 14
    STOP_W = 32

    # Collect best result per strategy first so we can mark the global winner
    bests: dict[str, Score | None] = {}
    for name, cands in strategy_cands.items():
        scored = sorted(
            [score_map[c.id] for c in cands if c.id in score_map],
            key=lambda s: (s.max_min, s.sum_min),
        )
        bests[name] = scored[0] if scored else None

    valid = [b for b in bests.values() if b is not None]
    winner_id = min(valid, key=lambda s: (s.max_min, s.sum_min)).candidate.id if valid else None

    header = (
        f"{'Strategy':<{NAME_W}}  {'Cands':>5}  {'Best stop':<{STOP_W}}  "
        f"{'max':>5}  {'sum':>5}  {'note'}"
    )
    sep = "-" * len(header)
    print()
    print(header)
    print(sep)

    for name in sorted(bests):
        best = bests[name]
        if best is None:
            print(f"{name:<{NAME_W}}  {'—':>5}  {'(no results)':<{STOP_W}}")
            continue
        note = "*** BEST ***" if best.candidate.id == winner_id else ""
        print(
            f"{name:<{NAME_W}}  {len([c for c in strategy_cands[name] if c.id in score_map]):>5}  "
            f"{best.candidate.name:<{STOP_W}}  "
            f"{best.max_min:5.1f}  {best.sum_min:5.1f}  {note}"
        )

    print(sep)
    if winner_id and valid:
        w = min(valid, key=lambda s: (s.max_min, s.sum_min))
        print(f"Best overall: {w.candidate.name}  (max {w.max_min:.1f} min, sum {w.sum_min:.1f} min)")
    unique_scored = len(score_map)
    total_api = unique_scored * len(starts)
    print(f"Journey API calls: {total_api}  ({unique_scored} unique candidates × {len(starts)} people)")
    print(f"Total wall time: {elapsed:.1f}s")
    print()
    print("Legend:")
    for i, st in enumerate(starts, 1):
        print(f"  P{i} = {st.name} ({st.id})")


def evaluate(queries: list[str], when: str | None, radius: int, results: int) -> None:
    starts = _resolve_starts(queries)
    t0 = time.time()

    print(f"\nCollecting candidates from {len(REGISTRY)} strategies…", file=sys.stderr)
    strategy_cands, all_stops = _collect_candidates(starts, radius, results)

    unique = list(all_stops.values())
    print(
        f"\nScoring {len(unique)} unique candidates "
        f"({len(starts) * len(unique)} journey calls)…",
        file=sys.stderr,
    )
    all_scores = score_candidates(starts, unique, when)
    score_map: dict[str, Score] = {s.candidate.id: s for s in all_scores}

    _print_comparison(strategy_cands, score_map, starts, time.time() - t0)


def _read_file(path: str) -> list[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("starts", nargs="*", help="Start stop names (one per person)")
    p.add_argument("-f", "--file", default=None, help="Text file with one address per line")
    p.add_argument("--when", default=None, help="Departure time, e.g. 'tomorrow 2pm'")
    p.add_argument("--radius", type=int, default=2000, help="Candidate search radius in metres")
    p.add_argument("--candidates", type=int, default=30, help="Max candidates per strategy query")
    args = p.parse_args()

    queries = list(args.starts)
    if args.file:
        queries += _read_file(args.file)
    if len(queries) < 2:
        p.error("Need at least 2 start locations (via args or --file)")

    evaluate(queries, args.when, args.radius, args.candidates)


if __name__ == "__main__":
    main()
