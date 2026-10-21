"""Policies under comparison. Each maps a health snapshot to a rung index."""

import copy

from src.core.decision.advisor import ThermalAdvisor
from src.core.decision.engine import DecisionEngine
from src.core.defaults import DEFAULTS


class Static:
    def __init__(self, rung: int):
        self.rung, self.name = rung, f"static-{rung}"

    def decide(self, snap) -> int:
        return self.rung


class Thermostat:
    """The obvious baseline: one step down above `hot`, one up below `cool`,
    evaluated on every sample with no timing guards."""

    name = "thermostat"

    def __init__(self, n_rungs: int, hot: float = 75.0, cool: float = 65.0):
        self.n, self.hot, self.cool, self.rung = n_rungs, hot, cool, 0

    def decide(self, snap) -> int:
        if snap.cpu_temp >= self.hot:
            self.rung = min(self.rung + 1, self.n - 1)
        elif snap.cpu_temp <= self.cool:
            self.rung = max(self.rung - 1, 0)
        return self.rung


class Shade:
    """The real DecisionEngine, optionally with the thermal-model advisor."""

    def __init__(self, name: str, n_rungs: int, rel_costs, forecast=False,
                 forecast_cfg=None, **policy_over):
        self.name = name
        policy = copy.deepcopy(DEFAULTS["policy"])
        policy.update(policy_over)
        fc = forecast_cfg or policy["forecast"]
        advisor = ThermalAdvisor(rel_costs, fc) if forecast else None
        self.engine = DecisionEngine(policy, n_rungs, 0, advisor)

    def decide(self, snap) -> int:
        return self.engine.evaluate(snap, now=snap.timestamp).rung


NO_GUARDS = dict(confirm_samples=1, dwell_s=0.0, cooldown_s=0.0, recover_hold_s=0.0)
NO_ANTICIPATION = dict(rise_c_per_s=1e9)


def make_policies(n_rungs: int, rel_costs, oracle_rung: int | None = None):
    pols = [Static(0), Static(n_rungs - 1), Thermostat(n_rungs),
            Shade("shade-noguards", n_rungs, rel_costs, **NO_GUARDS),
            Shade("shade-noanticip", n_rungs, rel_costs, **NO_ANTICIPATION),
            Shade("shade-reactive", n_rungs, rel_costs),
            Shade("shade-forecast", n_rungs, rel_costs, forecast=True)]
    if oracle_rung is not None:
        pols.insert(2, Static(oracle_rung))
        pols[2].name = "static-oracle"
    return pols
