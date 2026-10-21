"""Deterministic decision engine.

Maps health snapshots to a degradation rung (0 = best) with anti-flapping
guards. It never touches models or hardware; the controller applies its
decisions. Time is passed in, so every behaviour is unit-testable.

Guards (all from the policy config):
  confirm_samples  consecutive samples needed before degrading
  dwell_s          minimum time since the last change before degrading
  cooldown_s       minimum time since the last change before upgrading
  recover_hold_s   continuous calm needed before each single-step upgrade
Critical pressure (level 3) bypasses confirm and dwell.
"""

import logging

from src.core.decision.signals import SlopeTracker, read_signals
from src.core.decision.states import Decision, State
from src.core.snapshots import HealthSnapshot

logger = logging.getLogger(__name__)
CRITICAL_LEVEL = 3


class DecisionEngine:
    def __init__(self, policy: dict, n_rungs: int, start_rung: int = 0,
                 advisor=None):
        self._p = policy
        self._advisor = advisor  # optional ThermalAdvisor (model-based floor)
        self.n_rungs = max(1, n_rungs)
        self.rung = min(max(start_rung, 0), self.n_rungs - 1)
        self.state = State.NOMINAL
        self._slope = SlopeTracker(policy["slope_window_s"])
        self._map = [min(r, self.n_rungs - 1) for r in policy["level_to_rung"]]
        self._escalations = 0
        self._last_change: float | None = None
        self._calm_since: float | None = None
        self._bad: set[int] = set()

    # -- control-plane hooks ------------------------------------------
    def mark_unavailable(self, rung: int) -> None:
        """A rung failed to load; never target it again this run."""
        self._bad.add(rung)
        logger.warning("Rung %d marked unavailable.", rung)

    def force_rung(self, rung: int, now: float) -> None:
        """Resync after a failed or reverted swap."""
        self.rung = rung
        self._last_change = now
        self._escalations = 0
        self._calm_since = None

    # -- helpers -------------------------------------------------------
    def _since_change(self, now: float) -> float:
        return float("inf") if self._last_change is None else now - self._last_change

    def _worse_or_equal(self, desired: int) -> int:
        for r in range(desired, self.n_rungs):
            if r not in self._bad:
                return r
        for r in range(desired - 1, -1, -1):
            if r not in self._bad:
                return r
        return self.rung

    def _next_better(self) -> int | None:
        for r in range(self.rung - 1, -1, -1):
            if r not in self._bad:
                return r
        return None

    def _label(self, snap: HealthSnapshot, sig) -> State:
        if snap.input_fault and sig.level == 0:
            return State.FAULT
        if sig.power:
            return State.POWER_WARNING
        if sig.contention:
            return State.OS_CONTENTION
        if self.rung == 0:
            return State.ELEVATED if sig.level >= 1 else State.NOMINAL
        if self._calm_since is not None:
            return State.RECOVERING
        if self.rung >= self.n_rungs - 1:
            return State.CRITICAL
        return State.DEGRADED

    # -- main entry point ---------------------------------------------
    def evaluate(self, snap: HealthSnapshot, now: float | None = None) -> Decision:
        now = snap.timestamp if now is None else now
        p = self._p
        if snap.cpu_temp > 0:
            self._slope.add(now, snap.cpu_temp)
        fps_valid = self._since_change(now) >= p["fps_grace_s"]
        sig = read_signals(snap, p, self._slope.slope(), fps_valid)
        if snap.input_fault:
            sig.reasons.append(f"input fault: {snap.input_fault}")

        prev_rung, prev_state = self.rung, self.state
        action, reasons = "hold", list(sig.reasons)
        floor = 0
        if self._advisor and snap.cpu_temp > 0:
            throttled = "Thermally throttled" in snap.throttle_status
            self._advisor.observe(now, snap.cpu_temp, self.rung,
                                  snap.cpu_util, throttled)
            floor = self._advisor.floor(snap.cpu_temp, self.n_rungs)
            if floor > self.rung:
                reasons.append(f"forecast: rung {self.rung} not sustainable")
            sig.calm = sig.calm or not sig.reasons  # model replaces the gate
        desired = self._worse_or_equal(max(self._map[sig.level], floor))
        if not sig.calm:
            self._calm_since = None

        if desired > self.rung:
            self._escalations += 1
            critical = sig.level >= CRITICAL_LEVEL
            need = 1 if critical else p["confirm_samples"]
            dwell_ok = critical or self._since_change(now) >= p["dwell_s"]
            if self._escalations >= need and dwell_ok:
                self.rung, action = desired, "degrade"
                self._mark_change(now)
        else:
            self._escalations = 0
            if desired < self.rung and sig.calm:
                self._calm_since = self._calm_since or now
                held = now - self._calm_since
                better = self._next_better()
                if (better is not None and held >= p["recover_hold_s"]
                        and self._since_change(now) >= p["cooldown_s"]):
                    self.rung, action = better, "upgrade"
                    reasons = [f"calm for {held:.0f}s at {snap.cpu_temp:.1f}C"]
                    self._mark_change(now)
                    self._calm_since = now  # fresh hold for the next step

        self.state = self._label(snap, sig)
        signals = {
            "temp": snap.cpu_temp, "fps": snap.fps, "mem": snap.memory_percent,
            "swap": snap.swap_percent, "throttle": snap.throttle_raw,
            "slope": round(sig.slope, 3), "level": sig.level,
        }
        return Decision(now, self.state, self.rung, prev_rung, prev_state,
                        action, tuple(reasons), signals)

    def _mark_change(self, now: float) -> None:
        self._last_change = now
        self._escalations = 0
