"""Battery pack and robot power budget (pure Python, no physics).

Pack: open-circuit voltage linear in state of charge, series internal
resistance, so terminal voltage sags under load. The Pi's 5 V converter
reports undervoltage when the pack falls below `dcdc_min_v`, which SHADE
sees as the firmware "Undervoltage" flag.
"""

import math
from dataclasses import dataclass


@dataclass
class PowerSample:
    pi_w: float
    motors_w: float
    electronics_w: float

    @property
    def total_w(self) -> float:
        return self.pi_w + self.motors_w + self.electronics_w


def power_budget(power: dict, util: float, speed_scale: float,
                 wheel_mech_w: float) -> PowerSample:
    """Electrical power drawn this instant.

    util: Pi CPU utilisation 0..1; speed_scale: <1 while throttled (the
    clock is capped, so dynamic power falls); wheel_mech_w: positive
    mechanical power at the wheels (torque x speed).
    """
    span = power["pi_full_w"] - power["pi_idle_w"]
    pi_w = power["pi_idle_w"] + span * min(max(util, 0.0), 1.0) * speed_scale
    motors_w = max(wheel_mech_w, 0.0) / power["motor_eff"]
    return PowerSample(pi_w, motors_w, power["electronics_w"])


class Battery:
    def __init__(self, cfg: dict):
        self.c = cfg
        self.soc = cfg["soc0"]
        self.energy_used_wh = 0.0
        self.voltage = self.ocv()

    def ocv(self) -> float:
        c = self.c
        return c["v_empty"] + (c["v_full"] - c["v_empty"]) * self.soc

    def step(self, power_w: float, dt: float) -> float:
        """Draw `power_w` for `dt` seconds; returns terminal voltage."""
        e, r = self.ocv(), self.c["r_internal_ohm"]
        # P = V*I with V = E - I*R  ->  R*I^2 - E*I + P = 0
        disc = e * e - 4.0 * r * power_w
        current = (e - math.sqrt(max(disc, 0.0))) / (2.0 * r)
        self.voltage = e - current * r
        wh = power_w * dt / 3600.0
        self.energy_used_wh += wh
        self.soc = max(0.0, self.soc - wh / self.c["capacity_wh"])
        return self.voltage

    @property
    def undervoltage(self) -> bool:
        return self.voltage < self.c["dcdc_min_v"]
