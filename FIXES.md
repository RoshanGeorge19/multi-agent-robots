# IsaacLab 3.0 fixes for the collision-avoidance training environment

This fork fixes the RL training setup under `IsaacSim/Scripts/train/`, which hung
on startup and could not complete a single RL step. The root cause was a second
Omniverse Kit boot, on top of a set of IsaacLab 2.x assumptions that no longer
hold on 3.0.

Two files changed: `collision_env.py` and `train.py`.

## Environment this was fixed against

| Component | Version |
| --- | --- |
| IsaacLab | 3.0.0 (Newton-backed physics stack) |
| gymnasium | 1.2.1 |
| Python | 3.12 |

The physics backend matters: several of the bugs below exist specifically
because IsaacLab 3.0 no longer runs PhysX as the simulating engine.

---

## 1. The freeze: two Isaac apps in one process

**Symptom.** Training printed the Isaac Lab launch banner and then hung forever,
before any user code ran.

`train.py` launched Kit via `AppLauncher`, then imported `collision_env`, which
at *module scope* launched Kit a second time:

```python
# collision_env.py, at import time
simulation_app = SimulationApp({"headless": False})
```

`SimulationApp` has no re-entry guard — nothing in its `__init__` detects an
already-running framework — so the second boot blocked against the first. Because
this ran during the import on line 14 of `train.py`, it hung before reaching any
of the training code.

**Fix.** The env module no longer launches the app. `train.py` is the sole
entrypoint and owns the `AppLauncher`. The now-dead `if __name__ == "__main__"`
block at the bottom of `collision_env.py` was removed: it duplicated `train.py`
and referenced the deleted `simulation_app`. It could not work as a standalone
entrypoint anyway, since Isaac must be launched *before* the `isaaclab`/`omni`
imports at the top of the module, which is too late from inside `__main__`.

Two more import-time failures were fixed alongside it:

- `from isaaclab.utils import video` — no such module in IsaacLab 3.0.0, and unused.
- The scene USD path was hardcoded to `/home/johanna/Workspaces/...`, a path that
  exists only on the original author's machine. It is now derived from `__file__`.

## 2. `train.py` built an environment and used it as a config

```python
env_cfg = CollisionAvoidanceEnv(cfg=rb3_cfg)   # this is an ENV, not a cfg
env_cfg.viewer.resolution = (640, 480)         # AttributeError
env = gym.make("CollisionAvoidance", cfg=env_cfg, ...)   # builds a SECOND env
```

This constructed a full environment (spawning the entire scene), then set viewer
attributes on the env instead of the config, then passed that env object as `cfg`
to `gym.make`, which built another one. `DirectRLEnv` has no `.viewer` attribute —
the viewer lives on the *config* (`DirectRLEnvCfg.viewer`) — so this raised
`AttributeError` as soon as the freeze was fixed.

Now `train.py` builds a `CollisionEnvRB3Cfg`, sets the viewer fields on it, and
passes the config to `gym.make`.

Also in `train.py`:

- `if terminated or truncated:` raised `Boolean value of Tensor with more than one
  element is ambiguous` — these are per-env tensors. `DirectRLEnv` auto-resets
  finished envs, so the block was removed rather than rewritten.
- Attribute access goes through `env.unwrapped`. Gymnasium 1.x wrappers no longer
  forward arbitrary attributes, so `env.num_envs` / `env.cfg` / `env.device` would
  fail through `RecordVideo`.
- `disable_env_checker=True` on `gym.register`, since IsaacLab returns batched
  observations that the passive env checker rejects.
- `steps_done` is actually incremented — the benchmark previously always printed `0`.
- Video recording is opt-in behind `--video` (which implies `--enable_cameras`), so
  the default path runs headless without a camera pipeline. Added `--steps`.

## 3. Quaternion order changed in IsaacLab 3.x

IsaacLab 3.0 uses **`(x, y, z, w)`** throughout — see `asset_base_cfg.py` and
`base_rigid_object_data.py`. IsaacLab 2.x used `(w, x, y, z)`.

The reset wrote w-first:

```python
root_pose[:, 3] = torch.cos(yaw / 2.0)  # labelled W -- actually X in 3.0
root_pose[:, 6] = torch.sin(yaw / 2.0)  # labelled Z -- actually W
```

So the intended random yaw became a rotation about **X**, and robots spawned
tipped over. Now written as `(0, 0, sin(yaw/2), cos(yaw/2))`.

Note the `init_state` `rot=(0, 0, 0, 1)` elsewhere in the config was already
correct — that is identity in xyzw.

## 4. Observation space mismatch: 258 declared, 770 delivered

The lidar is configured with `channels=16` and a `-180°..180°` sweep at `22.5°`
resolution. IsaacLab detects the full circle and drops the duplicate wrap point,
giving 16 horizontal angles, so **256 rays** total.

`ray_hits_w` is therefore `(num_envs, 256, 3)`. The code flattened those raw xyz
hit coordinates into the observation:

```python
lidar_output.reshape(self.num_envs, -1)   # 768 values
```

768 + 2 velocities = 770, against a declared `observation_space = 258`. Since
258 = 256 + 2, the intent was clearly per-ray *distances*, which the code already
computed (twice, redundantly). It now feeds `lidar_distances`.

> Worth knowing: `vertical_fov_range=(0.0, 0.0)` with `channels=16` produces 16
> identical copies of the same 16 directions. The observation is 256 numbers but
> only 16 are unique. Setting `channels=1` gives 16 real rays and an observation
> of 18 — a deliberate choice to make, since it changes `observation_space`.

## 5. Lidar misses returned `inf`

Rays that hit nothing come back as `inf`, which propagates into the observation
and would produce `NaN` on the first backward pass of any policy.

