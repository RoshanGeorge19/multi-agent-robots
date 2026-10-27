# AMR negotiation in constrained spaces

A research benchmark for how autonomous mobile robots negotiate right of way when space is tight. Two
**TurtleBot3 Waffles** meet head-on in a single-lane corridor. One must reverse into a pull-in bay (or back out to
an end room) so the other can pass. **Who should yield, into which refuge, and how do the robots agree?**

The same agent code (`amr_negotiation/agent.py`) drives a fast 2D Monte Carlo simulator and a ROS 2 Jazzy +
Gazebo Harmonic stack. On top of it sit ten decision policies, about 20 studies with released per-episode data, and
two paper drafts (classical policies; LLM/VLM negotiators).

**New here?** Start with [`PROJECT_HIERARCHY.md`](PROJECT_HIERARCHY.md), the map of every folder with a link to
its README. Then read [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) for the full picture: architecture, metrics,
every experiment and its headline result, and the open issues.

## Repository map

| Folder | What is in it | Start with |
|---|---|---|
| [`amr_negotiation/`](amr_negotiation/README.md) | Core Python package: geometry, cost model, policies, agent state machine, 2D simulator, sweep/CLI tools, Gazebo world generator | [`amr_negotiation/README.md`](amr_negotiation/README.md) |
| [`configs/`](configs) | YAML inputs: `scenarios/` (corridor layouts and robots), `rulebooks/` (rule-based policy orders), `sweeps/` (Monte Carlo sweep definitions) | [`configs/README.md`](configs/README.md) |
| [`experiments/`](experiments) | Scripts that ran every study: `classical/` (2D studies), `analysis/` (tables and figures from raw data), `gazebo/` (Gazebo batches and 2D-vs-Gazebo comparison), `llm/` (LLM/VLM study) | [`experiments/README.md`](experiments/README.md) |
| [`data/`](data) | Results: `raw/` (per-episode CSV / JSONL, the source of truth) and `tables/` (generated summary tables and figures) | [`data/README.md`](data/README.md) |
| [`reports/`](reports) | Written study reports, one per study, in the order they were done | [`reports/README.md`](reports/README.md) |
| [`papers/`](papers) | Paper 1 (RA-L letter, classical policies) and paper 2 (T-ASE, LLM/VLM negotiators), with their review cycles | [`papers/README.md`](papers/README.md) |
| [`docs/`](docs/README.md) | Literature review, LLM experiment plan, local-LLM how-to | [`docs/README.md`](docs/README.md) |
| [`tests/`](tests/README.md) | pytest suite for the core package and the LLM adapter | [`tests/README.md`](tests/README.md) |
| [`ros2_ws/`](ros2_ws/README.md), [`docker/`](docker/README.md) | ROS 2 package (agent, referee and recorder nodes, launch file) and the Gazebo Docker image | [`ros2_ws/README.md`](ros2_ws/README.md), [`docker/README.md`](docker/README.md) |
| [`media/`](media) | Gazebo and 2D videos, with provenance READMEs | [`media/README.md`](media/README.md) |

## Quick start (2D, no ROS)

```bash
pip install -e .[dev]
pytest -q

amrneg-run configs/scenarios/corridor_single_bay.yaml --policy rule_based --events --plot ep.png --gif ep.gif
amrneg-run configs/scenarios/corridor_single_bay.yaml --policy cost_bid --set bays.0.x=2.0 comms.loss=0.5
amrneg-sweep configs/sweeps/bay_position.yaml --out results     # CSV per episode + summary CSV + plot
```

Any scenario field can be overridden with `--set key.path=value`. `results/` is git-ignored scratch space. The
released results live in `data/`. To rerun a study, see [`experiments/README.md`](experiments/README.md).

## Scenario

```
 room_lo |=============[bay0]==============| room_hi
   A ->            corridor 8 m x 0.65 m            <- B
```

