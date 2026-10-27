# Configs

YAML inputs to the simulators. Any scenario field can be overridden on the command line with
`--set key.path=value`, e.g. `--set bays.0.x=2.5 comms.loss=0.3`.

## `scenarios/`: corridor layouts and robots

| File | Layout | Robots | Used by |
|---|---|---|---|
| `corridor_single_bay.yaml` | 8 m × 0.65 m corridor, one 0.8 × 0.6 m bay at x = 4, 2.5 m end rooms | A vs B (B delayed 2 s) | S1–S3, S6–S10, reservation, Gazebo |
| `corridor_two_bays.yaml` | 10 m, bays at x = 3 (north) and x = 7 (south) | A vs B | S4, maps, blocked bays, explore, learned |
| `corridor_urgent_loaded.yaml` | as single bay | B urgent (u = 2) and loaded | tests, Gazebo spot check |
| `corridor_convoy.yaml` | 10 m, two bays, finished robots despawn | A + C convoy vs B | convoy / `group_bid` |
| `corridor_tjunction.yaml` | 8 m; the side branch is a 2 m-deep bay at x = 5.5 | A, B, and S leaving the branch | T-junction (exit) |
| `corridor_tjunction_goal.yaml` | as above | A turns *into* the branch, B passes, S leaves | T-junction (turn-in) |

The top-level keys are geometry (`length`, `width`, `bays`, `room_*`), `robot` (Waffle limits), `comms` (latency,
jitter, loss, STATE rate), `agents`, and the optional `agent_params`, `blocked_bays` and `despawn_done`. Field definitions are in
`amr_negotiation/geometry.py`.

## `rulebooks/`: rule orders for `rule_based`

- `default.yaml`: `no_refuge` → `urgency` → `loaded` → `first_in_corridor` → `refuge_behind_within` → `lower_id_priority`. This is also the fallback for `llm` and `reservation`.
- `proximity_first.yaml`: puts `closest_refuge` ahead of seniority.

## `sweeps/`: inputs to `amrneg-sweep`

Each file defines policies × a factorial `grid` of overrides × per-seed `random` jitter. Paths inside a sweep
are resolved relative to `configs/`.

- `bay_position.yaml`: bay x ∈ {1, 2.5, 4, 5.5, 7} for six policies.
- `comms_loss.yaml`: packet loss 0–95% for the rulebook and `cost_bid`.

The published studies use their own grids, defined in `experiments/classical/run_studies*.py`. These two sweeps are small demonstrations.