Distances are now saturated at the sensor range via a new `lidar_max_distance`
config field, which the sensor config also reads so the two cannot drift apart.

## 6. Every robot reset into env 0's maze

Spawn points were sampled from the world-space bounding box of
`/World/envs/env_0/scene/_MAZE_`, then written directly as world root poses for
*all* envs. Every robot teleported into env 0 regardless of which env it belonged
to.

Spawn points are now stored relative to env 0's origin and re-based onto each
env's own origin at reset.

## 7. Goals were sampled outside the maze entirely

```python
rand_x = torch.rand(...) * (4.0 - 2.0 * WALL_MARGIN) + WALL_MARGIN
self.goal_pos[env_ids, 0] = self.scene.env_origins[env_ids, 0] + rand_x
```

This samples a 4×4 box anchored at the env origin. But the maze occupies roughly
`x ∈ [-1.74, -0.26]`, `y ∈ [0.22, 1.11]` in env-local coordinates — it is not
centred on the origin, and the two regions do not overlap at all.

Every goal was unreachable, so the task was unlearnable regardless of the RL
algorithm. Goals are now drawn from the same validated free-space set as spawns,
which guarantees they sit on open floor inside the maze.

## 8. Wheel commands were never scaled or converted

Three separate problems in `_apply_action`:

- `linear_scale` and `angular_scale` were never applied. Instead, `__init__`
  contained `self.actions[0] = self.cfg.linear_scale` / `self.actions[1] = ...`,
  which does not set scale factors — `self.actions` is a `(num_envs, action_space)`
  tensor created by `DirectRLEnv.__init__`, so those lines clobbered the entire
  action rows of envs 0 and 1. Both lines removed.
- Differential-drive output was in m/s, but `set_joint_velocity_target` expects
  **rad/s**. `self.wheel_radius` was defined and never used. Speeds are now divided
  by the wheel radius.
- Wheel ordering assumed the articulation's joint order matches the order of
  `joint_names_expr` in the config, which is not guaranteed. Indices are now
  resolved with `find_joints(..., preserve_order=True)` and passed to
  `set_joint_velocity_target_index`.

A `print(self.actions)` executing on every physics substep was also removed.

## 9. Spawn-point search: PhysX scene queries do not work on this backend

This was the most significant finding, and the reason the spawn filter could
never have worked.

`_get_spawn_points` filtered candidates using
`get_physx_scene_query_interface().raycast_closest(...)`. On IsaacLab 3.0's
Newton-backed stack, **PhysX is not the simulating engine and that interface has
no populated scene**. Direct measurement: every ray returns `{'hit': False}`,
anywhere in the scene, before sim start, after `sim.reset()`, and after stepping.
PhysX itself warns `Physx scene queries can only be performed during simulation`.

Two further bugs compounded it:

- **The result of a miss is truthy.** `raycast_closest` returns a `dict`; on a miss
  that is `{'hit': False}`, which is a non-empty dict. The original `if hit:` was
  therefore always true, so *all* 10,000 candidates were accepted unfiltered. The
  filter was a silent no-op and robots could spawn inside walls.
- **The ray could not reach the maze.** The probe started at `z = 10.0` with
  `distance = WALL_MARGIN` (0.20), so it stopped at `z = 9.8` while the maze tops
  out at `z ≈ 1.58`. `WALL_MARGIN` is a lateral clearance, not a probe length; the
  two were conflated.

**Fix.** Replaced with `isaaclab.utils.warp.raycast_mesh` against a warp mesh built
from the maze's USD geometry (27,755 vertices / 55,242 triangles). This is
backend-independent and batched on the GPU rather than looping 10,000 sequential
Python raycasts. The filter now does:

1. A downward probe from above the maze, rejecting candidates with geometry
   standing at their `(x, y)`.
2. Four lateral rays at body height, rejecting anything within `WALL_MARGIN` of a
   wall.

If no candidate survives, it raises a clear error naming the thresholds, instead
of failing inside `torch.stack` on an empty list.

Typical yield is ~1,300 of 4,000 candidates, a plausible free-space fraction for
this maze.

---

## Verification

`train.py --headless --steps 200` runs to completion. Measured directly:

- 200/200 steps executed, clean shutdown, no traceback.
- Observations are `(num_envs, 258)`, matching `cfg.observation_space`, and
  `torch.isfinite(obs).all()` is `True`.
- All four robots spawn inside their **own** maze (env origins `(±6, ±6)`).
- All four spawn upright — body up-axis z-component is exactly `1.0`, and the
  quaternions are pure yaw (`x = y = 0`).
- Commanded wheel velocity under full forward action is ~6.6 rad/s, matching
  `linear_scale / wheel_radius = 0.25 / 0.038 = 6.58`.

## Known remaining issues

These are **not** fixed here.

- **Throughput is low.** ~14–17 steps/s at 4 envs, roughly 0.5× real-time. Expected
  for a 55k-triangle maze cloned four times with `replicate_physics=True`, but
  worth addressing before any long training run.
- **No learning algorithm is attached.** Everything above steps a zero/constant
  action policy. The env is in a shape that can feed rsl_rl / skrl / RL-Games, but
  wiring one up is still to do.
- **The XGO quadruped is loaded then deactivated** in every env. It is the source
  of the `NewtonMimicAPI ... revolute joint without a finite limit` errors in the
  log. Harmless, but it is dead weight in every environment.
- **Lidar rays are 16× redundant**, as described in section 4.
- **`.pyc` files are tracked in git** — 29 of them, including ROS build output.
  Worth a `.gitignore` and an `git rm --cached` pass.
- **Unused imports** (`sample_uniform`, `physicsUtils`, `Gf`, `UsdPhysics`) remain
  in `collision_env.py`; they predate these changes and were left alone to keep
  the diff focused.
