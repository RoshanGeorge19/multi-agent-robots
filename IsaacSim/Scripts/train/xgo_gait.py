"""Batched kinematics for the XGO (mini2) quadruped.

The repo ships a working single-robot gait stack under IsaacSim/Scripts/controllers
(`quadruped_leg_kinematics.LegIK`, `quadruped_kinematics.XGOModel`,
`quadruped_gait_generator.BezierGait`). That code is numpy, scalar, and solves one
robot at a time, so it cannot drive a vectorised IsaacLab environment where every
env holds its own XGO. This module is a torch port of the parts needed for
locomotion, batched over environments and legs and running on the sim device.

The geometry constants are not guesses: they were read back out of the USD joint
frames (see JOINT_FRAME_OFFSETS below) and agree with XGOModel's defaults.
"""

from __future__ import annotations

import torch

# ---------------------------------------------------------------------------
# Geometry, measured from the USD joint frames
# ---------------------------------------------------------------------------
# localPos0 of each joint, i.e. the offset from its parent body:
#   base_link -> N3_Link : (+/-0.075, +/-0.0225, 0)   -> hip_x/2, hip_y/2
#   N3_Link   -> N2_Link : 0.030988                   -> shoulder_length
#   N2_Link   -> N1_Link : 0.059900                   -> elbow_length
# wrist_length is the foot offset inside N1_Link, which no joint frame exposes;
# it is taken from XGOModel and validated empirically by the standing test.
SHOULDER_LENGTH = 0.030988
ELBOW_LENGTH = 0.059900
WRIST_LENGTH = 0.080400

HIP_X = 0.150
HIP_Y = 0.045
FOOT_X = 0.0825
FOOT_Y = 0.095

# nominal body height above the feet
STAND_HEIGHT = 0.13

# Leg order used throughout this module.
LEG_NAMES = ("FL", "FR", "BL", "BR")

# Which USD leg index is which. Derived from the measured hip offsets:
#   leg 1 -> (+x, +y) front-left    leg 2 -> (+x, -y) front-right
#   leg 4 -> (-x, +y) back-left     leg 3 -> (-x, -y) back-right
LEG_USD_INDEX = {"FL": 1, "FR": 2, "BL": 4, "BR": 3}

# Within a leg the chain is base -> N3 -> N2 -> N1, so N3 is the shoulder
# (closest to the body) and N1 the wrist. LegIK returns angles in that same
# shoulder/elbow/wrist order, so joints are listed N3, N2, N1.
JOINT_ORDER = (3, 2, 1)

# LegIK differentiates left and right legs only by the sign of shoulder_length.
LEG_SIDE_SIGN = {"FL": 1.0, "FR": -1.0, "BL": 1.0, "BR": -1.0}


def xgo_joint_names() -> list[str]:
    """USD joint names in [FL, FR, BL, BR] x [shoulder, elbow, wrist] order."""
    return [
        f"tn__{LEG_USD_INDEX[leg]}{joint}_Joint_"
        for leg in LEG_NAMES
        for joint in JOINT_ORDER
    ]


def hip_offsets(device: str | torch.device) -> torch.Tensor:
    """Hip position relative to the body centre, shape (4, 3)."""
    return torch.tensor(
        [
            [HIP_X / 2.0, HIP_Y / 2.0, 0.0],    # FL
            [HIP_X / 2.0, -HIP_Y / 2.0, 0.0],   # FR
            [-HIP_X / 2.0, HIP_Y / 2.0, 0.0],   # BL
            [-HIP_X / 2.0, -HIP_Y / 2.0, 0.0],  # BR
        ],
        device=device,
    )


def stance_foot_positions(device: str | torch.device, height: float = STAND_HEIGHT) -> torch.Tensor:
    """Neutral foot positions relative to the body centre, shape (4, 3)."""
    return torch.tensor(
        [
            [FOOT_X / 2.0, FOOT_Y / 2.0, -height],
            [FOOT_X / 2.0, -FOOT_Y / 2.0, -height],
            [-FOOT_X / 2.0, FOOT_Y / 2.0, -height],
            [-FOOT_X / 2.0, -FOOT_Y / 2.0, -height],
        ],
        device=device,
    )


def side_signs(device: str | torch.device) -> torch.Tensor:
    return torch.tensor([LEG_SIDE_SIGN[leg] for leg in LEG_NAMES], device=device)


def leg_ik(hip_to_foot: torch.Tensor, side_sign: torch.Tensor) -> torch.Tensor:
    """Closed-form leg IK, batched over environments and legs.

    A direct port of `quadruped_leg_kinematics.LegIK`. The scalar original
    branches on legtype to flip the sign of shoulder_length in one atan2; here
    that becomes a multiply, so left and right legs solve in the same call.
    Its two guard clauses (domain clamp, negative-sqrt clamp) become clamps,
    which keeps the solve finite when a target is out of reach instead of
    producing NaNs that would poison the joint targets.

    Args:
        hip_to_foot: Foot position relative to the hip. Shape (..., 4, 3).
        side_sign: +1 for left legs, -1 for right legs. Shape (4,).

    Returns:
        Joint angles in (shoulder, elbow, wrist) order. Shape (..., 4, 3).
    """
    x = hip_to_foot[..., 0]
    y = hip_to_foot[..., 1]
    z = hip_to_foot[..., 2]

    # leg domain, clamped on reach breach
    domain = (
        y**2 + z**2 - SHOULDER_LENGTH**2 + x**2 - ELBOW_LENGTH**2 - WRIST_LENGTH**2
    ) / (2.0 * WRIST_LENGTH * ELBOW_LENGTH)
    domain = domain.clamp(-1.0, 1.0)

    wrist_angle = torch.atan2(-torch.sqrt(1.0 - domain**2), domain)

    sqrt_component = (y**2 + z**2 - SHOULDER_LENGTH**2).clamp(min=0.0)
    sqrt_component = torch.sqrt(sqrt_component)

    shoulder_angle = -torch.atan2(z, y) - torch.atan2(
        sqrt_component, side_sign * SHOULDER_LENGTH
    )

    elbow_angle = torch.atan2(-x, sqrt_component) - torch.atan2(
        WRIST_LENGTH * torch.sin(wrist_angle),
        ELBOW_LENGTH + WRIST_LENGTH * torch.cos(wrist_angle),
    )

    return torch.stack((-shoulder_angle, elbow_angle, wrist_angle), dim=-1)


def foot_targets_to_joint_targets(
    foot_pos_body: torch.Tensor, hip_offset: torch.Tensor, side_sign: torch.Tensor
) -> torch.Tensor:
    """Body-frame foot targets -> flat joint targets.

    Args:
        foot_pos_body: Foot positions in the body frame. Shape (N, 4, 3).
        hip_offset: Hip offsets from :func:`hip_offsets`. Shape (4, 3).
        side_sign: From :func:`side_signs`. Shape (4,).

    Returns:
        Joint targets ordered to match :func:`xgo_joint_names`. Shape (N, 12).
    """
    hip_to_foot = foot_pos_body - hip_offset.unsqueeze(0)
    angles = leg_ik(hip_to_foot, side_sign)
    return angles.reshape(foot_pos_body.shape[0], -1)


def stance_joint_angles(height: float = STAND_HEIGHT) -> dict[str, float]:
    """Neutral standing pose as a {joint_name: angle} map for ArticulationCfg."""
    device = "cpu"
    targets = foot_targets_to_joint_targets(
        stance_foot_positions(device, height).unsqueeze(0),
        hip_offsets(device),
        side_signs(device),
    )[0]
    return dict(zip(xgo_joint_names(), (float(v) for v in targets)))
