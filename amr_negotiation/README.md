# AMR negotiation in constrained spaces

A research framework for studying how autonomous mobile robots negotiate right of way when space is tight.
The first scenario has two **TurtleBot3 Waffles** meeting head-on in a single-lane corridor. A pull-in bay
lets one robot make way, but only if the robots decide which of them should use it.

The same negotiation code (`amr_negotiation/agent.py`) drives two simulators:

| Layer | What it is for |
|---|---|
| `amr_negotiation` (pure Python) | Scenario geometry, cost model, message protocol, policies and the agent state machine |
| `sim2d` | A fast 2D unicycle simulator using the Waffle's dimensions and limits, for Monte Carlo sweeps (thousands of episodes per minute) |
| `ros2_ws/src/amr_negotiation_ros` | ROS 2 Jazzy + Gazebo Harmonic: a generated world, two namespaced Waffles, one agent node per robot, a referee and an MP4 recorder |

## Scenario

```
 room_lo |=============[bay0]==============| room_hi
   A ->            corridor 8 m x 0.65 m            <- B
```

- Corridor width is 0.65 m. One Waffle (0.306 m wide, about 0.25 m swept radius) fits; two cannot pass each other.
- The bay is 0.8 m wide and 0.6 m deep, and its position and side are configurable. Any number of bays is allowed.
- The end rooms also count as refuges: a robot can back all the way out of the corridor.
- Each robot has `start_delay`, `urgency`, `loaded`, and its own speed limits.
- Comms are a broadcast bus with configurable latency, jitter and packet loss.

Scenario files are in `scenarios/*.yaml`. Any field can be overridden from the CLI with `--set`, e.g. `--set bays.0.x=2.5 comms.loss=0.3`.

## Policies

| `policy` | Communication | Who yields |
|---|---|---|
| `reactive` | none | Each robot stops when blocked. After a random patience timeout it backs up to the nearest refuge behind it. This is the baseline for deadlock and livelock. |
| `fixed_priority` | state exchange | The robot with the higher ID always yields |
| `rule_based` | state exchange | An ordered rulebook (YAML, see below). The first rule that tells the robots apart decides, and the log records which rule it was. |
| `cost_bid` | state + bids | Each robot bids its cost of yielding (predicted total delay for the best feasible refuge). The lower bid yields. |
| `forced` | state exchange | A named robot yields. This policy is used by the oracle. |
| `llm` | state exchange | A local or remote LLM (OpenAI-compatible, e.g. llama.cpp) picks the yielder, either as a mediator or as one prompt per robot. On server errors, bad JSON or disagreement it falls back to the rulebook. See [docs/llm_local.md](docs/llm_local.md). |
| `oracle` | — | Hindsight baseline: simulates each possible yielder and keeps the best outcome |

Both robots run the same deterministic decision function on the same pair of snapshots, so they agree without
needing a third message. If no BID arrives within `neg_timeout`, the agent falls back to reactive behaviour.

### Rulebooks

```yaml
# rulebooks/default.yaml
rules:
  - rule: no_refuge            # a robot with no feasible refuge cannot yield
  - rule: urgency              # urgency difference > threshold: the less urgent robot yields
    threshold: 0.5
  - rule: loaded               # an empty robot yields to a loaded one
  - rule: first_in_corridor    # the robot that entered the corridor first keeps right of way
    min_gap: 1.0
  - rule: refuge_behind_within # a robot with a refuge behind it within `distance` m yields
    distance: 2.0
  - rule: lower_id_priority    # deterministic final tie-break
```

Other available rules: `closest_refuge` (see `rulebooks/proximity_first.yaml`). Pass a rulebook with
`--rulebook path.yaml`, or set `rulebook:` on a policy in a sweep file.

### Metrics (per episode)

`success`, `deadlock`, `collision`, `makespan`, `total_delay` / `max_delay` (both measured against each
robot's free-flow travel time), `min_clearance`, `reverse_dist`, `n_yields`, `msgs`, `msgs_dropped`,
`time_to_decide`, `agreement` (whether both robots reached the same decision), `yielder`, `refuge`, `rule`, and the full event log.

## Quick start (2D, no ROS)

```bash
cd amr_negotiation
pip install -e .[dev]
pytest -q

amrneg-run scenarios/corridor_single_bay.yaml --policy rule_based --events --plot ep.png --gif ep.gif
amrneg-run scenarios/corridor_single_bay.yaml --policy cost_bid --set bays.0.x=2.0 comms.loss=0.5
amrneg-sweep sweeps/bay_position.yaml --out results     # CSV per episode + summary CSV + plot
amrneg-sweep sweeps/comms_loss.yaml --out results
```

A sweep file lists the policies, a factorial `grid` of overrides and per-seed `random` ranges (see the docstring in `sweep.py`).

## Gazebo (ROS 2 Jazzy + Gazebo Harmonic, Docker)

```bash
cd amr_negotiation
docker build -f docker/Dockerfile -t amrneg .
docker run --rm -v $PWD/results:/results amrneg \
  ros2 launch amr_negotiation_ros corridor.launch.py \
    scenario:=/amr_negotiation/scenarios/corridor_single_bay.yaml policy:=rule_based record:=true
# -> results/corridor_single_bay_rule_based_s0.{json,mp4}
```

- `amrneg-world` writes the world SDF and `ros_gz_bridge` YAML from a scenario. The world contains the corridor
  walls, a bay floor marker, an optional overhead camera, and one TurtleBot3 Waffle per agent. Each robot is an inlined
  copy of the official `turtlebot3_gazebo` model, with topics `/<id>/{cmd_vel,odom,scan,ground_truth}`, the RGB camera and
  IMU removed, and an OdometryPublisher for ground-truth world pose.
- The world starts paused. The referee unpauses it once every agent node is up, so that `start_delay` is measured from t = 0.
- `agent_node` runs on each robot. Pose comes from ground truth. The lidar scan is projected into the world frame,
  points on the known walls are removed, and the remaining points are clustered into peer robots. Bus messages are JSON on
  `/amr_negotiation/bus` with the scenario's emulated latency and loss.
- The referee logs the event stream, minimum distance, collisions and reversing distance. It writes a result JSON with the same
  keys as `sim2d`, then shuts the launch down.
- Pass `gui:=true` to run with the Gazebo GUI (needs X forwarding). For multiple simultaneous containers, set distinct
  `-e ROS_DOMAIN_ID=.. -e GZ_PARTITION=..`.
- Headless rendering (lidar and camera) uses Mesa llvmpipe. Without a GPU, recording a run takes several times real time.

## Layout

```
amr_negotiation/      core package (geometry, planner, policies, agent, sim2d, sweep, viz, gzworld, cli)
scenarios/            scenario YAMLs
rulebooks/            rule-based policy configs
sweeps/               sweep definitions
tests/                pytest suite
ros2_ws/src/amr_negotiation_ros/   ROS 2 nodes + launch
docker/               Dockerfile + entrypoint
```

## Known limitations and next steps

- In 2D, robots are circles on a unicycle model with acceleration limits, and perception is ideal (peer outlines
  within lidar range). Gazebo adds real contact physics, wheel dynamics and lidar noise.
- The agent uses ground-truth pose in Gazebo. Swapping in AMCL or SLAM localisation is a natural robustness study.
- The protocol is pairwise. Conflicts among three or more robots, junctions and doorways are planned variations.
- Other policies to add: auctions, multi-turn LLM dialogue over the comms channel, and MARL. Scenario variations: heterogeneous robots (Burger vs Waffle), adversarial or selfish agents.
