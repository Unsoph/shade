"""MJCF for the differential-drive AMR: chassis, driven wheels, casters,
payload tote, onboard camera, chase camera and wheel velocity actuators.

Body origin sits at the wheel-axle centre. Wheels spin about +y (positive
spin drives forward). Casters are frictionless spheres (condim=1).
"""

import math

from src.sim.amr.mjcf_props import f


def _camera(name, pos, pitch_deg, fov) -> str:
    p = math.radians(pitch_deg)
    return (f'<camera name="{name}" pos="{f(*pos)}" fovy="{fov:.4g}" '
            f'xyaxes="0 -1 0 {f(-math.sin(p), 0, math.cos(p))}"/>')


def robot_xml(c: dict, cam: dict, x, y, yaw, friction: float, payload_kg: float):
    L, W, H = c["chassis_m"]
    r, w, cr = c["wheel_radius_m"], c["wheel_width_m"], c["caster_radius_m"]
    half_track = c["track_m"] / 2
    cz = H / 2 - r / 2
    wheels = "".join(
        f'<body name="wheel_{side}" pos="0 {s * half_track:.4g} 0">'
        f'<joint name="wheel_{side}" type="hinge" axis="0 1 0" damping="0.01"/>'
        f'<geom type="cylinder" size="{f(r, w / 2)}" euler="90 0 0" mass="{c["wheel_kg"]}" '
        f'friction="{friction:.3g} 0.005 0.0001" rgba="0.1 0.1 0.1 1"/></body>'
        for side, s in (("left", 1), ("right", -1)))
    casters = "".join(
        f'<geom type="sphere" size="{cr}" pos="{f(s * (L / 2 - cr), 0, cr - r)}" '
        f'mass="0.2" condim="1" priority="1" rgba="0.3 0.3 0.3 1"/>' for s in (1, -1))
    tote = ""
    if payload_kg > 0.05:
        tote = (f'<geom type="box" size="0.2 0.15 0.1" pos="{f(-0.02, 0, cz + H / 2 + 0.1)}" '
                f'mass="{payload_kg:.3g}" rgba="0.1 0.35 0.75 1" contype="0" conaffinity="0"/>')
    body = (
        f'<body name="amr" pos="{f(x, y, r + 0.002)}" euler="0 0 {math.degrees(yaw):.4g}">'
        '<freejoint name="amr_root"/>'
        f'<geom name="chassis" type="box" size="{f(L / 2, W / 2, H / 2)}" pos="0 0 {cz:.4g}" '
        f'mass="{c["chassis_kg"]}" material="amr"/>'
        f'<geom type="box" size="{f(0.04, W / 2 - 0.02, 0.03)}" pos="{f(L / 2, 0, cz)}" '
        'rgba="0.1 0.1 0.1 1" contype="0" conaffinity="0"/>'
        f'{wheels}{casters}{tote}'
        + _camera("onboard", cam["mount_m"], cam["pitch_deg"], cam["fov_deg"])
        + _camera("chase", (-2.6, 0, 1.5), -22.0, 60.0)
        + '</body>')
    act = "".join(
        f'<velocity name="drive_{side}" joint="wheel_{side}" kv="{c["wheel_kv"]}" '
        f'forcelimited="true" forcerange="{f(-c["max_wheel_torque_nm"], c["max_wheel_torque_nm"])}"/>'
        for side in ("left", "right"))
    return body, act
