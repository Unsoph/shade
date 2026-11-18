"""AMR digital twin with SHADE onboard.

Each simulated second:
  1. the robot follows its route (PyBullet, `physics_hz`), the onboard camera
     renders `camera_fps` frames, and SHADE's real Scheduler decides which
     frames get a detection (ComputeModel);
  2. that CPU load heats the Pi (ThermalPlant) and, with the motors, drains
     the battery (Battery);
  3. a HealthSnapshot built from temperature, load, throttle and
     undervoltage flags goes to the policy (e.g. the real DecisionEngine),
     which picks the next ladder rung. A rung that needs a different model
     file costs a preload window (`swap_s` seconds at `swap_util` extra CPU).
"""

import math
from dataclasses import replace

import pybullet as p

from src.core.defaults import DEFAULTS as SHADE_DEFAULTS
from src.core.ladder import parse_ladder
from src.core.snapshots import HealthSnapshot
from src.sim.amr.battery import Battery, power_budget
from src.sim.amr.camera import Camera
from src.sim.amr.compute import ComputeModel
from src.sim.amr.nav import WaypointNav
from src.sim.amr.robot import DiffDrive
from src.sim.amr.world import World, connect
from src.sim.plant import PlantConfig, ThermalPlant


class AmrTwin:
    def __init__(self, cfg: dict, policy):
        self.cfg, self.policy = cfg, policy
        s = cfg["sim"]
        self.fps, self.hz = s["camera_fps"], s["physics_hz"]
        self.cid = connect(s["gui"], self.hz)
        self.world = World(self.cid, cfg["world"])
        route = cfg["route"]
        (x0, y0), (x1, y1) = route[-1]["xy"], route[0]["xy"]
        self.robot = DiffDrive(self.cid, cfg["robot"], x0, y0, math.atan2(y1 - y0, x1 - x0))
        self.camera = Camera(self.cid, cfg["camera"])
        self.nav = WaypointNav(route, cfg["nav"], cfg["robot"]["max_v"], cfg["robot"]["max_w"])
        self.rungs = parse_ladder(SHADE_DEFAULTS)
        self.compute = ComputeModel(cfg["compute"], cfg["scheduling"],
                                    [r.detect_every for r in self.rungs])
        self.plant = ThermalPlant(replace(PlantConfig(), **cfg["plant"]), s["seed"])
        self.battery = Battery(cfg["battery"])
        self.t, self.rung, self.scale = 0.0, 0, 1.0
        self.swap_left = 0.0
        self.switches = self.swaps = 0

    def close(self) -> None:
        if p.isConnected(self.cid):
            p.disconnect(self.cid)

    def _drive_second(self, on_frame=None) -> tuple[float, bool]:
        """Advance one second of driving and camera frames; returns
        (mean wheel power W, parked at end)."""
        sub = max(1, self.hz // self.fps)
        energy, parked = 0.0, False
        rolling_n = self.cfg["power"]["rolling_crr"] * self.robot.mass_kg * 9.81
        for _ in range(self.fps):
            x, y, yaw = self.robot.pose()
            cmd = self.nav.update(self.t, x, y, yaw)
            parked = cmd.parked
            self.robot.command(cmd.v, cmd.w)
            for _ in range(sub):
                p.stepSimulation(physicsClientId=self.cid)
                drive_w = self.robot.wheel_power_w() + rolling_n * self.robot.speed()
                energy += drive_w / self.hz
            self.t += 1.0 / self.fps
            self.world.step(self.t)
            frame = self.camera.capture(*self.robot.base_state())
            ran = self.compute.on_frame(frame)
            if on_frame:
                on_frame(self.t, frame, ran)
        return energy, parked

    def step_second(self, on_frame=None) -> dict:
        swapping = self.swap_left > 0
        self.compute.start_window(self.rung, self.scale, swapping)
        wheel_w, parked = self._drive_second(on_frame)
        win = self.compute.end_window()
        temp, self.scale = self.plant.step(win.util, 1.0, self.t)
        pw = power_budget(self.cfg["power"], win.util, self.scale, wheel_w)
        volts = self.battery.step(pw.total_w, 1.0)
        flags = (["Thermally throttled"] if self.plant.throttled else []) + \
            (["Undervoltage"] if self.battery.undervoltage else [])
        snap = HealthSnapshot(
            timestamp=self.t, fps=float(win.detections), cpu_temp=temp,
            cpu_util=win.util, memory_percent=self.cfg["compute"]["memory_pct"],
            throttle_status=", ".join(flags) or "Clean")
        rung_used = self.rung
        new = self.policy.decide(snap)
        if new != self.rung:
            self.switches += 1
            if not self.rungs[new].same_model(self.rungs[self.rung]):
                self.swaps += 1
                self.swap_left = self.cfg["compute"]["swap_s"]
            self.rung = new
        self.swap_left = max(0.0, self.swap_left - 1.0)
        x, y, yaw = self.robot.pose()
        engine = getattr(self.policy, "engine", None)
        return {
            "t_s": round(self.t, 3), "x": x, "y": y, "yaw": yaw,
            "speed": self.robot.speed(), "parked": int(parked),
            "waypoint": self.nav.index, "laps": self.nav.laps,
            "rung": rung_used, "next_rung": self.rung,
            "state": engine.state.value if engine else "",
            "temp_c": temp, "throttled": int(self.plant.throttled),
            "util": win.util, "detections": win.detections, "wanted": win.wanted,
            "dropped": win.dropped, "motion": win.motion, "swapping": int(swapping),
            "soc": self.battery.soc, "voltage": volts,
            "undervoltage": int(self.battery.undervoltage),
            "pi_w": pw.pi_w, "motors_w": pw.motors_w, "total_w": pw.total_w,
        }

    def run(self, duration_s: float, on_frame=None) -> list[dict]:
        rows = []
        while self.t < duration_s - 1e-9:
            rows.append(self.step_second(on_frame))
        return rows
