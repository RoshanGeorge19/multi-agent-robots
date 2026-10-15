"""Exact kinematics for the XGO (mini2), derived from the asset's own joint frames.

Why this exists
---------------
The repo ships `quadruped_leg_kinematics.LegIK`, a closed-form solver written for a
conventional quadruped (hip about X, knee about Y, zero pose hanging straight down).
That solver cannot drive this robot: at all-zero joint angles the XGO's legs lie
flat in the horizontal plane, and every joint reports `axis = Z` with the real
orientation folded into its frame.

That is not a conversion artifact. The source URDF
(`IsaacSim/Robots/mini2_description/reference/mini2_description.urdf`) declares
every joint as `axis="0 0 1"` with the orientation in `<origin rpy>`, which is
ordinary SolidWorks exporter output. Deriving kinematics from the URDF directly
still does not work, because the USD's joint frames are not a transcription of the
URDF's -- a URDF-based FK was measured 5 cm off the simulator.

So the kinematics are read from the **USD joint frames themselves**
(`localPos0/localRot0/localPos1/localRot1`), which is what the simulator actually
integrates. Verified against the running simulation to **1e-6 m**.

Convention note: USD `Gf` matrices are row-vector (`v' = v * M`), so quaternion
matrices are transposed on the way in for column-vector math. Getting this wrong
was worth 0.14 m of error.
"""

from __future__ import annotations

import torch
from pxr import Gf, Usd, UsdPhysics

# Leg order used throughout, and which USD leg index each corresponds to.
# Derived from the measured hip offsets: leg 1 -> (+x, +y), 2 -> (+x, -y),
# 4 -> (-x, +y), 3 -> (-x, -y).
LEG_NAMES = ("FL", "FR", "BL", "BR")
LEG_USD_INDEX = {"FL": 1, "FR": 2, "BL": 4, "BR": 3}

# Within a leg the chain is base -> N3 -> N2 -> N1, so N3 is the hip.
JOINT_ORDER = (3, 2, 1)

# Foot contact point in the lower-link frame, measured from the collision meshes
# (22,814 vertices per link, traversed with Usd.TraverseInstanceProxies -- a plain
# PrimRange does not descend into instance proxies and finds nothing). The
# extreme vertex is identical on all four legs at y = -0.085. XGOModel's
# wrist_length of 0.0804 is close but not this asset's value.
FOOT_OFFSET = (0.0, -0.085, 0.0)

# Hip origins in the base frame, from the USD joint frames.
HIP_OFFSETS = {
    "FL": (0.075, 0.0225, 0.0),
    "FR": (0.075, -0.0225, 0.0),
    "BL": (-0.075, 0.0225, 0.0),
    "BR": (-0.075, -0.0225, 0.0),
}

# Body height above the feet. The vendor driver puts the real range at 75-115 mm
# (body_limit[2] in xgomini.yaml) and defaults foot height to 108 mm (xgo.h:53).
STAND_HEIGHT = 0.09


def xgo_joint_names() -> list[str]:
    """USD joint names in [FL, FR, BL, BR] x [hip, upper, lower] order."""
    return [
        f"tn__{LEG_USD_INDEX[leg]}{joint}_Joint_"
        for leg in LEG_NAMES
        for joint in JOINT_ORDER
    ]


def _quat_to_matrix(quat) -> list[list[float]]:
    """Gf quaternion -> 3x3 rotation matrix for column-vector math."""
    m = Gf.Matrix3d(Gf.Quatd(quat.GetReal(), Gf.Vec3d(*quat.GetImaginary())))
    # transpose: USD matrices are row-vector convention
    return [[m[j][i] for j in range(3)] for i in range(3)]


def read_joint_frames(stage, joints_scope: str) -> dict[str, dict]:
    """Read every revolute joint's parent/child frames out of the USD."""
    frames = {}
    for prim in Usd.PrimRange(stage.GetPrimAtPath(joints_scope)):
        if prim.GetTypeName() != "PhysicsRevoluteJoint":
            continue
        joint = UsdPhysics.Joint(prim)
        frames[prim.GetName()] = {
            "pos0": list(joint.GetLocalPos0Attr().Get()),
            "rot0": _quat_to_matrix(joint.GetLocalRot0Attr().Get()),
            "pos1": list(joint.GetLocalPos1Attr().Get()),
            "rot1": _quat_to_matrix(joint.GetLocalRot1Attr().Get()),
        }
    return frames


def _rot_z(angle: torch.Tensor) -> torch.Tensor:
    c, s = torch.cos(angle), torch.sin(angle)
    z, o = torch.zeros_like(angle), torch.ones_like(angle)
    return torch.stack(
        [
            torch.stack([c, -s, z], dim=-1),
            torch.stack([s, c, z], dim=-1),
            torch.stack([z, z, o], dim=-1),
        ],
        dim=-2,
    )


