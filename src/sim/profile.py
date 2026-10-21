"""Rung operating points used by the simulator.

ASSUMED numbers for illustration. Replace with your own measurements
(scripts/benchmark.py: eff_fps; scripts/eval_agreement.py: agreement)
before drawing any conclusion about a real device.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RungProfile:
    name: str
    det_hz: float   # detector updates per second when not throttled
    quality: float  # agreement with the best rung per detection, 0..1
    util: float     # CPU utilisation, 0..1

    @property
    def utility(self) -> float:
        return self.det_hz * self.quality


ASSUMED = [
    RungProfile("nominal", 8.0, 1.00, 0.95),
    RungProfile("frame-skip", 4.0, 1.00, 0.50),
    RungProfile("small-320", 3.5, 0.85, 0.28),
    RungProfile("emergency", 2.0, 0.70, 0.15),
]
