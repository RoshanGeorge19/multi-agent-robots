"""Train XGO locomotion (velocity tracking) with PPO via skrl.

Standalone task -- flat ground, one robot, a commanded body velocity to track.
Learning to walk inside the maze environment is the wrong shape of problem; see
xgo_locomotion_env for why.

Usage:
    python.sh train_xgo.py --headless
    python.sh train_xgo.py --headless --num_envs 4096 --timesteps 20000
"""

from __future__ import annotations

import argparse
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Train XGO locomotion with PPO.")
parser.add_argument("--num_envs", type=int, default=None)
parser.add_argument("--timesteps", type=int, default=None)
parser.add_argument("--seed", type=int, default=None)
parser.add_argument("--checkpoint", type=str, default=None, help="Resume from a checkpoint.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import os
from datetime import datetime

import torch  # noqa: F401
import yaml

from skrl.utils import set_seed
from skrl.utils.runner.torch import Runner
from isaaclab_rl.skrl import SkrlVecEnvWrapper

from xgo_locomotion_env import XGOLocomotionEnv, XGOLocomotionCfg

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    with open(os.path.join(HERE, "agents", "skrl_xgo_ppo_cfg.yaml"), encoding="utf-8") as fh:
        agent_cfg = yaml.safe_load(fh)

    if args_cli.timesteps is not None:
        agent_cfg["trainer"]["timesteps"] = args_cli.timesteps
    if args_cli.seed is not None:
        agent_cfg["seed"] = args_cli.seed
    set_seed(agent_cfg["seed"])

    env_cfg = XGOLocomotionCfg()
    if args_cli.num_envs is not None:
        env_cfg.scene.num_envs = args_cli.num_envs

    env = XGOLocomotionEnv(cfg=env_cfg)

    print()
    print("========== XGO LOCOMOTION ==========")
    print(f"Environments: {env_cfg.scene.num_envs}")
    print(f"Obs / act:    {env_cfg.observation_space} / {env_cfg.action_space}")
    print(f"Timesteps:    {agent_cfg['trainer']['timesteps']}")

    env = SkrlVecEnvWrapper(env, ml_framework="torch", wrapper="isaaclab")

    log_root = os.path.join(HERE, "logs", "skrl", agent_cfg["agent"]["experiment"]["directory"])
    run_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_ppo"
    agent_cfg["agent"]["experiment"]["directory"] = log_root
    agent_cfg["agent"]["experiment"]["experiment_name"] = run_name
    print(f"Logging to:   {os.path.join(log_root, run_name)}")
    print("====================================")
    print()

    runner = Runner(env, agent_cfg)
    if args_cli.checkpoint is not None:
        runner.agent.load(os.path.abspath(args_cli.checkpoint))
    runner.run()
    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
