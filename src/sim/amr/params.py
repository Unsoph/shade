"""AMR digital-twin parameters: defaults merged with an optional YAML file.

Every number here is an ASSUMPTION for a generic 24 V differential-drive
AMR carrying a Raspberry Pi 5. Replace robot, battery and power values with
your robot's datasheet, and the compute costs with experiment E1, before
quoting any result. config/amr_twin.yaml overrides any key below.
"""

import yaml

from src.core.config import deep_merge, resolve_path
from src.core.defaults import DEFAULTS as SHADE_DEFAULTS

AMR_DEFAULTS: dict = {
    "sim": {
        "physics_hz": 240,       # PyBullet step rate
        "camera_fps": 10,        # onboard camera frame rate
        "duration_s": 900.0,
        "seed": 0,
        "gui": False,            # True opens the PyBullet window
    },
    "robot": {
        "chassis_m": [0.50, 0.40, 0.15],   # length, width, height
        "chassis_kg": 20.0,
        "wheel_radius_m": 0.08,
        "wheel_width_m": 0.04,
        "wheel_kg": 1.0,
        "track_m": 0.44,                   # distance between wheel centres
        "caster_radius_m": 0.04,
        "max_wheel_torque_nm": 6.0,
        "max_v": 0.8,                      # m/s
        "max_w": 1.5,                      # rad/s
    },
    "camera": {
        "width": 320, "height": 240, "fov_deg": 70.0,
        "mount_m": [0.24, 0.0, 0.30],      # forward, left, up from base
        "pitch_deg": -8.0, "near_m": 0.05, "far_m": 25.0,
    },
    "nav": {"k_heading": 2.5, "arrive_m": 0.25, "slow_angle_deg": 40.0},
    # Warehouse loop; dwell_s = time parked at a station (static scene).
    "route": [
        {"xy": [4.0, -3.0], "dwell_s": 0.0},
        {"xy": [4.0, 3.0], "dwell_s": 45.0},
        {"xy": [-4.0, 3.0], "dwell_s": 0.0},
        {"xy": [-4.0, -3.0], "dwell_s": 45.0},
    ],
    "world": {
        "arena_m": 12.0,
        # shelves: [x, y, size_x, size_y, height]
        "shelves": [[0.0, 0.0, 5.0, 1.0, 1.8], [6.2, 0.0, 0.6, 4.0, 1.8],
                    [-6.2, 0.0, 0.6, 4.0, 1.8], [0.0, 5.4, 6.0, 0.6, 1.8],
                    [0.0, -5.4, 6.0, 0.6, 1.8]],
        # walkers move between a and b (visual only, no collisions)
        "walkers": [{"a": [-3.0, 4.3], "b": [3.0, 4.3], "speed": 0.9},
                    {"a": [5.0, -4.5], "b": [5.0, 4.5], "speed": 0.6},
                    {"a": [-3.0, -4.3], "b": [3.0, -4.3], "speed": 1.1}],
    },
    "battery": {
        "capacity_wh": 240.0, "v_full": 25.2, "v_empty": 19.8,  # 6S Li-ion
        "r_internal_ohm": 0.08, "soc0": 0.9,
        "dcdc_min_v": 20.5,      # Pi 5 V converter drops out below this
    },
    "power": {
        "electronics_w": 4.0,    # motor drivers, sensors, networking
        "pi_idle_w": 3.0, "pi_full_w": 8.0,
        "motor_eff": 0.7,
        "rolling_crr": 0.02,     # tyre/floor rolling resistance coefficient
    },
    "compute": {
        "base_util": 0.08,       # capture, display, control loop
        # CPU-seconds per detection, one per ladder rung (assumed, see E1)
        "det_cost_s": [0.09, 0.09, 0.025, 0.018],
        "swap_s": 3.0,           # model preload + warm-up time
        "swap_util": 0.35,       # extra CPU while preloading
        "memory_pct": 55.0,
    },
    "plant": {"ambient_c": 35.0},  # PlantConfig overrides (enclosure air)
    # content gate on; box shifting is not modelled (no real detections)
    "scheduling": dict(SHADE_DEFAULTS["scheduling"], gate=True, shift=False),
    "policy": {},                # overrides for the DecisionEngine policy
}


def load_amr_config(path: str | None = None) -> dict:
    """Defaults merged with the YAML file at `path` (if given)."""
    if not path:
        return deep_merge(AMR_DEFAULTS, {})
    with open(resolve_path(path), "r") as f:
        return deep_merge(AMR_DEFAULTS, yaml.safe_load(f) or {})
