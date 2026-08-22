"""Evaluate a trained XGO locomotion policy: does it actually track the command?

Reward going up does not prove locomotion -- a policy that stands still and
collects the alive bonus scores well too. This drives fixed commands and measures
the body velocity that results.
"""

from __future__ import annotations

import argparse
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Evaluate an XGO locomotion policy.")
parser.add_argument("--checkpoint", type=str, required=True)
parser.add_argument("--num_envs", type=int, default=256)
parser.add_argument("--steps", type=int, default=240)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import os
import torch
import warp as wp
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
    env_cfg.scene.num_envs = args_cli.num_envs
    base = XGOLocomotionEnv(cfg=env_cfg)
    env = SkrlVecEnvWrapper(base, ml_framework="torch", wrapper="isaaclab")

    runner = Runner(env, agent_cfg)
    runner.agent.load(os.path.abspath(args_cli.checkpoint))
    runner.agent.enable_training_mode(False)

    print("\n===== VELOCITY TRACKING =====")
    print(f"{'commanded vx':>13} {'achieved vx':>12} {'commanded wz':>13} {'achieved wz':>12} {'upright':>8} {'fell':>10}")

    for vx, wz in ((0.0, 0.0), (0.15, 0.0), (0.25, 0.0), (-0.15, 0.0), (0.0, 0.8), (0.15, -0.8)):
        obs, _ = env.reset()
        base.commands[:, 0] = vx
        base.commands[:, 1] = wz

        vx_meas, wz_meas, up_meas = [], [], []
        fell = 0
        for i in range(args_cli.steps):
            with torch.inference_mode():
                actions = runner.agent.act(obs, None, timestep=0, timesteps=0)[0]
            obs, _, _, _, _ = env.step(actions)
            # hold the command fixed across resets
            base.commands[:, 0] = vx
            base.commands[:, 1] = wz
            if i > args_cli.steps // 3:      # let the gait settle first
                vx_meas.append(wp.to_torch(base.robot.data.root_lin_vel_b)[:, 0].mean().item())
                wz_meas.append(wp.to_torch(base.robot.data.root_ang_vel_b)[:, 2].mean().item())
                up_meas.append(base._upright().mean().item())
            fell = max(fell, int(base._fallen().sum()))

        n = len(vx_meas)
        print(f"{vx:>13.2f} {sum(vx_meas)/n:>12.3f} {wz:>13.2f} {sum(wz_meas)/n:>12.3f} "
              f"{sum(up_meas)/n:>8.3f} {fell:>6d}/{args_cli.num_envs}")

    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
