"""Scripted hardware scenarios for simulation, demos and chaos tests.

Each scenario maps elapsed seconds to a Sample. They are deterministic, so
the same trace drives unit tests, the Stage 2 demo and live --simulate runs.
"""

from dataclasses import dataclass

from src.core.hardware.base_hw_monitor import ThrottleFlags

BASE_TEMP = 48.0
BASE_MEM = 40.0


@dataclass(frozen=True)
class Sample:
    temp: float = BASE_TEMP
    mem: float = BASE_MEM
    swap: float = 0.0
    flags: ThrottleFlags = ThrottleFlags()


def _interp(points: list[tuple[float, float]], t: float) -> float:
    """Piecewise-linear interpolation, clamped at both ends."""
    if t <= points[0][0]:
        return points[0][1]
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return points[-1][1]


def nominal(t: float) -> Sample:
    return Sample()


def thermal_ramp(t: float) -> Sample:
    """Slow heat-soak to 84C, hold, then cool back down."""
    temp = _interp([(0, 48), (30, 48), (130, 84), (190, 84),
                    (230, 55), (400, 50)], t)
    flags = ThrottleFlags(throttled=True, raw_hex="0x4") if temp >= 82 \
        else ThrottleFlags()
    return Sample(temp=temp, flags=flags)


def thermal_spike(t: float) -> Sample:
    """A 4-second spike (e.g. a neighbouring process) on a cool device."""
    temp = _interp([(0, 52), (30, 52), (31, 83), (35, 83), (36, 52), (300, 50)], t)
    return Sample(temp=temp)


def undervoltage(t: float) -> Sample:
    """Weak power supply: undervoltage flag for 60 s."""
    bad = 30 <= t <= 90
    flags = ThrottleFlags(undervoltage=True, raw_hex="0x1") if bad \
        else ThrottleFlags()
    return Sample(temp=58.0, flags=flags)


def memory_pressure(t: float) -> Sample:
    """Swap thrashing between 30 s and 90 s."""
    if 30 <= t <= 90:
        return Sample(temp=55.0, mem=95.0, swap=40.0)
    return Sample(temp=52.0)


def oscillation(t: float) -> Sample:
    """Temperature hovering around the thresholds; tests anti-flapping."""
    cycle = t % 20.0
    temp = _interp([(0, 64), (10, 78), (20, 64)], cycle)
    return Sample(temp=temp)


SCENARIOS = {
    "nominal": nominal,
    "thermal_ramp": thermal_ramp,
    "thermal_spike": thermal_spike,
    "undervoltage": undervoltage,
    "memory_pressure": memory_pressure,
    "oscillation": oscillation,
}


def get_scenario(name: str):
    if name not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{name}'. Available: {sorted(SCENARIOS)}")
    return SCENARIOS[name]
