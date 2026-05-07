"""Find the fairest BVG meeting stop between n people.

Usage:
    python bvg.py "Mehringdamm" "Alexanderplatz" "Zoologischer Garten"
    python bvg.py "Mehringdamm" "Alexanderplatz" --strategy union
    python bvg.py -f stops.txt --strategy two_pass --top 5

Candidate-generation strategies (--strategy):
  centroid      Arithmetic-mean of coordinates [simple baseline]
  median        Geographic median, Weiszfeld — outlier-robust
  union         Union of per-person neighborhoods [good default]
  hub_weighted  Centroid pool filtered by transit connectivity
  steiner       Iterative center shift toward best hub
  gravity       Inverse-density weighting toward sparse-transit areas
  two_pass      Large union + hub pre-filter [recommended]

Run evaluate.py to compare all strategies side-by-side on the same inputs.
"""
from __future__ import annotations

import argparse
import sys

from api import print_table, resolve_stop, score_candidates
from strategies import REGISTRY


def find_best(
    queries: list[str],
    when: str | None,
    top: int,
    radius: int,
    candidates: int,
    strategy_name: str,
) -> None:
    if strategy_name not in REGISTRY:
        available = ", ".join(sorted(REGISTRY))
        print(f"Unknown strategy {strategy_name!r}. Available: {available}", file=sys.stderr)
        sys.exit(1)

    strategy = REGISTRY[strategy_name]
    print(f"Strategy: {strategy.NAME} — {strategy.DESCRIPTION}", file=sys.stderr)

    print(f"Resolving {len(queries)} start locations…", file=sys.stderr)
    starts = [resolve_stop(q) for q in queries]
    for q, s in zip(queries, starts):
        print(f"  {q!r} -> {s.name} ({s.id})", file=sys.stderr)

    cands = strategy.get_candidates(starts, radius=radius, results=candidates)
    start_ids = {s.id for s in starts}
    cands = [c for c in cands if c.id not in start_ids]
    print(f"Scoring {len(cands)} candidates…", file=sys.stderr)

    ranked = score_candidates(starts, cands, when)
    if not ranked:
        print("No reachable candidate stops found.", file=sys.stderr)
        sys.exit(1)

    print_table(ranked[:top], starts)


def _read_file(path: str) -> list[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("starts", nargs="*", help="Start stop names (one per person)")
    p.add_argument("-f", "--file", default=None, help="Text file with one address per line")
    p.add_argument("--when", default=None, help="Departure time, e.g. 'tomorrow 2pm'. Default: now.")
    p.add_argument("--top", type=int, default=3, help="Number of top stops to show (default 3)")
    p.add_argument("--radius", type=int, default=2000, help="Candidate search radius in metres")
    p.add_argument("--candidates", type=int, default=30, help="Max candidates per strategy query")
    p.add_argument(
        "--strategy",
        default="union",
        choices=sorted(REGISTRY),
        help="Candidate generation strategy (default: union)",
    )
    args = p.parse_args()

    queries = list(args.starts)
    if args.file:
        queries += _read_file(args.file)
    if len(queries) < 2:
        p.error("Need at least 2 start locations (via args or --file)")

    find_best(queries, args.when, args.top, args.radius, args.candidates, args.strategy)


if __name__ == "__main__":
    main()
