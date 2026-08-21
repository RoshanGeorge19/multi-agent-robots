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
from isaaclab.envs import DirectRLEnv, DirectRLEnvCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.sim import SimulationCfg
from isaaclab.utils.configclass import configclass
from isaaclab.sim.schemas import ArticulationRootPropertiesCfg
from isaaclab.sensors import ContactSensor, ContactSensorCfg, RayCaster, RayCasterCfg, patterns, Camera, CameraCfg
from isaaclab.utils.math import sample_uniform, quat_apply_inverse, yaw_quat
from isaaclab.utils.mesh import create_trimesh_from_geom_mesh
from isaaclab.utils.warp import convert_to_warp_mesh, raycast_mesh
import warp as wp
from pxr import UsdGeom, Usd, PhysxSchema, UsdPhysics, Gf
from omni.physx.scripts import physicsUtils


WALL_MARGIN = 0.20
ROVER_PATH = "_ROBOTS_/rover_rb3/Geometry/world/base_link"

# XGO quadruped (mini2). The articulation root sits under Geometry/world, while the
# joints live in a sibling Physics scope.
XGO_PATH = "_ROBOTS_/xgo_lite/Geometry/world/base_link"
XGO_JOINTS_SCOPE = "_ROBOTS_/xgo_lite/Physics"

# Leg joints, named <leg><index>: legs 1-4, three joints each. The remaining
# revolute joints (51/52/53) are the arm and are not used for locomotion.
XGO_LEG_JOINTS = [f"{leg}{idx}_Joint" for leg in (1, 2, 3, 4) for idx in (1, 2, 3)]

