[↑ Project hierarchy](../../PROJECT_HIERARCHY.md) · [Parent: media](../README.md)

# `media/gazebo/`: first Gazebo clips (initial code)

Overhead-camera recordings, sped up, of two TurtleBot3 Waffles in `configs/scenarios/corridor_single_bay.yaml`,
seed 0. They were recorded on commit `ba2ca27`, the initial protocol: no decision commit and no explore mode. For
clips on the final code, see [`media/gazebo_final/`](../gazebo_final/README.md).

| File | Preview | Policy | Outcome |
|---|---|---|---|
| `corridor_single_bay_cost_bid_s0.mp4` | `gz_cost_bid.webp` | `cost_bid` | A yields into the bay; makespan 59.9 s |
| `corridor_single_bay_rule_based_s0.mp4` | `gz_rule_based.webp` | `rule_based` (default rulebook) | B yields under `first_in_corridor`; 62.2 s |
| `corridor_single_bay_reactive_s0.mp4` | `gz_reactive.webp` | `reactive` | Both give way: B reverses ~3 m to its end room, then A pulls into the bay; 126.8 s |
