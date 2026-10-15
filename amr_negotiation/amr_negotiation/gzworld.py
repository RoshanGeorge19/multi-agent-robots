"""Generate a Gazebo (gz-sim Harmonic) world SDF and ros_gz_bridge config from a Scenario.

Each robot is an inlined copy of the TurtleBot3 Waffle model with absolute, namespaced topics
(/<id>/cmd_vel, /<id>/odom, /<id>/scan, /<id>/ground_truth), its RGB camera removed and an
OdometryPublisher added for ground-truth world pose.
"""

from __future__ import annotations

import math
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from .geometry import Scenario

WALL_T = 0.05
WALL_H = 0.35


def find_waffle_sdf() -> Path:
    cands = []
    if os.environ.get("TB3_WAFFLE_SDF"):
        cands.append(Path(os.environ["TB3_WAFFLE_SDF"]))
    try:
        from ament_index_python.packages import get_package_share_directory

        cands.append(Path(get_package_share_directory("turtlebot3_gazebo")) / "models/turtlebot3_waffle/model.sdf")
    except Exception:  # noqa: BLE001, S110 - ament index missing outside ROS
        pass
    cands.append(Path("/opt/ros/jazzy/share/turtlebot3_gazebo/models/turtlebot3_waffle/model.sdf"))
    for c in cands:
        if c.exists():
            return c
    raise FileNotFoundError("TurtleBot3 waffle model.sdf not found; set TB3_WAFFLE_SDF")


def _inside(sc: Scenario, x: float, y: float) -> bool:
    return any(r.contains(x, y, eps=0.0) for r in sc.free_rects())


def wall_boxes(sc: Scenario) -> list[tuple[float, float, float, float]]:
    """(cx, cy, yaw, length) for each wall, offset outward so the free space is not reduced."""
    out = []
    for (x0, y0), (x1, y1) in sc.wall_segments():
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 1e-6:
            continue
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        nx, ny = -(y1 - y0) / L, (x1 - x0) / L
        if _inside(sc, mx + 0.01 * nx, my + 0.01 * ny):
            nx, ny = -nx, -ny
        out.append((mx + nx * WALL_T / 2, my + ny * WALL_T / 2, math.atan2(y1 - y0, x1 - x0), L + WALL_T))
    return out


def robot_model(template: str, rid: str, x: float, y: float, yaw: float, color=None) -> ET.Element:
    root = ET.fromstring(template)
    m = root.find("model")
    m.set("name", rid)
    m.find("pose").text = f"{x} {y} 0.01 0 0 {yaw}"
    for link in m.findall("link"):
        for s in list(link.findall("sensor")):
            if s.get("type") in ("camera", "imu"):
                link.remove(s)
            else:
                s.find("topic").text = f"/{rid}/scan"
                fid = s.find("gz_frame_id")
                if fid is not None:
                    fid.text = f"{rid}/base_scan"
                s.find("visualize").text = "false"
    for p in m.findall("plugin"):
        if "DiffDrive" in p.get("name"):
            p.find("topic").text = f"/{rid}/cmd_vel"
            p.find("odom_topic").text = f"/{rid}/odom"
            p.find("tf_topic").text = f"/{rid}/tf"
            p.find("frame_id").text = f"{rid}/odom"
            p.find("child_frame_id").text = f"{rid}/base_footprint"
        elif "JointStatePublisher" in p.get("name"):
            p.find("topic").text = f"/{rid}/joint_states"
    gt = ET.SubElement(m, "plugin", filename="gz-sim-odometry-publisher-system",
                       name="gz::sim::systems::OdometryPublisher")
    for k, v in (("odom_frame", "world"), ("robot_base_frame", f"{rid}/base_footprint"),
                 ("odom_topic", f"/{rid}/ground_truth"), ("odom_publish_frequency", "30"),
                 ("dimensions", "2")):
        ET.SubElement(gt, k).text = v
    if color:
        for vis in m.iter("visual"):
            if vis.get("name", "").startswith("base"):
                mat = vis.find("material") or ET.SubElement(vis, "material")
                for tag in ("ambient", "diffuse"):
                    e = mat.find(tag) if mat.find(tag) is not None else ET.SubElement(mat, tag)
                    e.text = color
    return m


