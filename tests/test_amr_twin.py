"""AMR twin on MuJoCo: robot physics, scene, camera, randomness, closed loop.

Skipped when mujoco is not installed (a simulation-only dependency, see
simulation/requirements.txt) or no OpenGL context can be created.
"""

import math
import os
import sys

import pytest

if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
    os.environ.setdefault("MUJOCO_GL", "egl")
mujoco = pytest.importorskip("mujoco")

from src.sim.amr.disturb import Disturbances, spawn_rngs  # noqa: E402
from src.sim.amr.params import load_amr_config  # noqa: E402
from src.sim.policies import Shade, Static  # noqa: E402

try:
    from src.sim.amr.engine import MjEngine
    from src.sim.amr.twin import AmrTwin
    _probe = MjEngine(load_amr_config(), spawn_rngs(0), (0.0, -3.0, 0.0))
    _probe.close()
except Exception as exc:  # no EGL / OpenGL available
    pytest.skip(f"MuJoCo rendering unavailable: {exc}", allow_module_level=True)


def engine(seed=0, pose=(-7.0, -3.0, 0.0)):
    return MjEngine(load_amr_config(), spawn_rngs(seed), pose)


def test_drives_straight_at_commanded_speed():
    e = engine()
    e.command(0.5, 0.0)
    e.step(250)                       # 0.5 s: accelerating takes torque
    assert e.wheel_power_w() > 0
    e.step(1750)                      # 4 s total
    x, y, yaw = e.pose()
    assert 1.6 < x + 7.0 < 2.1
    assert abs(y + 3.0) < 0.05 and abs(yaw) < 0.05
    assert 22.0 < e.mass_kg < 36.0    # robot + random payload
    e.close()


def test_turns_on_the_spot():
    e = engine()
    e.command(0.0, 1.0)
    e.step(500)
    x, y, yaw = e.pose()
    assert math.hypot(x + 7.0, y + 3.0) < 0.05
    assert 0.6 < yaw < 1.1
    e.close()


def test_camera_frames_and_snapshots():
    e = engine()
    cfg = load_amr_config()["render"]
    small, snap = e.render("onboard"), e.render("chase", snapshot=True)
    assert small.shape == (cfg["height"], cfg["width"], 3)
    assert snap.shape == (cfg["snap_height"], cfg["snap_width"], 3)
    assert small.std() > 5 and snap.std() > 5
    e.close()


def test_same_seed_same_world_different_seed_differs():
    a, b, c = engine(1), engine(1), engine(2)
    assert a.meta == b.meta and a.meta != c.meta
    assert a.model.ngeom == b.model.ngeom
    for e in (a, b, c):
        e.close()


def test_workers_walk():
    e = engine()
    start = [(w.x, w.y) for w in e.workers]
    for _ in range(50):
        e.move_people(0.1)
    moved = sum(math.dist(s, (w.x, w.y)) > 0.5 for s, w in zip(start, e.workers))
    assert moved >= len(e.workers) // 2
    e.close()


def test_disturbances_are_seeded_and_bounded():
    rnd = load_amr_config()["random"]
    runs = []
    for _ in range(2):
        r = spawn_rngs(5)
        d = Disturbances(rnd, 35.0, r["disturb"], r["camera"])
        runs.append([d.step(1.0) for _ in range(600)])
    assert runs[0] == runs[1]
    amb = [a for a, _ in runs[0]]
    assert 25 < min(amb) and max(amb) < 45
    assert any(b > 0 for _, b in runs[0])


def short_cfg(**plant):
    cfg = load_amr_config()
    cfg["sim"]["camera_fps"] = 5
    cfg["plant"].update(plant)
    return cfg


def test_closed_loop_rows_and_battery():
    twin = AmrTwin(short_cfg(), Static(0))
    try:
        rows = twin.run(12)
    finally:
        twin.close()
    assert len(rows) == 12
    assert rows[-1]["soc"] < rows[0]["soc"]
    assert math.hypot(rows[-1]["x"] - rows[0]["x"], rows[-1]["y"] - rows[0]["y"]) > 2
    assert all(0.0 <= r["util"] <= 1.0 for r in rows)


def test_shade_degrades_when_hot():
    twin = AmrTwin(short_cfg(ambient_c=60.0), Shade("shade", 4, [1, 1, .3, .2]))
    twin.plant.temp = 82.0
    try:
        rows = twin.run(15)
    finally:
        twin.close()
    assert max(r["next_rung"] for r in rows) >= 2
    assert twin.swaps >= 1
