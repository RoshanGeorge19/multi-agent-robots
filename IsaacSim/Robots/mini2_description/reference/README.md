# Reference sources for the XGO (mini2)

Provenance for the numbers hardcoded in `IsaacSim/Scripts/train/collision_env.py`
and `xgo_gait.py`. Only the two small text files are kept here; the 38 MB of STL
meshes from `mini2_description.rar` are not committed, since the USD already
carries the geometry.

## `mini2_description.urdf`

The source URDF the scene USD was converted from. Two things it does **not**
provide, both of which were previously assumed to be import artifacts:

- **No joint limits.** All 15 revolute joints are `type="continuous"` with no
  `<limit>` element. The missing limits in the USD are faithful to the source, so
  re-importing cannot recover them.
- **No conventional axes.** Every joint declares `axis = "0 0 1"`; the real
  orientation lives in each joint's `<origin rpy>`. This is standard SolidWorks
  URDF exporter output, not something the importer did.

What it *does* give is an explicit, readable `<origin xyz rpy>` per joint, which
fully specifies the kinematic chain -- the input needed to derive a correct IK for
this robot.

## `xgomini.yaml`

From the vendor's `xgo_ros` driver package. This is where the **real hardware
limits** live:

```yaml
joint_limit:      # degrees
  - [-73, 57]     # within-leg index 0
  - [-66, 93]     # within-leg index 1
  - [-31, 31]     # within-leg index 2
  - [-65, 65]     # arm
  - [-50, 85]     # arm
  - [-90, 75]     # arm
body_limit:
  - [35, -35]     # x, mm
  - [18, -18]     # y, mm
  - [75, 115]     # z (body height), mm
  ...
vx_max: 0.3       # m/s
vy_max: 0.2       # m/s
vyaw_max: 1.2     # rad/s
```

`xgo_ros/src/xgo.cpp:162` indexes these as `joint_limit[i % 3]` across the 12 leg
joints, so all four legs share the same three pairs, ordered by position within
the leg. Arm joints use `joint_limit[i - 9]`, i.e. entries 3-5.

**Inferred mapping** (the SDK does not name the joints): within-leg indices 0/1/2
correspond to joints `N1` / `N2` / `N3` by numeric suffix. The hip joint `N3` --
the one attached to `base_link` -- therefore gets the tightest range, `[-31, 31]`,
which is what you would expect for hip abduction.

`body_limit[2]` also shows the real standing height range is **75-115 mm**, and
`xgo.h:53` defaults foot height to **108 mm**. `XGOModel.height = 0.13` is outside
what this robot can do.
