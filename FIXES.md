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

The space was subsequently widened to **261** to include the goal — see section 10.

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

## 10. The policy could not perceive the goal

The observation was 256 lidar distances + linear velocity + angular velocity.
It contained **no goal information at all**. `_get_observations` computed
`goal_relative` and `self.goal_distance` and then discarded both — `goal_distance`
was assigned and never read anywhere in the file.

The reward function asked the robot to reach a goal that was invisible to the
policy. No RL algorithm can solve that; the best available behaviour is
"drive around without hitting walls."

The goal offset is now expressed in the **robot's own frame** — using
`quat_apply_inverse(yaw_quat(root_quat_w), ...)`, so it rotates with the robot
rather than being a fixed world vector — and appended as three values:
body-frame `x`, body-frame `y`, and the scalar distance.
`observation_space` is now **261** (256 + 2 + 3).

## 11. Terminations and rewards ran on stale sensor data

`DirectRLEnv.step()` executes in this order:

```
_get_dones()        <- line 467
_get_rewards()      <- line 469
_reset_idx()        <- line 474
_get_observations() <- line 486
```

`self.collisions_array` and `self.is_too_close` were only computed inside
`_get_observations()`, i.e. at the *end* of the step. So dones and rewards
consumed values produced by the previous step: collisions terminated one step
late and were rewarded one step late.

There was also a reset-loop risk. `_get_observations()` runs immediately after
`_reset_idx()` teleports the robot, so it could latch contact forces from the
pre-reset pose and terminate the freshly-started episode.

Extracted into `_update_sensor_state()`, called at the top of `_get_dones()` so
that dones and rewards both see the current step, and again from
`_get_observations()` to cover the `reset()` path where `_get_dones()` never runs.
Collision flags are not part of the observation, so the second call cannot leak a
stale value into the policy input.

## 12. Forward velocity was measured in the world frame

`root_lin_vel_w[:, 0]` is the world x-component, not the robot's forward speed —
the two diverge as soon as the robot turns, so the observation stopped meaning
what its name implied. Now uses `root_lin_vel_b` / `root_ang_vel_b`.

## 13. Dead state and duplicated reward terms

`wall_collision`, `robot_collision`, `goal_distance` and `rb3_linear_velocity`
were initialised and never read. In `_get_rewards`, `collision_rew` and
`proximity_rew` were each computed twice, the first pair immediately overwritten
by the second. All removed.


## 14. Second agent (XGO): what works and what is blocked

The project goal is two robots. The XGO quadruped was previously deactivated in
`_setup_scene`; it is now simulated, but it is **not yet drivable** via the gait
stack that ships in this repo. This section records why, because the reason is
not obvious and it changes the cost of finishing the job.

### Fixed: joint limits

The URDF -> USD conversion left all 15 revolute joints at `(-inf, inf)`, which the
physics parser rejects outright. The limits are absent from the asset:
`payloads/Physics/physx.usda` only sublayers `physics.usda` and adds
`PhysxJointAPI`, and `physics.usda` authors just two limit attributes, both zero.
No URDF is present in the repo to recover the true values from.

`_fix_xgo_joint_limits()` now authors finite limits before simulation start.
This originally used an assumed +/-90 deg. **Superseded by section 19**: the real
per-joint travel now comes from the vendor's driver config.

Result: zero `NewtonMimicAPI` errors, articulation loads as 17 joints / 18 bodies,
all 12 leg joints resolve, robot settles upright without exploding.

### Fixed: batched kinematics

`quadruped_leg_kinematics.LegIK` is scalar numpy solving one leg at a time, which
cannot drive a vectorised env. `xgo_gait.py` is a torch port, batched over
environments and legs. It **agrees with the original to 1.8e-07** over random
targets, and additionally stays finite on out-of-reach targets where the original
returns NaN (its domain and negative-sqrt guards become clamps).

