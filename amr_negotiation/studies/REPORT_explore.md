# Explore mode: robots map as they go and share the map only after sensing each other

Scenario: `scenarios/corridor_two_bays.yaml` (bay0 at x=3 north, bay1 at x=7 south, end rooms). Script
`python studies/explore_map.py` → `report/explore_map.md`, raw rows in `results_raw/explore_map.csv.gz`.
Grid: 4 map conditions × 3 policies × {0%, 50%} loss × negotiation range {6.0, 3.5} m × 30 seeds
(B start delay random 0–8 s) = 1440 episodes. Gazebo subset: see the Gazebo section below.

## Model

New `AgentParams` switches (all default off, so earlier studies are unchanged):

- `explore`: the robot starts knowing only the corridor and the end rooms. A bay is added to its map once the
  bay is within `lidar_range` (3.5 m) while the robot is in the corridor lane (`refuge_learned`, source `sensed`).
  This is bay discovery on a known corridor layout, not SLAM: there is no occupancy grid and no occlusion by walls.
- `share_map`: BIDs carry the sender's known bays (as in the asymmetric-map study).
- `share_on_detect`: with `share_map`, a robot sends its map only once its own sensor has detected the other
  robot (a sensed object at the peer's STATE position, `peer_detected`). On detection it sends one `MAP`
  message, and later BIDs carry the map. Before that, the robots still talk (STATE, BID) but share no map.
- `Scenario.agent_params` sets these for every robot from the scenario file, so the ROS nodes pick them up
  without new launch arguments.

Conditions: `full` (complete map, the earlier studies), `explore_no_share`, `explore_share_always`,
`explore_share_on_detect`. The negotiation range (`detect_range`, from STATE messages) is 6.0 m by default, which
is beyond the 3.5 m lidar range; 3.5 m makes the robots start negotiating only when they could also sense each other.

## Results

Every episode succeeded; 0 collisions and 0 deadlocks in 1440 episodes (Wilson 95% upper bound 0.27%).
Extra delay is paired per seed against `full` with the same policy, loss and range (mean ± 95% CI, s):

| Policy | Range | No share | Share always | Share on detect | Map in time (on detect) |
|---|---|---|---|---|---|
| fixed_priority | 6.0 m | +29.2 ± 1.8 | +0.0 | +29.2 ± 1.8 | 0/30 |
| rules_default | 6.0 m | +29.2 ± 1.8 | +0.0 | +29.2 ± 1.8 | 0/30 |
| cost_bid | 6.0 m | +8.8 ± 1.6 | +0.0 | +8.8 ± 1.6 | 0/30 |
| fixed_priority | 3.5 m | +5.8 ± 5.4 | +0.0 | +0.0 | 30/30 |
| rules_default | 3.5 m | +3.0 ± 3.9 | +0.0 | +0.0 | 30/30 |
| cost_bid | 3.5 m | +0.2 ± 0.2 | +0.0 | +0.0 | 30/30 |

(0% loss; the 50% loss rows are in `report/explore_map.md` and differ by at most 2 s, except that at 3.5 m only
24/30 maps arrive before the decision and share-on-detect then costs +1.7 ± 3.2 s for fixed priority and the rulebook.)

- **Without sharing, partial maps cost time.** At the 6 m range each robot has seen only the bay nearest its
  start when the robots negotiate. Fixed priority and the rulebook adopt A's plan, and A has not seen bay1, so
  B reverses to its end room: +29 s. `cost_bid` loses less (+8.8 s).
- **Sharing in every BID recovers the full-map result in every cell.**
- **Share-on-detect comes too late at the default range.** The robots agree who yields at about 6 m apart,
  before either lidar (3.5 m) can see the other robot, so the map always arrives after the decision and the
  result equals not sharing. The map is still used afterwards (e.g. for a fallback refuge), but not for the decision.
- **If negotiation starts within sensor range (3.5 m), share-on-detect matches the full map** at 0% loss.
  At that range the robots have also seen more bays themselves, so even no sharing costs much less.

So "share only on detection" works only when detection happens before the decision. With a radio range larger
than the sensor range, a robot should either share in its first BID or wait for detection before deciding.

## Hold the decision until the map exchange (`hold_for_map`)

`hold_for_map: true` (with `share_map` and `share_on_detect`; off by default) makes a robot that has started a
negotiation keep driving along its lane, undecided, until its own lidar has detected the peer **and** it has the
peer's map (a MAP message, or a BID that carries `known`, which BIDs do once the sender has detected us). Its BID
snapshot is refreshed while it holds. After `hold_timeout` (15 s) without both, it logs `hold_timeout` and decides
as before. Time to decision is first `decision` minus first `conflict_detected`.

Rerun of the full grid with the hold arm: 1,800 episodes; the 1,440 rows of the four existing conditions are
byte-for-byte the same values as before. All 360 hold episodes succeeded, 0 collisions, 0 hold timeouts.

| Range | Loss | No share | Share on detect | Share on detect + hold | Share every BID | Time to decision, hold / others [s] |
|---|---|---|---|---|---|---|
| 6.0 m | 0% | +29.2 / +8.8 | +29.2 / +8.8 | **−0.4 / −0.4** | +0.0 / +0.0 | 4.9 / 0.1 |
| 6.0 m | 50% | +29.0 / +8.7 | +29.0 / +8.7 | **−0.5 / −0.5** | +0.0 / +0.0 | 5.5 / 0.3 |
| 3.5 m | 0% | +5.8 / +0.2 | +0.0 / +0.0 | +0.0 / +0.0 | +0.0 / +0.0 | 0.1 / 0.1 |
| 3.5 m | 50% | +4.5 / +0.3 | +1.7 / +0.3 | +0.1 / +0.1 | +0.0 / +0.0 | 0.2 / 0.2 |

(Excess over the full map, fixed priority / `cost_bid`; the rulebook is within 0.1 s of fixed priority in every hold cell.)

- **Holding recovers the full-map result at 6 m**, and is 0.4–0.5 s better, because the robots keep driving
  while they hold and decide from closer positions. The cost is time to decision: about 5 s instead of 0.1–0.3 s.
- **At 3.5 m and 50% loss it removes share-on-detect's +1.7 s**, because the map no longer rides on one MAP message.
- An earlier version waited for the one-shot MAP only; at 50% loss 20–24 of 30 episodes per cell then hit the
  timeout and `cost_bid` lost up to +34 s. Counting a BID that carries the map fixed it (commit `f5249a6`).
- The "map in time" column of `report/explore_map.md` counts bays *learned* from the peer before the decision.
  With hold it reads 19/30 at 6 m, 50% loss, because by the time it decides a robot has often sensed the
  peer's bay itself, so the exchange teaches it nothing new.

## Gazebo (current code, 84 runs)

Same two-bay layout, seeds 0–5 (6 per cell), fixed priority and `cost_bid`, 0% loss: `full` (3.5 m), no share,
share always and share on detect at 6.0 m and 3.5 m. Runs from `studies/gazebo/make_scen_all.py`, per-run
comparison in `report/gazebo_all_runs.csv`, summary in `report/gazebo_all.md`. Delay is total delay (equal urgency).

| Condition | Range | Fixed priority, Gazebo / 2D [s] | `cost_bid`, Gazebo / 2D [s] | Map before decision (on detect), Gazebo / 2D |
|---|---|---|---|---|
| full map | 3.5 m | 21.9 / 22.1 | 21.9 / 22.1 | |
| no share | 6.0 m | 50.3 / 50.7 | 30.6 / 30.9 | |
| share always | 6.0 m | 22.0 / 22.1 | 21.9 / 22.1 | |
| share on detect | 6.0 m | 50.3 / 50.7 | 30.6 / 30.9 | 0/6 / 0/6 |
| no share | 3.5 m | 28.7 / 29.4 | 22.1 / 22.4 | |
| share always | 3.5 m | 21.9 / 22.1 | 21.9 / 22.1 | |
| share on detect | 3.5 m | **28.9 / 22.1** | 22.2 / 22.1 | **0/6 / 6/6** |

- All 84 runs succeeded with no collisions, and 83/84 chose the same first yielder as 2D.
- **At 3.5 m, share-on-detect works in 2D but not in Gazebo.** In Gazebo a robot detects its peer from lidar
  clusters left after removing the known walls, and the first detection happened 2.3–2.6 m apart on average,
  against 3.4 m in 2D. The robots had already decided at 3.5 m, so the map always arrived late and the result
  equals no sharing (+6.8 s for fixed priority). Sharing in every BID is robust to this.
- At 6.0 m both simulators agree: share-on-detect is too late and equals no sharing.

## Gazebo with `hold_for_map` (36 runs)

Batch on branch code `f5249a6` (built as image `amrneg:hold-be50818` before a rebase onto main; same code), 2 runs at a time: share on detect + hold at 3.5 m and
6.0 m, plus a rerun of the six 3.5 m share-on-detect cases, fixed priority and `cost_bid`, seeds 0–5, 0% loss. Raw
JSONs in `results_raw/gazebo_hold.jsonl.gz`, Gazebo-vs-2D per run in `report/gazebo_hold_runs.csv`
(`analyse_gazebo_main.py`), table below from `gazebo/analyse_hold.py`. Excess is total delay over the Gazebo
full-map run (`gz_2bay35_sN` / `gz_2bay_sN`) of the same seed and policy.

| Condition | Range | Policy | Success | Coll. | Yielder's refuge | Excess [s] | Time to decision [s] | Hold timeouts |
|---|---|---|---|---|---|---|---|---|
| share on detect (rerun) | 3.5 m | fixed priority | 6/6 | 0 | bay1 ×5, room_hi ×1 | +7.0 | 0.1 | – |
| share on detect (rerun) | 3.5 m | `cost_bid` | 6/6 | 0 | bay1 ×6 | +0.3 | 0.1 | – |
| share on detect + hold | 3.5 m | fixed priority | 6/6 | 0 | bay1 ×6 | +10.0 | 4.7 | 0 |
| share on detect + hold | 3.5 m | `cost_bid` | 6/6 | 0 | bay1 ×6 | +10.1 | 4.7 | 0 |
| share on detect + hold | 6.0 m | fixed priority | 6/6 | 0 | bay1 ×6 | +10.0 | 9.5 | 0 |
| share on detect + hold | 6.0 m | `cost_bid` | 6/6 | 0 | bay1 ×6 | +10.0 | 9.5 | 0 |

- **Hold fixes the wrong refuge, not the delay.** The seed-3 fixed-priority case that sent B to its end room
  (+36 s makespan) now uses bay1, but every hold run waits for lidar detection at 2.3–2.6 m, so it decides 4.7 s
  (3.5 m) or 9.5 s (6 m) after the conflict starts and finishes 4.7–4.9 s later than the paired 2D hold run.
  Mean excess is +10 s, worse than plain share-on-detect (+7.0 / +0.3 s). Sharing in every BID is ~0 in both sims.
- **The map exchange adds little in Gazebo.** When they detect each other, A has sensed both bays itself in 6/6
  seeds and B in 5/6, so a bay is learned from the peer before the decision in only 1/6 per cell.
- The share-on-detect rerun reproduces the PR #24 batch (same refuges); one `cost_bid` run (seed 3) picked A as
  the yielder where 2D picked B, with the same makespan to 0.4 s.

## Limits

2D and a 6-seed Gazebo subset; discovery is geometric (range only, no wall occlusion); one corridor layout; 30 seeds per cell.
