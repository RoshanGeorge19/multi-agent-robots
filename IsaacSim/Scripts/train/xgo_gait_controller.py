"""Batched trot gait for the XGO, turning a velocity command into foot targets.

Why this is not a port of `quadruped_gait_generator.BezierGait`
--------------------------------------------------------------
The shipped generator is per-robot scalar numpy carrying a lot of mutable state --
a phase clock, touch-down times, stance/swing flags, previous foot positions -- and
its phase advances on *contact events*. Vectorising it faithfully would need
per-foot contact sensors, which this scene does not have: the contact sensor is on
`base_link` only, so there is nothing to detect touch-down with.

This is a fixed-phase trot instead: the clock advances on time rather than contact,
diagonal pairs move together, and every leg's target is closed-form in the phase
variable. That vectorises over environments with no per-env branching, needs no
extra sensors, and is simple enough to verify directly.

The interface is the one the gait generator would have exposed -- linear and
angular velocity in, foot targets out -- so swapping a faithful Bezier port back in
later only changes this file.
"""

from __future__ import annotations

import torch

from xgo_kinematics import LEG_NAMES, HIP_OFFSETS, STAND_HEIGHT

# Diagonal pairs move together: FL with BR, FR with BL.
PHASE_OFFSETS = {"FL": 0.0, "FR": 0.5, "BL": 0.5, "BR": 0.0}

# Vendor limits, from xgo_ros/config/xgomini.yaml.
VX_MAX = 0.3      # m/s
VYAW_MAX = 1.2    # rad/s


class XGOTrotGait:
    """Fixed-phase trot. Stateless except for the per-environment phase clock."""

    def __init__(
        self,
        num_envs: int,
        device,
        period: float = 0.5,
        duty: float = 0.5,
        step_height: float = 0.015,
        stand_height: float = STAND_HEIGHT,
    ):
        self.device = device
        self.period = period
        self.duty = duty
        self.step_height = step_height

        self.phase = torch.zeros(num_envs, device=device)

        # neutral foot position under each hip
        self.nominal = torch.tensor(
            [[HIP_OFFSETS[leg][0], HIP_OFFSETS[leg][1], -stand_height] for leg in LEG_NAMES],
            device=device,
        )
        # hip position in the horizontal plane, for the yaw-rate contribution
        self.hip_xy = torch.tensor(
            [[HIP_OFFSETS[leg][0], HIP_OFFSETS[leg][1]] for leg in LEG_NAMES], device=device
        )
        self.offsets = torch.tensor([PHASE_OFFSETS[leg] for leg in LEG_NAMES], device=device)

    def reset(self, env_ids: torch.Tensor | None = None) -> None:
        if env_ids is None:
            self.phase.zero_()
        else:
            self.phase[env_ids] = 0.0

    def step(
        self, command: torch.Tensor, dt: float, body_height: torch.Tensor | None = None
    ) -> torch.Tensor:
        """Advance the clock and return foot targets in the base frame.

        Args:
            command: Actions in [-1, 1], shape (N, 2) as (forward, yaw).
            dt: Control timestep in seconds.
            body_height: Accepted and ignored. Feeding the measured height back
                into the stance depth is unstable: pressing the feet down raises
                the body, which deepens the plan, which raises it further. It ran
                away to 0.138 m when commanded to stand still. The stance plane is
                fixed instead, at the height the robot actually settles to.

        Returns:
            Foot targets, shape (N, 4, 3).
        """
        self.phase = torch.remainder(self.phase + dt / self.period, 1.0)

        vx = command[:, 0].clamp(-1.0, 1.0) * VX_MAX
        wz = command[:, 1].clamp(-1.0, 1.0) * VYAW_MAX

        # Foot velocity relative to the body during stance is the opposite of the
        # body's own motion at that hip: -(v + omega x r).
        foot_vx = -(vx.unsqueeze(-1) - wz.unsqueeze(-1) * self.hip_xy[:, 1])
        foot_vy = -(wz.unsqueeze(-1) * self.hip_xy[:, 0]).expand_as(foot_vx)

        # A full stride is covered over the stance phase.
        stance_time = self.period * self.duty
        stride_x = foot_vx * stance_time
        stride_y = foot_vy * stance_time

        leg_phase = torch.remainder(self.phase.unsqueeze(-1) + self.offsets, 1.0)

        stance = leg_phase < self.duty
        # stance: sweep from +half stride to -half stride
        stance_frac = (leg_phase / self.duty).clamp(0.0, 1.0)
        stance_scale = 0.5 - stance_frac
        # swing: return the other way
        swing_frac = ((leg_phase - self.duty) / (1.0 - self.duty)).clamp(0.0, 1.0)
        swing_scale = swing_frac - 0.5

        scale = torch.where(stance, stance_scale, swing_scale)

        # lift only during swing, a smooth arc that starts and ends at ground level
        lift = torch.where(
            stance,
            torch.zeros_like(swing_frac),
            self.step_height * torch.sin(torch.pi * swing_frac),
        )

        targets = self.nominal.unsqueeze(0).expand(command.shape[0], 4, 3).clone()
        targets[:, :, 0] = targets[:, :, 0] + scale * stride_x
        targets[:, :, 1] = targets[:, :, 1] + scale * stride_y

        targets[:, :, 2] = self.nominal[:, 2].unsqueeze(0) + lift

        return targets
