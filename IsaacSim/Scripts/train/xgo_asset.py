"""Shared XGO (mini2) asset definition: joint limits, actuators, articulation cfg.

Used by both the multi-agent maze environment and the standalone locomotion
environment so the robot is defined once.
"""

from __future__ import annotations

import math
from pathlib import Path

from pxr import Usd, UsdPhysics, UsdShade

from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg

import xgo_kinematics

# Path within a spawned scene to the articulation root and the joints scope.
XGO_PATH = "_ROBOTS_/xgo_lite/Geometry/world/base_link"
XGO_JOINTS_SCOPE = "_ROBOTS_/xgo_lite/Physics"

# Standalone asset, for environments that do not need the whole maze scene.
XGO_USD_PATH = str(
    Path(__file__).resolve().parents[2] / "Robots" / "mini2_description" / "mini2_description.usda"
)

XGO_LEG_JOINTS = xgo_kinematics.xgo_joint_names()
XGO_NUM_JOINTS = 12

# Real per-joint travel, from the vendor's xgo_ros driver config
# (IsaacSim/Robots/mini2_description/reference/xgomini.yaml). The source URDF
# declares every revolute joint as type="continuous" with no <limit>, so the USD is
# faithful to it and these must be authored before simulation starts -- the physics
# parser rejects infinite limits outright.
#
# xgo.cpp:162 indexes joint_limit[i % 3] across the 12 leg joints, so all four legs
# share three pairs ordered by position within the leg. Mapping to the N1/N2/N3
# names is inferred from the numeric suffix; the hip (N3, attached to base_link)
# taking the tightest range is what hip abduction should look like.
XGO_JOINT_LIMITS_DEG = {
    "1": (-73.0, 57.0),   # N1, lower leg
    "2": (-66.0, 93.0),   # N2, upper leg
    "3": (-31.0, 31.0),   # N3, hip abduction
}
XGO_ARM_LIMITS_DEG = {
    "1": (-90.0, 75.0),
    "2": (-50.0, 85.0),
    "3": (-65.0, 65.0),
}
XGO_DEFAULT_LIMIT_DEG = (-90.0, 90.0)

# Body height above the feet. The vendor driver puts the real range at 75-115 mm
# (body_limit[2] in xgomini.yaml) and defaults foot height to 108 mm (xgo.h:53).
XGO_STAND_HEIGHT = 0.09

# Nothing in these scenes authors a physics material, so contacts otherwise fall
# back to the PhysX default. Rubber feet on a hard floor want more grip.
XGO_FOOT_FRICTION = 1.2


def find_joints_scope(stage, root_path: str) -> str | None:
    """Locate the scope holding the revolute joints beneath `root_path`.

    The standalone asset and the composed maze scene nest the robot differently,
    so the path is discovered rather than hardcoded.
    """
    root = stage.GetPrimAtPath(root_path)
    if not root.IsValid():
        return None
    for prim in Usd.PrimRange(root):
        if prim.GetTypeName() == "PhysicsRevoluteJoint":
            return str(prim.GetPath().GetParentPath())
    return None


def limit_for(joint_name: str) -> tuple[float, float]:
    """Hardware travel in degrees for a USD joint named e.g. 'tn__13_Joint_'."""
    digits = "".join(c for c in joint_name if c.isdigit())
    if not digits:
        return XGO_DEFAULT_LIMIT_DEG
    leg, index = digits[0], digits[-1]
    table = XGO_ARM_LIMITS_DEG if leg == "5" else XGO_JOINT_LIMITS_DEG
    return table.get(index, XGO_DEFAULT_LIMIT_DEG)


def joint_limits_rad() -> tuple[list[float], list[float]]:
    """Lower and upper travel for the leg joints, in XGO_LEG_JOINTS order."""
    lower = [math.radians(limit_for(n)[0]) for n in XGO_LEG_JOINTS]
    upper = [math.radians(limit_for(n)[1]) for n in XGO_LEG_JOINTS]
    return lower, upper


def fix_joint_limits(stage, joints_scope_path: str) -> int:
    """Author finite limits on any unbounded revolute joint under `joints_scope_path`."""
    scope = stage.GetPrimAtPath(joints_scope_path)
    if not scope.IsValid():
        return 0

    fixed = 0
    for joint_prim in Usd.PrimRange(scope):
        if joint_prim.GetTypeName() != "PhysicsRevoluteJoint":
            continue
        joint = UsdPhysics.RevoluteJoint(joint_prim)

        lower = joint.GetLowerLimitAttr().Get()
        upper = joint.GetUpperLimitAttr().Get()
        # leave authored limits alone
        if lower is not None and upper is not None and lower > -1e30 and upper < 1e30:
            continue

        lo, hi = limit_for(joint_prim.GetName())
        joint.CreateLowerLimitAttr().Set(lo)
        joint.CreateUpperLimitAttr().Set(hi)
        fixed += 1

    return fixed


def apply_foot_friction(stage, robot_root: str, material_path: str) -> None:
    """Bind a high-friction physics material to the XGO's lower legs.

    Bound on each link rather than its colliders: the collision geometry lives
    inside instance proxies, where USD refuses edits. Bindings inherit to
    descendants, so this reaches them anyway.
    """
    material = UsdPhysics.MaterialAPI.Apply(
        UsdShade.Material.Define(stage, material_path).GetPrim()
    )
    material.CreateStaticFrictionAttr().Set(XGO_FOOT_FRICTION)
    material.CreateDynamicFrictionAttr().Set(XGO_FOOT_FRICTION)
    material.CreateRestitutionAttr().Set(0.0)

    for leg in (1, 2, 3, 4):
        link = stage.GetPrimAtPath(
            f"{robot_root}/tn__{leg}3_Link_/tn__{leg}2_Link_/tn__{leg}1_Link_"
        )
        if not link.IsValid():
            continue
        UsdShade.MaterialBindingAPI.Apply(link).Bind(
            UsdShade.Material(stage.GetPrimAtPath(material_path)),
            bindingStrength=UsdShade.Tokens.weakerThanDescendants,
            materialPurpose="physics",
        )


def actuators() -> dict:
    """Leg and arm actuator groups.

    Every joint must belong to a group or IsaacLab warns the articulation is only
    partially actuated, so the arm and gripper get a group that just holds them.
    """
    return {
        "legs": ImplicitActuatorCfg(
            joint_names_expr=XGO_LEG_JOINTS,
            stiffness=20.0,
            damping=0.5,
        ),
        # covers 50, 51, 52, 53 and 500
        "arm": ImplicitActuatorCfg(
            joint_names_expr=["tn__5.*_Joint_"],
            stiffness=50.0,
            damping=1.0,
        ),
    }
