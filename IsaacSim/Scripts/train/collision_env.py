# from __future__ import annotations 

# import argparse
# from isaaclab.app import AppLauncher

# parser = argparse.ArgumentParser(description="Collision Avoidance Environment")
# AppLauncher.add_app_launcher_args(parser)
# args_cli = parser.parse_args()

# app_launcher = AppLauncher(args_cli)
# simulation_app = app_launcher.app


from __future__ import annotations 

# NOTE: the Omniverse app is launched by the entrypoint (train.py) via AppLauncher.
# This module must NOT create a SimulationApp -- a second Kit boot in the same
# process deadlocks against the first one.

# from isaacsim.robot.experimental.wheeled_robots.controllers import DifferentialController
import omni.physics.tensors
import omni.usd
import math
import os
from pathlib import Path
from collections.abc import Sequence
import numpy as np
import torch
import isaaclab
import isaaclab_physx
import isaaclab.sim as sim_utils
from isaaclab.assets import Articulation, ArticulationCfg, AssetBaseCfg
from isaaclab.envs import DirectMARLEnv, DirectMARLEnvCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.sim import SimulationCfg
from isaaclab.utils.configclass import configclass
from isaaclab.sim.schemas import ArticulationRootPropertiesCfg
from isaaclab.sensors import ContactSensor, ContactSensorCfg, RayCaster, RayCasterCfg, patterns, Camera, CameraCfg
from isaaclab.utils.math import sample_uniform, quat_apply, quat_apply_inverse, yaw_quat
from isaaclab.utils.mesh import create_trimesh_from_geom_mesh
from isaaclab.utils.warp import convert_to_warp_mesh, raycast_mesh
import xgo_kinematics
import xgo_gait_controller
import xgo_policy
import xgo_locomotion_env
import warp as wp
from pxr import UsdGeom, Usd, PhysxSchema, UsdPhysics, UsdShade, Gf
from omni.physx.scripts import physicsUtils


WALL_MARGIN = 0.20
ROVER_PATH = "_ROBOTS_/rover_rb3/Geometry/world/base_link"

# XGO quadruped (mini2). The articulation root sits under Geometry/world, while the
# joints live in a sibling Physics scope.
XGO_PATH = "_ROBOTS_/xgo_lite/Geometry/world/base_link"
XGO_JOINTS_SCOPE = "_ROBOTS_/xgo_lite/Physics"

# Leg joints in [FL, FR, BL, BR] x [shoulder, elbow, wrist] order, matching the
# output of the IK. The remaining revolute joints (51/52/53) are the arm and take
# no part in locomotion.
XGO_LEG_JOINTS = xgo_kinematics.xgo_joint_names()

# Real per-joint travel, from the vendor's xgo_ros driver config
# (IsaacSim/Robots/mini2_description/reference/xgomini.yaml). These replace an
# earlier +/-90 deg guess.
#
# The joint limits are genuinely absent upstream: the source URDF declares all 15
# revolute joints as type="continuous" with no <limit>, so the USD is faithful to
# it and re-importing cannot recover them. The physics parser still rejects
# infinite limits ("revolute joint without a finite limit set"), so they must be
# authored before simulation starts.
#
# xgo.cpp:162 indexes joint_limit[i % 3] across the 12 leg joints, so all four
# legs share three pairs ordered by position within the leg. Mapping to the N1/N2/
# N3 names is inferred from the numeric suffix; the hip (N3, attached to base_link)
# taking the tightest range is what hip abduction should look like.
XGO_JOINT_LIMITS_DEG = {
    "1": (-73.0, 57.0),   # N1, lower leg
    "2": (-66.0, 93.0),   # N2, upper leg
    "3": (-31.0, 31.0),   # N3, hip abduction
}
# Arm and gripper (51/52/53, 50/500); not used for locomotion, held still.
XGO_ARM_LIMITS_DEG = {
    "1": (-90.0, 75.0),
    "2": (-50.0, 85.0),
    "3": (-65.0, 65.0),
}
XGO_DEFAULT_LIMIT_DEG = (-90.0, 90.0)

# Agent identifiers. The two robots learn independently: separate policies, no
# shared critic and no parameter sharing (they do not even share an action space).
ROVER_AGENT = "rover"
XGO_AGENT = "xgo"

# The XGO is commanded like the rover -- forward and yaw velocity -- with a trot
# gait turning that into foot targets and the IK turning those into joint targets.
# This replaces direct 12-DoF joint control: the policy no longer has to discover
# how to stand before it can learn to navigate.
XGO_NUM_JOINTS = 12
XGO_NUM_ACTIONS = 2
# must match xgo_locomotion_env.ACTION_SCALE, or the policy's outputs are rescaled
# into a different joint range than it learned on
XGO_LOCO_ACTION_SCALE = xgo_locomotion_env.ACTION_SCALE

# The locomotion policy's command input is in physical units (m/s, rad/s), not
# normalised. Feeding it a raw [-1, 1] action asks for 1.0 m/s -- four times the
# fastest command it ever trained on -- and it walks backwards. Scale to the
# ranges it actually saw.
XGO_CMD_VX_SCALE = xgo_locomotion_env.CMD_VX_RANGE[1]
XGO_CMD_WZ_SCALE = xgo_locomotion_env.CMD_WZ_RANGE[1]
# Actions in [-1, 1] map onto each joint's own travel, so -1/+1 are exactly the
# authored limits. Built once in __init__ as centre +/- half-range.
# Termination thresholds for "the quadruped fell over".
XGO_MIN_HEIGHT = 0.04
XGO_MIN_UPRIGHT = 0.5
# Body height above the feet at reset. The vendor driver puts the real range at
# 75-115 mm (body_limit[2] in xgomini.yaml), so this sits mid-range.
XGO_STAND_HEIGHT = 0.09

# Nothing in this scene authors a physics material -- not the robots, not the maze
# -- so every contact falls back to the PhysX default. Rubber feet on a hard floor
# want far more grip than that, and without it a gait's stance legs slide instead
# of pushing.
XGO_FOOT_FRICTION = 1.2

# The maze itself has no floor: every _MAZE_ collider is a wall. The robots stand
# on _LAB_/Plane, a 12 x 18 m plane inside the scene USD, which authors no physics
# material and so falls back to the PhysX scene default. The locomotion policy was
# trained on IsaacLab's terrain plane, which does author one, so the two surfaces
# were not the same. This makes the maze floor explicit and matched.
MAZE_FLOOR_PATH = "_LAB_/Plane"
MAZE_FLOOR_FRICTION = float(os.environ.get("MAZE_FLOOR_FRICTION", "0.5"))

# Frozen low-level locomotion policy. The navigation policy issues a velocity
# command; this turns it into joint targets. Trained on flat ground by
# train_xgo.py, where it tracks ~70% of commanded velocity against the scripted
# trot's ~7%.
#
# If the checkpoint is missing the environment falls back to the scripted trot,
# so the repo still runs without a trained policy present.
XGO_POLICY_CHECKPOINT = str(
    Path(__file__).resolve().parent / "logs" / "skrl" / "xgo_locomotion" / "best_agent.pt"
)

# Success radius, and the minimum spawn-to-goal distance. Without the latter a
# goal can be drawn inside the success radius, so the episode is already solved at
# reset -- measured at 5/64 envs for the rover before this was enforced. Those
# instant terminations give PPO near-zero-length episodes and degenerate advantage
# statistics.
GOAL_REACHED_RADIUS = 0.15
# Was 0.75, which put every goal far enough away that random exploration never
# reached one -- the goal reward measured exactly 0.0 across a whole run, so it
# shaped nothing. A lower floor mixes in goals that are occasionally reachable by
# chance, which is what lets the bonus start doing work.
MIN_SPAWN_GOAL_DISTANCE = 0.30

# Lidar. IsaacLab 3.0's RayCaster supports only a single static mesh
# ("Currently, only a single static mesh is supported" -- ray_caster_cfg.py), so
# mesh_prim_paths=["/World"] silently bound to the first mesh under /World -- an
# 8-vertex april tag -- and every ray missed the maze forever. The scan is now cast
# directly against the merged maze mesh with isaaclab.utils.warp.raycast_mesh, the
# same mesh already built for the spawn search.
#
# The old pattern was 16 channels x 16 headings with vertical_fov_range=(0, 0),
# i.e. 16 unique directions duplicated 16 times. The same budget now buys 256
# distinct headings.
LIDAR_NUM_RAYS = 256
LIDAR_HEIGHT_ROVER = 0.21
LIDAR_HEIGHT_XGO = 0.10

