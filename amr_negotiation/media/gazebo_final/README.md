# Gazebo clips on the final code

Ten Gazebo Harmonic runs (TurtleBot3 Waffle, ROS 2 Jazzy) recorded with `record:=true` from the overhead camera,
on main `c99270c`. Two runs at a time, each with its own `ROS_DOMAIN_ID` / `GZ_PARTITION`. Each `.mp4` has its
result JSON (same name) and an animated `.webp` preview (8 fps, 480 px wide). Outcomes below come from those JSONs.
"Batch" is the unrecorded run of the same case in the 460-run final-code batch (`studies/results_raw/gazebo_current.jsonl.gz`).

| Clip | Scenario | Policy | Seed | Success / collision | Yielder → refuge | Makespan [s] | Batch makespan [s] | What it shows |
|---|---|---|---|---|---|---|---|---|
| `corridor_fixed_priority` | `gz_s2`, one-bay corridor | `fixed_priority` | 2 | yes / no | B → bay0 | 65.5 | 65.4 | B gives way by rule, not by cost |
| `corridor_cost_bid` | `gz_s2` | `cost_bid` | 2 | yes / no | A → bay0 | 65.8 | 65.8 | the robot nearer the bay yields |
| `blocked_bay_cost_bid` | `gz_blk_s0`, bay1 holds a box | `cost_bid` | 0 | yes / no | B → bay1, then room_hi | 114.7 | 114.8 | B finds bay1 blocked and falls back to its end room |
| `explore_det35_fixed_priority` | `gz_expdet35_s3`, explore, share on detect, 3.5 m | `fixed_priority` | 3 | yes / no | B → room_hi | 112.4 | 112.4 | the map arrives after the decision, so B reverses to its end room (the paper's late-map failure) |
| `explore_all35_fixed_priority` | `gz_expall35_s3`, explore, share every BID, 3.5 m | `fixed_priority` | 3 | yes / no | B → bay1 | 76.1 | 76.1 | same seed with the map in every BID: B uses bay1, 36 s faster |
| `convoy_group_bid` | `gz_convoy_s0`, A+C convoy vs B | `group_bid` | 0 | yes / no | B → bay1 | 84.5 | 84.5 | the single robot yields to the convoy |
| `tj_exit_fixed_priority` | `gz_tj_s2`, stem robot S leaves the branch | `fixed_priority` | 2 | yes / no | B → bay0, then S → bay1 | 94.5 | 94.5 | the extra robot giving way at the T-junction (Gazebo only, as in the paper) |
| `tj_turnin_cost_bid` | `gz_tjgoal_s1`, S turns into the branch | `cost_bid` | 1 | yes / no | A → bay0 (re-yields to bay1) | 60.7 | 60.7 | turn-in case; A yields twice |
| `clarke_Bx0.5` | `gz_pay_s0`, B reports 0.5× its cost | `clarke` | 0 | yes / no | B → room_hi | 91.7 | 91.6 | B's misreport makes it the yielder |
| `noise_sigma1.0` | `gz_noise_s1`, bid noise σ = 1.0 | `cost_bid` | 1 | yes / no | A → bay0 | 74.4 | 91.7 (B → room_hi) | **differs from the batch run**, see below |

Notes:
- **Noisy bid differs from its batch run.** The noise draw depends on the decision time, which shifts slightly
  between Gazebo runs, so this recording drew different noise and A yielded instead of B. The paper reports this
  source of Gazebo/2D mismatch (5 noisy-bid runs). The clip still shows a noisy-bid encounter, not the batch outcome.
- Excess delay needs the forced-yielder runs of the same case, which exist in Gazebo only for the one-bay
  corridor. Against the batch's better forced run for `gz_s2` ("A yields", total delay = sum of arrival times
  minus the same free-flow times), the corridor clips have +14.6 s (`fixed_priority`) and
  -0.1 s (`cost_bid`). The other clips report makespan only.
- All clips are under 1 MB; no LFS needed.

## Hold variant (branch code, not on main yet)

Recorded on the `hold_for_map` branch, commit `f5249a6` (image `amrneg:hold-be50818`, built before that branch was rebased; same code), same recorder settings.

| Clip | Scenario | Policy | Seed | Success / collision | Yielder → refuge | Makespan [s] | Batch makespan [s] | Excess vs full map [s] | Time to decision [s] | Hold | What it shows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `explore_hold35_fixed_priority` | `gz_exphold35_s3`, explore, share on detect + hold, 3.5 m | `fixed_priority` | 3 | yes / no | B → bay1 | 82.6 | 82.4 | +12.8 | 4.75 | released (no timeout) | the same seed as `explore_det35_fixed_priority`: with the hold, B uses bay1 instead of its end room |

- Conflict at 17.00 s, both robots detect each other at 21.65 s, decision at 21.75 s; no `hold_timeout` in the log.
- Excess is the sum of arrival times minus that of the batch full-map run `gz_2bay35_s3` (fixed priority).
  It is larger than the batch hold run's +12.5 s for this seed; the clip waits ~4.8 s before deciding.
- Both robots had sensed both bays themselves (A at 17.75 s, B at 18.45 s) before they detected each other,
  so here the hold helps by waiting, not through the exchanged map.
