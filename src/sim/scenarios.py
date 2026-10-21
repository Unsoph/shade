"""Plant scenarios for the ablation study (all parameters are assumptions)."""

import random
from dataclasses import replace

from src.sim.plant import PlantConfig

BASE = PlantConfig()

SCENARIOS = {
    "cool-room": replace(BASE, ambient_c=25.0),
    "warm-room": replace(BASE, ambient_c=35.0),
    "hot-enclosure": replace(BASE, ambient_c=42.0),
    "ambient-step": replace(BASE, ambient_c=28.0,
                            ambient_steps=((1200.0, 42.0), (2400.0, 28.0))),
    # model mismatch: the estimator assumes one thermal mass and no leakage
    "two-mass": replace(BASE, ambient_c=30.0, slow_frac=0.4, tau_slow_s=600.0),
    "leaky": replace(BASE, ambient_c=30.0, leak=0.5),
}


def perturb(cfg: PlantConfig, rng: random.Random, rel: float = 0.15) -> PlantConfig:
    """Per-seed variation of the thermal parameters."""
    j = lambda v: v * (1 + rng.uniform(-rel, rel))  # noqa: E731
    return replace(cfg, tau_s=j(cfg.tau_s), k_c=j(cfg.k_c))