# <repo>/IsaacSim/Scripts/train/collision_env.py -> <repo>/IsaacSim/multi_agent_robots.usd
SCENE_USD_PATH = str(Path(__file__).resolve().parents[2] / "multi_agent_robots.usd")


# -----------------------------------------------------------------------------
# Scene Configuration
# -----------------------------------------------------------------------------

@configclass
class CollisionEnvSceneCfg(InteractiveSceneCfg):
    rover_rb3: ArticulationCfg = ArticulationCfg(
        prim_path="{ENV_REGEX_NS}/scene/" + ROVER_PATH,
        spawn=None, 
        init_state=ArticulationCfg.InitialStateCfg(
            pos=(-1.274781178649809, 0.39281118685148864, 0.05064811513781181),
            rot=(0.0, 0.0, 0.0, 1.0), 
        ),
        actuators={
            "wheels": ImplicitActuatorCfg(
                joint_names_expr=["wheel_fl_joint", "wheel_fr_joint", "wheel_rl_joint", "wheel_rr_joint"],
                stiffness=0.0,
                damping=10000.0,
            ),
        },
    )

    xgo_lite: ArticulationCfg = ArticulationCfg(
        prim_path="{ENV_REGEX_NS}/scene/" + XGO_PATH,
        spawn=None,
        init_state=ArticulationCfg.InitialStateCfg(
            # Start from the asset's own zero pose. A stance could now be built
            # with xgo_kinematics (its FK matches the simulator to 1e-6 m), but
            # the foot offset inside the last link is not yet pinned down, so
            # there is no calibrated standing pose to seed. See FIXES.md 20.
            pos=(0.0, 0.0, XGO_STAND_HEIGHT + 0.01),
            rot=(0.0, 0.0, 0.0, 1.0),
        ),
        actuators={
            # position-controlled legs: the gait generator supplies joint targets
            "legs": ImplicitActuatorCfg(
                joint_names_expr=XGO_LEG_JOINTS,
                stiffness=20.0,
                damping=0.5,
            ),
            # The arm (51/52/53) and gripper (50/500) take no part in locomotion,
            # but every joint must belong to an actuator group or IsaacLab warns
            # that the articulation is only partially actuated. Hold them still.
            "arm": ImplicitActuatorCfg(
                # covers 50, 51, 52, 53 and 500
                joint_names_expr=["tn__5.*_Joint_"],
                stiffness=50.0,
                damping=1.0,
            ),
        },
    )

    maze: AssetBaseCfg = AssetBaseCfg(prim_path="{ENV_REGEX_NS}/scene/_MAZE_")

# -----------------------------------------------------------------------------
# Environment Configuration
# -----------------------------------------------------------------------------

@configclass
class CollisionEnvRB3Cfg(DirectMARLEnvCfg):
    decimation = 4 # nb of physics simulation steps for each RL action
    episode_length_s = 18.0

    possible_agents = [ROVER_AGENT, XGO_AGENT]

    # Both robots now take a linear/angular velocity command. They remain separate
    # agents with separate policies: the observation spaces differ, and the XGO's
    # command drives a gait rather than wheels.
    action_spaces = {
        ROVER_AGENT: 2,
        XGO_AGENT: XGO_NUM_ACTIONS,
    }

    # rover: 256 lidar + lin vel + ang vel + goal (x, y, distance)
    #        + the other robot (x, y, distance) in body frame
    # xgo:   the same, plus proprioception (projected gravity, body velocities,
    #        joint positions and velocities) which joint-level control needs
    #
    # The other robot has to be observed explicitly: the lidar is cast against the
    # maze mesh only, so neither robot appears in the other's scan. Without this
    # the agents are blind to each other and robot-robot avoidance is unlearnable.
    observation_spaces = {
        ROVER_AGENT: 261 + 3,
        XGO_AGENT: 256 + 3 + 3 + 3 + XGO_NUM_JOINTS * 2 + 3 + 3,
    }

    # IPPO is an independent learner and never reads a joint state, so 0 ("build
    # no state space") would be the honest value. skrl's Runner builds models
    # generically and cannot handle a zero-dimensional space, so use -1
    # (concatenate every agent's observations), which is what IsaacLab's own MARL
    # reference task does. The buffer is built but unused by IPPO, and it is what
    # MAPPO would need if a centralised critic is ever wanted.
    state_space = -1

    linear_scale = 0.25   # m/s
    angular_scale = 0.5   # rad/s

    lidar_max_distance = 10.0  # m -- also the value reported for rays that hit nothing

    sim = SimulationCfg(
        device="cuda:0",
        dt=1.0 / 120.0,
        render_interval=decimation,
    )

    # Per-step cost is almost entirely fixed overhead: measured step time barely
    # moves from 4 envs (552 ms) to 256 envs (575 ms), so throughput scales nearly
    # linearly with env count. 4 envs yields ~15 agent-samples/s; 256 yields ~890.
    # Override with train.py --num_envs.
    scene: CollisionEnvSceneCfg = CollisionEnvSceneCfg(
        num_envs=256,
        env_spacing=12.0,
        replicate_physics=True,
        clone_in_fabric=True,
    )

    scene_cfg = AssetBaseCfg(
        prim_path="{ENV_REGEX_NS}/scene", 
        spawn=sim_utils.UsdFileCfg(
            usd_path=SCENE_USD_PATH,
            articulation_props=ArticulationRootPropertiesCfg(fix_root_link=False),
        ),
    )

    # Balanced against an 18 s (540 step) episode. The previous weights made
    # loitering strictly optimal: the graded wall-proximity penalty ran at up to
    # -1.0 every step (~-130 per episode at the measured mean wall distance of
    # 0.27 m) while reaching the goal paid +10 once and crossing the whole maze
    # paid +0.1. The policy correctly learned to keep away from walls and ignore
    # the goal -- 0 goal hits, 0 collisions, 0.17 m of a 0.98 m gap closed.
    # Set against *measured* term magnitudes, not predicted ones. At the previous
    # weights a 540-step episode scored: collision -51.5, step -10.8, wall
    # proximity -7.6, robot proximity -6.6, progress +0.8, goal +0.0. Roughly 98%
    # penalty, and the goal bonus was never once received -- so it could not shape
    # anything, and standing still was the correct answer.
    #
    # Progress is now the dense signal that carries the policy toward the goal,
    # worth ~+20 for crossing the maze, with arrival worth +100 on top.
    rew_gets_closer_to_goal = 20.0
    rew_reach_goal = 100.0
    rew_step = -0.02
    # Proximity penalties are graded by distance, not switched by a threshold.
    # A boolean "closer than WALL_MARGIN" gives the same penalty at 0.19 m as at
    # 0.01 m and none at 0.21 m -- a cliff with no gradient for the policy to
    # follow. These ramp linearly from zero at the trigger distance to full
    # penalty at contact.
    # A nudge away from walls, not a wall of cost. Worst case now ~-27 over an
    # episode against ~+55 for actually reaching the goal.
    rew_wall_proximity_penalty = -0.05
    rew_robot_proximity_penalty = -0.5
    wall_proximity_distance = 0.35
    robot_proximity_distance = 0.50
    # Was -100, which at the measured ~0.5 collisions per episode cost -51.5 and
    # dominated every other term combined. Still clearly punitive, no longer
    # overwhelming: crossing to the goal now pays ~+120 against this -25.
    rew_wall_collision = -25.0

    # XGO-only locomotion shaping. Joint-level control has to learn to stay up
    # before it can learn to navigate, so staying upright is rewarded directly
    # and falling ends the episode.
    rew_xgo_alive = 0.05
    rew_xgo_fell = -50.0
    rew_xgo_action_rate = -0.005


# -----------------------------------------------------------------------------
# Environment Creation
# -----------------------------------------------------------------------------

