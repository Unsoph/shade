"""Latency statistics for benchmark runs."""

import math


def percentile(sorted_vals: list[float], pct: float) -> float:
    """Linear-interpolated percentile of an already sorted list."""
    if not sorted_vals:
        return 0.0
    pos = (len(sorted_vals) - 1) * pct / 100.0
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def summarize(latencies_ms: list[float], detect_every: int = 1) -> dict:
    """Summary of per-inference latencies.

    `eff_fps` is output frames per second when only every Nth frame runs
    the detector (skipped frames cost ~0), i.e. detect_every * 1000 / mean.
    """
    n = len(latencies_ms)
    if n == 0:
        return {"n": 0}
    vals = sorted(latencies_ms)
    mean = sum(vals) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in vals) / n)
    return {
        "n": n, "mean_ms": mean, "p50_ms": percentile(vals, 50),
        "p95_ms": percentile(vals, 95), "p99_ms": percentile(vals, 99),
        "max_ms": vals[-1], "std_ms": std,
        "det_fps": 1000.0 / mean if mean else 0.0,
        "eff_fps": detect_every * 1000.0 / mean if mean else 0.0,
    }
