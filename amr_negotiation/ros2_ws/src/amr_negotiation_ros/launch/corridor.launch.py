"""Headless Gazebo run of one negotiation episode.

ros2 launch amr_negotiation_ros corridor.launch.py scenario:=/amr_negotiation/scenarios/corridor_single_bay.yaml \
    policy:=rule_based record:=true output_dir:=/results
"""

import os
from pathlib import Path

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    EmitEvent,
    ExecuteProcess,
    OpaqueFunction,
    RegisterEventHandler,
    SetEnvironmentVariable,
)
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from amr_negotiation import gzworld
from amr_negotiation.geometry import load_scenario


def setup(context):
    lc = lambda n: LaunchConfiguration(n).perform(context)
    sc = load_scenario(lc("scenario"))
    out = Path(lc("output_dir"))
    record = lc("record").lower() == "true"
    gui = lc("gui").lower() == "true"
    tag = f"{sc.name}_{lc('policy')}_s{lc('seed')}"
    world, bridge = gzworld.write_world(sc, out / "worlds" / tag, overhead_camera=record,
                                        camera_size=(960, 540))
    gz_cmd = ["gz", "sim", str(world)] + ([] if gui else ["-s", "--headless-rendering"])
    actions = [ExecuteProcess(cmd=gz_cmd, output="screen" if lc("verbose") == "true" else "log")]
    actions.append(Node(package="ros_gz_bridge", executable="parameter_bridge", name="bridge",
                        parameters=[{"config_file": str(bridge), "use_sim_time": True}], output="log"))
    common = {"scenario": lc("scenario"), "use_sim_time": True}
    for a in sc.agents:
        actions.append(Node(package="amr_negotiation_ros", executable="agent_node", name=f"agent_{a.id}",
                            parameters=[{**common, "robot_id": a.id, "policy": lc("policy"),
                                         "rulebook": lc("rulebook"), "seed": int(lc("seed"))}],
                            output="screen"))
    referee = Node(package="amr_negotiation_ros", executable="referee_node", name="referee",
                   parameters=[{**common, "policy": lc("policy"), "output": str(out / f"{tag}.json")}],
                   output="screen")
    actions.append(referee)
    if record:
        actions.append(Node(package="amr_negotiation_ros", executable="recorder_node", name="recorder",
                            parameters=[{"use_sim_time": True, "output": str(out / f"{tag}.mp4"),
                                         "fps": 10, "speedup": float(lc("video_speedup"))}],
                            output="screen"))
    actions.append(RegisterEventHandler(OnProcessExit(target_action=referee,
                                                      on_exit=[EmitEvent(event=Shutdown(reason="episode done"))])))
    return actions


def generate_launch_description():
    models = "/opt/ros/jazzy/share/turtlebot3_gazebo/models"
    return LaunchDescription([
        SetEnvironmentVariable("GZ_SIM_RESOURCE_PATH",
                               models + ":" + os.environ.get("GZ_SIM_RESOURCE_PATH", "")),
        DeclareLaunchArgument("scenario", default_value="/amr_negotiation/scenarios/corridor_single_bay.yaml"),
        DeclareLaunchArgument("policy", default_value="rule_based"),
        DeclareLaunchArgument("rulebook", default_value=""),
        DeclareLaunchArgument("seed", default_value="0"),
        DeclareLaunchArgument("record", default_value="false"),
        DeclareLaunchArgument("video_speedup", default_value="4.0"),
        DeclareLaunchArgument("gui", default_value="false"),
        DeclareLaunchArgument("verbose", default_value="false"),
        DeclareLaunchArgument("output_dir", default_value="/results"),
        OpaqueFunction(function=setup),
    ])
