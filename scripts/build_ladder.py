"""Prune a candidate ladder to its Pareto-efficient rungs from measurements.

    python scripts/benchmark.py --source <imgs> --out benchmarks/pi.csv
    python scripts/eval_agreement.py --images <imgs> --json benchmarks/q.json
    python scripts/build_ladder.py benchmarks/pi.csv benchmarks/q.json

A rung is dropped when another rung is at least as fast, at least as
accurate and at least as steady (p95), and strictly better on one of them:
keeping it would only add a swap that buys nothing. Survivors are printed
best-quality first, ready to paste under `ladder:`.
"""

import argparse
import csv
import json
import sys


def pareto(rows: list[dict]) -> list[dict]:
    """rows need eff_fps, quality, p95_ms. Returns the non-dominated rows."""
    def key(r):
        return (r["eff_fps"], r["quality"], -r["p95_ms"])

    keep = []
    for r in rows:
        dominated = any(
            all(a >= b for a, b in zip(key(o), key(r))) and key(o) != key(r)
            for o in rows if o is not r)
        if not dominated:
            keep.append(r)
    return sorted(keep, key=lambda r: (-r["quality"], -r["eff_fps"]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bench_csv")
    ap.add_argument("quality_json", help="{rung_name: agreement f1}")
    args = ap.parse_args(argv)
    quality = json.load(open(args.quality_json))
    rows = []
    for rec in csv.DictReader(open(args.bench_csv)):
        if rec["rung"] in quality and not rec["rung"].startswith("sustained"):
            rows.append({"name": rec["rung"], "model": rec["model"],
                         "input": int(rec["input"]),
                         "detect_every": int(rec["detect_every"]),
                         "eff_fps": float(rec["eff_fps"]),
                         "p95_ms": float(rec["p95_ms"]),
                         "quality": float(quality[rec["rung"]])})
    kept = pareto(rows)
    for r in rows:
        print(f"{'keep' if r in kept else 'drop':5s}{r['name']:14s} "
              f"eff_fps={r['eff_fps']:.1f} p95={r['p95_ms']:.0f}ms q={r['quality']:.3f}")
    print("\nladder:")
    for r in kept:
        print(f"  - {{name: {r['name']}, model: {r['model']}, "
              f"input_size: {r['input']}, detect_every: {r['detect_every']}}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
