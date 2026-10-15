# Media

Gazebo Harmonic recordings (overhead camera, sped up) of two TurtleBot3 Waffles in `scenarios/corridor_single_bay.yaml`, seed 0. Recorded with `ros2 launch amr_negotiation_ros corridor.launch.py policy:=<P> record:=true` on commit `ba2ca27` (the initial PR #1 code). Later protocol changes (decision commit, explore mode, etc.) are not in these clips. See `studies/` for results on the final code.

| File | Policy | Outcome |
|---|---|---|
| `gazebo/corridor_single_bay_cost_bid_s0.mp4` (`gz_cost_bid.webp` preview) | `cost_bid` | A yields into the bay; makespan 59.9 s |
| `gazebo/corridor_single_bay_rule_based_s0.mp4` (`gz_rule_based.webp`) | `rule_based` (default rulebook) | B yields under `first_in_corridor`; 62.2 s |
| `gazebo/corridor_single_bay_reactive_s0.mp4` (`gz_reactive.webp`) | `reactive` (no messages) | Both give way (B reverses ~3 m to its end room, then A pulls into the bay); 126.8 s |
