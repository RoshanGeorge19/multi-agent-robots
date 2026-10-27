[↑ Project hierarchy](../PROJECT_HIERARCHY.md) · [Repo README](../README.md)

# `docker/`: Gazebo / ROS 2 image

| File | Role |
|---|---|
| `Dockerfile` | Starts from `osrf/ros:jazzy-desktop`. Adds `ros-gz`, the TurtleBot3 Gazebo models, ffmpeg, xvfb and Mesa; copies the repo to `/amr_negotiation`; installs the Python package; builds [`ros2_ws/`](../ros2_ws/README.md) |
| `entrypoint.sh` | Sources ROS 2 Jazzy and the workspace overlay, then runs the given command |

```bash
docker build -f docker/Dockerfile -t amrneg .            # from the repo root
docker run --rm -v $PWD/results:/results amrneg \
  ros2 launch amr_negotiation_ros corridor.launch.py \
    scenario:=/amr_negotiation/configs/scenarios/corridor_single_bay.yaml policy:=cost_bid record:=true
```

- **Rendering.** Headless rendering uses Mesa llvmpipe, so no GPU is needed. A run takes about 3–5 min.
- **Parallel runs.** Give each container its own `-e ROS_DOMAIN_ID=.. -e GZ_PARTITION=..`.
- **Ignored files.** `.dockerignore` at the repo root keeps `results/` and build output out of the image.