The geometry constants were read back out of the USD joint frames rather than
trusted: `localPos0` gives hip offsets of `(+/-0.075, +/-0.0225, 0)`, shoulder
`0.030988` and elbow `0.059900`, which match `XGOModel`'s defaults exactly.

### Blocked: the asset's joint convention is not the one the IK assumes

Driving the IK's stance angles into the XGO produces a collapsed, pitched robot:
body at ~0.065 m against a commanded 0.13 m, and upright measure 0.52 (~58 deg of
pitch). The joints track their targets to within 1.2 deg, so the actuators are
fine -- the *angles themselves* do not mean what `LegIK` thinks they mean.

Two concrete mismatches, both measured:

1. **The zero pose is wrong.** At all-zero joint angles the legs lie flat in the
   horizontal plane. For the front-left leg, in the body frame:

   ```
   hip (13_Link)  (+0.075, +0.022, -0.000)
       12_Link    (+0.075, +0.053, -0.001)   <- out along +y by shoulder_length
       11_Link    (+0.015, +0.053, -0.001)   <- back along -x by elbow_length
   ```

   `LegIK`'s zero is a leg hanging straight down.

2. **The axes were baked.** Every revolute joint reports `axis = Z`; the URDF
   importer folded the real axis into each joint's `localRot0`. Those local Z axes
   map to world **Y** (shoulder), **-Y** (elbow) and **Z** (wrist) -- not the
   X/Y/Y a conventional quadruped IK assumes.

So this is not a unit or sign fix. Closing it means re-deriving the IK against the
asset's own frame chain (`localRot0` / `localRot1` per joint), or re-importing the
URDF with a converter that preserves conventional axes -- which would also restore
the missing joint limits, and is probably the better fix if the URDF can be found.

### Still outstanding for two agents

- A second lidar and contact sensor for the XGO.
- `DirectRLEnv` -> `DirectMARLEnv`, `possible_agents = ["rover", "xgo"]`, with
  per-agent observation/action spaces, rewards and terminations.
- Two-robot spawn logic so the pair does not spawn overlapping, and robot-robot
  proximity/collision detection -- the actual point of the exercise, and still
  impossible while only one robot moves.

## 15. Two independent agents (DirectMARLEnv)

`DirectRLEnv` -> `DirectMARLEnv` with `possible_agents = ["rover", "xgo"]`, both
robots sharing each env so they can actually collide. They are **independent
learners**: separate policies, no shared critic, no parameter sharing, and
`state_space = 0`. They do not even share an action space.

| agent | action space | observation space |
| --- | --- | --- |
| rover | 2 (linear, angular velocity) | 261 |
| xgo | 12 (joint position targets) | 292 |

The XGO is driven at the **joint level** rather than through the shipped gait
stack. That stack cannot drive this asset (section 14), and learning joint targets
sidesteps the problem entirely: the policy discovers whatever convention the asset
has. Its observation adds the proprioception joint control needs -- projected
gravity, body linear and angular velocity, joint positions and velocities -- which
a velocity-commanded wheeled base never requires.

XGO-specific reward and termination shaping was added because a joint-level policy
has to solve standing before goal progress means anything: an alive/upright bonus,
a large penalty for falling, an action-rate penalty for smoothness, and termination
when the body drops below `XGO_MIN_HEIGHT` or tips past `XGO_MIN_UPRIGHT`.

Note on reset semantics: `DirectMARLEnv` resets an env only when **all** agents are
done (`reset_buf = prod(terminated) | prod(time_out)`), so one robot finishing does
not cut the other's episode short.

Reset now draws four independent points from the validated free-space set -- a
spawn and a goal per robot -- with `_resample_far_enough` rejecting only pairs that
would start on top of each other. Bounded retries rather than a `while` loop,
because in a small maze there may be no valid pair and a loop would hang the reset.

## 16. The lidar never saw anything

The single most consequential bug found so far, and it was silent.