def _box(name, x, y, z, yaw, sx, sy, sz, rgba):
    return f"""
    <model name="{name}"><static>true</static><pose>{x:.4f} {y:.4f} {z:.4f} 0 0 {yaw:.5f}</pose>
      <link name="l">
        <collision name="c"><geometry><box><size>{sx:.4f} {sy:.4f} {sz:.4f}</size></box></geometry></collision>
        <visual name="v"><geometry><box><size>{sx:.4f} {sy:.4f} {sz:.4f}</size></box></geometry>
          <material><ambient>{rgba}</ambient><diffuse>{rgba}</diffuse></material></visual>
      </link></model>"""


ROBOT_COLORS = ["0.15 0.35 0.85 1", "0.95 0.5 0.1 1", "0.2 0.7 0.3 1", "0.8 0.2 0.2 1"]


def blocked_bay_poses(sc: Scenario) -> list[tuple[float, float]]:
    return [(r.x, r.park_y) for r in sc.refuges() if r.id in set(sc.blocked_bays)]


def build_world(sc: Scenario, waffle_sdf: str | Path | None = None, overhead_camera: bool = True,
                camera_size=(1280, 720)) -> str:
    template = Path(waffle_sdf or find_waffle_sdf()).read_text()
    parts = []
    for k, (cx, cy, yaw, L) in enumerate(wall_boxes(sc)):
        parts.append(_box(f"wall_{k}", cx, cy, WALL_H / 2, yaw, L, WALL_T, WALL_H, "0.6 0.6 0.65 1"))
    for k, b in enumerate(sc.bays):
        y = b["side"] * (sc.half_width + b["depth"] / 2)
        parts.append(_box(f"bay_marker_{k}", b["x"], y, 0.001, 0, b["width"], b["depth"], 0.002,
                          "0.9 0.85 0.3 1").replace("<collision", "<!--c").replace("</collision>", "-->"))
    for x, y in blocked_bay_poses(sc):  # a pallet the size of a Waffle, as the 2D sim's robot-sized obstacle
        x0, x1, y0, y1 = sc.robot.footprint
        parts.append(_box(f"obstacle_{x:.2f}_{y:.2f}", x + (x0 + x1) / 2, y + (y0 + y1) / 2, 0.1, 0,
                          x1 - x0, y1 - y0, 0.2, "0.55 0.35 0.15 1"))
    robots = []
    for k, a in enumerate(sc.agents):
        x, y, yaw = sc.start_pose(a)
        m = robot_model(template, a.id, x, y, yaw, ROBOT_COLORS[k % len(ROBOT_COLORS)])
        robots.append(ET.tostring(m, encoding="unicode"))
    cam = ""
    if overhead_camera:
        cx = sc.length / 2
        span = sc.length + 2 * sc.room_length
        h = 0.55 * span
        w, hh = camera_size
        cam = f"""
    <model name="overhead_camera"><static>true</static>
      <pose>{cx:.3f} {-0.45 * h:.3f} {h:.3f} 0 1.15 1.5708</pose>
      <link name="l"><sensor name="cam" type="camera">
        <always_on>true</always_on><update_rate>10</update_rate><topic>/overhead_camera</topic>
        <camera><horizontal_fov>1.25</horizontal_fov>
          <image><width>{w}</width><height>{hh}</height><format>R8G8B8</format></image>
          <clip><near>0.1</near><far>60</far></clip></camera>
      </sensor></link></model>"""
    return f"""<?xml version="1.0"?>
<sdf version="1.8">
  <world name="corridor">
    <physics name="1ms" type="ignored"><max_step_size>0.004</max_step_size><real_time_factor>1.0</real_time_factor></physics>
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors"><render_engine>ogre2</render_engine></plugin>
    <scene><ambient>0.6 0.6 0.6 1</ambient><background>0.8 0.85 0.9 1</background><shadows>false</shadows></scene>
    <light type="directional" name="sun"><cast_shadows>false</cast_shadows><pose>0 0 10 0 0 0</pose>
      <diffuse>0.9 0.9 0.9 1</diffuse><direction>-0.3 0.2 -0.9</direction></light>
    <model name="ground"><static>true</static><link name="l">
      <collision name="c"><geometry><plane><normal>0 0 1</normal><size>60 60</size></plane></geometry></collision>
      <visual name="v"><geometry><plane><normal>0 0 1</normal><size>60 60</size></plane></geometry>
        <material><ambient>0.85 0.85 0.85 1</ambient><diffuse>0.85 0.85 0.85 1</diffuse></material></visual>
    </link></model>
    {''.join(parts)}
    {cam}
    {''.join(robots)}
  </world>
</sdf>
"""


