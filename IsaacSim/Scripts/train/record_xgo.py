"""Record a video of a trained XGO locomotion policy.

Uses gymnasium's RecordVideo over the environment's viewport camera. The camera
tracks the robot (origin_type="asset_root"), since a fixed camera loses a walking
robot within a couple of seconds.

Usage:
    python.sh record_xgo.py --headless --enable_cameras --checkpoint <path>
"""

from __future__ import annotations

import argparse
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Record the XGO walking.")
parser.add_argument("--checkpoint", type=str, required=True)
parser.add_argument("--video_length", type=int, default=400, help="Frames to record.")
parser.add_argument("--vx", type=float, default=0.25, help="Commanded forward velocity.")
parser.add_argument("--wz", type=float, default=0.0, help="Commanded yaw rate.")
parser.add_argument("--out", type=str, default="videos/xgo", help="Output directory.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

# rendering the viewport requires the camera pipeline even when headless
args_cli.enable_cameras = True

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import os

import gymnasium as gym
import torch
import yaml

from skrl.utils.runner.torch import Runner
from isaaclab_rl.skrl import SkrlVecEnvWrapper

from xgo_locomotion_env import XGOLocomotionEnv, XGOLocomotionCfg

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    with open(os.path.join(HERE, "agents", "skrl_xgo_ppo_cfg.yaml"), encoding="utf-8") as fh:
        agent_cfg = yaml.safe_load(fh)
    agent_cfg["trainer"]["timesteps"] = 0

    env_cfg = XGOLocomotionCfg()
    # one robot, framed close: this is a ~0.28 m machine
    env_cfg.scene.num_envs = 1
    env_cfg.viewer.resolution = (1280, 720)
    env_cfg.viewer.origin_type = "asset_root"
    env_cfg.viewer.asset_name = "robot"
    env_cfg.viewer.eye = (0.9, 0.9, 0.5)
    env_cfg.viewer.lookat = (0.0, 0.0, 0.0)

    base = XGOLocomotionEnv(cfg=env_cfg, render_mode="rgb_array")

    video_dir = os.path.join(HERE, args_cli.out)
    base = gym.wrappers.RecordVideo(
        base,
        video_folder=video_dir,
        step_trigger=lambda step: step == 0,
        video_length=args_cli.video_length,
        name_prefix=f"xgo_vx{args_cli.vx}_wz{args_cli.wz}",
        disable_logger=True,
    )

    env = SkrlVecEnvWrapper(base, ml_framework="torch", wrapper="isaaclab")
    runner = Runner(env, agent_cfg)
    runner.agent.load(os.path.abspath(args_cli.checkpoint))
    runner.agent.enable_training_mode(False)

    print(f"\nRecording {args_cli.video_length} frames to {video_dir}")
    print(f"  command: vx={args_cli.vx} wz={args_cli.wz}")

    obs, _ = env.reset()
    inner = base.unwrapped
    for _ in range(args_cli.video_length + 10):
        inner.commands[:, 0] = args_cli.vx
        inner.commands[:, 1] = args_cli.wz
        with torch.inference_mode():
            actions = runner.agent.act(obs, None, timestep=0, timesteps=0)[0]
        obs, _, _, _, _ = env.step(actions)

    env.close()
    print("done")


if __name__ == "__main__":
    main()
    simulation_app.close()
