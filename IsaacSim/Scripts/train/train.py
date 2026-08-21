from __future__ import annotations 

import argparse
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Collision Avoidance Environment")
parser.add_argument("--steps", type=int, default=100, help="Number of RL steps to run.")
parser.add_argument(
    "--video",
    action="store_true",
    help="Record videos of training. Requires --enable_cameras when running headless.",
)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

if args_cli.video:
    args_cli.enable_cameras = True

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym
from collision_env import CollisionAvoidanceEnv, CollisionEnvRB3Cfg
import time
import torch


gym.register(
    id="CollisionAvoidance",
    entry_point="collision_env:CollisionAvoidanceEnv",
    disable_env_checker=True,
)

env_cfg = CollisionEnvRB3Cfg()

# adjust camera resolution and pose
env_cfg.viewer.resolution = (640, 480)
env_cfg.viewer.eye = (1.0, 1.0, 1.0)
env_cfg.viewer.lookat = (0.0, 0.0, 0.0)

# set render mode to rgb_array to obtain images on render calls
env = gym.make(
    "CollisionAvoidance",
    cfg=env_cfg,
    render_mode="rgb_array" if args_cli.video else None,
)

if args_cli.video:
    video_kwargs = {
        "video_folder": "videos/train",
        "step_trigger": lambda step: True,  # step % 1500 == 0,
        "video_length": 100,
    }
    env = gym.wrappers.RecordVideo(env, **video_kwargs)


if __name__ == "__main__":
    # gymnasium 1.x wrappers do not forward arbitrary attributes -> go through .unwrapped
    base_env = env.unwrapped

    print("Creating environment...")

    obs, info = env.reset()
    print("AFTER RESET")

    steps = args_cli.steps

    start_time = time.perf_counter()

    print("training...")
    steps_done = 0
    for step in range(steps):
        actions = torch.zeros(
            (
                base_env.num_envs,
                base_env.cfg.action_space,
            ),
            device=base_env.device,
        )

        # terminated / truncated are per-env tensors; DirectRLEnv resets finished
        # envs itself, so there is no manual reset to do here.
        obs, reward, terminated, truncated, info = env.step(actions)

        steps_done += 1

    elapsed = (time.perf_counter() - start_time)

    simulated_seconds = (steps * base_env.cfg.decimation * base_env.cfg.sim.dt)

    print()
    print("========== BENCHMARK ==========")
    print(f"Environments:       {base_env.num_envs}")
    print(f"Steps:              {steps}")
    print(f"Steps executed      {steps_done}")
    print(f"Simulated time:     {simulated_seconds:.2f} s")
    print(f"Real time:    {elapsed:.2f} s")
    print(f"Steps/sec:          {steps / elapsed:.2f}")
    print(
        f"Simulation speed:   "
        f"{simulated_seconds / elapsed:.2f}x real-time"
    )
    print("================================")
    env.close()
    simulation_app.close()
