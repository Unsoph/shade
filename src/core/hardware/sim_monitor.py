"""Simulated hardware monitor: replays a scripted scenario.

Lets the full pipeline, dashboard and watchdog run on a laptop. `speed`
compresses scenario time (policy timers must be scaled to match; see
src.core.simulation.scale_policy).
"""

import time
from typing import Callable

from src.core.hardware.base_hw_monitor import HardwareMonitor, ThrottleFlags
from src.core.hardware.scenarios import Sample, get_scenario


class SimulatedMonitor(HardwareMonitor):
    def __init__(self, scenario: str = "nominal", speed: float = 1.0,
                 clock: Callable[[], float] = time.monotonic):
        self._scenario = get_scenario(scenario)
        self._speed = speed
        self._clock = clock
        self._t0 = clock()

    def elapsed(self) -> float:
        return (self._clock() - self._t0) * self._speed

    def _sample(self) -> Sample:
        return self._scenario(self.elapsed())

    def get_cpu_temp(self) -> float:
        return self._sample().temp

    def get_gpu_temp(self) -> float:
        return self._sample().temp

    def get_memory_percent(self) -> float:
        return self._sample().mem

    def get_swap_percent(self) -> float:
        return self._sample().swap

    def get_throttle_flags(self) -> ThrottleFlags:
        return self._sample().flags

    def get_platform_name(self) -> str:
        return "Simulated"
