"""Velocity-tracking locomotion task for the XGO quadruped.

Learning to walk inside the maze environment is the wrong shape of problem: the
XGO would have to solve standing, walking and navigation against one reward, with
collision penalties and a shared episode boundary interfering throughout. This is
the standard IsaacLab locomotion setup instead -- flat ground, one robot, a
commanded body velocity to track -- which is how the ANYmal and Unitree tasks are
posed.

Actions are **offsets from the calibrated standing pose** (see xgo_kinematics),
not absolute joint targets. The robot therefore starts every episode already
standing, and exploration perturbs a working stance rather than searching 12-DoF
joint space for one.
"""

from __future__ import annotations

import math

import torch
import omni.usd
from pxr import Usd

import isaaclab.sim as sim_utils
from isaaclab.assets import Articulation, ArticulationCfg
from isaaclab.envs import DirectRLEnv, DirectRLEnvCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sensors import ContactSensor, ContactSensorCfg
from isaaclab.sim import SimulationCfg
from isaaclab.terrains import TerrainImporterCfg
from isaaclab.utils.configclass import configclass
from isaaclab.utils.math import quat_apply_inverse
import warp as wp

import xgo_asset
import xgo_kinematics

ROBOT_ROOT = "Geometry/world/base_link"

# How far, in radians, an action of +/-1 moves a joint from its stance angle.
ACTION_SCALE = 0.4

# Command sampling ranges, capped by the vendor's own limits
# (vx_max 0.3, vyaw_max 1.2 in xgomini.yaml).
CMD_VX_RANGE = (-0.25, 0.25)
CMD_WZ_RANGE = (-1.0, 1.0)

# Termination thresholds.
MIN_HEIGHT = 0.045
MIN_UPRIGHT = 0.5


@configclass
class XGOLocomotionSceneCfg(InteractiveSceneCfg):
    """Deliberately empty.

    In the direct workflow the robot, terrain and sensors are created by
    _setup_scene(). Declaring them here as well makes InteractiveScene spawn them
    a second time, which fails with "A prim already exists at path".
    """


@configclass
class XGOLocomotionCfg(DirectRLEnvCfg):
    decimation = 4
    episode_length_s = 12.0

    action_space = xgo_asset.XGO_NUM_JOINTS
    # projected gravity (3), base lin vel (3), base ang vel (3),
    # joint pos offset (12), joint vel (12), previous actions (12), command (2)
    observation_space = 3 + 3 + 3 + 12 + 12 + 12 + 2
    state_space = 0

    sim = SimulationCfg(device="cuda:0", dt=1.0 / 120.0, render_interval=decimation)

    scene: XGOLocomotionSceneCfg = XGOLocomotionSceneCfg(
        num_envs=2048, env_spacing=2.0, replicate_physics=True
    )

    terrain: TerrainImporterCfg = TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="plane",
        collision_group=-1,
    )

    robot: ArticulationCfg = ArticulationCfg(
        prim_path="/World/envs/env_.*/Robot",
        spawn=sim_utils.UsdFileCfg(
            usd_path=xgo_asset.XGO_USD_PATH,
            # required before a ContactSensor can bind to any of its bodies
            activate_contact_sensors=True,
        ),
        init_state=ArticulationCfg.InitialStateCfg(
            pos=(0.0, 0.0, xgo_asset.XGO_STAND_HEIGHT + 0.01),
            rot=(0.0, 0.0, 0.0, 1.0),
        ),
        actuators=xgo_asset.actuators(),
    )

    contact: ContactSensorCfg = ContactSensorCfg(
        prim_path="/World/envs/env_.*/Robot/" + ROBOT_ROOT,
        update_period=0.0,
        history_length=3,
        track_pose=False,
    )

    # Per-foot contact, which the base sensor cannot provide. Without it there is
    # no way to reward stride length, and velocity tracking alone is solved by a
    # high-frequency shuffle: tiny steps produce the commanded velocity with
    # minimal risk of falling, so PPO finds that long before it finds a gait.
    #
    # One sensor per foot. A single sensor with a wildcard over the leg index
    # resolves to just one body per environment, however the pattern is written.
    foot_contacts: dict[int, ContactSensorCfg] = {
        leg: ContactSensorCfg(
            prim_path=f"/World/envs/env_.*/Robot/{ROBOT_ROOT}"
            f"/tn__{leg}3_Link_/tn__{leg}2_Link_/tn__{leg}1_Link_",
            update_period=0.0,
            history_length=3,
            track_air_time=True,
            track_pose=False,
            # The default 1.0 N is too high for this machine: it weighs well under
            # a kilogram, and a loaded foot reports only ~0.7 N. At the default no
            # foot ever counts as landed, so air time never resets and the reward
            # is silently dead.
            force_threshold=0.1,
        )
        for leg in (1, 2, 3, 4)
    }

    # --- reward weights ---
    rew_track_lin = 1.5        # match the commanded forward velocity
    rew_track_ang = 0.75       # match the commanded yaw rate
    rew_alive = 0.5
    rew_fell = -10.0
    pen_vertical_vel = -2.0    # discourage bouncing
    pen_roll_pitch = -0.05
    pen_joint_accel = -2.5e-7
    pen_action_rate = -0.01
    pen_joint_limit = -0.5     # discourage sitting on the end stops

    # Pay for keeping each foot airborne. This is what produces a stride rather
    # than a shuffle: without it the policy is free to satisfy the velocity
    # command with very short, very fast steps.
    rew_feet_air_time = 1.0
    feet_air_time_target = 0.3   # seconds aloft per step
    # only pay it when actually asked to move, or standing still gets rewarded
    # for marching on the spot
    air_time_command_threshold = 0.05

    tracking_sigma = 0.25