class CollisionAvoidanceEnv(DirectMARLEnv):

    cfg: CollisionEnvRB3Cfg

    def __init__(self, cfg: CollisionEnvRB3Cfg, render_mode: str | None = None, **kwargs):
        print("Collision env init")
        super().__init__(cfg, render_mode, **kwargs)

        # continues after setup_scene()

        print("Scene entities: ")
        print(self.scene.keys())

        spawn_points = self._get_spawn_points()
        if len(spawn_points) == 0:
            raise RuntimeError(
                "No valid spawn points found in the maze. Check the floor probe / "
                "wall clearance thresholds in _get_spawn_points()."
            )
        # The maze is authored inside env_0, so the sampled points are in env_0's frame.
        # Store them relative to that origin so they can be re-based onto any env.
        self.spawn_points = torch.stack(spawn_points).to(self.device) - self.scene.env_origins[0, :2]
        print(f"{self.spawn_points.shape[0]} valid spawn points, first: {self.spawn_points[0]}")

        print("========== AFTER CLONING ==========")

        print("ENV REGEX:", self.scene.env_regex_ns)

        print("Contact sensor:")
        print("  prim_path:", self.contact_sensor.cfg.prim_path)
        print("  num_instances:", self.contact_sensor.num_instances)
        print("  body_physx_view:", self.contact_sensor.body_physx_view)

        stage = omni.usd.get_context().get_stage()

        for i in range(self.cfg.scene.num_envs):
            p = f"/World/envs/env_{i}/scene/{ROVER_PATH}"
            prim = stage.GetPrimAtPath(p)
            print(f"env_{i}: {p} -> valid={prim.IsValid()}")

        print("===================================")

        print("CONTACT DEVICE NUM:", self.contact_sensor.num_instances)
        print("CONTACT PRIM PATH:", self.contact_sensor.cfg.prim_path)

        print(f"LIDAR: {LIDAR_NUM_RAYS} rays/robot cast against the merged maze mesh")

        self.goal_pos = torch.zeros((self.num_envs, 2), device=self.device)
        self.previous_distance = torch.zeros(self.num_envs, device=self.device)
        self.xgo_goal_pos = torch.zeros((self.num_envs, 2), device=self.device)
        self.xgo_previous_distance = torch.zeros(self.num_envs, device=self.device)
        self._prev_xgo_actions = torch.zeros((self.num_envs, XGO_NUM_ACTIONS), device=self.device)

        # Episode diagnostics, surfaced through `extras` so they reach tensorboard
        # during training. Aggregate return and episode length cannot distinguish
        # "reached the goal" from "loitered safely" -- both give long episodes and
        # low per-step cost. These can.
        self._episode_start_pos = torch.zeros((self.num_envs, 2), device=self.device)
        self._xgo_episode_start_pos = torch.zeros((self.num_envs, 2), device=self.device)
        self._goal_hits = torch.zeros(self.num_envs, device=self.device)
        self._xgo_goal_hits = torch.zeros(self.num_envs, device=self.device)
        self._reached_goal = torch.zeros(self.num_envs, device=self.device)
        self._xgo_reached_goal = torch.zeros(self.num_envs, device=self.device)
        # Per-step event flags for evaluation, latched in _get_dones. Unlike
        # collisions_array they survive the reset that follows a termination in
        # the same step(), so code reading them after step() sees what happened.
        self.step_events = {
            name: torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            for name in ("rover_goal", "xgo_goal", "rover_collision", "xgo_collision", "xgo_fell")
        }

        # Optional navigation targets, for a high-level planner (llm_coordinator.py).
        # Where the mask is set, the policy *observes* this target instead of its
        # goal; rewards, goal-reaching and respawns still use the true goal. Off by
        # default, so training is unaffected.
        self.nav_target = {
            agent: torch.zeros((self.num_envs, 2), device=self.device)
            for agent in (ROVER_AGENT, XGO_AGENT)
        }
        self.nav_override = {
            agent: torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
            for agent in (ROVER_AGENT, XGO_AGENT)
        }

        # self.rover_rb3_controller = DifferentialController(wheel_radius=0.038, wheel_base=0.095) # apparently uses CPU and not GPU
        self.wheel_radius = 0.038
        self.wheel_base = 0.095

        # Resolve wheel joints explicitly: articulation joint order is not guaranteed
        # to match the order of joint_names_expr in the config.
        self._wheel_ids, self._wheel_names = self.rover_rb3.find_joints(
            ["wheel_fl_joint", "wheel_fr_joint", "wheel_rl_joint", "wheel_rr_joint"],
            preserve_order=True,
        )
        print("Wheel joints:", self._wheel_names, "->", self._wheel_ids)

        self._xgo_leg_ids, xgo_leg_names = self.xgo_lite.find_joints(
            XGO_LEG_JOINTS, preserve_order=True
        )
        print("XGO leg joints:", xgo_leg_names, "->", self._xgo_leg_ids)

        # Translation from each env into env_0's frame, for lidar ray-casting.
        self._env_offset_to_env0 = self.scene.env_origins - self.scene.env_origins[0]

        # Fixed body-frame ray fan: LIDAR_NUM_RAYS evenly spaced headings in the
        # horizontal plane, excluding the duplicate wrap point at +pi.
        angles = torch.linspace(-math.pi, math.pi, LIDAR_NUM_RAYS + 1, device=self.device)[:-1]
        self._lidar_dirs = torch.stack(
            (torch.cos(angles), torch.sin(angles), torch.zeros_like(angles)), dim=-1
        )

        # Exact kinematics, read from the asset's own joint frames. Used to seed a
        # standing pose: without it the XGO starts belly-down from the zero pose,
        # falls within a couple of steps, and (because the episode boundary is
        # shared) cuts the rover's episodes short too.
        stage = omni.usd.get_context().get_stage()
        self.xgo_kin = xgo_kinematics.XGOLegKinematics(
            xgo_kinematics.read_joint_frames(
                stage, f"/World/envs/env_0/scene/{XGO_JOINTS_SCOPE}"
            ),
            self.device,
        )

        # Map actions in [-1, 1] onto each leg joint's own travel, so the policy
        # cannot command a target outside the authored limits.
        lo = torch.tensor(
            [math.radians(self._xgo_limit_for(n)[0]) for n in XGO_LEG_JOINTS], device=self.device
        )
        hi = torch.tensor(
            [math.radians(self._xgo_limit_for(n)[1]) for n in XGO_LEG_JOINTS], device=self.device
        )
        self._xgo_action_centre = (hi + lo) / 2.0
        self._xgo_action_range = (hi - lo) / 2.0

        # Neutral standing pose, solved once. Verified to hold: commanding this
        # through the action interface puts the body within ~3 mm of the requested
        # height, level, with feet on the ground.
        stance_targets = xgo_kinematics.stance_foot_targets(
            self.device, height=XGO_STAND_HEIGHT
        ).unsqueeze(0).expand(self.num_envs, 4, 3)
        self._xgo_stance_joints = self.xgo_kin.inverse(
            stance_targets,
            torch.zeros((self.num_envs, 4, 3), device=self.device),
            iterations=60,
            damping=1e-4,
        ).reshape(self.num_envs, XGO_NUM_JOINTS)

        residual = torch.linalg.vector_norm(
            self.xgo_kin.forward(self._xgo_stance_joints.reshape(self.num_envs, 4, 3))
            - stance_targets,
            dim=-1,
        ).max()
        print(f"XGO stance IK residual: {float(residual) * 1000:.4f} mm")

        self._xgo_joint_targets = self._xgo_stance_joints.clone()
        self.xgo_gait = xgo_gait_controller.XGOTrotGait(
            self.num_envs, self.device, stand_height=XGO_STAND_HEIGHT
        )

        # Hierarchical control: prefer the trained locomotion policy, fall back to
        # the scripted trot if no checkpoint is present.
        self.xgo_locomotion = None
        if os.path.isfile(XGO_POLICY_CHECKPOINT):
            self.xgo_locomotion = xgo_policy.XGOLocomotionPolicy(
                XGO_POLICY_CHECKPOINT, self.device
            )
            print(
                f"XGO low-level policy: {XGO_POLICY_CHECKPOINT} "
                f"(obs {self.xgo_locomotion.obs_dim}, act {self.xgo_locomotion.action_dim})"
            )
        else:
            print(f"XGO low-level policy: not found at {XGO_POLICY_CHECKPOINT}; using scripted trot")

        self._xgo_prev_loco_actions = torch.zeros(
            (self.num_envs, XGO_NUM_JOINTS), device=self.device
        )

        # spawn heights, taken from each robot's configured initial state
        self._rover_spawn_z = self.cfg.scene.rover_rb3.init_state.pos[2]
        # stand the body its own stance height above the feet, plus clearance
        self._xgo_spawn_z = XGO_STAND_HEIGHT + 0.01


        self.collisions_array = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
        self.xgo_collisions = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
        max_range = self.cfg.lidar_max_distance
        self.nearest_wall = torch.full((self.num_envs,), max_range, device=self.device)
        self.xgo_nearest_wall = torch.full((self.num_envs,), max_range, device=self.device)
        self.robot_separation = torch.full((self.num_envs,), max_range, device=self.device)
        # per-ray lidar distances, populated by _update_sensor_state()
        self.lidar_distances: torch.Tensor | None = None

        print("Collision env init done")


    def _fix_xgo_joint_limits(self, stage, env_root: str) -> int:
        """Author finite limits on the XGO's revolute joints.

        The URDF -> USD conversion left every revolute joint at (-inf, inf). The
        physics parser rejects that outright, so the joints must be given finite
        travel before the simulation starts. See XGO_JOINT_LIMIT_DEG for the
        assumption being made about the real hardware range.
        """
        scope = stage.GetPrimAtPath(f"{env_root}/scene/{XGO_JOINTS_SCOPE}")
        if not scope.IsValid():
            return 0

        fixed = 0
        for joint_prim in Usd.PrimRange(scope):
            if joint_prim.GetTypeName() != "PhysicsRevoluteJoint":
                continue
            joint = UsdPhysics.RevoluteJoint(joint_prim)

            lower = joint.GetLowerLimitAttr().Get()
            upper = joint.GetUpperLimitAttr().Get()

            # only touch joints that are actually unbounded; leave authored limits alone
            if lower is not None and upper is not None and lower > -1e30 and upper < 1e30:
                continue

            lo, hi = self._xgo_limit_for(str(joint_prim.GetPath()).split("/")[-1])
            joint.CreateLowerLimitAttr().Set(lo)
            joint.CreateUpperLimitAttr().Set(hi)
            fixed += 1

        return fixed

    def _apply_foot_friction(self, stage, env_root: str) -> None:
        """Bind a high-friction physics material to the XGO's lower legs."""
        material_path = f"{env_root}/scene/xgo_foot_material"
        material = UsdPhysics.MaterialAPI.Apply(
            UsdShade.Material.Define(stage, material_path).GetPrim()
        )
        material.CreateStaticFrictionAttr().Set(XGO_FOOT_FRICTION)
        material.CreateDynamicFrictionAttr().Set(XGO_FOOT_FRICTION)
        material.CreateRestitutionAttr().Set(0.0)

        for leg in (1, 2, 3, 4):
            link = stage.GetPrimAtPath(
                f"{env_root}/scene/_ROBOTS_/xgo_lite/Geometry/world/base_link"
                f"/tn__{leg}3_Link_/tn__{leg}2_Link_/tn__{leg}1_Link_"
            )
            if not link.IsValid():
                continue
            # Bind on the link itself, not its colliders: the collision geometry
            # lives inside instance proxies, and USD refuses edits there. Material
            # bindings inherit to descendants, so this reaches them anyway.
            binding = UsdShade.MaterialBindingAPI.Apply(link)
            binding.Bind(
                UsdShade.Material(stage.GetPrimAtPath(material_path)),
                bindingStrength=UsdShade.Tokens.weakerThanDescendants,
                materialPurpose="physics",
            )

    def _apply_floor_friction(self, stage, env_root: str) -> None:
        """Author a physics material on the scene's floor plane."""
        floor = stage.GetPrimAtPath(f"{env_root}/scene/{MAZE_FLOOR_PATH}")
        if not floor.IsValid():
            return

        material_path = f"{env_root}/scene/floor_material"
        material = UsdPhysics.MaterialAPI.Apply(
            UsdShade.Material.Define(stage, material_path).GetPrim()
        )
        material.CreateStaticFrictionAttr().Set(MAZE_FLOOR_FRICTION)
        material.CreateDynamicFrictionAttr().Set(MAZE_FLOOR_FRICTION)
        material.CreateRestitutionAttr().Set(0.0)

        UsdShade.MaterialBindingAPI.Apply(floor).Bind(
            UsdShade.Material(stage.GetPrimAtPath(material_path)),
            bindingStrength=UsdShade.Tokens.weakerThanDescendants,
            materialPurpose="physics",
        )

    @staticmethod
    def _xgo_limit_for(joint_name: str) -> tuple[float, float]:
        """Hardware travel in degrees for a USD joint named e.g. 'tn__13_Joint_'."""
        digits = "".join(c for c in joint_name if c.isdigit())
        if not digits:
            return XGO_DEFAULT_LIMIT_DEG
        leg, index = digits[0], digits[-1]
        table = XGO_ARM_LIMITS_DEG if leg == "5" else XGO_JOINT_LIMITS_DEG
        return table.get(index, XGO_DEFAULT_LIMIT_DEG)

    def _build_maze_warp_mesh(self, maze_prim):
        """Collect every mesh under the maze prim into a single world-space warp mesh.

        PhysX scene queries (get_physx_scene_query_interface) are not usable here: this
        build runs on a non-PhysX physics backend, so that interface reports no hits for
        any ray. Ray-casting against the USD geometry via warp is backend-independent.
        """
        all_points = []
        all_indices = []
        offset = 0

        for prim in Usd.PrimRange(maze_prim):
            if prim.GetTypeName() != "Mesh":
                continue
            try:
                tri = create_trimesh_from_geom_mesh(prim)
            except Exception as exc:  # noqa: BLE001 - skip geometry we cannot read
                print(f"[WARN] skipping mesh {prim.GetPath()}: {exc}")
                continue
            if len(tri.vertices) == 0 or len(tri.faces) == 0:
                continue

            # trimesh points are in prim-local space -> lift them to world space
            xform = np.array(
                UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default()),
                dtype=np.float64,
            )
            pts = np.asarray(tri.vertices, dtype=np.float64)
            pts_h = np.hstack([pts, np.ones((pts.shape[0], 1))])
            # USD uses row-vector convention: v' = v @ M
            pts_w = (pts_h @ xform)[:, :3]

            all_points.append(pts_w.astype(np.float32))
            all_indices.append(np.asarray(tri.faces, dtype=np.int32).reshape(-1) + offset)
            offset += pts.shape[0]

        if not all_points:
            return None

        points = np.concatenate(all_points, axis=0)
        indices = np.concatenate(all_indices, axis=0)
        print(f"maze mesh: {points.shape[0]} vertices, {indices.shape[0] // 3} triangles")

        return convert_to_warp_mesh(points, indices, device=self.device)

    def _get_spawn_points(self):
        stage = omni.usd.get_context().get_stage()

        prim = stage.GetPrimAtPath("/World/envs/env_0/scene/_MAZE_")

        # compute maze bounding box
        bbox_cache = UsdGeom.BBoxCache(
            Usd.TimeCode.Default(),
            includedPurposes=["default", "render", "proxy"],
        )

        bbox = bbox_cache.ComputeWorldBound(prim)
        bbox = bbox.ComputeAlignedBox()

        # get lowest and highest points to detect borders
        min_point = bbox.GetMin()
        max_point = bbox.GetMax()

        print(f"min: {min_point}, max: {max_point}")

        maze_mesh = self._build_maze_warp_mesh(prim)
        if maze_mesh is None:
            raise RuntimeError("Could not build a warp mesh for the maze -- no readable Mesh prims found.")

        # reused every step by _cast_lidar()
        self._maze_mesh = maze_mesh

        num_candidates = 4000

        x = torch.rand(num_candidates, device=self.device) * (max_point[0] - min_point[0]) + min_point[0]
        y = torch.rand(num_candidates, device=self.device) * (max_point[1] - min_point[1]) + min_point[1]

        candidates_xy = torch.stack((x, y), dim=1)

        floor_z = float(min_point[2])
        # anything standing more than this above the floor counts as an obstacle
        obstacle_height = floor_z + 0.05
        # height at which lateral clearance is measured (roughly the rover body)
        clearance_z = floor_z + 0.10
        probe_height = float(max_point[2]) + 1.0

        # raycast_mesh expects rays shaped (num_instances, num_rays, 3)
        # --- 1. reject candidates with maze geometry standing at their (x, y) ---
        ray_starts = torch.stack(
            (x, y, torch.full_like(x, probe_height)),
            dim=1,
        ).unsqueeze(1)
        ray_dirs = torch.zeros_like(ray_starts)
        ray_dirs[:, :, 2] = -1.0

        hits, _, _, _ = raycast_mesh(ray_starts, ray_dirs, maze_mesh, max_dist=probe_height + 1.0)
        hit_z = hits[:, 0, 2]
        # misses come back as inf -> nothing standing there, which is fine
        blocked = torch.isfinite(hit_z) & (hit_z > obstacle_height)
        valid = ~blocked

        # --- 2. reject candidates within WALL_MARGIN of a wall ---
        lateral_dirs = torch.tensor(
            [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, -1.0, 0.0]],
            device=self.device,
        )

        side_starts = torch.stack(
            (x, y, torch.full_like(x, clearance_z)),
            dim=1,
        ).unsqueeze(1)

        for d in lateral_dirs:
            dirs = d.view(1, 1, 3).expand(num_candidates, 1, 3).contiguous()
            _, dist, _, _ = raycast_mesh(
                side_starts, dirs, maze_mesh, max_dist=WALL_MARGIN, return_distance=True
            )
            dist = dist[:, 0]
            valid &= ~(torch.isfinite(dist) & (dist <= WALL_MARGIN))

        spawn_points = [candidates_xy[i] for i in torch.nonzero(valid, as_tuple=False).flatten().tolist()]

        print(f"spawn points: {len(spawn_points)} / {num_candidates} candidates accepted")

        return spawn_points


    # -------------------------------------------------------------------------
    # Scene setup
    # -------------------------------------------------------------------------

    def _setup_scene(self):
        print(">>> _setup_scene()")

        env_regex = self.scene.env_regex_ns

        usd_cfg = self.cfg.scene_cfg

        # Spawn the USD once per environment.
        for env_id in range(self.cfg.scene.num_envs):
            prim_path = usd_cfg.prim_path.format(
                ENV_REGEX_NS=f"/World/envs/env_{env_id}"
            )

            usd_cfg.spawn.func(
                prim_path,
                usd_cfg.spawn,
                translation=(0.0, 0.0, 0.0),
                orientation=(0.0, 0.0, 0.0, 1.0),
            )

        stage = omni.usd.get_context().get_stage()

        # The XGO used to be deactivated here. It is now simulated as the second
        # agent, which first requires repairing the joint limits lost on import.
        for env_id in range(self.cfg.scene.num_envs):
            self._fix_xgo_joint_limits(stage, f"/World/envs/env_{env_id}")
            self._apply_foot_friction(stage, f"/World/envs/env_{env_id}")
            self._apply_floor_friction(stage, f"/World/envs/env_{env_id}")

        source_robot_path = f"{prim_path}/{ROVER_PATH}"
        robot_prim = stage.GetPrimAtPath(source_robot_path)

        contact_cfg = ContactSensorCfg(
            prim_path=f"{env_regex}/scene/{ROVER_PATH}",
            update_period=0.0,
            history_length=6,
            track_pose=False
            # filter_prim_paths_expr=["/World"] # detect contacts with everything that is under _MAZE_ (leave .*)
        )
        self.contact_sensor = ContactSensor(contact_cfg)

        contact_prim_path = f"{prim_path}/{ROVER_PATH}"

        contact_prim = stage.GetPrimAtPath(contact_prim_path)

        print("CONTACT REPORT PRIM:", contact_prim_path)
        print("VALID:", contact_prim.IsValid())

        if contact_prim.IsValid():
            PhysxSchema.PhysxContactReportAPI.Apply(contact_prim)
            print("[INFO] ContactReport API applied")

        for env_id in range(self.cfg.scene.num_envs):
            xgo_contact_prim = stage.GetPrimAtPath(f"/World/envs/env_{env_id}/scene/{XGO_PATH}")
            if xgo_contact_prim.IsValid():
                PhysxSchema.PhysxContactReportAPI.Apply(xgo_contact_prim)

        self.scene.sensors["contact_forces"] = self.contact_sensor

        # self.scene.clone_environments(copy_from_source=False)

        xgo_contact_cfg = ContactSensorCfg(
            prim_path=f"{env_regex}/scene/{XGO_PATH}",
            update_period=0.0,
            history_length=6,
            track_pose=False,
        )
        self.xgo_contact_sensor = ContactSensor(xgo_contact_cfg)
        self.scene.sensors["xgo_contact_forces"] = self.xgo_contact_sensor

        env_regex = self.scene.env_regex_ns
        self.cfg.scene.rover_rb3.prim_path = f"{env_regex}/scene/{ROVER_PATH}"

        self.rover_rb3 = Articulation(self.cfg.scene.rover_rb3)
        self.scene.articulations["rover_rb3"] = self.rover_rb3

        self.cfg.scene.xgo_lite.prim_path = f"{env_regex}/scene/{XGO_PATH}"
        self.xgo_lite = Articulation(self.cfg.scene.xgo_lite)
        self.scene.articulations["xgo_lite"] = self.xgo_lite

        print(">>> _setup_scene() terminé avec succès, capteurs synchronisés.")
    
        # context has not been updated yet here so this will not work
        # stage = omni.usd.get_context().get_stage()

        print("ENV REGEX:", self.scene.env_regex_ns)
        print("CONTACT PRIM:", contact_cfg.prim_path)



    # -------------------------------------------------------------------------
    # Physics
    # -------------------------------------------------------------------------

    def _pre_physics_step(self, actions: dict[str, torch.Tensor]) -> None:
        self.actions = {k: v.clone() for k, v in actions.items()}

        # The low-level policy was trained at the env-step rate with its action
        # held across the decimated substeps, so evaluate it here rather than in
        # _apply_action (which runs once per substep).
        if self.xgo_locomotion is not None:
            offsets = self.xgo_locomotion.act(self._xgo_locomotion_obs())
            self._xgo_prev_loco_actions = offsets.clone()
            targets = self._xgo_stance_joints + offsets.clamp(-1.0, 1.0) * XGO_LOCO_ACTION_SCALE
            lower = self._xgo_action_centre - self._xgo_action_range
            upper = self._xgo_action_centre + self._xgo_action_range
            self._xgo_joint_targets = targets.clamp(lower, upper)

    def _xgo_velocity_command(self) -> torch.Tensor:
        """Navigation action in [-1, 1] -> the physical command units the policy expects."""
        action = self.actions[XGO_AGENT].clamp(-1.0, 1.0)
        return torch.stack(
            (action[:, 0] * XGO_CMD_VX_SCALE, action[:, 1] * XGO_CMD_WZ_SCALE), dim=-1
        )

    def _xgo_locomotion_obs(self) -> torch.Tensor:
        """Observation in the exact layout the locomotion policy was trained on."""
        joint_pos = wp.to_torch(self.xgo_lite.data.joint_pos)[:, self._xgo_leg_ids]
        joint_vel = wp.to_torch(self.xgo_lite.data.joint_vel)[:, self._xgo_leg_ids]

        return torch.cat(
            (
                self._projected_gravity(self.xgo_lite),
                wp.to_torch(self.xgo_lite.data.root_lin_vel_b),
                wp.to_torch(self.xgo_lite.data.root_ang_vel_b),
                joint_pos - self._xgo_stance_joints,
                joint_vel,
                self._xgo_prev_loco_actions,
                self._xgo_velocity_command(),
            ),
            dim=-1,
        )


    def _apply_action(self):
        # ---------------- rover: differential drive ----------------
        rover_actions = self.actions[ROVER_AGENT]

        # policy outputs are in [-1, 1]; scale them to physical command units
        linear_speed = rover_actions[:, 0] * self.cfg.linear_scale    # m/s
        angular_speed = rover_actions[:, 1] * self.cfg.angular_scale  # rad/s

        # differential drive: contact-point speed of each side, in m/s
        left_speed = linear_speed - angular_speed * self.wheel_base / 2.0
        right_speed = linear_speed + angular_speed * self.wheel_base / 2.0

        # joint targets are angular velocities (rad/s), so divide by the wheel radius
        left_velocity = left_speed / self.wheel_radius
        right_velocity = right_speed / self.wheel_radius

        # order must match self._wheel_ids: [fl, fr, rl, rr]
        wheel_velocities = torch.stack(
            [left_velocity, right_velocity, left_velocity, right_velocity],
            dim=-1,
        )

        self.rover_rb3.set_joint_velocity_target_index(
            target=wheel_velocities,
            joint_ids=self._wheel_ids,
        )

        # ---------------- XGO ----------------
        # With a trained low-level policy the joint targets were already computed
        # in _pre_physics_step and are simply held across the substeps. The
        # scripted trot is the fallback, and its clock advances per substep.
        if self.xgo_locomotion is None:
            body_height = (
                wp.to_torch(self.xgo_lite.data.root_pos_w)[:, 2] - self.scene.env_origins[:, 2]
            )
            foot_targets = self.xgo_gait.step(
                self.actions[XGO_AGENT], self.physics_dt, body_height=body_height
            )
            # Warm-started: targets move little between steps, so a couple of
            # Gauss-Newton iterations suffice.
            solved = self.xgo_kin.inverse(
                foot_targets,
                self._xgo_joint_targets.reshape(self.num_envs, 4, 3),
                iterations=3,
                damping=1e-3,
            ).reshape(self.num_envs, XGO_NUM_JOINTS)
            lower = self._xgo_action_centre - self._xgo_action_range
            upper = self._xgo_action_centre + self._xgo_action_range
            self._xgo_joint_targets = solved.clamp(lower, upper)

        self.xgo_lite.set_joint_position_target_index(
            target=self._xgo_joint_targets,
            joint_ids=self._xgo_leg_ids,
        )

    # -------------------------------------------------------------------------
    # Sensor state
    # -------------------------------------------------------------------------

    def _update_sensor_state(self) -> None:
        """Refresh contact / lidar derived state for both robots.

        DirectMARLEnv.step() calls _get_dones() and _get_rewards() *before*
        _get_observations(), so computing this inside _get_observations() would
        leave terminations and rewards acting on the previous step's readings.
        Called at the top of _get_dones(), and again from _get_observations() to
        cover the reset path where _get_dones() does not run.
        """
        self.collisions_array = self._contact_hit(self.contact_sensor)
        self.xgo_collisions = self._contact_hit(self.xgo_contact_sensor)

        self.lidar_distances = self._cast_lidar(self.rover_rb3, LIDAR_HEIGHT_ROVER)
        self.xgo_lidar_distances = self._cast_lidar(self.xgo_lite, LIDAR_HEIGHT_XGO)

        # Shortest wall distance, graded rather than thresholded. The lidar sees
        # only the maze, so this is unambiguously wall proximity.
        self.nearest_wall = self.lidar_distances.min(dim=1).values
        self.xgo_nearest_wall = self.xgo_lidar_distances.min(dim=1).values

        # Robot-robot separation, which no lidar reports.
        rover_pos = wp.to_torch(self.rover_rb3.data.root_pos_w)[:, :2]
        xgo_pos = wp.to_torch(self.xgo_lite.data.root_pos_w)[:, :2]
        self.robot_separation = torch.linalg.vector_norm(rover_pos - xgo_pos, dim=-1)

    def _contact_hit(self, sensor) -> torch.Tensor:
        forces = wp.to_torch(sensor.data.net_forces_w)
        return (torch.linalg.vector_norm(forces, dim=-1) > 1.0).any(dim=1)

    def _cast_lidar(self, robot, height: float) -> torch.Tensor:
        """A planar 360-degree scan from `robot`, cast against the merged maze mesh.

        Replaces the RayCaster sensor, which can only bind to one static mesh and
        therefore never saw the maze at all.
        """
        pos = wp.to_torch(robot.data.root_pos_w)
        quat = wp.to_torch(robot.data.root_quat_w)

        # The maze mesh is env_0's geometry in world coordinates, so rays have to
        # be cast in env_0's frame. Every env holds an identical clone, and the
        # offset is a pure translation, so distances carry over unchanged.
        # Without this only env_0 ever registers a hit: every other robot sits
        # env_spacing metres away and its rays miss the mesh completely.
        pos = pos - self._env_offset_to_env0

        ray_starts = pos.clone()
        ray_starts[:, 2] += height
        ray_starts = ray_starts.unsqueeze(1).expand(-1, LIDAR_NUM_RAYS, 3).contiguous()

        # rotate the fixed body-frame fan by the robot's heading only
        yaw = yaw_quat(quat).unsqueeze(1).expand(-1, LIDAR_NUM_RAYS, 4).contiguous()
        ray_dirs = quat_apply(yaw, self._lidar_dirs.unsqueeze(0).expand(self.num_envs, -1, -1).contiguous())

        _, distance, _, _ = raycast_mesh(
            ray_starts,
            ray_dirs,
            self._maze_mesh,
            max_dist=self.cfg.lidar_max_distance,
            return_distance=True,
        )

        # Rays that hit nothing come back as inf. Feeding inf to the policy
        # produces NaNs on the first backward pass, so saturate at sensor range.
        return torch.nan_to_num(
            distance,
            nan=self.cfg.lidar_max_distance,
            posinf=self.cfg.lidar_max_distance,
            neginf=self.cfg.lidar_max_distance,
        ).clamp(0.0, self.cfg.lidar_max_distance)

    # -------------------------------------------------------------------------
    # Observations
    # -------------------------------------------------------------------------

    def _goal_in_body_frame(self, robot, goal_pos) -> tuple[torch.Tensor, torch.Tensor]:
        """Goal offset expressed in the robot's own frame, plus its magnitude."""
        robot_pos = wp.to_torch(robot.data.root_pos_w)[:, :2]
        robot_quat = wp.to_torch(robot.data.root_quat_w)

        goal_relative_w = torch.zeros((self.num_envs, 3), device=self.device)
        goal_relative_w[:, :2] = goal_pos - robot_pos

        # only the heading matters for a ground robot; ignore roll/pitch
        goal_relative_b = quat_apply_inverse(yaw_quat(robot_quat), goal_relative_w)

        distance = torch.linalg.vector_norm(goal_relative_b[:, :2], dim=-1)

        return goal_relative_b[:, :2], distance

    @staticmethod
    def _proximity(distance: torch.Tensor, trigger: float) -> torch.Tensor:
        """0 at or beyond `trigger`, ramping linearly to 1 at zero distance."""
        return (1.0 - distance / trigger).clamp(0.0, 1.0)

    def _other_robot_in_body_frame(self, robot, other) -> tuple[torch.Tensor, torch.Tensor]:
        """Where the other robot is, in this robot's own frame, plus the distance."""
        pos = wp.to_torch(robot.data.root_pos_w)[:, :2]
        quat = wp.to_torch(robot.data.root_quat_w)
        other_pos = wp.to_torch(other.data.root_pos_w)[:, :2]

        relative_w = torch.zeros((self.num_envs, 3), device=self.device)
        relative_w[:, :2] = other_pos - pos

        relative_b = quat_apply_inverse(yaw_quat(quat), relative_w)
        return relative_b[:, :2], torch.linalg.vector_norm(relative_b[:, :2], dim=-1)

    def _projected_gravity(self, robot) -> torch.Tensor:
        """Gravity direction in the body frame -- tells the policy which way is down."""
        quat = wp.to_torch(robot.data.root_quat_w)
        gravity_w = torch.zeros((self.num_envs, 3), device=self.device)
        gravity_w[:, 2] = -1.0
        return quat_apply_inverse(quat, gravity_w)

    def _observed_goal(self, agent: str, goal_pos: torch.Tensor) -> torch.Tensor:
        """The goal the policy sees: its true goal, or a planner's nav target."""
        return torch.where(
            self.nav_override[agent].unsqueeze(-1), self.nav_target[agent], goal_pos
        )

    def _get_observations(self) -> dict[str, torch.Tensor]:
        # covers reset(), where _get_dones() has not run
        self._update_sensor_state()

        # ---------------- rover ----------------
        rover_lin = wp.to_torch(self.rover_rb3.data.root_lin_vel_b)[:, 0]
        rover_ang = wp.to_torch(self.rover_rb3.data.root_ang_vel_b)[:, 2]
        rover_goal_xy, rover_goal_dist = self._goal_in_body_frame(
            self.rover_rb3, self._observed_goal(ROVER_AGENT, self.goal_pos)
        )

        rover_other_xy, rover_other_dist = self._other_robot_in_body_frame(
            self.rover_rb3, self.xgo_lite
        )

        rover_obs = torch.cat(
            (
                self.lidar_distances.reshape(self.num_envs, -1),
                rover_lin.unsqueeze(-1),
                rover_ang.unsqueeze(-1),
                rover_goal_xy,
                rover_goal_dist.unsqueeze(-1),
                rover_other_xy,
                rover_other_dist.unsqueeze(-1),
            ),
            dim=-1,
        )

        # ---------------- XGO ----------------
        # Joint-level control needs proprioception: the policy has to sense its own
        # posture and orientation to keep the body up, which a velocity-commanded
        # wheeled base never has to do.
        xgo_goal_xy, xgo_goal_dist = self._goal_in_body_frame(
            self.xgo_lite, self._observed_goal(XGO_AGENT, self.xgo_goal_pos)
        )
        xgo_other_xy, xgo_other_dist = self._other_robot_in_body_frame(
            self.xgo_lite, self.rover_rb3
        )

        xgo_obs = torch.cat(
            (
                self.xgo_lidar_distances.reshape(self.num_envs, -1),
                self._projected_gravity(self.xgo_lite),
                wp.to_torch(self.xgo_lite.data.root_lin_vel_b),
                wp.to_torch(self.xgo_lite.data.root_ang_vel_b),
                wp.to_torch(self.xgo_lite.data.joint_pos)[:, self._xgo_leg_ids],
                wp.to_torch(self.xgo_lite.data.joint_vel)[:, self._xgo_leg_ids],
                xgo_goal_xy,
                xgo_goal_dist.unsqueeze(-1),
                xgo_other_xy,
                xgo_other_dist.unsqueeze(-1),
            ),
            dim=-1,
        )

        return {ROVER_AGENT: rover_obs, XGO_AGENT: xgo_obs}

    # -------------------------------------------------------------------------
    # Rewards
    # -------------------------------------------------------------------------

    def _get_rewards(self) -> dict[str, torch.Tensor]:
        step_rew = torch.full((self.num_envs,), self.cfg.rew_step, device=self.device)

        # ---------------- rover ----------------
        _, rover_dist = self._goal_in_body_frame(self.rover_rb3, self.goal_pos)

        robot_proximity = self._proximity(
            self.robot_separation, self.cfg.robot_proximity_distance
        ) * self.cfg.rew_robot_proximity_penalty

        # Kept as named terms so their magnitudes can be logged. Two reward
        # weights in this project have already been set by analogy and found wrong
        # only after a full training run; measuring beats guessing.
        terms = {
            "goal": self._reached_goal * self.cfg.rew_reach_goal,
            "progress": self.cfg.rew_gets_closer_to_goal
            * (self.previous_distance - rover_dist),
            "collision": self.collisions_array.float() * self.cfg.rew_wall_collision,
            "wall_proximity": self._proximity(
                self.nearest_wall, self.cfg.wall_proximity_distance
            )
            * self.cfg.rew_wall_proximity_penalty,
            "robot_proximity": robot_proximity,
            "step": step_rew,
        }
        rover_reward = sum(terms.values())

        # Logged here, every step. Publishing these from _log_episode_diagnostics
        # instead sampled them only on steps where an episode ended -- which are
        # collision steps -- so the goal term always read 0.0 even while goals were
        # being reached on other steps.
        log = self.extras.setdefault("log", {})
        for name, value in terms.items():
            log[f"reward_terms/{name}"] = value.mean()
        self.previous_distance = rover_dist

        # ---------------- XGO ----------------
        _, xgo_dist = self._goal_in_body_frame(self.xgo_lite, self.xgo_goal_pos)

        # Staying upright is rewarded on its own: a joint-level policy has to solve
        # standing before goal progress can mean anything.
        upright = self._upright_measure(self.xgo_lite)
        alive = (~self._xgo_has_fallen()).float() * self.cfg.rew_xgo_alive

        action_rate = torch.linalg.vector_norm(
            self.actions[XGO_AGENT] - self._prev_xgo_actions, dim=-1
        ) * self.cfg.rew_xgo_action_rate
        self._prev_xgo_actions = self.actions[XGO_AGENT].clone()

        xgo_reward = (
            self._xgo_reached_goal * self.cfg.rew_reach_goal
            + self.cfg.rew_gets_closer_to_goal * (self.xgo_previous_distance - xgo_dist)
            + self.xgo_collisions.float() * self.cfg.rew_wall_collision
            + self._proximity(self.xgo_nearest_wall, self.cfg.wall_proximity_distance)
            * self.cfg.rew_wall_proximity_penalty
            + robot_proximity
            + alive
            + upright * self.cfg.rew_xgo_alive
            + self._xgo_has_fallen().float() * self.cfg.rew_xgo_fell
            + action_rate
            + step_rew
        )
        self.xgo_previous_distance = xgo_dist

        return {ROVER_AGENT: rover_reward, XGO_AGENT: xgo_reward}

    # -------------------------------------------------------------------------
    # Termination
    # -------------------------------------------------------------------------

    def _upright_measure(self, robot) -> torch.Tensor:
        """1.0 when the body's up axis is vertical, 0 when horizontal."""
        quat = wp.to_torch(robot.data.root_quat_w)
        return 1.0 - 2.0 * (quat[:, 0] ** 2 + quat[:, 1] ** 2)

    def _xgo_has_fallen(self) -> torch.Tensor:
        height = wp.to_torch(self.xgo_lite.data.root_pos_w)[:, 2]
        env_z = self.scene.env_origins[:, 2]
        return ((height - env_z) < XGO_MIN_HEIGHT) | (
            self._upright_measure(self.xgo_lite) < XGO_MIN_UPRIGHT
        )

    def _get_dones(self) -> tuple[dict[str, torch.Tensor], dict[str, torch.Tensor]]:
        # runs before _get_rewards() and _get_observations(), so refresh here to
        # keep terminations and rewards on the current step's sensor data
        self._update_sensor_state()

        _, rover_dist = self._goal_in_body_frame(self.rover_rb3, self.goal_pos)
        _, xgo_dist = self._goal_in_body_frame(self.xgo_lite, self.xgo_goal_pos)

        # Reaching a goal does NOT end the episode -- the goal is respawned and the
        # robot carries on. Terminating on success coupled the two agents through
        # the shared episode boundary: every time the rover arrived it cut the
        # XGO's episode short, so as the rover improved the XGO got less and less
        # time. Measured over training, the rover's goal rate rose 0.07 -> 0.23
        # while the XGO's peaked at 0.21 and fell back to 0.17, with its net
        # displacement declining over the same span.
        #
        # Now an improving rover *lengthens* episodes rather than truncating them,
        # and both robots get repeated attempts within one episode.
        # Latch *before* respawning. _get_dones runs ahead of _get_rewards, so
        # once the goal has moved the reward function can no longer tell that it
        # was reached: it recomputes the distance against the new goal and pays
        # nothing. Measured, that zeroed the goal term while the goal rate was
        # 0.43 per episode.
        self._reached_goal = (rover_dist < GOAL_REACHED_RADIUS).float()
        self._xgo_reached_goal = (xgo_dist < GOAL_REACHED_RADIUS).float()

        self._respawn_reached_goals(rover_dist, xgo_dist)

        rover_terminated = self.collisions_array
        xgo_fell = self._xgo_has_fallen()
        xgo_terminated = self.xgo_collisions | xgo_fell

        self.step_events["rover_goal"][:] = self._reached_goal.bool()
        self.step_events["xgo_goal"][:] = self._xgo_reached_goal.bool()
        self.step_events["rover_collision"][:] = self.collisions_array
        self.step_events["xgo_collision"][:] = self.xgo_collisions
        self.step_events["xgo_fell"][:] = xgo_fell

        time_out = self.episode_length_buf >= self.max_episode_length - 1

        # Shared episode boundary. DirectMARLEnv resets an env only once *every*
        # agent is done (reset_buf = prod(terminated) | prod(time_out)), so an agent
        # that finishes early keeps being stepped: a rover parked against a wall was
        # taking rew_wall_collision every step for the rest of the episode, driving
        # mean return from -100 to -3000 while learning nothing.
        #
        # Masking the dead agent's reward instead is worse -- it makes most of the
        # batch exactly zero, and the near-zero advantage variance sends PPO to NaN.
        #
        # Ending the episode for both robots when either one finishes matches how
        # the environment already behaves: a single episode_length_buf, and a reset
        # that repositions both robots together.
        shared_terminated = rover_terminated | xgo_terminated

        # Count goals, not "reached at least one": goals respawn now, so an
        # episode can contain several and a saturating flag would hide the
        # difference between one and ten.
        self._goal_hits += (rover_dist < GOAL_REACHED_RADIUS).float()
        self._xgo_goal_hits += (xgo_dist < GOAL_REACHED_RADIUS).float()
        self._log_episode_diagnostics(shared_terminated | time_out)

        return (
            {ROVER_AGENT: shared_terminated, XGO_AGENT: shared_terminated},
            {ROVER_AGENT: time_out, XGO_AGENT: time_out},
        )

    def _respawn_reached_goals(self, rover_dist: torch.Tensor, xgo_dist: torch.Tensor) -> None:
        """Give a robot a fresh goal when it reaches its current one."""
        origins = self.scene.env_origins[:, :2]

        for agent, reached, goal_pos, previous, robot in (
            (ROVER_AGENT, rover_dist < GOAL_REACHED_RADIUS, self.goal_pos, self.previous_distance, self.rover_rb3),
            (XGO_AGENT, xgo_dist < GOAL_REACHED_RADIUS, self.xgo_goal_pos, self.xgo_previous_distance, self.xgo_lite),
        ):
            if not bool(reached.any()):
                continue

            env_ids = reached.nonzero(as_tuple=False).squeeze(-1)
            pos = wp.to_torch(robot.data.root_pos_w)[env_ids, :2] - origins[env_ids]

            fresh = self._resample_far_enough(
                pos, self._sample_spawn(len(env_ids)), MIN_SPAWN_GOAL_DISTANCE
            )
            goal_pos[env_ids] = fresh + origins[env_ids]
            # a planner's waypoint was for the old goal
            self.nav_override[agent][env_ids] = False

            # reseed the progress baseline, or the jump to a distant goal reads as
            # a large negative step in the progress reward
            previous[env_ids] = torch.linalg.vector_norm(
                goal_pos[env_ids] - (pos + origins[env_ids]), dim=-1
            )

    def _log_episode_diagnostics(self, done: torch.Tensor) -> None:
        """Publish goal-hit rate and net displacement for finishing episodes.

        Net displacement, not path length: a robot rocking on the spot racks up
        path length while going nowhere, which is exactly the failure this exists
        to expose.
        """
        if not bool(done.any()):
            return

        rover_pos = wp.to_torch(self.rover_rb3.data.root_pos_w)[:, :2]
        xgo_pos = wp.to_torch(self.xgo_lite.data.root_pos_w)[:, :2]

        rover_net = torch.linalg.vector_norm(rover_pos - self._episode_start_pos, dim=-1)
        xgo_net = torch.linalg.vector_norm(xgo_pos - self._xgo_episode_start_pos, dim=-1)

        log = self.extras.setdefault("log", {})
        log.update({
            "diagnostics/rover_goal_rate": self._goal_hits[done].mean(),
            "diagnostics/xgo_goal_rate": self._xgo_goal_hits[done].mean(),
            "diagnostics/rover_net_displacement": rover_net[done].mean(),
            "diagnostics/xgo_net_displacement": xgo_net[done].mean(),
        })

    # -------------------------------------------------------------------------
    # Reset
    # -------------------------------------------------------------------------

    def _reset_idx(self, env_ids: Sequence[int] | None):
        if env_ids is None:
            env_ids = self.rover_rb3._ALL_INDICES

        env_ids = torch.as_tensor(env_ids, device=self.device, dtype=torch.long)

        super()._reset_idx(env_ids)

        n = len(env_ids)
        origins = self.scene.env_origins[env_ids, :2]

        # Four independent draws from the validated free-space set: a spawn and a
        # goal for each robot. Drawing separately means the pair can still land
        # close together, which is what makes robot-robot avoidance a real problem;
        # _resample_far_enough only rules out spawning literally on top of one
        # another.
        rover_spawn = self._sample_spawn(n)
        xgo_spawn = self._resample_far_enough(rover_spawn, self._sample_spawn(n))
        # A goal drawn inside the success radius would make the episode already
        # solved at reset, so keep goals a real distance from their spawn.
        rover_goal = self._resample_far_enough(
            rover_spawn, self._sample_spawn(n), MIN_SPAWN_GOAL_DISTANCE
        )
        xgo_goal = self._resample_far_enough(
            xgo_spawn, self._sample_spawn(n), MIN_SPAWN_GOAL_DISTANCE
        )

        self._place_robot(self.rover_rb3, env_ids, rover_spawn + origins, self._rover_spawn_z)
        self._place_robot(self.xgo_lite, env_ids, xgo_spawn + origins, self._xgo_spawn_z)

        # start standing rather than belly-down from the asset's zero pose
        self.xgo_lite.write_joint_position_to_sim_index(
            position=self._xgo_stance_joints[env_ids],
            joint_ids=self._xgo_leg_ids,
            env_ids=env_ids,
        )
        self.xgo_lite.write_data_to_sim()

        self.goal_pos[env_ids] = rover_goal + origins
        self.xgo_goal_pos[env_ids] = xgo_goal + origins

        self.previous_distance[env_ids] = torch.linalg.vector_norm(
            self.goal_pos[env_ids] - (rover_spawn + origins), dim=-1
        )
        self.xgo_previous_distance[env_ids] = torch.linalg.vector_norm(
            self.xgo_goal_pos[env_ids] - (xgo_spawn + origins), dim=-1
        )

        self._prev_xgo_actions[env_ids] = 0.0
        self._episode_start_pos[env_ids] = rover_spawn + origins
        self._xgo_episode_start_pos[env_ids] = xgo_spawn + origins
        self._goal_hits[env_ids] = 0.0
        self._xgo_goal_hits[env_ids] = 0.0
        for override in self.nav_override.values():
            override[env_ids] = False
        self._xgo_joint_targets[env_ids] = self._xgo_stance_joints[env_ids]
        self._xgo_prev_loco_actions[env_ids] = 0.0
        self.xgo_gait.reset(env_ids)

        self.collisions_array[env_ids] = False
        self.xgo_collisions[env_ids] = False
        self.nearest_wall[env_ids] = self.cfg.lidar_max_distance
        self.xgo_nearest_wall[env_ids] = self.cfg.lidar_max_distance
        self.robot_separation[env_ids] = self.cfg.lidar_max_distance


    def _sample_spawn(self, n: int) -> torch.Tensor:
        """n env-local (x, y) positions drawn from the validated free-space set."""
        idx = torch.randint(0, self.spawn_points.shape[0], (n,), device=self.device)
        return self.spawn_points[idx]

    def _resample_far_enough(
        self, first: torch.Tensor, second: torch.Tensor, min_separation: float = 0.4
    ) -> torch.Tensor:
        """Redraw any point that landed on top of `first`.

        Bounded retries rather than a while loop: in a small maze there may be no
        valid pair at all, and a loop would hang the reset. Any still-overlapping
        point is nudged away as a fallback so two robots never start interpenetrating.
        """
        for _ in range(8):
            too_close = torch.linalg.vector_norm(second - first, dim=-1) < min_separation
            if not bool(too_close.any()):
                return second
            redraw = self._sample_spawn(int(too_close.sum()))
            second = second.clone()
            second[too_close] = redraw

        offset = torch.nn.functional.normalize(second - first, dim=-1, eps=1e-6) * min_separation
        still_close = torch.linalg.vector_norm(second - first, dim=-1) < min_separation
        second = second.clone()
        second[still_close] = first[still_close] + offset[still_close]
        return second

    def _place_robot(self, robot, env_ids, xy: torch.Tensor, spawn_z: float) -> None:
        """Teleport a robot to `xy` with a random yaw and zeroed velocities."""
        n = len(env_ids)
        yaw = torch.rand(n, device=self.device) * 2.0 * math.pi

        root_pose = torch.zeros((n, 7), device=self.device, dtype=torch.float32)
        root_pose[:, 0:2] = xy
        root_pose[:, 2] = spawn_z

        # IsaacLab 3.x quaternion order is (x, y, z, w) -- yaw is a rotation about Z
        root_pose[:, 3] = 0.0
        root_pose[:, 4] = 0.0
        root_pose[:, 5] = torch.sin(yaw / 2.0)
        root_pose[:, 6] = torch.cos(yaw / 2.0)

        robot.write_root_pose_to_sim(root_pose, env_ids)
        robot.write_root_velocity_to_sim(
            torch.zeros((n, 6), device=self.device, dtype=torch.float32), env_ids
        )
        robot.write_joint_velocity_to_sim_index(
            velocity=torch.zeros((n, robot.num_joints), device=self.device),
            joint_ids=None,
            env_ids=env_ids,
        )
        robot.write_data_to_sim()
