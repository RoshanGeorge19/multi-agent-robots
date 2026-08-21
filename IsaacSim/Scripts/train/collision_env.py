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
# only the measured joint-name ordering is used; the IK in this module cannot
# drive this asset (see FIXES.md section 14)
import xgo_gait
import warp as wp
from pxr import UsdGeom, Usd, PhysxSchema, UsdPhysics, Gf
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
XGO_LEG_JOINTS = xgo_gait.xgo_joint_names()

# The URDF -> USD import dropped the joint limits: all 15 revolute joints come
# through with (-inf, inf), which the physics parser rejects with
#   "revolute joint without a finite limit set. A finite limit is required."
# The source URDF is not in this repo, so the real hardware travel is unknown.
# ASSUMPTION: +/- 90 deg, a typical range for the serial bus servos on this class
# of hobby quadruped. Replace with the true per-joint limits when the URDF is
# available -- this value affects what gaits are reachable.
XGO_JOINT_LIMIT_DEG = 90.0

# Agent identifiers. The two robots learn independently: separate policies, no
# shared critic and no parameter sharing (they do not even share an action space).
ROVER_AGENT = "rover"
XGO_AGENT = "xgo"

# The XGO is driven at the joint level rather than through the shipped gait stack.
# That stack's IK cannot be used: the asset's joint convention is not the one it
# assumes (see FIXES.md section 14). Learning joint targets directly sidesteps the
# problem entirely, because the policy discovers whatever convention the asset has.
XGO_NUM_JOINTS = 12
# Actions are in [-1, 1] and scale to this fraction of the joint travel, keeping
# targets inside the authored limits.
XGO_ACTION_SCALE = math.radians(XGO_JOINT_LIMIT_DEG)
# Termination thresholds for "the quadruped fell over".
XGO_MIN_HEIGHT = 0.04
XGO_MIN_UPRIGHT = 0.5
# Drop height at spawn. At all-zero joint angles the body settles to ~0.069 m,
# so this leaves a little clearance without a large fall.
XGO_SPAWN_HEIGHT = 0.10

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
            # Start from the asset's own zero pose rather than the IK stance:
            # xgo_gait's stance is derived from LegIK, whose joint convention does
            # not match this asset (FIXES.md section 14), so it would seed a
            # collapsing pose. The policy learns its own posture from neutral.
            pos=(0.0, 0.0, XGO_SPAWN_HEIGHT),
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

    # The two robots have genuinely different action spaces: the rover takes a
    # linear/angular velocity command, the XGO takes 12 joint position targets.
    action_spaces = {
        ROVER_AGENT: 2,
        XGO_AGENT: XGO_NUM_JOINTS,
    }

    # rover: 256 lidar + lin vel + ang vel + goal (x, y, distance)
    # xgo:   the same, plus proprioception (projected gravity, body velocities,
    #        joint positions and velocities) which joint-level control needs
    observation_spaces = {
        ROVER_AGENT: 261,
        XGO_AGENT: 256 + 3 + 3 + 3 + XGO_NUM_JOINTS * 2 + 3,
    }

    # no centralised critic -- these are independent learners
    state_space = 0

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

    rew_gets_closer_to_goal = 0.1
    rew_reach_goal = 10.0
    rew_step = -0.01
    rew_robot_proximity_penalty = -2.0
    rew_wall_collision = -100.0

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
        self._prev_xgo_actions = torch.zeros((self.num_envs, XGO_NUM_JOINTS), device=self.device)

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

        # Fixed body-frame ray fan: LIDAR_NUM_RAYS evenly spaced headings in the
        # horizontal plane, excluding the duplicate wrap point at +pi.
        angles = torch.linspace(-math.pi, math.pi, LIDAR_NUM_RAYS + 1, device=self.device)[:-1]
        self._lidar_dirs = torch.stack(
            (torch.cos(angles), torch.sin(angles), torch.zeros_like(angles)), dim=-1
        )

        # spawn heights, taken from each robot's configured initial state
        self._rover_spawn_z = self.cfg.scene.rover_rb3.init_state.pos[2]
        self._xgo_spawn_z = self.cfg.scene.xgo_lite.init_state.pos[2]


        self.collisions_array = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
        self.is_too_close = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
        self.xgo_collisions = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
        self.xgo_is_too_close = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
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

            joint.CreateLowerLimitAttr().Set(-XGO_JOINT_LIMIT_DEG)
            joint.CreateUpperLimitAttr().Set(XGO_JOINT_LIMIT_DEG)
            fixed += 1

        return fixed

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

        # ---------------- XGO: direct joint position control ----------------
        # Actions in [-1, 1] map onto the authored joint travel. No IK is involved,
        # so the asset's joint convention does not need to be known.
        xgo_targets = self.actions[XGO_AGENT].clamp(-1.0, 1.0) * XGO_ACTION_SCALE

        self.xgo_lite.set_joint_position_target_index(
            target=xgo_targets,
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

        # NOTE: this measures proximity to *any* lidar return -- walls as well as
        # the other robot. Separating the two needs per-hit ownership, which the
        # ray caster does not report; until then wall proximity is penalised both
        # here and through rew_wall_collision.
        self.is_too_close = (self.lidar_distances < WALL_MARGIN).any(dim=1)
        self.xgo_is_too_close = (self.xgo_lidar_distances < WALL_MARGIN).any(dim=1)

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

    def _projected_gravity(self, robot) -> torch.Tensor:
        """Gravity direction in the body frame -- tells the policy which way is down."""
        quat = wp.to_torch(robot.data.root_quat_w)
        gravity_w = torch.zeros((self.num_envs, 3), device=self.device)
        gravity_w[:, 2] = -1.0
        return quat_apply_inverse(quat, gravity_w)

    def _get_observations(self) -> dict[str, torch.Tensor]:
        # covers reset(), where _get_dones() has not run
        self._update_sensor_state()

        # ---------------- rover ----------------
        rover_lin = wp.to_torch(self.rover_rb3.data.root_lin_vel_b)[:, 0]
        rover_ang = wp.to_torch(self.rover_rb3.data.root_ang_vel_b)[:, 2]
        rover_goal_xy, rover_goal_dist = self._goal_in_body_frame(self.rover_rb3, self.goal_pos)

        rover_obs = torch.cat(
            (
                self.lidar_distances.reshape(self.num_envs, -1),
                rover_lin.unsqueeze(-1),
                rover_ang.unsqueeze(-1),
                rover_goal_xy,
                rover_goal_dist.unsqueeze(-1),
            ),
            dim=-1,
        )

        # ---------------- XGO ----------------
        # Joint-level control needs proprioception: the policy has to sense its own
        # posture and orientation to keep the body up, which a velocity-commanded
        # wheeled base never has to do.
        xgo_goal_xy, xgo_goal_dist = self._goal_in_body_frame(self.xgo_lite, self.xgo_goal_pos)

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

        rover_reward = (
            (rover_dist < 0.15).float() * self.cfg.rew_reach_goal
            + self.cfg.rew_gets_closer_to_goal * (self.previous_distance - rover_dist)
            + self.collisions_array.float() * self.cfg.rew_wall_collision
            + self.is_too_close.float() * self.cfg.rew_robot_proximity_penalty
            + step_rew
        )
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
            (xgo_dist < 0.15).float() * self.cfg.rew_reach_goal
            + self.cfg.rew_gets_closer_to_goal * (self.xgo_previous_distance - xgo_dist)
            + self.xgo_collisions.float() * self.cfg.rew_wall_collision
            + self.xgo_is_too_close.float() * self.cfg.rew_robot_proximity_penalty
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
        rover_terminated = self.collisions_array | (rover_dist < 0.15)

        _, xgo_dist = self._goal_in_body_frame(self.xgo_lite, self.xgo_goal_pos)
        xgo_terminated = self.xgo_collisions | (xgo_dist < 0.15) | self._xgo_has_fallen()

        time_out = self.episode_length_buf >= self.max_episode_length - 1

        return (
            {ROVER_AGENT: rover_terminated, XGO_AGENT: xgo_terminated},
            {ROVER_AGENT: time_out, XGO_AGENT: time_out},
        )

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
        rover_goal = self._sample_spawn(n)
        xgo_goal = self._sample_spawn(n)

        self._place_robot(self.rover_rb3, env_ids, rover_spawn + origins, self._rover_spawn_z)
        self._place_robot(self.xgo_lite, env_ids, xgo_spawn + origins, self._xgo_spawn_z)

        self.goal_pos[env_ids] = rover_goal + origins
        self.xgo_goal_pos[env_ids] = xgo_goal + origins

        self.previous_distance[env_ids] = torch.linalg.vector_norm(
            self.goal_pos[env_ids] - (rover_spawn + origins), dim=-1
        )
        self.xgo_previous_distance[env_ids] = torch.linalg.vector_norm(
            self.xgo_goal_pos[env_ids] - (xgo_spawn + origins), dim=-1
        )

        self._prev_xgo_actions[env_ids] = 0.0

        self.collisions_array[env_ids] = False
        self.is_too_close[env_ids] = False
        self.xgo_collisions[env_ids] = False
        self.xgo_is_too_close[env_ids] = False

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
