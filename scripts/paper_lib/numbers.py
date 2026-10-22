"""Headline numbers as LaTeX macros (paper/generated/numbers.tex)."""

import statistics as st

from scripts.paper_lib.fmt import TBD
from scripts.paper_lib.loaders import DATA, load_trials, parse_gating, read_json

ROOT = DATA.parents[1]


def macro(name: str, value, hint: str) -> str:
    hint = hint.replace("%", "\\%").replace("->", "to")
    text = value if value is not None else f"\\TBD{{{hint}}}"
    return f"\\newcommand{{\\{name}}}{{{text}}}"


def mean(trials, arm, key, digits=1):
    runs = trials.get(arm, [])
    return f"{st.mean(r[key] for r in runs):.{digits}f}" if runs else None


def gating_pair(rows, iou, every, field, a="hold", b="gate"):
    ra = next((r for r in rows or [] if (r["arm"], r["every"], r["iou"]) == (a, every, iou)), None)
    rb = next((r for r in rows or [] if (r["arm"], r["every"], r["iou"]) == (b, every, iou)), None)
    return (ra[field], rb[field]) if ra and rb else None


def build() -> str:
    t = load_trials()
    real = parse_gating(DATA / "e8_gating.txt")
    synth = parse_gating(ROOT / "docs" / "gating_eval_output.txt")
    fit = read_json(DATA / "e7_plant.json")
    lines = [
        macro("resStaticThrottled", mean(t, "static-0", "throttled_pct"), "static throttled %"),
        macro("resShadeThrottled", mean(t, "shade", "throttled_pct"), "SHADE throttled %"),
        macro("resStaticPfive", mean(t, "static-0", "p5_fps"), "static p5 FPS"),
        macro("resShadePfive", mean(t, "shade", "p5_fps"), "SHADE p5 FPS"),
        macro("resStaticFps", mean(t, "static-0", "mean_fps"), "static mean FPS"),
        macro("resShadeFps", mean(t, "shade", "mean_fps"), "SHADE mean FPS"),
        macro("resPlantR", f"{fit['fit']['r2_rate']:.2f}" if fit else None, "plant fit R2"),
    ]
    g = gating_pair(real, 0.75, 4, "calls")
    lines.append(macro("resGateSaving", f"{100 * (1 - g[1] / g[0]):.0f}" if g else None,
                       "gate call saving % (real video)"))
    s = gating_pair(real, 0.75, 8, "fast", "hold", "shift")
    lines.append(macro("resShiftGain", f"{s[0]:.2f}$\\to${s[1]:.2f}" if s else None,
                       "F1 hold->shift, fast motion"))
    g = gating_pair(synth, 0.75, 4, "calls")
    lines.append(macro("simGateSaving", f"{100 * (1 - g[1] / g[0]):.0f}" if g else None, "n/a"))
    s = gating_pair(synth, 0.75, 8, "fast", "hold", "shift")
    lines.append(macro("simShiftGain", f"{s[0]:.2f}$\\to${s[1]:.2f}" if s else None, "n/a"))
    return "\n".join(lines) + "\n"
