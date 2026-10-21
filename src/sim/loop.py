"""Virtual-time closed loop: policy <-> thermal plant, one sample per second."""

import random
from dataclasses import dataclass

from src.core.snapshots import HealthSnapshot
from src.sim.plant import PlantConfig, ThermalPlant
from src.sim.profile import RungProfile

SWAP_COST_S = 0.5  # output lost per rung change (first-frame + warmup)


@dataclass
class Result:
    utility: float          # mean detections/s x quality
    p5_utility: float       # 5th percentile of per-second utility
    throttled_pct: float
    above_warm_pct: float
    switches_per_h: float
    max_temp: float
    final_rung: int


def simulate(policy, plant_cfg: PlantConfig, profiles: list[RungProfile],
             duration_s: float = 3600.0, dt: float = 1.0, seed: int = 0) -> Result:
    plant = ThermalPlant(plant_cfg, seed)
    rung, last = 0, 0
    total = throttled = warm = switches = 0
    per_second = []
    max_t = 0.0
    t = 0.0
    while t < duration_s:
        prof = profiles[rung]
        temp, scale = plant.step(prof.util, dt, t)
        gain = prof.utility * scale * dt
        if rung != last:
            gain -= prof.utility * SWAP_COST_S
            switches += 1
            last = rung
        total += max(gain, 0.0)
        per_second.append(max(gain, 0.0) / dt)
        throttled += plant.throttled
        warm += temp >= 70.0
        max_t = max(max_t, temp)
        t += dt
        snap = HealthSnapshot(
            timestamp=t, fps=prof.det_hz * scale, cpu_temp=temp,
            cpu_util=prof.util * scale,
            throttle_status="Thermally throttled" if plant.throttled else "Clean")
        rung = policy.decide(snap)
    n = duration_s / dt
    per_second.sort()
    p5 = per_second[int(0.05 * len(per_second))]
    return Result(total / duration_s, p5, 100 * throttled / n, 100 * warm / n,
                  switches * 3600.0 / duration_s, max_t, rung)


def jitter(profiles: list[RungProfile], rng: random.Random, rel: float = 0.15):
    """Per-run perturbation of the (assumed) profiles."""
    return [RungProfile(p.name, p.det_hz, p.quality,
                        min(1.0, p.util * (1 + rng.uniform(-rel, rel))))
            for p in profiles]
