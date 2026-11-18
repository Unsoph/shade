"""AMR twin models that need no physics engine: nav, battery, compute."""

import math

import numpy as np
import pytest

from src.sim.amr.battery import Battery, power_budget
from src.sim.amr.compute import ComputeModel
from src.sim.amr.nav import WaypointNav, wrap
from src.sim.amr.params import AMR_DEFAULTS, load_amr_config

NAV = {"k_heading": 2.5, "arrive_m": 0.25, "slow_angle_deg": 40.0}


def drive(nav, x, y, yaw, seconds, dt=0.05):
    """Integrate the unicycle model under the nav commands."""
    t, parked_steps = 0.0, 0
    while t < seconds:
        cmd = nav.update(t, x, y, yaw)
        parked_steps += cmd.parked
        x += cmd.v * math.cos(yaw) * dt
        y += cmd.v * math.sin(yaw) * dt
        yaw = wrap(yaw + cmd.w * dt)
        t += dt
    return x, y, parked_steps * dt


def test_nav_reaches_waypoint_and_parks():
    nav = WaypointNav([{"xy": [2.0, 1.0], "dwell_s": 5.0}, {"xy": [0.0, 0.0]}],
                      NAV, max_v=0.8, max_w=1.5)
    x, y, parked = drive(nav, 0.0, 0.0, math.pi, seconds=12.0)
    assert parked >= 4.9          # it arrived and waited out the dwell
    assert nav.index == 1         # then moved on to the next waypoint
    assert math.hypot(x - 2.0, y - 1.0) < 1.5


def test_nav_loops_route():
    route = [{"xy": [1.0, 0.0]}, {"xy": [1.0, 1.0]}, {"xy": [0.0, 0.0]}]
    nav = WaypointNav(route, NAV, max_v=0.8, max_w=1.5)
    drive(nav, 0.0, 0.0, 0.0, seconds=30.0)
    assert nav.laps >= 1


def test_nav_rejects_empty_route():
    with pytest.raises(ValueError):
        WaypointNav([], NAV, 1.0, 1.0)


def test_battery_drains_and_sags():
    b = Battery(dict(AMR_DEFAULTS["battery"], soc0=1.0))
    v_light = b.step(20.0, 1.0)
    v_heavy = b.step(400.0, 1.0)
    assert v_heavy < v_light < b.c["v_full"]
    assert b.soc < 1.0 and b.energy_used_wh > 0


def test_battery_undervoltage_when_low():
    b = Battery(dict(AMR_DEFAULTS["battery"], soc0=0.05))
    b.step(150.0, 1.0)
    assert b.undervoltage


def test_power_budget_throttle_cuts_pi_power():
    pw = AMR_DEFAULTS["power"]
    full = power_budget(pw, 1.0, 1.0, 0.0)
    throttled = power_budget(pw, 1.0, 0.55, 0.0)
    assert throttled.pi_w < full.pi_w
    assert power_budget(pw, 0.0, 1.0, 35.0).motors_w == pytest.approx(50.0)


def frames(n, moving):
    rng = np.random.default_rng(0)
    base = rng.integers(0, 255, (240, 320, 3), dtype=np.uint8)
    return [np.roll(base, 7 * i, axis=1) if moving else base.copy() for i in range(n)]


def compute(gate):
    sched = dict(AMR_DEFAULTS["scheduling"], gate=gate)
    return ComputeModel(AMR_DEFAULTS["compute"], sched, [1, 2, 2, 3])


def run_window(model, rung, fr, scale=1.0, swapping=False):
    model.start_window(rung, scale, swapping)
    for f in fr:
        model.on_frame(f)
    return model.end_window()


def test_gate_saves_compute_on_static_scene():
    static_on = run_window(compute(True), 0, frames(30, moving=False))
    static_off = run_window(compute(False), 0, frames(30, moving=False))
    assert static_on.detections < static_off.detections
    assert static_on.util < static_off.util


def test_throttle_and_budget_drop_detections():
    fast = run_window(compute(False), 0, frames(10, True), scale=1.0)
    slow = run_window(compute(False), 0, frames(10, True), scale=0.55)
    assert slow.dropped > fast.dropped
    assert slow.util <= 1.0


def test_cost_list_must_match_ladder():
    with pytest.raises(ValueError):
        ComputeModel(AMR_DEFAULTS["compute"], AMR_DEFAULTS["scheduling"], [1, 2])


def test_yaml_overrides(tmp_path):
    f = tmp_path / "amr.yaml"
    f.write_text("plant: {ambient_c: 22.0}\nsim: {duration_s: 60}\n")
    cfg = load_amr_config(str(f))
    assert cfg["plant"]["ambient_c"] == 22.0
    assert cfg["sim"]["camera_fps"] == AMR_DEFAULTS["sim"]["camera_fps"]
