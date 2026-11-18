"""AMR twin with PyBullet: robot physics, camera and the closed loop.

Skipped when pybullet is not installed (it is a simulation-only dependency,
see simulation/requirements.txt).
"""

import math

import pytest

pytest.importorskip("pybullet")

import pybullet as p  # noqa: E402

from src.sim.amr.camera import Camera  # noqa: E402
from src.sim.amr.params import load_amr_config  # noqa: E402
from src.sim.amr.robot import DiffDrive  # noqa: E402
from src.sim.amr.twin import AmrTwin  # noqa: E402
from src.sim.amr.world import World, connect  # noqa: E402
from src.sim.policies import Shade, Static  # noqa: E402


@pytest.fixture
def scene():
    cfg = load_amr_config()
    cid = connect(False, cfg["sim"]["physics_hz"])
    World(cid, dict(cfg["world"], shelves=[], walkers=[]))
    yield cfg, cid
    p.disconnect(cid)


def test_drives_straight_at_commanded_speed(scene):
    cfg, cid = scene
    bot = DiffDrive(cid, cfg["robot"], 0.0, 0.0, 0.0)
    bot.command(0.5, 0.0)
    p.stepSimulation(physicsClientId=cid)
    assert bot.wheel_power_w() > 0  # accelerating takes torque
    for _ in range(cfg["sim"]["physics_hz"] * 4 - 1):
        p.stepSimulation(physicsClientId=cid)
    x, y, yaw = bot.pose()
    assert 1.6 < x < 2.1            # ~0.5 m/s for 4 s, minus spin-up
    assert abs(y) < 0.05 and abs(yaw) < 0.05
    assert 22.0 < bot.mass_kg < 24.0


def test_turns_on_the_spot(scene):
    cfg, cid = scene
    bot = DiffDrive(cid, cfg["robot"], 0.0, 0.0, 0.0)
    bot.command(0.0, 1.0)
    for _ in range(cfg["sim"]["physics_hz"]):
        p.stepSimulation(physicsClientId=cid)
    x, y, yaw = bot.pose()
    assert math.hypot(x, y) < 0.05
    assert 0.6 < yaw < 1.1


def test_camera_frame_shape(scene):
    cfg, cid = scene
    bot = DiffDrive(cid, cfg["robot"], 0.0, 0.0, 0.0)
    frame = Camera(cid, cfg["camera"]).capture(*bot.base_state())
    assert frame.shape == (cfg["camera"]["height"], cfg["camera"]["width"], 3)
    assert frame.std() > 1.0        # not a blank image


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
    assert rows[-1]["temp_c"] > rows[0]["temp_c"]


def test_shade_degrades_when_hot():
    # start the Pi already near its limit so the engine must step down
    twin = AmrTwin(short_cfg(ambient_c=60.0), Shade("shade", 4, [1, 1, .3, .2]))
    twin.plant.temp = 82.0
    try:
        rows = twin.run(15)
    finally:
        twin.close()
    assert max(r["next_rung"] for r in rows) >= 2
    assert twin.swaps >= 1           # 640 -> 320 needs a different model file
