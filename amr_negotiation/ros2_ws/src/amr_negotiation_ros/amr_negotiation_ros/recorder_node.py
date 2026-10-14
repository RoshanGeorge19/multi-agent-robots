"""Pipe the overhead camera (sensor_msgs/Image, rgb8) into ffmpeg to produce an MP4."""

from __future__ import annotations

import subprocess

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


class Recorder(Node):
    def __init__(self):
        super().__init__("recorder")
        self.declare_parameter("output", "/tmp/amrneg_gazebo.mp4")
        self.declare_parameter("fps", 10)
        self.declare_parameter("speedup", 1.0)
        self.out = self.get_parameter("output").value
        self.fps = int(self.get_parameter("fps").value * self.get_parameter("speedup").value)
        self.proc = None
        self.frames = 0
        self.create_subscription(Image, "/overhead_camera", self.on_image, 5)

    def on_image(self, m: Image):
        if self.proc is None:
            self.proc = subprocess.Popen(
                ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                 "-s", f"{m.width}x{m.height}", "-r", str(self.fps), "-i", "-", "-c:v", "libx264",
                 "-pix_fmt", "yuv420p", "-crf", "23", self.out], stdin=subprocess.PIPE)
            self.get_logger().info(f"recording {m.width}x{m.height} -> {self.out}")
        self.proc.stdin.write(bytes(m.data))
        self.frames += 1

    def close(self):
        if self.proc:
            self.proc.stdin.close()
            self.proc.wait(timeout=30)
            self.get_logger().info(f"wrote {self.frames} frames to {self.out}")


def main():
    rclpy.init()
    node = Recorder()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
