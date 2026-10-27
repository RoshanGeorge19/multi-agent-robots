[↑ Project hierarchy](../PROJECT_HIERARCHY.md) · [Repo README](../README.md)

# `amr_negotiation/`: core package

The simulator-agnostic negotiation code (about 2.6k lines). The 2D simulator, the ROS 2 nodes in
[`ros2_ws/`](../ros2_ws/README.md) and every script in [`experiments/`](../experiments/README.md) import it.
Install it with `pip install -e .[dev]` from the repo root.

## Modules, in dependency order

| Module | What it provides |
|---|---|
| `geometry.py` | `Scenario`, `RobotSpec` (Waffle limits), `AgentConfig`, `Refuge`. Corridor/bay/room geometry, wall segments, start poses, YAML loading with overrides, and the footprint-rectangle collision test |
| `planner.py` | `Snapshot`, the frozen state a robot broadcasts in its BID. Refuge feasibility and the constant-speed yield-plan timeline: yielder/proceeder delay, urgency-weighted delay, reverse distance. `best_plan()` picks the refuge |
| `mechanism.py` | Clarke-pivot (VCG) mechanism for the two-outcome yield decision: outcome choice and payments |
| `policies.py` | Every decision function: the rulebook rules, `cost_bid` (+ noise), `group_bid`, `learned`, `clarke`, `forced`, and the `decide()` dispatcher. Default rulebook: `configs/rulebooks/default.yaml` |
| `llm.py` | The `llm` policy. Prompts (mediator / agents, raw / plans, text / image / egocentric), JSON-schema-constrained calls to an OpenAI-compatible endpoint, response cache, latency charged as decision time, and tiebreaks (rulebook, hash draw, commit-reveal) |
| `agent.py` | `Agent`, the per-robot state machine (WAIT_START → CRUISE → NEGOTIATE → YIELD / PROCEED → DONE). It covers conflict detection, BID exchange, the commit / state-guard / bay-check safeguards, timeouts and reactive fallback, make-room for convoys, junction-aware waiting, blocked-bay detection, and map sharing / explore / hold-for-map. `AgentParams` holds every switch and timer |
| `sim2d.py` | 2D unicycle simulator (20 Hz) with a lossy broadcast `Bus`. `run_episode()` returns the metrics dict; `run_oracle()` returns the best forced yielder; free-flow times are cached |
| `sweep.py` | `amrneg-sweep`: factorial Monte Carlo over a sweep YAML ([`configs/sweeps/`](../configs/sweeps/README.md)) → episode CSV, summary CSV, plot |
| `cli.py` | `amrneg-run`: one episode with `--set` overrides; prints metrics and can save JSON / plot / GIF |
| `viz.py` | Static plots and animated GIFs of a recorded episode |
| `gzworld.py` | `amrneg-world`: Gazebo SDF world and `ros_gz_bridge` config generated from a scenario |
| `__init__.py` | Re-exports `Refuge`, `RobotSpec`, `Scenario`, `load_scenario`, `run_episode` |

## Where to start reading

1. `planner.py`: how a yield is costed. Everything else builds on it.
2. `policies.py`: who yields under each policy.
3. `agent.py`: how two robots agree and act. `tick_negotiate()` is the heart.
4. `sim2d.run_episode()`: how an episode is simulated and scored.

Tests for this package: [`tests/`](../tests/README.md).