def bridge_config(sc: Scenario, overhead_camera: bool = True) -> list[dict]:
    cfg = [{"ros_topic_name": "/clock", "gz_topic_name": "/clock", "ros_type_name": "rosgraph_msgs/msg/Clock",
            "gz_type_name": "gz.msgs.Clock", "direction": "GZ_TO_ROS"}]
    for a in sc.agents:
        r = a.id
        cfg += [
            {"ros_topic_name": f"/{r}/cmd_vel", "gz_topic_name": f"/{r}/cmd_vel",
             "ros_type_name": "geometry_msgs/msg/TwistStamped", "gz_type_name": "gz.msgs.Twist",
             "direction": "ROS_TO_GZ"},
            {"ros_topic_name": f"/{r}/odom", "gz_topic_name": f"/{r}/odom",
             "ros_type_name": "nav_msgs/msg/Odometry", "gz_type_name": "gz.msgs.Odometry", "direction": "GZ_TO_ROS"},
            {"ros_topic_name": f"/{r}/ground_truth", "gz_topic_name": f"/{r}/ground_truth",
             "ros_type_name": "nav_msgs/msg/Odometry", "gz_type_name": "gz.msgs.Odometry", "direction": "GZ_TO_ROS"},
            {"ros_topic_name": f"/{r}/scan", "gz_topic_name": f"/{r}/scan",
             "ros_type_name": "sensor_msgs/msg/LaserScan", "gz_type_name": "gz.msgs.LaserScan",
             "direction": "GZ_TO_ROS"},
            {"ros_topic_name": f"/{r}/tf", "gz_topic_name": f"/{r}/tf",
             "ros_type_name": "tf2_msgs/msg/TFMessage", "gz_type_name": "gz.msgs.Pose_V", "direction": "GZ_TO_ROS"},
        ]
    if overhead_camera:
        cfg.append({"ros_topic_name": "/overhead_camera", "gz_topic_name": "/overhead_camera",
                    "ros_type_name": "sensor_msgs/msg/Image", "gz_type_name": "gz.msgs.Image",
                    "direction": "GZ_TO_ROS"})
    return cfg


def write_world(sc: Scenario, out_dir: str | Path, **kw) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    w = out / f"{sc.name}.sdf"
    w.write_text(build_world(sc, **kw))
    b = out / f"{sc.name}_bridge.yaml"
    b.write_text(yaml.safe_dump(bridge_config(sc, kw.get("overhead_camera", True)), sort_keys=False))
    return w, b


def main(argv=None) -> int:
    import argparse

    from .geometry import load_scenario

    ap = argparse.ArgumentParser(description="Write Gazebo world SDF + bridge YAML for a scenario")
    ap.add_argument("scenario")
    ap.add_argument("--out", default="build/worlds")
    ap.add_argument("--no-camera", action="store_true")
    a = ap.parse_args(argv)
    w, b = write_world(load_scenario(a.scenario), a.out, overhead_camera=not a.no_camera)
    print(w)
    print(b)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