`RayCasterCfg(mesh_prim_paths=["/World"])` looks like "ray cast against the whole
scene". It is not. IsaacLab 3.0's ray caster states plainly in
`ray_caster_cfg.py`: *"Currently, only a single static mesh is supported."* The
config therefore bound to the **first** mesh found under `/World` -- visible in
every run log as:

```
[INFO]: Read mesh prim: /World/envs/env_0/scene/_MAZE_/april_tag_origin
        with 8 vertices and 24 faces.
```

An 8-vertex april tag. Every one of the 256 rays missed the maze on every step, so
the lidar returned a constant `10.0` (the saturation value from section 5). 256 of
the rover's 261 observations were a constant. The policy had **no obstacle
perception at all**, which for a collision-avoidance task means the central signal
was absent while everything still looked healthy -- shapes correct, values finite.

Measured before the fix: driving the rover flat out into walls for 250 steps, the
minimum lidar range ever observed was `10.0000`. Contact forces peaked at 362 N over
the same run, so the robot was demonstrably hitting walls the lidar could not see.

The scan is now cast directly with `isaaclab.utils.warp.raycast_mesh` against the
merged maze mesh already built for the spawn search (27,755 vertices / 55,242
triangles), replacing the `RayCaster` sensors entirely. After the fix the same test
reports a minimum range of `0.1058 m`.

While replacing it: the old pattern was 16 channels x 16 headings with
`vertical_fov_range=(0, 0)`, i.e. 16 unique directions duplicated 16 times. The
same 256-value budget now buys **256 distinct headings**.


## 17. Throughput: the step cost is fixed, so run many more envs

Simulating the quadruped dropped throughput from ~15 steps/s to ~1.8. Profiling
showed the time is **not** in the observation pipeline:

```
full env.step            ~500 ms
  raw sim.step             55.5 ms  x4 (decimation)  = 222 ms
  scene.write_data_to_sim  38.4 ms  x4               = 154 ms
  _update_sensor_state     17.3 ms  x2 (dones + obs) =  35 ms
  one _cast_lidar           3.0 ms
```

A single physics substep costing 55 ms for four environments is pathological --
standard IsaacLab does this in well under a millisecond -- and the same is true of
`write_data_to_sim`. Both turn out to be almost entirely **fixed overhead**, which
the scaling measurement makes obvious:

| envs | startup | step time | agent-samples/s |
| ---: | ---: | ---: | ---: |
| 4 | 22 s | 552 ms | 14.5 |
| 32 | 31 s | 557 ms | 115 |
| 128 | 35 s | 607 ms | 422 |
| 256 | 47 s | 575 ms | 891 |
| 512 | 74 s | 724 ms | 1415 |

Step time barely moves from 4 to 256 environments. Throughput therefore scales
almost linearly with env count, and going from the original 4 to 512 is a **98x**
improvement in samples per second for 31% more wall time per step.

`scene.num_envs` now defaults to 256, and `train.py` takes `--num_envs`.

This mitigates the problem rather than fixing it. The fixed cost is still there;
it is just amortised over far more samples. Two candidates for attacking it
directly, neither attempted here:

- **The scene is spawned per environment, not cloned.** `_setup_scene` loops over
  `num_envs` calling `usd_cfg.spawn.func(...)`, so each env gets its own full copy
  of the 55k-triangle maze instead of an instanced one. The original code has
  `self.scene.clone_environments(copy_from_source=False)` commented out. This is
  the most likely source of both the fixed per-step cost and the startup time
  (74 s at 512 envs). Switching to cloning would need care: the per-env XGO joint
  limit repair and the prim paths both assume independent copies.
- **Platform.** This machine is a GB10 (Grace Blackwell, ARM). Isaac Sim's
  per-call CPU overhead may simply be higher here than on x86.


## 18. Training: IPPO via skrl

