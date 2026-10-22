"""Figures for the paper. Missing data -> a clearly marked placeholder."""

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from scripts.paper_lib.loaders import DATA, parse_gating, read_csv  # noqa: E402

ROOT = DATA.parents[1]
OUT = ROOT / "paper" / "figures"
SIZE = (3.4, 2.3)


def _save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.pdf")
    plt.close(fig)


def placeholder(name: str, what: str):
    fig, ax = plt.subplots(figsize=SIZE)
    ax.text(0.5, 0.5, f"PENDING HARDWARE DATA\n{what}", ha="center", va="center",
            color="crimson", fontsize=8, transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_linestyle("--")
        s.set_color("crimson")
    _save(fig, name)


def f_sustained():
    rows = read_csv(DATA / "e2_sustained.csv")
    rows = [r for r in rows or [] if r["rung"].startswith("sustained") and r["temp_end_c"]]
    if not rows:
        return placeholder("f_sustained", "E2: p50 latency vs temperature")
    fig, ax = plt.subplots(figsize=SIZE)
    ax.plot([float(r["temp_end_c"]) for r in rows], [float(r["p50_ms"]) for r in rows], "o-")
    ax.set_xlabel("CPU temperature (C)")
    ax.set_ylabel("p50 latency (ms)")
    _save(fig, "f_sustained")


def f_traces():
    files = {k: DATA / "trials" / f"{k}-run1.csv" for k in ("static-0", "shade")}
    if not all(f.is_file() for f in files.values()):
        return placeholder("f_traces", "E3: temperature and rung vs time")
    fig, ax = plt.subplots(figsize=SIZE)
    for key, path in files.items():
        rows = read_csv(path)
        ax.plot([float(r["t_s"]) / 60 for r in rows], [float(r["temp_c"]) for r in rows],
                label=key, lw=0.8)
    ax.set_xlabel("time (min)")
    ax.set_ylabel("CPU temperature (C)")
    ax.legend(fontsize=7)
    _save(fig, "f_traces")


def f_pareto():
    """Simulation (docs/results/pareto_cool.txt): utility vs time above 70 C."""
    path = ROOT / "docs" / "results" / "pareto_cool.txt"
    if not path.is_file():
        return placeholder("f_pareto", "simulation output missing")
    pts = {"reactive": [], "forecast": []}
    for line in path.read_text().splitlines():
        m = re.match(r"(reactive|forecast)\s.*?\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+[\d.]+$", line)
        if m:
            pts[m.group(1)].append((float(m.group(3)), float(m.group(2))))
    fig, ax = plt.subplots(figsize=SIZE)
    for name, p in pts.items():
        ax.plot(*zip(*p), "o-", label=name)
    ax.set_xlabel("time above 70 C (%)")
    ax.set_ylabel("utility (det/s x quality)")
    ax.legend(fontsize=7)
    _save(fig, "f_pareto")


def f_gating():
    g = parse_gating(ROOT / "docs" / "gating_eval_output.txt")
    if not g:
        return placeholder("f_gating", "gating output missing")
    fig, ax = plt.subplots(figsize=SIZE)
    for arm in ("hold", "shift", "gate", "gate+shift"):
        p = sorted((r["calls"], r["f1"]) for r in g if r["arm"] == arm and r["iou"] == 0.75)
        ax.plot(*zip(*p), "o-", label=arm)
    ax.set_xlabel("detector calls / frame")
    ax.set_ylabel("F1 vs per-frame reference (IoU 0.75)")
    ax.legend(fontsize=7)
    _save(fig, "f_gating")


ALL = {"f_sustained": f_sustained, "f_traces": f_traces, "f_pareto": f_pareto,
       "f_gating": f_gating}
