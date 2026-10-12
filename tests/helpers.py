"""Shared test helpers (plain functions, no fixtures)."""

import copy

from src.core.defaults import DEFAULTS
from src.core.snapshots import HealthSnapshot


def policy(**over) -> dict:
    p = copy.deepcopy(DEFAULTS["policy"])
    p.update(over)
    return p


def snap(temp=50.0, t=0.0, fps=10.0, mem=40.0, swap=0.0,
         throttle="Clean", fault="") -> HealthSnapshot:
    return HealthSnapshot(
        timestamp=t, fps=fps, cpu_temp=temp, gpu_temp=temp,
        memory_percent=mem, swap_percent=swap, throttle_status=throttle,
        input_fault=fault,
    )


def run_trace(engine, temps, start=0.0, step=1.0, **kw):
    """Feed temps at `step` second intervals; return the decisions."""
    return [engine.evaluate(snap(temp, start + i * step, **kw))
            for i, temp in enumerate(temps)]


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def sleep(self, dt):
        self.t += dt

    def wait(self, dt):
        self.t += dt
        return False