`train_rl.py` trains both robots with **IPPO** (independent PPO) from skrl 2.1.0,
configured by `agents/skrl_ippo_cfg.yaml`. IPPO is the right fit: each agent keeps
its own policy and its own critic, no shared critic, no parameter sharing. Verified
from a checkpoint -- the saved networks are genuinely independent and correctly
sized per agent:

```
rover  policy: 261 -> 256 -> 128 -> 64 -> 2
xgo    policy: 292 -> 256 -> 128 -> 64 -> 12
```

`train.py` remains the benchmark / smoke-test harness.

Three things had to be fixed to get a numerically stable run.

### state_space must be -1, not 0

`state_space = 0` ("build no state space") is the honest value for IPPO, which
never reads a joint state. But skrl's `Runner` builds models generically and dies
on a zero-dimensional space:

```
RuntimeError: cannot reshape tensor of 0 elements into shape [-1, 0]
```

`-1` (concatenate every agent's observations) is what IsaacLab's own MARL reference
task uses. The buffer is built but unused by IPPO, and it is what MAPPO would need
if a centralised critic is ever wanted.

### Goals could spawn inside the success radius

Goals were drawn from the free-space set with no minimum distance from the spawn,
so an episode could begin already solved -- measured at 5/64 envs for the rover.
Those instant terminations gave PPO near-zero-length episodes (mean episode length
**1.09 steps**), and the resulting degenerate advantage statistics drove the XGO's
policy, value and entropy losses to `NaN`.

`MIN_SPAWN_GOAL_DISTANCE = 0.75` now applies, reusing `_resample_far_enough`. Mean
episode length went to ~79 steps and the NaNs disappeared.

### Terminated agents kept accruing penalties

`DirectMARLEnv` resets an env only once **every** agent is done
(`reset_buf = prod(terminated) | prod(time_out)`), so an agent that finishes early
keeps being stepped. A rover parked against a wall took `rew_wall_collision` every
step for the rest of the episode, driving mean return from -100 to **-3081** while
learning nothing.

Masking the dead agent's reward to zero was tried first and is **worse**: it makes
most of the batch exactly zero, and the near-zero advantage variance sends PPO
straight back to NaN.

The fix is a shared episode boundary -- when either robot finishes, the episode
ends for both. That matches how the environment already behaves: one
`episode_length_buf`, and a reset that repositions both robots together.

### Measured after the fixes (128 envs, 300 timesteps)

```
NaN tags                     : NONE
Value loss (rover)           : 0.472 -> 0.250
Value loss (xgo)             : 3.655 -> 0.439
Total reward (mean)          : -58.0 -> -52.8
Episode length (mean)        : 1.7 -> 4.4 steps
```

Both agents are learning and the run is numerically stable. Episodes are still
short because the XGO falls quickly -- it cannot stand yet, which is the open
locomotion problem, not an environment bug.


## 19. The vendor sources: real joint limits, but the URDF does not fix the convention

The `mini2_description` and `xgo_ros` archives were obtained and inspected. The
outcome contradicted the expectation in section 14, in both directions.

### Re-importing the URDF would not have helped

Section 14 assumed the missing joint limits and the all-Z joint axes were URDF ->
USD import artifacts. They are not. Read directly from
`reference/mini2_description.urdf`:

- **All 15 revolute joints are `type="continuous"` with no `<limit>` element.**
  The limits are absent from the source, so the USD is faithful to it and no
  re-import can recover them.
- **Every joint declares `axis = "0 0 1"`.** The importer baked nothing; the URDF
  itself uses the convention where each axis is local Z and the real orientation
  lives in the joint's `<origin rpy>`. This is standard SolidWorks URDF exporter
  output.

So the `LegIK` convention mismatch is inherent to how the robot was authored, and
re-importing produces the same asset. What the URDF *does* provide is an explicit,
readable `<origin xyz rpy>` per joint -- the input needed to derive a correct IK,
which is now a tractable job rather than USD archaeology.

### The ROS driver has the real hardware limits

`xgo_ros/config/xgomini.yaml` carries what the URDF lacks:

```yaml
joint_limit:  [[-73,57], [-66,93], [-31,31],   # legs, by within-leg index
               [-65,65], [-50,85], [-90,75]]   # arm
body_limit:   [..., [75,115], ...]             # body height, mm
vx_max: 0.3   vy_max: 0.2   vyaw_max: 1.2
```

`xgo.cpp:162` indexes these as `joint_limit[i % 3]` over the 12 leg joints, so all
four legs share three pairs ordered by position within the leg (arm joints use
`joint_limit[i - 9]`).

The **+/-90 deg assumption from section 14 is now gone**, replaced by these values.
Actions in `[-1, 1]` map onto each joint's own travel, so the policy cannot command
an out-of-range target. Verified: authored limits read back as `13_Joint [-31, 31]`,
`12_Joint [-66, 93]`, `11_Joint [-73, 57]`, and driving actions to both rails keeps
every joint inside its range.

One inference remains, flagged rather than hidden: the SDK does not name its joints,
so mapping within-leg indices 0/1/2 to `N1`/`N2`/`N3` is read off the numeric
suffix. It is well supported -- the hip joint `N3`, attached to `base_link`, gets
the tightest range `[-31, 31]`, exactly what hip abduction should look like.

### Standing height was out of range

`body_limit[2]` puts the real body height at **75-115 mm**, and `xgo.h:53` defaults
foot height to **108 mm**. `XGOModel.height = 0.13` -- inherited by
`xgo_gait.STAND_HEIGHT` -- is above what the robot can reach. Now 0.108.


---

## Verification

`train.py --headless --steps 200` runs to completion. Measured directly:

- 200/200 steps executed, clean shutdown, no traceback.
- Observations are `(num_envs, 261)`, matching `cfg.observation_space`, and
  `torch.isfinite(obs).all()` is `True`.
- The goal distance carried in the observation matches the true goal distance to
  within 6e-8, and the body-frame goal bearing rotates as the robot turns in
  place, confirming it is a body-frame quantity rather than a world-frame one.
- `_update_sensor_state()` runs exactly twice per step (dones + observations).
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
- **The XGO has not learned to stand, let alone walk.** Joint-level control is
  wired and training is stable, but episodes end in ~4 steps because it falls.
  Learning locomotion and navigation from one reward is optimistic; a
  locomotion-first curriculum (flat ground, no goal term, reward for staying up)
  is the likely next step.
- **This is still a single-robot environment.** The XGO quadruped is deactivated
  and only `rover_rb3` is registered, so the project goal of training *two* robots
  is not met. `rew_robot_proximity_penalty`, the commented-out
  `rew_robot_collision` and the former `robot_collision` buffer all show the
  intent, but none of it can do anything with one robot per env. Adding a second
  agent is a design decision — a second articulation under `DirectMARLEnv`, or two
  independent single-agent policies — not a bug fix.
- **`is_too_close` measures walls, not robots.** It triggers on any lidar return
  within `WALL_MARGIN`, which in a single-robot env is always a wall, yet it is
  applied with `rew_robot_proximity_penalty` while walls are already penalised via
  `rew_wall_collision`. Wall proximity is therefore double-counted. This needs
  separating once a second robot exists.
- **The XGO quadruped is loaded then deactivated** in every env. It is the source
  of the `NewtonMimicAPI ... revolute joint without a finite limit` errors in the
  log. Harmless, but it is dead weight in every environment.
- **Lidar rays are 16× redundant**, as described in section 4.
- **`.pyc` files are tracked in git** — 29 of them, including ROS build output.
  Worth a `.gitignore` and an `git rm --cached` pass.
- **Unused imports** (`sample_uniform`, `physicsUtils`, `Gf`, `UsdPhysics`) remain
  in `collision_env.py`; they predate these changes and were left alone to keep
  the diff focused.