class XGOLegKinematics:
    """Batched FK/IK for the four legs, in the base_link frame."""

    def __init__(self, frames: dict[str, dict], device):
        self.device = device
        self._foot_offset = torch.tensor(FOOT_OFFSET, device=device)

        # Stack the per-leg constants so forward() batches all four legs together
        # instead of looping over them in Python. Each entry is one step of the
        # chain (hip, upper, lower) holding (4, ...) tensors.
        self._steps = []
        for joint in JOINT_ORDER:
            rot0, pos0, rot1_inv, pos1 = [], [], [], []
            for leg in LEG_NAMES:
                f = frames[f"tn__{LEG_USD_INDEX[leg]}{joint}_Joint_"]
                r1 = torch.tensor(f["rot1"], device=device)
                rot0.append(torch.tensor(f["rot0"], device=device))
                pos0.append(torch.tensor(f["pos0"], device=device))
                rot1_inv.append(r1.T)
                # child frame is entered by the inverse of (pos1, rot1)
                pos1.append(-(r1.T @ torch.tensor(f["pos1"], device=device)))
            self._steps.append(
                {
                    "rot0": torch.stack(rot0),           # (4, 3, 3)
                    "pos0": torch.stack(pos0),           # (4, 3)
                    "rot1_inv": torch.stack(rot1_inv),   # (4, 3, 3)
                    "child_offset": torch.stack(pos1),   # (4, 3)
                }
            )

    def forward(self, joint_angles: torch.Tensor, offset: torch.Tensor | None = None) -> torch.Tensor:
        """Foot positions for each leg, in the base frame.

        Args:
            joint_angles: Shape (N, 4, 3), ordered [FL, FR, BL, BR] x [hip, upper, lower].
            offset: Point in the lower-link frame to report. Defaults to
                :data:`FOOT_OFFSET`; pass zeros to get the link origin instead.

        Returns:
            Positions, shape (N, 4, 3).
        """
        n = joint_angles.shape[0]
        rot = torch.eye(3, device=self.device).expand(n, 4, 3, 3)
        pos = torch.zeros(n, 4, 3, device=self.device)

        for k, step in enumerate(self._steps):
            # parent -> joint frame 0
            pos = pos + torch.einsum("nlij,lj->nli", rot, step["pos0"])
            rot = rot @ step["rot0"]
            # the joint's own rotation, about local Z
            rot = rot @ _rot_z(joint_angles[:, :, k])
            # joint frame 1 -> child link
            pos = pos + torch.einsum("nlij,lj->nli", rot, step["child_offset"])
            rot = rot @ step["rot1_inv"]

        if offset is None:
            offset = self._foot_offset
        return pos + torch.einsum("nlij,j->nli", rot, offset)

    def inverse(
        self,
        target: torch.Tensor,
        seed: torch.Tensor,
        iterations: int = 24,
        damping: float = 0.02,
    ) -> torch.Tensor:
        """Damped least-squares IK for all legs at once.

        A closed-form solve would need the geometry re-derived by hand in this
        asset's unusual frame convention. DLS reuses the verified FK instead, is
        batched, and degrades gracefully on unreachable targets rather than
        producing NaNs.

        Args:
            target: Desired foot-link origins, shape (N, 4, 3).
            seed: Starting joint angles, shape (N, 4, 3).
            iterations: Gauss-Newton steps.
            damping: Levenberg-Marquardt damping.

        Returns:
            Joint angles, shape (N, 4, 3).
        """
        angles = seed.clone()
        n = angles.shape[0]
        eps = 1e-4

        for _ in range(iterations):
            current = self.forward(angles)
            error = target - current                      # (N, 4, 3)

            # numeric Jacobian: 3 columns per leg, one per joint
            columns = []
            for j in range(3):
                bumped = angles.clone()
                bumped[:, :, j] += eps
                columns.append((self.forward(bumped) - current) / eps)
            jac = torch.stack(columns, dim=-1)            # (N, 4, 3, 3)

            jt = jac.transpose(-1, -2)
            normal = jt @ jac
            normal = normal + damping * torch.eye(3, device=self.device).expand_as(normal)

            rhs = torch.einsum("nlij,nlj->nli", jt, error)
            step = torch.linalg.solve(normal, rhs)

            angles = angles + step

        return angles


def stance_foot_targets(device, height: float = STAND_HEIGHT, spread: float = 0.0) -> torch.Tensor:
    """Neutral stance: each foot directly below its hip, `height` below the body.

    Args:
        device: Torch device.
        height: Body height above the feet, in metres.
        spread: Extra outward offset in y, positive pushes the feet wider.

    Returns:
        Foot targets in the base frame, shape (4, 3).
    """
    rows = []
    for leg in LEG_NAMES:
        hx, hy, _ = HIP_OFFSETS[leg]
        side = 1.0 if hy > 0 else -1.0
        rows.append([hx, hy + side * spread, -height])
    return torch.tensor(rows, device=device)
