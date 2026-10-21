"""Closed-loop thermal plant: the chosen rung's CPU load heats the chip.

The scripted scenarios in src/core/hardware are open-loop (temperature does
not react to SHADE's actions). This plant is closed-loop: utilisation drives
temperature, firmware throttling cuts both heat and speed, and the model can
be made deliberately *different* from the estimator's assumptions (second
thermal mass, temperature-dependent leakage, ambient steps).
All parameters are assumptions until fitted to a real device.
"""

import random
from dataclasses import dataclass, field


@dataclass
class PlantConfig:
    ambient_c: float = 30.0
    tau_s: float = 80.0          # fast (die/heatsink) time constant
    k_c: float = 60.0            # deg C above ambient at utilisation 1.0
    throttle_c: float = 80.0     # firmware soft limit
    throttle_off_c: float = 77.0
    throttle_scale: float = 0.55  # speed and heat multiplier while throttled
    noise_c: float = 0.3
    slow_frac: float = 0.0       # share of heat that goes via a slow mass
    tau_slow_s: float = 600.0
    leak: float = 0.0            # extra heat per 40 deg C above 40 C
    ambient_steps: tuple = field(default_factory=tuple)  # ((t_s, ambient_c), ...)


class ThermalPlant:
    def __init__(self, cfg: PlantConfig, seed: int = 0):
        self.cfg = cfg
        self.rng = random.Random(seed)
        self.temp = cfg.ambient_c
        self.slow = 0.0
        self.throttled = False

    def ambient(self, t: float) -> float:
        amb = self.cfg.ambient_c
        for t_step, value in self.cfg.ambient_steps:
            if t >= t_step:
                amb = value
        return amb

    def step(self, util: float, dt: float, t: float) -> tuple[float, float]:
        """Advance dt seconds at CPU utilisation `util`. Returns
        (measured temperature, speed multiplier from throttling)."""
        c = self.cfg
        if self.throttled and self.temp <= c.throttle_off_c:
            self.throttled = False
        elif not self.throttled and self.temp >= c.throttle_c:
            self.throttled = True
        scale = c.throttle_scale if self.throttled else 1.0
        heat = c.k_c * util * scale
        heat *= 1.0 + c.leak * max(self.temp - 40.0, 0.0) / 40.0
        fast = (1.0 - c.slow_frac) * heat
        target = self.ambient(t) + fast + self.slow
        self.temp += dt * (target - self.temp) / c.tau_s
        self.slow += dt * (c.slow_frac * heat - self.slow) / c.tau_slow_s
        return self.temp + self.rng.gauss(0.0, c.noise_c), scale
