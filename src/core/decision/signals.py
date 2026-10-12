"""Turn a HealthSnapshot into a pressure level (0..3) plus reasons.

Level 0 nominal, 1 warm/mild, 2 degrade, 3 critical. The engine maps the
level to a degradation rung; this module only reads signals.
"""

from collections import deque
from dataclasses import dataclass, field

from src.core.snapshots import HealthSnapshot


class SlopeTracker:
    """Least-squares temperature slope (deg C / s) over a sliding window."""

    MIN_POINTS = 3
    MIN_SPAN_S = 3.0

    def __init__(self, window_s: float):
        self._window = window_s
        self._pts: deque[tuple[float, float]] = deque()

    def add(self, t: float, temp: float) -> None:
        self._pts.append((t, temp))
        while self._pts and t - self._pts[0][0] > self._window:
            self._pts.popleft()

    def slope(self) -> float:
        if len(self._pts) < self.MIN_POINTS:
            return 0.0
        if self._pts[-1][0] - self._pts[0][0] < self.MIN_SPAN_S:
            return 0.0
        n = len(self._pts)
        mt = sum(p[0] for p in self._pts) / n
        mv = sum(p[1] for p in self._pts) / n
        den = sum((p[0] - mt) ** 2 for p in self._pts)
        if den == 0:
            return 0.0
        return sum((p[0] - mt) * (p[1] - mv) for p in self._pts) / den


@dataclass
class Signals:
    level: int = 0
    reasons: list[str] = field(default_factory=list)
    power: bool = False
    contention: bool = False
    calm: bool = True
    slope: float = 0.0


def _bump(sig: Signals, level: int, why: str) -> None:
    sig.level = max(sig.level, level)
    sig.reasons.append(why)
    sig.calm = False


def read_signals(snap: HealthSnapshot, policy: dict, slope: float,
                 fps_valid: bool) -> Signals:
    """Evaluate one snapshot against the policy thresholds."""
    sig = Signals(slope=slope)
    temp = snap.cpu_temp

    if temp >= policy["critical_c"]:
        _bump(sig, 3, f"temp {temp:.1f}C >= critical {policy['critical_c']}C")
    elif temp >= policy["degrade_c"]:
        _bump(sig, 2, f"temp {temp:.1f}C >= degrade {policy['degrade_c']}C")
    elif temp >= policy["warm_c"]:
        _bump(sig, 1, f"temp {temp:.1f}C >= warm {policy['warm_c']}C")
    elif temp > policy["upgrade_gate_c"]:
        sig.calm = False  # between gate and warm: not hot, not calm

    if temp >= policy["warm_c"] and slope >= policy["rise_c_per_s"]:
        _bump(sig, sig.level + 1, f"rising {slope:.2f}C/s while warm")
        sig.level = min(sig.level, 3)

    raw = snap.throttle_status
    if "Thermally throttled" in raw:
        _bump(sig, 3, "firmware reports thermal throttling")
    if "Freq capped" in raw:
        _bump(sig, 2, "firmware reports frequency cap")
    if "Undervoltage" in raw:
        sig.power = True
        _bump(sig, 2, "undervoltage: physical power problem")

    if snap.swap_percent >= policy["swap_crit_pct"] or \
            snap.memory_percent >= policy["mem_crit_pct"]:
        sig.contention = True
        _bump(sig, 2, f"memory {snap.memory_percent:.0f}% swap "
                      f"{snap.swap_percent:.0f}% critical")
    elif snap.swap_percent >= policy["swap_warn_pct"] or \
            snap.memory_percent >= policy["mem_warn_pct"]:
        sig.contention = True
        _bump(sig, 1, f"memory {snap.memory_percent:.0f}% swap "
                      f"{snap.swap_percent:.0f}% elevated")

    min_fps = policy["min_fps"]
    if min_fps > 0 and fps_valid and 0 < snap.fps < min_fps:
        _bump(sig, 1, f"fps {snap.fps:.1f} < min {min_fps}")
    return sig
