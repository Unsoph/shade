"""Read experiment outputs from paper/data/ (missing files return None)."""

import csv
import json
import re
import statistics as st
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "paper" / "data"


def read_csv(path: Path):
    return list(csv.DictReader(open(path))) if path.is_file() else None


def read_json(path: Path):
    return json.load(open(path)) if path.is_file() else None


def trial_metrics(rows: list[dict]) -> dict:
    """Summary of one trial CSV written by scripts/trial.py."""
    t = [float(r["t_s"]) for r in rows]
    fps = sorted(float(r["fps"]) for r in rows if float(r["fps"]) > 0)
    temp = [float(r["temp_c"]) for r in rows]
    rung = [int(r["rung"]) for r in rows]
    hours = max((t[-1] - t[0]) / 3600.0, 1e-9)
    n = len(rows)
    return {
        "mean_fps": st.mean(fps) if fps else 0.0,
        "p5_fps": fps[int(0.05 * len(fps))] if fps else 0.0,
        "mean_temp": st.mean(temp), "max_temp": max(temp),
        "throttled_pct": 100.0 * sum(int(r["throttled"]) for r in rows) / n,
        "above70_pct": 100.0 * sum(x >= 70.0 for x in temp) / n,
        "switches_per_h": sum(a != b for a, b in zip(rung, rung[1:])) / hours,
        "minutes": hours * 60.0,
    }


def load_trials(directory: Path = DATA / "trials") -> dict[str, list[dict]]:
    """{arm: [metrics per run]} from files named <arm>-run<k>.csv."""
    out: dict[str, list[dict]] = {}
    for path in sorted(directory.glob("*-run*.csv")):
        arm = re.sub(r"-run\d+$", "", path.stem)
        rows = read_csv(path)
        if rows:
            out.setdefault(arm, []).append(trial_metrics(rows))
    return out


def parse_gating(path: Path):
    """Rows of scripts/eval_gating.py output."""
    if not path.is_file():
        return None
    rows = []
    for line in path.read_text().splitlines():
        p = line.split()
        if len(p) == 8 and re.match(r"^\d\.\d+$", p[0]):
            rows.append({"iou": float(p[0]), "every": int(p[1]), "arm": p[2],
                         "calls": float(p[3]), "f1": float(p[4]),
                         "static": float(p[5]), "slow": float(p[6]),
                         "fast": float(p[7])})
    return rows or None