- The corridor is 0.65 m wide. One Waffle (0.306 m wide, about 0.25 m swept radius) fits; two cannot pass.
- Bays are 0.8 m wide and 0.6 m deep. Their position, side and number are configurable. The end rooms also count as refuges.
- Each robot has `start_delay`, `urgency`, `loaded` and its own speed limits.
- Comms are a broadcast bus with configurable latency, jitter and packet loss.
- Variants in `configs/scenarios/` add a second bay, an urgent and loaded robot, a two-robot convoy, and a T-junction (exit and turn-in).

## Policies

| `policy` | Communication | Who yields |
|---|---|---|
| `reactive` | none | Stops when blocked; after a random patience time, backs up to the nearest refuge. The deadlock/livelock baseline. |
| `fixed_priority` | state + bids | The robot with the higher ID always yields. |
| `rule_based` | state + bids | An ordered rulebook (`configs/rulebooks/`); the first rule that tells the robots apart decides. |
| `reservation` | state | First come, first served on the corridor; a robot outside waits in its end room while an oncoming robot is inside. |
| `cost_bid` | state + bids | Each robot bids the predicted urgency-weighted cost of yielding; the lower bid yields. |
| `group_bid` | state + bids | Like `cost_bid`, but a convoy bids as a group, including its followers. |
| `clarke` | state + bids | Clarke-pivot (VCG) mechanism: the cheapest outcome wins and each robot pays its externality, so truthful reporting is dominant. |
| `learned` | state + bids | A tabular contextual bandit trained in the 2D simulator. |
| `llm` | state + bids | An LLM/VLM over an OpenAI-compatible endpoint picks the yielder. It runs as a mediator or one call per robot, with text or image input. See [`docs/llm_local.md`](docs/llm_local.md). |
| `forced` / `oracle` | — | Forced yielder; the hindsight reference keeps the better of "A yields" and "B yields". |

Both robots run the same deterministic decision function on the same pair of snapshots, so they agree without a
third message. Under message loss, three safeguards apply (commit, state guard, bay check), with timeouts that fall back to
reactive behaviour.

### Metrics (per episode)

`success`, `deadlock`, `collision`, `makespan`, `total_delay` / `max_delay` (against each robot's free-flow
travel time), urgency-weighted delay, `min_clearance`, `reverse_dist`, `n_yields`, `msgs`, `msgs_dropped`,
`time_to_decide`, `agreement`, `yielder`, `refuge`, `rule`, and the event log. Studies report **excess delay** over the best
forced yielder, paired per encounter. See `PROJECT_OVERVIEW.md` §7.

## Gazebo (ROS 2 Jazzy + Gazebo Harmonic, Docker)

```bash
docker build -f docker/Dockerfile -t amrneg .
docker run --rm -v $PWD/results:/results amrneg \
  ros2 launch amr_negotiation_ros corridor.launch.py \
    scenario:=/amr_negotiation/configs/scenarios/corridor_single_bay.yaml policy:=rule_based record:=true
# -> results/corridor_single_bay_rule_based_s0.{json,mp4}
```

- `amrneg-world` writes the world SDF and the `ros_gz_bridge` YAML from a scenario.
- `agent_node` runs per robot. Pose comes from ground truth; the lidar is clustered into peers after the known walls are removed.
- The referee writes a result JSON with the same keys as `sim2d`.
- Pass `gui:=true` for the Gazebo GUI. For parallel containers, set distinct `ROS_DOMAIN_ID` and `GZ_PARTITION` values.
- Batch tooling for the 460-run Gazebo validation is in [`experiments/gazebo/`](experiments/gazebo).

## Known limitations

- **Simulation only.** There are no physical robot trials. Gazebo uses ground-truth pose.
- **The 2D simulator is idealised.** Robots are circles on a unicycle model, and the lidar has no occlusion.
- **Negotiation is pairwise.** Convoys and T-junctions are handled by extensions: make-room, group bids, junction-aware waiting. The T-junction is approximated as a deep bay.
- **Bidding uses the simulator's own cost model.** Cost bidding and Clarke are therefore efficient and truthful only relative to that model.
- **Next steps:** physical TurtleBot3 trials, AMCL/SLAM localisation, more layouts, multi-turn LLM dialogue, and independent learners.