class XGOLocomotionEnv(DirectRLEnv):
    cfg: XGOLocomotionCfg

    def __init__(self, cfg: XGOLocomotionCfg, render_mode: str | None = None, **kwargs):
        super().__init__(cfg, render_mode, **kwargs)

        self._leg_ids, _ = self.robot.find_joints(xgo_asset.XGO_LEG_JOINTS, preserve_order=True)

        lower, upper = xgo_asset.joint_limits_rad()
        self._joint_lower = torch.tensor(lower, device=self.device)
        self._joint_upper = torch.tensor(upper, device=self.device)

        stage = omni.usd.get_context().get_stage()
        scope = xgo_asset.find_joints_scope(stage, "/World/envs/env_0/Robot")
        if scope is None:
            raise RuntimeError("Could not locate the XGO's joint scope under /World/envs/env_0/Robot")
        self.kin = xgo_kinematics.XGOLegKinematics(
            xgo_kinematics.read_joint_frames(stage, scope), self.device
        )

        stance_targets = xgo_kinematics.stance_foot_targets(
            self.device, height=xgo_asset.XGO_STAND_HEIGHT
        ).unsqueeze(0).expand(self.num_envs, 4, 3)
        self.stance = self.kin.inverse(
            stance_targets,
            torch.zeros((self.num_envs, 4, 3), device=self.device),
            iterations=60,
            damping=1e-4,
        ).reshape(self.num_envs, xgo_asset.XGO_NUM_JOINTS)

        self.commands = torch.zeros((self.num_envs, 2), device=self.device)
        self.prev_actions = torch.zeros((self.num_envs, self.cfg.action_space), device=self.device)
        self.prev_joint_vel = torch.zeros((self.num_envs, len(self._leg_ids)), device=self.device)

    def _setup_scene(self):
        self.robot = Articulation(self.cfg.robot)
        self.scene.articulations["robot"] = self.robot

        self.cfg.terrain.num_envs = self.cfg.scene.num_envs
        self.cfg.terrain.env_spacing = self.cfg.scene.env_spacing
        self.terrain = self.cfg.terrain.class_type(self.cfg.terrain)

        self.scene.clone_environments(copy_from_source=False)

        self.contact = ContactSensor(self.cfg.contact)
        self.scene.sensors["contact"] = self.contact

        self.foot_contacts = {}
        for leg, foot_cfg in self.cfg.foot_contacts.items():
            sensor = ContactSensor(foot_cfg)
            self.foot_contacts[leg] = sensor
            self.scene.sensors[f"foot_contact_{leg}"] = sensor

        stage = omni.usd.get_context().get_stage()
        for env_id in range(self.cfg.scene.num_envs):
            root = f"/World/envs/env_{env_id}/Robot"
            scope = xgo_asset.find_joints_scope(stage, root)
            if scope is not None:
                xgo_asset.fix_joint_limits(stage, scope)
            xgo_asset.apply_foot_friction(
                stage, f"{root}/{ROBOT_ROOT}", f"{root}/foot_material"
            )
            xgo_asset.apply_foot_contact_api(stage, f"{root}/{ROBOT_ROOT}")

    # ------------------------------------------------------------------
    # Physics
    # ------------------------------------------------------------------

    def _pre_physics_step(self, actions: torch.Tensor) -> None:
        self.actions = actions.clone()

    def _apply_action(self) -> None:
        target = self.stance + self.actions.clamp(-1.0, 1.0) * ACTION_SCALE
        target = target.clamp(self._joint_lower, self._joint_upper)
        self.robot.set_joint_position_target_index(target=target, joint_ids=self._leg_ids)

    # ------------------------------------------------------------------
    # Observations
    # ------------------------------------------------------------------

    def _projected_gravity(self) -> torch.Tensor:
        quat = wp.to_torch(self.robot.data.root_quat_w)
        gravity = torch.zeros((self.num_envs, 3), device=self.device)
        gravity[:, 2] = -1.0
        return quat_apply_inverse(quat, gravity)

    def _get_observations(self) -> dict:
        joint_pos = wp.to_torch(self.robot.data.joint_pos)[:, self._leg_ids]
        joint_vel = wp.to_torch(self.robot.data.joint_vel)[:, self._leg_ids]

        obs = torch.cat(
            (
                self._projected_gravity(),
                wp.to_torch(self.robot.data.root_lin_vel_b),
                wp.to_torch(self.robot.data.root_ang_vel_b),
                joint_pos - self.stance,
                joint_vel,
                self.prev_actions,
                self.commands,
            ),
            dim=-1,
        )
        return {"policy": obs}

    # ------------------------------------------------------------------
    # Rewards
    # ------------------------------------------------------------------

    def _get_rewards(self) -> torch.Tensor:
        lin_vel = wp.to_torch(self.robot.data.root_lin_vel_b)
        ang_vel = wp.to_torch(self.robot.data.root_ang_vel_b)
        joint_vel = wp.to_torch(self.robot.data.joint_vel)[:, self._leg_ids]

        # exponential tracking: full reward only when the command is matched
        lin_err = (self.commands[:, 0] - lin_vel[:, 0]) ** 2
        ang_err = (self.commands[:, 1] - ang_vel[:, 2]) ** 2
        track_lin = torch.exp(-lin_err / self.cfg.tracking_sigma) * self.cfg.rew_track_lin
        track_ang = torch.exp(-ang_err / self.cfg.tracking_sigma) * self.cfg.rew_track_ang

        fell = self._fallen()
        alive = (~fell).float() * self.cfg.rew_alive
        fall_pen = fell.float() * self.cfg.rew_fell

        vertical = lin_vel[:, 2] ** 2 * self.cfg.pen_vertical_vel
        roll_pitch = torch.sum(ang_vel[:, :2] ** 2, dim=-1) * self.cfg.pen_roll_pitch

        # feet air time: rewarded on the step a foot lands, by how long it flew
        first_contact = torch.cat(
            [
                torch.as_tensor(s.compute_first_contact(self.step_dt), device=self.device)
                for s in self.foot_contacts.values()
            ],
            dim=1,
        )
        last_air_time = torch.cat(
            [
                torch.as_tensor(s.data.last_air_time, device=self.device)
                for s in self.foot_contacts.values()
            ],
            dim=1,
        )
        commanded = (
            torch.linalg.vector_norm(self.commands, dim=-1) > self.cfg.air_time_command_threshold
        ).float()
        air_time = (
            torch.sum((last_air_time - self.cfg.feet_air_time_target) * first_contact, dim=1)
            * commanded
            * self.cfg.rew_feet_air_time
        )

        joint_accel = torch.sum(
            ((joint_vel - self.prev_joint_vel) / self.step_dt) ** 2, dim=-1
        ) * self.cfg.pen_joint_accel
        self.prev_joint_vel = joint_vel.clone()

        action_rate = torch.sum(
            (self.actions - self.prev_actions) ** 2, dim=-1
        ) * self.cfg.pen_action_rate
        self.prev_actions = self.actions.clone()

        # how far each joint sits outside 90% of its travel
        joint_pos = wp.to_torch(self.robot.data.joint_pos)[:, self._leg_ids]
        span = (self._joint_upper - self._joint_lower) * 0.5
        centre = (self._joint_upper + self._joint_lower) * 0.5
        overrun = ((joint_pos - centre).abs() - 0.9 * span).clamp(min=0.0)
        limit_pen = torch.sum(overrun, dim=-1) * self.cfg.pen_joint_limit

        return (
            track_lin + track_ang + alive + fall_pen + air_time
            + vertical + roll_pitch + joint_accel + action_rate + limit_pen
        )

    # ------------------------------------------------------------------
    # Termination
    # ------------------------------------------------------------------

    def _upright(self) -> torch.Tensor:
        quat = wp.to_torch(self.robot.data.root_quat_w)
        return 1.0 - 2.0 * (quat[:, 0] ** 2 + quat[:, 1] ** 2)

    def _fallen(self) -> torch.Tensor:
        height = wp.to_torch(self.robot.data.root_pos_w)[:, 2] - self.scene.env_origins[:, 2]
        body_contact = (
            torch.linalg.vector_norm(wp.to_torch(self.contact.data.net_forces_w), dim=-1) > 1.0
        ).any(dim=1)
        return (height < MIN_HEIGHT) | (self._upright() < MIN_UPRIGHT) | body_contact

    def _get_dones(self) -> tuple[torch.Tensor, torch.Tensor]:
        time_out = self.episode_length_buf >= self.max_episode_length - 1
        return self._fallen(), time_out

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def _reset_idx(self, env_ids):
        if env_ids is None:
            env_ids = self.robot._ALL_INDICES
        env_ids = torch.as_tensor(env_ids, device=self.device, dtype=torch.long)
        super()._reset_idx(env_ids)

        n = len(env_ids)

        root_pose = torch.zeros((n, 7), device=self.device)
        root_pose[:, :2] = self.scene.env_origins[env_ids, :2]
        root_pose[:, 2] = xgo_asset.XGO_STAND_HEIGHT + 0.01
        yaw = torch.rand(n, device=self.device) * 2.0 * math.pi
        # IsaacLab 3.x quaternion order is (x, y, z, w)
        root_pose[:, 5] = torch.sin(yaw / 2.0)
        root_pose[:, 6] = torch.cos(yaw / 2.0)

        self.robot.write_root_pose_to_sim(root_pose, env_ids)
        self.robot.write_root_velocity_to_sim(torch.zeros((n, 6), device=self.device), env_ids)
        self.robot.write_joint_velocity_to_sim_index(
            velocity=torch.zeros((n, self.robot.num_joints), device=self.device),
            joint_ids=None,
            env_ids=env_ids,
        )
        # start standing, not collapsed
        self.robot.write_joint_position_to_sim_index(
            position=self.stance[env_ids], joint_ids=self._leg_ids, env_ids=env_ids
        )
        self.robot.write_data_to_sim()

        self.commands[env_ids, 0] = (
            torch.rand(n, device=self.device) * (CMD_VX_RANGE[1] - CMD_VX_RANGE[0])
            + CMD_VX_RANGE[0]
        )
        self.commands[env_ids, 1] = (
            torch.rand(n, device=self.device) * (CMD_WZ_RANGE[1] - CMD_WZ_RANGE[0])
            + CMD_WZ_RANGE[0]
        )

        self.prev_actions[env_ids] = 0.0
        self.prev_joint_vel[env_ids] = 0.0
