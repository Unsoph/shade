"""AMR digital-twin parameters: defaults merged with an optional YAML file.

Every number is an ASSUMPTION for a generic 24 V differential-drive AMR
carrying a Raspberry Pi 5 in a 20 x 14 m warehouse. Replace robot, battery
and power values with your robot's datasheet, and compute costs with
experiment E1, before quoting results. config/amr_twin.yaml overrides keys.
"""

import yaml

from src.core.config import deep_merge, resolve_path
from src.core.defaults import DEFAULTS as SHADE_DEFAULTS

AMR_DEFAULTS: dict = {
    "sim": {"timestep_s": 0.002, "camera_fps": 10, "duration_s": 900.0, "seed": 0},
    "render": {
        "width": 160, "height": 120,       # frames fed to SHADE's motion gate
        "snap_width": 640, "snap_height": 480,  # saved snapshots
        "shadows": True, "reflection": True,
        # shadows/reflection also on the gate frames? ~5x slower on a CPU
        # renderer; the gate only measures frame change, so off by default
        "gate_effects": False,
    },
    "robot": {
        "chassis_m": [0.50, 0.40, 0.15], "chassis_kg": 20.0,
        "wheel_radius_m": 0.08, "wheel_width_m": 0.04, "wheel_kg": 1.0,
        "track_m": 0.44, "caster_radius_m": 0.04,
        "max_wheel_torque_nm": 6.0, "wheel_kv": 20.0,
        "max_v": 0.8, "max_w": 1.5,       # m/s, rad/s
    },
    "camera": {"fov_deg": 60.0, "mount_m": [0.24, 0.0, 0.30], "pitch_deg": -8.0},
    "nav": {"k_heading": 2.5, "arrive_m": 0.25, "slow_angle_deg": 40.0},
    "route": [  # stations (dwell_s > 0) are where the robot parks
        {"xy": [7.0, -3.0], "dwell_s": 0.0},
        {"xy": [7.0, 3.0], "dwell_s": 45.0},
        {"xy": [-7.0, 3.0], "dwell_s": 0.0},
        {"xy": [-7.0, -3.0], "dwell_s": 45.0},
    ],
    "world": {
        "hall_m": [20.0, 14.0], "wall_h_m": 5.0,
        "racks": [[0.0, 0.0, 12.0, 1.4, 0.0], [0.0, 6.2, 16.0, 1.0, 0.0],
                  [0.0, -6.2, 16.0, 1.0, 0.0], [9.4, 0.0, 6.0, 1.0, 1.5708]],
        "pallets": [[-9.2, -2.0], [-9.2, -0.5], [-9.2, 1.0], [-5.8, -4.7], [-7.4, -4.7]],
        "pillars": [[-4.0, 4.6], [4.0, 4.6], [-4.0, -4.6], [4.0, -4.6]],
        "cones": [[-8.0, 3.9], [-7.3, 4.0], [-5.2, -3.9], [8.3, -1.0]],
        "forklift": [-8.6, 5.0, 0.0],
        "table": [8.2, 4.6],
        "lanes_y": [2.3, 3.7, -2.3, -3.7], "lanes_x": [-8.0, 8.0],
        "ceiling_lights": [[-6, -3], [0, -3], [6, -3], [-6, 3], [0, 3], [6, 3]],
    },
    "people": {
        "count": 6, "speed_mean": 1.25, "speed_sd": 0.15,
        "pause_prob": 0.3, "pause_s": [2.0, 8.0],
        "grid_x": [-8.2, -5.5, -2.0, 2.0, 5.5, 8.2],
        "grid_y": [-4.0, -1.6, 1.6, 4.0],
    },
    "random": {  # everything stochastic is drawn from sim.seed
        "camera_noise_sd": 2.0,         # pixel noise, grey levels
        "dwell_jitter": 0.4,            # station time x U(1-j, 1+j)
        "cost_sd": 0.10,                # log-normal noise on detection cost
        "burst_rate_per_s": 1 / 90,     # background CPU bursts (other processes)
        "burst_s": [5.0, 20.0], "burst_util": [0.10, 0.30],
        "ambient_sd_c": 1.5, "ambient_tau_s": 600.0,  # slow ambient drift
        "friction_jitter": 0.10, "payload_kg": [0.0, 10.0],
    },
    "battery": {"capacity_wh": 240.0, "v_full": 25.2, "v_empty": 19.8,  # 6S Li-ion
                "r_internal_ohm": 0.08, "soc0": 0.9, "dcdc_min_v": 20.5},
    "power": {"electronics_w": 4.0, "pi_idle_w": 3.0, "pi_full_w": 8.0,
              "motor_eff": 0.7, "rolling_crr": 0.02},
    "compute": {
        "base_util": 0.08,
        "det_cost_s": [0.09, 0.09, 0.025, 0.018],  # CPU-s per detection per rung
        "swap_s": 3.0, "swap_util": 0.35, "memory_pct": 55.0,
    },
    "plant": {"ambient_c": 35.0},
    # content gate on; box shifting is not modelled (no real detections)
    "scheduling": dict(SHADE_DEFAULTS["scheduling"], gate=True, shift=False),
    "policy": {},
}


def load_amr_config(path: str | None = None) -> dict:
    """Defaults merged with the YAML file at `path` (if given)."""
    if not path:
        return deep_merge(AMR_DEFAULTS, {})
    with open(resolve_path(path), "r") as f:
        return deep_merge(AMR_DEFAULTS, yaml.safe_load(f) or {})
