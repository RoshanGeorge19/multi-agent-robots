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
from isaaclab.utils.math import sample_uniform
from isaaclab.utils.mesh import create_trimesh_from_geom_mesh
from isaaclab.utils.warp import convert_to_warp_mesh, raycast_mesh
import warp as wp
from pxr import UsdGeom, Usd, PhysxSchema, UsdPhysics, Gf
from omni.physx.scripts import physicsUtils


WALL_MARGIN = 0.20
ROVER_PATH = "_ROBOTS_/rover_rb3/Geometry/world/base_link"

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

    maze: AssetBaseCfg = AssetBaseCfg(prim_path="{ENV_REGEX_NS}/scene/_MAZE_")

# -----------------------------------------------------------------------------
# Environment Configuration
# -----------------------------------------------------------------------------

@configclass
class CollisionEnvRB3Cfg(DirectRLEnvCfg):
    decimation = 4 # nb of physics simulation steps for each RL action
    episode_length_s = 18.0
    action_space = 2 # linear and angular velocity
    observation_space = 258 # [lidar lasers, linear_velocity, angular_velocity]
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
        self.wall_collision = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
        self.robot_collision = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)

        self.rb3_linear_velocity = 0.0
        self.rb3_angular_velocity = 0.0
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

        self.goal_distance = torch.zeros(self.num_envs, device=self.device)
        self.collisions_array = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
        self.is_too_close = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)

        print("Collision env init done")


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

        xgo_prim_path = f"{prim_path}/_ROBOTS_/xgo_lite"

        xgo_prim = stage.GetPrimAtPath(xgo_prim_path)

        if xgo_prim.IsValid():
            xgo_prim.SetActive(False)
            print(f"[INFO] Disabled XGO: {xgo_prim_path}")

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

    def _get_observations(self) -> dict:
        # get tag pose in isaac sim + noise

        # wp.to_torch avoids compatibility problems
        robot_pos = wp.to_torch(self.rover_rb3.data.root_pos_w)[:, :2] # world frame position, exclude z

        # TODO measure proximity using Lidar

        # TODO check collisions
        contact_forces = wp.to_torch(self.contact_sensor.data.net_forces_w)

        contact_magnitude = torch.linalg.vector_norm(
            contact_forces,
            dim=-1,
        )

        self.collisions_array = (contact_magnitude > 1.0).any(dim=1)

        # compute distance to goal for reward
        goal_relative = (self.goal_pos - robot_pos)
        self.goal_distance = torch.linalg.vector_norm(goal_relative, dim=-1).unsqueeze(-1)

        linear_velocity = (wp.to_torch(self.rover_rb3.data.root_lin_vel_w)[:, 0])
        angular_velocity = (wp.to_torch(self.rover_rb3.data.root_ang_vel_w)[:, 2])

        # check the distances for wall proximity reward
        lidar_origin = torch.as_tensor(self.scene["lidar"].data.pos_w, device=self.device)

        lidar_output = torch.as_tensor(self.scene["lidar"].data.ray_hits_w, device=self.device)

        # print("origin torch:", lidar_origin.shape)
        # print("output torch:", lidar_output.shape)

        lidar_distances = torch.linalg.vector_norm(lidar_output - lidar_origin.unsqueeze(1), dim=-1)

        # Rays that hit nothing come back as inf. Feeding inf to the policy produces
        # NaNs on the first backward pass, so saturate misses at the sensor range.
        lidar_distances = torch.nan_to_num(
            lidar_distances,
            nan=self.cfg.lidar_max_distance,
            posinf=self.cfg.lidar_max_distance,
            neginf=self.cfg.lidar_max_distance,
        ).clamp(0.0, self.cfg.lidar_max_distance)

        # print("========== LIDAR DATA ==========")
        # print("origin type:", type(lidar_origin))
        # print("origin:", lidar_origin)
        # print("output type:", type(lidar_output))
        # print("output:", lidar_output)

        # try:
        #     print("origin shape:", lidar_origin.shape)
        # except Exception as e:
        #     print("origin shape ERROR:", e)

        # try:
        #     print("output shape:", lidar_output.shape)
        # except Exception as e:
        #     print("output shape ERROR:", e)

        # print("===============================")

        self.is_too_close = (lidar_distances < WALL_MARGIN).any(dim=1)

        # pass per-ray distances to the policy: num_rays + linear vel + angular vel,
        # which must equal cfg.observation_space
        obs = torch.cat(
            (
                lidar_distances.reshape(self.num_envs, -1),
                linear_velocity.unsqueeze(-1),
                angular_velocity.unsqueeze(-1),
            ),
            dim=-1,
        )

        return { "policy": obs }

    # -------------------------------------------------------------------------
    # Rewards
    # -------------------------------------------------------------------------

    def _get_rewards(self) -> torch.Tensor:

        robot_pos = wp.to_torch(self.rover_rb3.data.root_pos_w)[:, :2]

        current_distance = torch.linalg.vector_norm(self.goal_pos - robot_pos, dim=-1)

        collision_rew = (
            self.collisions_array.float()
            * self.cfg.rew_wall_collision
        )

        proximity_rew = (
            self.is_too_close.float()
            * self.cfg.rew_robot_proximity_penalty
        )

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

        robot_pos = wp.to_torch(self.rover_rb3.data.root_pos_w)[:, :2]

        current_distance = torch.linalg.vector_norm(self.goal_pos - robot_pos, dim=-1)
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
