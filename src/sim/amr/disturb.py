"""Seeded randomness for the AMR twin.

One seed spawns independent streams (layout, people, robot, disturbances,
compute, nav, camera), so every policy compared under the same seed sees the
same warehouse, the same workers and the same disturbance schedule.

Disturbances:
  ambient drift   Ornstein-Uhlenbeck around the configured ambient
  CPU bursts      Poisson arrivals of other processes taking extra CPU
  camera noise    Gaussian pixel noise on every rendered frame
"""

import math

import numpy as np

STREAMS = ("layout", "people", "robot", "disturb", "compute", "nav", "camera")


def spawn_rngs(seed: int) -> dict:
    seqs = np.random.SeedSequence(seed).spawn(len(STREAMS))
    return {name: np.random.default_rng(s) for name, s in zip(STREAMS, seqs)}


class Disturbances:
    def __init__(self, cfg: dict, base_ambient: float, rng, cam_rng):
        self.c, self.rng, self.cam_rng = cfg, rng, cam_rng
        self.base = base_ambient
        self.ambient = base_ambient
        self.burst_left = 0.0
        self.burst_util = 0.0

    def step(self, dt: float = 1.0) -> tuple[float, float]:
        """Advance dt seconds; returns (ambient C, background CPU util)."""
        c, rng = self.c, self.rng
        tau, sd = c["ambient_tau_s"], c["ambient_sd_c"]
        a = math.exp(-dt / tau)  # exact OU update with stationary sd
        self.ambient = self.base + a * (self.ambient - self.base) + \
            sd * math.sqrt(1 - a * a) * rng.standard_normal()
        if self.burst_left > 0:
            self.burst_left -= dt
        elif rng.random() < 1 - math.exp(-c["burst_rate_per_s"] * dt):
            self.burst_left = rng.uniform(*c["burst_s"])
            self.burst_util = rng.uniform(*c["burst_util"])
        return self.ambient, (self.burst_util if self.burst_left > 0 else 0.0)

    def noisy(self, frame: np.ndarray) -> np.ndarray:
        sd = self.c["camera_noise_sd"]
        if sd <= 0:
            return frame
        noise = self.cam_rng.normal(0.0, sd, frame.shape)
        return np.clip(frame + noise, 0, 255).astype(np.uint8)
