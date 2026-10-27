[↑ Project hierarchy](../../PROJECT_HIERARCHY.md) · [Parent: configs](../README.md)

# `configs/scenarios/`: corridor layouts and robots

Load one with `amrneg-run configs/scenarios/<file> --policy <p>`, or `geometry.load_scenario(path, overrides)`.
Override any field with `--set key.path=value`, e.g. `bays.0.x=2.5`, `comms.loss=0.5` or `agents.1.urgency=3`.

| File | Corridor | Bays (x, side) | Robots | Used by |
|---|---|---|---|---|
| `corridor_single_bay.yaml` | 8 m × 0.65 m, 2.5 m rooms | x = 4, north | A from the west (t = 0); B from the east (delay 2 s; U[0, 8] s in studies) | S1–S3, S6–S10, reservation, Gazebo |
| `corridor_two_bays.yaml` | 10 m | x = 3 north, x = 7 south | A vs B (B delay 4 s) | S4, maps, blocked bays, explore, learned |
| `corridor_urgent_loaded.yaml` | 8 m | x = 4 | B urgent (u = 2) and loaded | tests, first Gazebo spot check |
| `corridor_convoy.yaml` | 10 m, 3.5 m rooms, finished robots despawn | x = 3, x = 7 | A + C eastbound in convoy (C 3 s behind) vs B | convoy / `group_bid` |
| `corridor_tjunction.yaml` | 8 m; the side branch is a 2 m-deep bay | x = 2.5 north; branch x = 5.5 south | A, B, and S starting in the branch and leaving westward | T-junction (exit) |
| `corridor_tjunction_goal.yaml` | as above | as above | A's destination is the branch; B passes; S leaves eastward | T-junction (turn-in) |

## Keys

- **Geometry:** `length`, `width`, `room_length`, `room_width`, `room_refuges`, and `bays` (`x`, `side` ±1, `width`, `depth`).
- **`robot`:** `radius`, `v_max`, `v_rev_max`, `w_max`, `a_max` (TurtleBot3 Waffle defaults).
- **`comms`:** `latency`, `jitter`, `loss`, `rate` (STATE messages per second).
- **`agents`:** `id`, `start_x`, `goal_x`, and optionally `start_delay`, `urgency`, `loaded`, speed limits, `start_refuge`, `goal_refuge`, `known_refuges`.
- **Optional:** `agent_params` (protocol switches such as `explore`, `share_map` and `hold_for_map`), `blocked_bays`, `despawn_done`, `t_max` (default 180 s).

Full definitions are in [`amr_negotiation/geometry.py`](../../amr_negotiation/README.md). The Gazebo batches use
generated variants of these files in [`experiments/gazebo/`](../../experiments/gazebo/README.md).
