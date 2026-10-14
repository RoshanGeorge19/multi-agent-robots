# ROS 2 Jazzy + Gazebo Harmonic + TurtleBot3 simulation for the corridor negotiation study.
# Build from amr_negotiation/:  docker build -f docker/Dockerfile -t amrneg .
FROM osrf/ros:jazzy-desktop
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-jazzy-ros-gz ros-jazzy-turtlebot3-gazebo ros-jazzy-turtlebot3-description ros-jazzy-turtlebot3-msgs \
      python3-pip python3-yaml python3-numpy python3-matplotlib python3-pytest ffmpeg xvfb mesa-utils \
 && rm -rf /var/lib/apt/lists/*

ENV TURTLEBOT3_MODEL=waffle LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    GZ_SIM_RESOURCE_PATH=/opt/ros/jazzy/share/turtlebot3_gazebo/models

WORKDIR /amr_negotiation
COPY . /amr_negotiation
RUN pip3 install --break-system-packages --no-deps -e /amr_negotiation \
 && . /opt/ros/jazzy/setup.sh \
 && cd /amr_negotiation/ros2_ws && colcon build --symlink-install

ENTRYPOINT ["/amr_negotiation/docker/entrypoint.sh"]
CMD ["bash"]
