"""AMR digital twin (MuJoCo) with SHADE onboard.

Each simulated second:
  1. the robot follows its route (MuJoCo physics), workers walk the aisles,
     the onboard camera renders `camera_fps` frames (plus pixel noise), and
     SHADE's real Scheduler decides which frames get a detection;
  2. that CPU load, plus random background bursts, heats the Pi
     (ThermalPlant, with a drifting ambient) and, with the motors, drains the
     battery;
  3. a HealthSnapshot (temperature, load, throttle and undervoltage flags)
     goes to the policy (e.g. the real DecisionEngine), which picks the next
     rung. A rung needing a different model file costs a preload window.
All randomness comes from `sim.seed` (see disturb.py).
"""

import math
from dataclasses import replace

from src.core.defaults import DEFAULTS as SHADE_DEFAULTS
from src.core.ladder import parse_ladder
from src.core.snapshots import HealthSnapshot
from src.sim.amr.battery import Battery, power_budget
from src.sim.amr.compute import ComputeModel
from src.sim.amr.disturb import Disturbances, spawn_rngs
from src.sim.amr.engine import MjEngine
from src.sim.amr.nav import WaypointNav
from src.sim.plant import PlantConfig, ThermalPlant


class AmrTwin:
    def __init__(self, cfg: dict, policy, tex_dir=None):
        self.cfg, self.policy = cfg, policy
        s, rnd = cfg["sim"], cfg["random"]
        rngs = spawn_rngs(s["seed"])
        self.fps = s["camera_fps"]
        self.sub = max(1, round(1.0 / (self.fps * s["timestep_s"])))
        route = cfg["route"]
        (x0, y0), (x1, y1) = route[-1]["xy"], route[0]["xy"]
        self.engine = MjEngine(cfg, rngs, (x0, y0, math.atan2(y1 - y0, x1 - x0)), tex_dir)
        r = cfg["robot"]
        self.nav = WaypointNav(route, cfg["nav"], r["max_v"], r["max_w"],
                               rngs["nav"], rnd["dwell_jitter"])
        self.rungs = parse_ladder(SHADE_DEFAULTS)
        self.compute = ComputeModel(cfg["compute"], cfg["scheduling"],
                                    [g.detect_every for g in self.rungs],
                                    rngs["compute"], rnd["cost_sd"])
        self.plant = ThermalPlant(replace(PlantConfig(), **cfg["plant"]), s["seed"])
        self.disturb = Disturbances(rnd, self.plant.cfg.ambient_c,
                                    rngs["disturb"], rngs["camera"])
        self.battery = Battery(cfg["battery"])
        self.t, self.rung, self.scale = 0.0, 0, 1.0
        self.swap_left = 0.0
        self.switches = self.swaps = 0

    def close(self) -> None:
        self.engine.close()

    def _drive_second(self, on_frame=None) -> tuple[float, bool]:
        """One second of driving and camera frames -> (mean drive W, parked)."""
        eng, dt = self.engine, self.cfg["sim"]["timestep_s"]
        rolling_n = self.cfg["power"]["rolling_crr"] * eng.mass_kg * 9.81
        energy, parked = 0.0, False
        for _ in range(self.fps):
            cmd = self.nav.update(self.t, *eng.pose())
            parked = cmd.parked
            eng.command(cmd.v, cmd.w)
            eng.move_people(1.0 / self.fps)
            for _ in range(self.sub):
                eng.step()
                energy += (eng.wheel_power_w() + rolling_n * eng.speed()) * dt
            self.t += 1.0 / self.fps
            frame = self.disturb.noisy(eng.render("onboard"))
            ran = self.compute.on_frame(frame)
            if on_frame:
                on_frame(self.t, frame, ran)
        return energy, parked

    def step_second(self, on_frame=None) -> dict:
        swapping = self.swap_left > 0
        ambient, burst = self.disturb.step(1.0)
        self.plant.cfg.ambient_c = ambient
        self.compute.start_window(self.rung, self.scale, swapping, extra_util=burst)
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
        rung_used, new = self.rung, self.policy.decide(snap)
        if new != self.rung:
            self.switches += 1
            if not self.rungs[new].same_model(self.rungs[self.rung]):
                self.swaps += 1
                self.swap_left = self.cfg["compute"]["swap_s"]
            self.rung = new
        self.swap_left = max(0.0, self.swap_left - 1.0)
        x, y, yaw = self.engine.pose()
        engine = getattr(self.policy, "engine", None)
        return {
            "t_s": round(self.t, 3), "x": x, "y": y, "yaw": yaw,
            "speed": self.engine.speed(), "parked": int(parked),
            "waypoint": self.nav.index, "laps": self.nav.laps,
            "rung": rung_used, "next_rung": self.rung,
            "state": engine.state.value if engine else "",
            "ambient_c": ambient, "burst_util": burst,
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
