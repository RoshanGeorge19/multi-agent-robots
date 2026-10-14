from glob import glob

from setuptools import setup

package_name = "amr_negotiation_ros"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Brian Deegan",
    maintainer_email="brian.deegan@universityofgalway.ie",
    description="ROS 2 / Gazebo layer for the AMR corridor negotiation study",
    license="MIT",
    entry_points={
        "console_scripts": [
            "agent_node = amr_negotiation_ros.agent_node:main",
            "referee_node = amr_negotiation_ros.referee_node:main",
            "recorder_node = amr_negotiation_ros.recorder_node:main",
        ],
    },
)
