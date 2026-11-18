"""Differential-drive AMR body for PyBullet, generated from parameters.

Base link origin sits at the wheel-axle centre: a box chassis above it, two
driven wheels on continuous joints (axis +y, positive spin drives forward)
and two frictionless spherical casters front and rear. Wheels are velocity
controlled with a torque limit; mechanical wheel power is reported for the
battery model.
"""

import math
import tempfile

import pybullet as p

URDF = """<?xml version="1.0"?>
<robot name="shade_amr">
  <link name="base">
    <inertial><origin xyz="0 0 {cz}"/><mass value="{cm}"/>
      <inertia ixx="{bx}" iyy="{by}" izz="{bz}" ixy="0" ixz="0" iyz="0"/></inertial>
    <visual><origin xyz="0 0 {cz}"/><geometry><box size="{L} {W} {H}"/></geometry>
      <material name="body"><color rgba="0.95 0.55 0.1 1"/></material></visual>
    <collision><origin xyz="0 0 {cz}"/><geometry><box size="{L} {W} {H}"/></geometry></collision>
  </link>
{wheels}
{casters}
</robot>
"""

WHEEL = """  <link name="{name}">
    <inertial><mass value="{m}"/><inertia ixx="{ia}" iyy="{iy}" izz="{ia}" ixy="0" ixz="0" iyz="0"/></inertial>
    <visual><origin rpy="1.5708 0 0"/><geometry><cylinder radius="{r}" length="{w}"/></geometry>
      <material name="tyre"><color rgba="0.1 0.1 0.1 1"/></material></visual>
    <collision><origin rpy="1.5708 0 0"/><geometry><cylinder radius="{r}" length="{w}"/></geometry></collision>
  </link>
  <joint name="{name}_joint" type="{jt}"><parent link="base"/><child link="{name}"/>
    <origin xyz="{x} {y} {z}"/><axis xyz="0 1 0"/></joint>"""

CASTER = """  <link name="{name}">
    <inertial><mass value="0.2"/><inertia ixx="1e-4" iyy="1e-4" izz="1e-4" ixy="0" ixz="0" iyz="0"/></inertial>
    <visual><geometry><sphere radius="{r}"/></geometry></visual>
    <collision><geometry><sphere radius="{r}"/></geometry></collision>
  </link>
  <joint name="{name}_joint" type="fixed"><parent link="base"/><child link="{name}"/>
    <origin xyz="{x} 0 {z}"/></joint>"""


def build_urdf(c: dict) -> str:
    L, W, H = c["chassis_m"]
    m, r, w, wm = c["chassis_kg"], c["wheel_radius_m"], c["wheel_width_m"], c["wheel_kg"]
    cr = c["caster_radius_m"]
    box = lambda a, b: m * (a * a + b * b) / 12.0  # noqa: E731
    wheels = "\n".join(
        WHEEL.format(name=n, m=wm, r=r, w=w, x=0, y=s * c["track_m"] / 2, z=0,
                     ia=wm * (3 * r * r + w * w) / 12, iy=wm * r * r / 2,
                     jt="continuous")
        for n, s in (("wheel_left", 1), ("wheel_right", -1)))
    casters = "\n".join(
        CASTER.format(name=n, r=cr, x=s * (L / 2 - cr), z=cr - r)
        for n, s in (("caster_front", 1), ("caster_rear", -1)))
    cz = H / 2 - r / 2
    return URDF.format(cz=cz, cm=m, L=L, W=W, H=H, bx=box(W, H), by=box(L, H),
                       bz=box(L, W), wheels=wheels, casters=casters)


class DiffDrive:
    def __init__(self, cid: int, cfg: dict, x: float, y: float, yaw: float):
        self.cid, self.c = cid, cfg
        with tempfile.NamedTemporaryFile("w", suffix=".urdf", delete=False) as f:
            f.write(build_urdf(cfg))
        orn = p.getQuaternionFromEuler([0, 0, yaw])
        self.body = p.loadURDF(f.name, [x, y, cfg["wheel_radius_m"] + 0.002], orn,
                               physicsClientId=cid)
        names = {p.getJointInfo(self.body, j, physicsClientId=cid)[1].decode(): j
                 for j in range(p.getNumJoints(self.body, physicsClientId=cid))}
        self.left, self.right = names["wheel_left_joint"], names["wheel_right_joint"]
        for j in (names["caster_front_joint"], names["caster_rear_joint"]):
            p.changeDynamics(self.body, j, lateralFriction=0.0, spinningFriction=0.0,
                             rollingFriction=0.0, physicsClientId=cid)
        for j in (self.left, self.right):
            p.changeDynamics(self.body, j, lateralFriction=1.2, physicsClientId=cid)
        self.v_cmd = self.w_cmd = 0.0
        self.mass_kg = sum(p.getDynamicsInfo(self.body, j, physicsClientId=cid)[0]
                           for j in range(-1, len(names)))

    def command(self, v: float, w: float) -> None:
        """Body speed (m/s) and yaw rate (rad/s) -> wheel speeds."""
        c = self.c
        self.v_cmd, self.w_cmd = v, w
        half, r = c["track_m"] / 2, c["wheel_radius_m"]
        for j, wheel in ((self.left, (v - w * half) / r), (self.right, (v + w * half) / r)):
            p.setJointMotorControl2(self.body, j, p.VELOCITY_CONTROL, targetVelocity=wheel,
                                    force=c["max_wheel_torque_nm"], physicsClientId=self.cid)

    def pose(self) -> tuple[float, float, float]:
        pos, orn = p.getBasePositionAndOrientation(self.body, physicsClientId=self.cid)
        return pos[0], pos[1], p.getEulerFromQuaternion(orn)[2]

    def base_state(self):
        return p.getBasePositionAndOrientation(self.body, physicsClientId=self.cid)

    def speed(self) -> float:
        lin, _ = p.getBaseVelocity(self.body, physicsClientId=self.cid)
        return math.hypot(lin[0], lin[1])

    def wheel_power_w(self) -> float:
        """Positive mechanical power delivered by both wheel motors."""
        total = 0.0
        for j in (self.left, self.right):
            _, vel, _, torque = p.getJointState(self.body, j, physicsClientId=self.cid)
            total += max(vel * torque, 0.0)
        return total
