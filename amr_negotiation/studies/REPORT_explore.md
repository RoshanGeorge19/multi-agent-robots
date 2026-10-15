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

## Limits

2D and a 6-seed Gazebo subset; discovery is geometric (range only, no wall occlusion); one corridor layout; 30 seeds per cell.
