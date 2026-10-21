"""Pick the best rung the device can sustain, from a learned thermal model.

The reactive guards in the engine only see the *current* temperature. The
advisor asks a different question: "at which rung would the temperature,
`horizon_s` from now, stay under `target_c`?" It answers with an online
thermal model (thermal_model.py), per-rung utilisation calibrated from
measurements, and an uncertainty margin (z standard deviations).
"""

from src.core.decision.thermal_model import ThermalModel

EMA = 0.2  # smoothing for measured per-rung utilisation


class ThermalAdvisor:
    def __init__(self, rel_costs: list[float], cfg: dict):
        """rel_costs[i]: relative compute per second of rung i (any scale),
        used only to extrapolate utilisation to rungs not yet measured."""
        self.cfg = cfg
        self.model = ThermalModel(cfg)
        self.rel = [max(c, 1e-6) for c in rel_costs]
        self.util: dict[int, float] = {}
        self.current = 0

    def observe(self, now: float, temp: float, rung: int, util: float,
                throttled: bool) -> None:
        self.current = rung
        if util > 0:
            prev = self.util.get(rung)
            self.util[rung] = util if prev is None else prev + EMA * (util - prev)
        self.model.observe(now, temp, self.util.get(rung, util), not throttled)

    def util_of(self, rung: int) -> float | None:
        """Measured utilisation, or scaled from the current rung's."""
        if rung in self.util:
            return self.util[rung]
        base = self.util.get(self.current)
        if base is None:
            return None
        return min(1.0, base * self.rel[rung] / self.rel[self.current])

    def ready(self) -> bool:
        return (self.model.n_updates >= self.cfg.get("min_updates", 4)
                and self.current in self.util)

    def predicted(self, rung: int, temp: float) -> float | None:
        u = self.util_of(rung)
        if u is None:
            return None
        return self.model.forecast(temp, u, self.cfg["horizon_s"], self.cfg["z"])

    def floor(self, temp: float, n_rungs: int) -> int:
        """Lowest rung index (= best quality) predicted to stay <= target.

        Moving *up* the ladder needs `upgrade_margin_c` extra headroom, so a
        forecast hovering at the target cannot make the rung flap."""
        if not self.ready():
            return 0
        for rung in range(n_rungs):
            limit = self.cfg["target_c"]
            if rung < self.current:
                limit -= self.cfg["upgrade_margin_c"]
            pred = self.predicted(rung, temp)
            if pred is not None and pred <= limit:
                return rung
        return n_rungs - 1
