"""Waypoint following for a differential-drive base (pure Python, no physics).

Go-to-goal with a proportional heading controller: turn on the spot when
the goal is far off-axis, slow down proportionally as the heading error
grows, and park for `dwell_s` at stations before moving on (optionally
jittered by a seeded RNG). The route loops.
"""

import math
from dataclasses import dataclass


def wrap(angle: float) -> float:
    """Wrap an angle to (-pi, pi]."""
    return math.atan2(math.sin(angle), math.cos(angle))


@dataclass
class NavCommand:
    v: float          # forward speed, m/s
    w: float          # yaw rate, rad/s
    parked: bool
    waypoint: int


class WaypointNav:
    def __init__(self, route: list[dict], nav: dict, max_v: float, max_w: float,
                 rng=None, dwell_jitter: float = 0.0):
        if not route:
            raise ValueError("route needs at least one waypoint")
        self.route = route
        self.k = nav["k_heading"]
        self.arrive = nav["arrive_m"]
        self.slow = math.radians(nav["slow_angle_deg"])
        self.max_v, self.max_w = max_v, max_w
        self.index = 0
        self._park_until: float | None = None
        self.laps = 0
        self.rng, self.jitter = rng, dwell_jitter

    def _advance(self) -> None:
        self.index = (self.index + 1) % len(self.route)
        if self.index == 0:
            self.laps += 1

    def update(self, t: float, x: float, y: float, yaw: float) -> NavCommand:
        if self._park_until is not None:
            if t < self._park_until:
                return NavCommand(0.0, 0.0, True, self.index)
            self._park_until = None
            self._advance()
        gx, gy = self.route[self.index]["xy"]
        dist = math.hypot(gx - x, gy - y)
        if dist <= self.arrive:
            dwell = float(self.route[self.index].get("dwell_s", 0.0))
            if self.rng is not None and dwell > 0:
                dwell *= 1 + self.rng.uniform(-self.jitter, self.jitter)
            if dwell > 0:
                self._park_until = t + dwell
                return NavCommand(0.0, 0.0, True, self.index)
            self._advance()
            return self.update(t, x, y, yaw)
        err = wrap(math.atan2(gy - y, gx - x) - yaw)
        w = max(-self.max_w, min(self.max_w, self.k * err))
        scale = max(0.0, 1.0 - abs(err) / self.slow)
        v = min(self.max_v, 0.8 * dist + 0.1) * scale
        return NavCommand(v, w, False, self.index)
