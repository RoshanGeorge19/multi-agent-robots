[↑ Project hierarchy](../PROJECT_HIERARCHY.md) · [Repo README](../README.md)

# `ros2_ws/`: ROS 2 Jazzy workspace (Gazebo Harmonic)

One package, `src/amr_negotiation_ros/`, runs the same [`amr_negotiation.agent.Agent`](../amr_negotiation/README.md)
on simulated TurtleBot3 Waffles. Build it with `colcon build --symlink-install` (the [Docker image](../docker/README.md)
does this). `build/`, `install/` and `log/` are git-ignored.

| File | Role |
|---|---|
| `amr_negotiation_ros/agent_node.py` | One per robot. Pose comes from `/<id>/ground_truth`. The lidar scan is projected to the world frame, points on known walls are removed, and the rest are clustered into peers. Negotiation messages are JSON on `/amr_negotiation/bus`, with the scenario's emulated latency, jitter and loss. Publishes `/<id>/cmd_vel` |
| `amr_negotiation_ros/referee_node.py` | Unpauses the world once every agent is up. Logs events, minimum distance, collisions and reversing. Writes a result JSON with the same keys as `sim2d`, then shuts the launch down |
| `amr_negotiation_ros/recorder_node.py` | Pipes the overhead camera into ffmpeg to make an MP4 (`record:=true`) |
| `launch/corridor.launch.py` | Generates the world with `gzworld`, then starts Gazebo, the bridge, one agent per robot, the referee and the optional recorder |
| `package.xml`, `setup.py`, `setup.cfg`, `resource/` | ament_python package metadata |

**Launch arguments (default):**
- `scenario` (`/amr_negotiation/configs/scenarios/corridor_single_bay.yaml`);
- `policy` (`rule_based`), `rulebook`, `policy_file` (JSON with extra policy keys);
- `seed` (0);
- `record` (false), `video_speedup` (4.0);
- `gui` (false), `verbose`;
- `output_dir` (`/results`).

Batch runs: [`experiments/gazebo/`](../experiments/gazebo/README.md).
