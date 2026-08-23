"""Record a video of the trained collision-avoidance policies in the maze.

Frames one environment from above-and-to-the-side so both robots and the maze
walls are visible at once. The camera is fixed to the environment rather than
tracking a robot, since the point is to watch the two robots move relative to each
other and the walls.

Usage:
    python.sh record_maze.py --headless --checkpoint <path>
"""

from __future__ import annotations

import argparse
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Record the maze policies.")
parser.add_argument("--checkpoint", type=str, required=True)
parser.add_argument("--video_length", type=int, default=600)
parser.add_argument("--out", type=str, default="videos/maze")
parser.add_argument("--eye", type=float, nargs=3, default=[0.4, -0.6, 1.9])
parser.add_argument("--lookat", type=float, nargs=3, default=[-1.0, 0.65, 0.0])
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

args_cli.enable_cameras = True

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import os

import gymnasium as gym
import torch
import yaml

from skrl.utils.runner.torch import Runner
from isaaclab_rl.skrl import SkrlVecEnvWrapper

import collision_env as CE

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    with open(os.path.join(HERE, "agents", "skrl_ippo_cfg.yaml"), encoding="utf-8") as fh:
        agent_cfg = yaml.safe_load(fh)
    agent_cfg["trainer"]["timesteps"] = 0

    env_cfg = CE.CollisionEnvRB3Cfg()
    env_cfg.scene.num_envs = 1
    env_cfg.viewer.resolution = (1280, 720)
    # frame the environment, not a robot: the subject is how the two move
    # relative to each other and the walls
    env_cfg.viewer.origin_type = "env"
    env_cfg.viewer.env_index = 0
    env_cfg.viewer.eye = tuple(args_cli.eye)
    env_cfg.viewer.lookat = tuple(args_cli.lookat)

    base = CE.CollisionAvoidanceEnv(cfg=env_cfg, render_mode="rgb_array")

    video_dir = os.path.join(HERE, args_cli.out)
    wrapped = gym.wrappers.RecordVideo(
        base,
        video_folder=video_dir,
        step_trigger=lambda step: step == 0,
        video_length=args_cli.video_length,
        name_prefix="maze_policy",
        disable_logger=True,
    )

    env = SkrlVecEnvWrapper(wrapped, ml_framework="torch", wrapper="isaaclab")
    runner = Runner(env, agent_cfg)
    runner.agent.load(os.path.abspath(args_cli.checkpoint))

    print(f"\nRecording {args_cli.video_length} frames to {video_dir}")
    print(f"  eye={args_cli.eye} lookat={args_cli.lookat}")

    obs, _ = env.reset()
    for _ in range(args_cli.video_length + 10):
        with torch.inference_mode():
            # IPPO needs a per-agent states dict; unlike single-agent PPO it
            # indexes it by agent id, so None raises TypeError.
            actions = runner.agent.act(obs, env.state(), timestep=0, timesteps=0)[0]
        obs, _, _, _, _ = env.step(actions)

    env.close()
    print("done")


if __name__ == "__main__":
    main()
    simulation_app.close()
