"""LaTeX tables for the paper. Any table whose data is missing is emitted
with \\TBD cells, so the PDF always builds and shows what is still owed."""

import json
import sqlite3
import statistics as st

from scripts.paper_lib.fmt import TBD, mean_sd, num, table
from scripts.paper_lib.loaders import DATA, load_trials, parse_gating, read_csv, read_json

ROOT = DATA.parents[1]
RUNGS = ["nominal", "frame-skip", "small-320", "emergency"]
ARMS = [("static-0", "Static nominal"), ("static-3", "Static emergency"),
        ("shade", "SHADE"), ("shade-gated", "SHADE + gate/shift"),
        ("shade-forecast", "SHADE + forecast")]


def t_rungs() -> str:
    rows = read_csv(DATA / "e1_rungs.csv")
    quality = read_json(DATA / "e1_quality.json") or {}
    out = []
    for name in RUNGS:
        r = next((x for x in rows or [] if x["rung"] == name), None)
        out.append([name] + ([num(float(r["p50_ms"])), num(float(r["p95_ms"])),
                              num(float(r["eff_fps"])), num(float(r["rss_delta_mb"]), 0),
                              num(quality.get(name), 3)] if r else [TBD] * 5))
    return table("Per-rung operating points on the target device (E1).",
                 "tab:rungs", ["Rung", "p50 (ms)", "p95 (ms)", "Eff. FPS",
                               "RSS (MB)", "Agreement F1"], out,
                 "Agreement = F1 at IoU 0.5 against the nominal rung.", wide=True)


def t_adaptive() -> str:
    trials = load_trials()
    out = []
    for key, label in ARMS:
        runs = trials.get(key, [])
        out.append([label, str(len(runs)) if runs else TBD] + [
            mean_sd([r[m] for r in runs], d) for m, d in (
                ("mean_fps", 1), ("p5_fps", 1), ("throttled_pct", 1),
                ("above70_pct", 1), ("max_temp", 1), ("switches_per_h", 1))])
    return table("Static versus adaptive operation under sustained load (E3).",
                 "tab:adaptive", ["Arm", "Runs", "Mean FPS", "p5 FPS",
                                  "Throttled \\%", "$>$70\\,\\textdegree C \\%",
                                  "Max T", "Switches/h"], out,
                 "Mean $\\pm$ s.d. over runs; ambient, enclosure and cooling in "
                 "Sec.~\\ref{sec:setup}.", wide=True)


def t_swap() -> str:
    vals = {"swap_ms": [], "first_frame_ms": [], "load_s": []}
    for db in sorted((DATA / "trials").glob("*.db")):
        con = sqlite3.connect(db)
        for (d,) in con.execute("SELECT detail FROM events WHERE kind='swap_done'"):
            d = json.loads(d)
            for k in vals:
                if k in d:
                    vals[k].append(float(d[k]))
        con.close()

    def q(v, p):
        v = sorted(v)
        return num(v[min(len(v) - 1, int(p * len(v)))], 2) if v else None

    rows = [[label, str(len(vals[k])) if vals[k] else TBD,
             num(st.median(vals[k]), 2) if vals[k] else TBD, q(vals[k], 0.95) or TBD]
            for label, k in (("Reference swap (ms)", "swap_ms"),
                             ("First-frame time (ms)", "first_frame_ms"),
                             ("Background load (s)", "load_s"))]
    return table("Model-swap cost from the audit log (E4).", "tab:swap",
                 ["Quantity", "n", "Median", "p95"], rows)


def t_gating_real() -> str:
    g = parse_gating(DATA / "e8_gating.txt")
    out = []
    for arm in ("hold", "shift", "gate", "gate+shift"):
        for every in (4, 8):
            r = next((x for x in g or [] if x["arm"] == arm and x["every"] == every
                      and x["iou"] == 0.75), None)
            out.append([arm, str(every)] + ([num(r["calls"], 2), num(r["f1"], 3),
                                             num(r["fast"], 3)] if r else [TBD] * 3))
    return table("Gating and box shifting on real footage (E8, IoU 0.75).",
                 "tab:gating-real", ["Arm", "N", "Calls", "F1", "F1 (fast motion)"],
                 out, "Reference: detector on every frame of the same clips.")


def t_gating_synth() -> str:
    g = parse_gating(ROOT / "docs" / "gating_eval_output.txt") or []
    out = [[r["arm"], str(r["every"]), num(r["calls"], 2), num(r["f1"], 3),
            num(r["fast"], 3)] for r in g if r["iou"] == 0.75]
    return table("Gating and shifting, real YOLOv8n on a synthetic pan of one "
                 "image (offline, IoU 0.75).", "tab:gating-synth",
                 ["Arm", "N", "Calls", "F1", "F1 (fast pan)"], out)


def t_fidelity() -> str:
    fit = read_json(DATA / "e7_plant.json")
    rows = []
    for key, label in (("static-0", "Static nominal"), ("shade", "SHADE")):
        sim = (fit or {}).get("sim", {}).get(key, {})
        real = (load_trials().get(key) or [{}])[0]
        for m, name in (("above70_pct", "$>$70\\,\\textdegree C \\%"),
                        ("throttled_pct", "Throttled \\%"), ("max_temp", "Max T")):
            rows.append([label, name, num(real.get(m)), num(sim.get(m))])
    return table("Simulator fidelity: fitted plant versus device (E7).",
                 "tab:fidelity", ["Arm", "Metric", "Device", "Simulator"], rows)


def t_sim_ablation() -> str:
    rows = read_csv(ROOT / "docs" / "results" / "ablation_ts055.csv") or []
    out = []
    for scen in ("cool-room", "hot-enclosure"):
        for pol in ("static-0", "thermostat", "shade-noguards", "shade-reactive",
                    "shade-forecast"):
            sel = [r for r in rows if r["scenario"] == scen and r["policy"] == pol]
            if sel:
                out.append([scen, pol] + [mean_sd([float(r[m]) for r in sel], d)
                            for m, d in (("utility", 2), ("p5_utility", 2),
                                         ("above_warm_pct", 0), ("switches_per_h", 0))])
    return table("Simulated policy comparison (assumed plant, 10 seeds).",
                 "tab:sim", ["Scenario", "Policy", "Utility", "p5", "$>$70\\,\\textdegree C \\%",
                             "Sw/h"], out, "Simulation only; see Sec.~\\ref{sec:sim}.", wide=True)


ALL = {"t_rungs": t_rungs, "t_adaptive": t_adaptive, "t_swap": t_swap,
       "t_gating_real": t_gating_real, "t_gating_synth": t_gating_synth,
       "t_fidelity": t_fidelity, "t_sim_ablation": t_sim_ablation}