# The URDF -> USD import dropped the joint limits: all 15 revolute joints come
# through with (-inf, inf), which the physics parser rejects with
#   "revolute joint without a finite limit set. A finite limit is required."
# The source URDF is not in this repo, so the real hardware travel is unknown.
# ASSUMPTION: +/- 90 deg, a typical range for the serial bus servos on this class
# of hobby quadruped. Replace with the true per-joint limits when the URDF is
# available -- this value affects what gaits are reachable.
XGO_JOINT_LIMIT_DEG = 90.0

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
            pos=(0.0, 0.0, 0.12),
            rot=(0.0, 0.0, 0.0, 1.0),
        ),
        actuators={
            # position-controlled legs: the gait generator supplies joint targets
            "legs": ImplicitActuatorCfg(
                joint_names_expr=[f"tn__{n}_" for n in XGO_LEG_JOINTS],
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
class CollisionEnvRB3Cfg(DirectRLEnvCfg):
    decimation = 4 # nb of physics simulation steps for each RL action
    episode_length_s = 18.0
    action_space = 2 # linear and angular velocity
    # [lidar distances (256), linear_velocity, angular_velocity,
    #  goal x/y in body frame, goal distance]
    observation_space = 261
    state_space = 0

    linear_scale = 0.25   # m/s
    angular_scale = 0.5   # rad/s

    lidar_max_distance = 10.0  # m -- also the value reported for rays that hit nothing

    sim = SimulationCfg(
        device="cuda:0",
        dt=1.0 / 120.0,
        render_interval=decimation,
    )

    scene: CollisionEnvSceneCfg = CollisionEnvSceneCfg(
        num_envs=4,
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
    # rew_robot_collision = -100.0


# -----------------------------------------------------------------------------
# Environment Creation
# -----------------------------------------------------------------------------

class CollisionAvoidanceEnv(DirectRLEnv):

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

        print("LIDAR DEVICE:", self.lidar.device)
        print("LIDAR PRIM PATH:", self.lidar.cfg.prim_path)

        self.goal_pos = torch.zeros((self.num_envs, 2), device=self.device)
        self.previous_distance = torch.zeros(self.num_envs, device=self.device)

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

        self.collisions_array = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
        self.is_too_close = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
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

        self.scene.sensors["contact_forces"] = self.contact_sensor

        # self.scene.clone_environments(copy_from_source=False)

        lidar_cfg = RayCasterCfg(
            prim_path=f"{env_regex}/scene/{ROVER_PATH}/lidar_link",
            mesh_prim_paths=["/World"],
            update_period=0.0,
            offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 0.21)),
            pattern_cfg=patterns.LidarPatternCfg(
                channels=16,
                vertical_fov_range=(0.0, 0.0),
                horizontal_fov_range=(-180.0, 180.0),
                horizontal_res=22.5,
            ),
            max_distance=self.cfg.lidar_max_distance,
        )
        self.lidar = RayCaster(lidar_cfg)
        self.scene.sensors["lidar"] = self.lidar

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

    def _pre_physics_step(self, actions: torch.Tensor) -> None:
        self.actions = actions.clone()


    def _apply_action(self):
        # policy outputs are in [-1, 1]; scale them to physical command units
        linear_speed = self.actions[:, 0] * self.cfg.linear_scale    # m/s
        angular_speed = self.actions[:, 1] * self.cfg.angular_scale  # rad/s

        # differential drive: contact-point speed of each side, in m/s
        left_speed = linear_speed - angular_speed * self.wheel_base / 2.0
        right_speed = linear_speed + angular_speed * self.wheel_base / 2.0

        # joint targets are angular velocities (rad/s), so divide by the wheel radius
        left_velocity = left_speed / self.wheel_radius
        right_velocity = right_speed / self.wheel_radius

        # order must match self._wheel_ids: [fl, fr, rl, rr]
        wheel_velocities = torch.stack(
            [
                left_velocity,
                right_velocity,
                left_velocity,
                right_velocity,
            ],
            dim=-1,
        )

        self.rover_rb3.set_joint_velocity_target_index(
            target=wheel_velocities,
            joint_ids=self._wheel_ids,
        )

    # -------------------------------------------------------------------------
    # Observations
    # -------------------------------------------------------------------------

    def _update_sensor_state(self) -> None:
        """Refresh contact / lidar derived state.

        DirectRLEnv.step() calls _get_dones() and _get_rewards() *before*
        _get_observations(), so computing this inside _get_observations() left
        terminations and rewards acting on the previous step's sensor readings.
        This is called at the top of _get_dones() so both see fresh data, and
        again from _get_observations() to cover the reset path, where
        _get_dones() does not run.
        """
        contact_forces = wp.to_torch(self.contact_sensor.data.net_forces_w)
        contact_magnitude = torch.linalg.vector_norm(contact_forces, dim=-1)
        self.collisions_array = (contact_magnitude > 1.0).any(dim=1)

        lidar_origin = torch.as_tensor(self.scene["lidar"].data.pos_w, device=self.device)
        lidar_output = torch.as_tensor(self.scene["lidar"].data.ray_hits_w, device=self.device)

        lidar_distances = torch.linalg.vector_norm(lidar_output - lidar_origin.unsqueeze(1), dim=-1)

        # Rays that hit nothing come back as inf. Feeding inf to the policy produces
        # NaNs on the first backward pass, so saturate misses at the sensor range.
        self.lidar_distances = torch.nan_to_num(
            lidar_distances,
            nan=self.cfg.lidar_max_distance,
            posinf=self.cfg.lidar_max_distance,
            neginf=self.cfg.lidar_max_distance,
        ).clamp(0.0, self.cfg.lidar_max_distance)

        # NOTE: this measures proximity to *any* lidar return, which in a
        # single-robot environment is always a wall. It is applied with
        # cfg.rew_robot_proximity_penalty; separate the two once a second robot
        # exists, otherwise wall proximity is penalised twice.
        self.is_too_close = (self.lidar_distances < WALL_MARGIN).any(dim=1)

    def _goal_in_body_frame(self) -> tuple[torch.Tensor, torch.Tensor]:
        """Goal offset expressed in the robot's own frame, plus its magnitude."""
        robot_pos = wp.to_torch(self.rover_rb3.data.root_pos_w)[:, :2]
        robot_quat = wp.to_torch(self.rover_rb3.data.root_quat_w)

        goal_relative_w = torch.zeros((self.num_envs, 3), device=self.device)
        goal_relative_w[:, :2] = self.goal_pos - robot_pos

        # only the heading matters for a ground robot; ignore roll/pitch
        goal_relative_b = quat_apply_inverse(yaw_quat(robot_quat), goal_relative_w)

        distance = torch.linalg.vector_norm(goal_relative_b[:, :2], dim=-1)

        return goal_relative_b[:, :2], distance

    def _get_observations(self) -> dict:
        # covers reset(), where _get_dones() has not run
        self._update_sensor_state()

        # body-frame velocities: root_lin_vel_w[:, 0] is the world x component,
        # which stops being the robot's forward speed as soon as it turns
        linear_velocity = wp.to_torch(self.rover_rb3.data.root_lin_vel_b)[:, 0]
        angular_velocity = wp.to_torch(self.rover_rb3.data.root_ang_vel_b)[:, 2]

        # Without this the policy cannot perceive the goal it is rewarded for
        # reaching, and the task is unlearnable.
        goal_relative_b, goal_distance = self._goal_in_body_frame()

        obs = torch.cat(
            (
                self.lidar_distances.reshape(self.num_envs, -1),
                linear_velocity.unsqueeze(-1),
                angular_velocity.unsqueeze(-1),
                goal_relative_b,
                goal_distance.unsqueeze(-1),
            ),
            dim=-1,
        )

        return { "policy": obs }

    # -------------------------------------------------------------------------
    # Rewards
    # -------------------------------------------------------------------------

    def _get_rewards(self) -> torch.Tensor:

        _, current_distance = self._goal_in_body_frame()

        progress = self.previous_distance - current_distance
        # TODO global variable
        goal_reached = current_distance < 0.15

        progress_rew = self.cfg.rew_gets_closer_to_goal * progress
        goal_rew = goal_reached.float() * self.cfg.rew_reach_goal
        collision_rew = self.collisions_array.float() * self.cfg.rew_wall_collision
        proximity_rew = self.is_too_close.float() * self.cfg.rew_robot_proximity_penalty
        step_rew = torch.full((self.num_envs,), self.cfg.rew_step, device=self.device)

        total_reward = goal_rew + progress_rew + collision_rew + proximity_rew + step_rew
        self.previous_distance = current_distance

        return total_reward

    # -------------------------------------------------------------------------
    # Termination
    # -------------------------------------------------------------------------

    def _get_dones(self):
        # runs before _get_rewards() and _get_observations(), so refresh here to
        # keep terminations and rewards on the current step's sensor data
        self._update_sensor_state()

        _, current_distance = self._goal_in_body_frame()
        goal_reached = current_distance < 0.15

        has_collided = self.collisions_array

        terminated = (has_collided | goal_reached)
        time_out = (self.episode_length_buf >= self.max_episode_length - 1)

        return terminated, time_out

    # -------------------------------------------------------------------------
    # Reset
    # -------------------------------------------------------------------------

    def _reset_idx(self, env_ids: Sequence[int] | None):
        if env_ids is None:
            env_ids = self.rover_rb3._ALL_INDICES

        env_ids = torch.as_tensor(
            env_ids,
            device=self.device,
            dtype=torch.long,
        )

        super()._reset_idx(env_ids)

        # choose a random position from the list of precomputed valid positions for each env
        indices = torch.randint(
            0,
            self.spawn_points.shape[0],
            (len(env_ids),),
            device=self.device,
        )

        # spawn points are stored in env-local coordinates -> re-base onto each env
        next_spawn_positions = self.spawn_points[indices] + self.scene.env_origins[env_ids, :2]

        # random robot orientation
        yaw = torch.rand(len(env_ids), device=self.device) * 2.0 * math.pi 

        root_pose = torch.zeros((len(env_ids), 7), device=self.device, dtype=torch.float32)

        init_rb3 = self.cfg.scene.rover_rb3.init_state.pos[2]
        root_pose[:, 0:2] = next_spawn_positions
        root_pose[:, 2] = init_rb3

        # IsaacLab 3.x quaternion order is (x, y, z, w) -- yaw is a rotation about Z
        root_pose[:, 3] = 0.0                   # X
        root_pose[:, 4] = 0.0                   # Y
        root_pose[:, 5] = torch.sin(yaw / 2.0)  # Z
        root_pose[:, 6] = torch.cos(yaw / 2.0)  # W

        root_vel = torch.zeros((len(env_ids), 6), device=self.device, dtype=torch.float32)

        self.rover_rb3.write_root_pose_to_sim(root_pose, env_ids)        
        self.rover_rb3.write_root_velocity_to_sim(root_vel, env_ids)

        zero_joint_vel = torch.zeros((len(env_ids), self.rover_rb3.num_joints), device=self.device)
        self.rover_rb3.write_joint_velocity_to_sim_index(velocity=zero_joint_vel, joint_ids=None, env_ids=env_ids)

        self.rover_rb3.write_data_to_sim()

        # Sample the goal from the same validated free-space set as the spawn, so it is
        # always reachable. The maze is not centred on the env origin, so the previous
        # hardcoded [WALL_MARGIN, 4 - WALL_MARGIN] box fell outside it entirely.
        goal_indices = torch.randint(
            0,
            self.spawn_points.shape[0],
            (len(env_ids),),
            device=self.device,
        )
        self.goal_pos[env_ids] = self.spawn_points[goal_indices] + self.scene.env_origins[env_ids, :2]

        self.previous_distance[env_ids] = torch.linalg.vector_norm(
            self.goal_pos[env_ids] - next_spawn_positions, dim=-1
        )

        self.collisions_array[env_ids] = False
        self.is_too_close[env_ids] = False
        # self.robot_collision[env_ids] = False
