"""Train the two robots with IPPO (independent PPO) via skrl.

Each robot learns its own policy and its own critic. There is no shared critic
and no parameter sharing -- they do not even share an action space:

    rover : 2 actions  (linear, angular velocity)  ->  261 observations
    xgo   : 12 actions (joint position targets)    ->  292 observations

train.py remains the benchmark / smoke-test harness; this script does the actual
training.

Usage:
    python.sh train_rl.py --headless
    python.sh train_rl.py --headless --num_envs 512 --timesteps 50000
"""

from __future__ import annotations

import argparse
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Train the collision-avoidance agents with IPPO.")
parser.add_argument("--num_envs", type=int, default=None, help="Number of parallel environments.")
parser.add_argument("--timesteps", type=int, default=None, help="Override trainer timesteps.")
parser.add_argument("--seed", type=int, default=None, help="Override the random seed.")
parser.add_argument(
    "--agent_cfg",
    type=str,
    default=None,
    help="Path to the skrl agent config (defaults to agents/skrl_ippo_cfg.yaml).",
)
parser.add_argument("--checkpoint", type=str, default=None, help="Resume from a checkpoint.")
parser.add_argument(
    "--reward_overrides",
    type=str,
    default=None,
    help="JSON file of reward weights to set on the env config (see llm/reward_space.py).",
)
parser.add_argument("--run_name", type=str, default=None, help="Log directory name for this run.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import os
from datetime import datetime

import json

import gymnasium as gym
import torch  # noqa: F401  (ensures torch initialises before skrl)
import yaml

from skrl.utils import set_seed
from skrl.utils.runner.torch import Runner
from isaaclab_rl.skrl import SkrlVecEnvWrapper

from collision_env import CollisionAvoidanceEnv, CollisionEnvRB3Cfg  # noqa: F401
from llm.reward_space import apply_overrides


HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_AGENT_CFG = os.path.join(HERE, "agents", "skrl_ippo_cfg.yaml")


def main() -> None:
    agent_cfg_path = args_cli.agent_cfg or DEFAULT_AGENT_CFG
    with open(agent_cfg_path, encoding="utf-8") as handle:
        agent_cfg = yaml.safe_load(handle)

    if args_cli.timesteps is not None:
        agent_cfg["trainer"]["timesteps"] = args_cli.timesteps
    if args_cli.seed is not None:
        agent_cfg["seed"] = args_cli.seed

    set_seed(agent_cfg["seed"])

    env_cfg = CollisionEnvRB3Cfg()
    if args_cli.num_envs is not None:
        env_cfg.scene.num_envs = args_cli.num_envs
    if args_cli.reward_overrides is not None:
        with open(args_cli.reward_overrides, encoding="utf-8") as handle:
            overrides = json.load(handle)
        apply_overrides(env_cfg, overrides)
        print(f"Reward overrides: {overrides}")

    env = CollisionAvoidanceEnv(cfg=env_cfg)

    print()
    print("========== IPPO TRAINING ==========")
    print(f"Environments: {env_cfg.scene.num_envs}")
    for agent in env_cfg.possible_agents:
        print(
            f"  {agent:6s} obs {env_cfg.observation_spaces[agent]:4d}"
            f"  act {env_cfg.action_spaces[agent]:3d}"
        )
    print(f"Timesteps:    {agent_cfg['trainer']['timesteps']}")

    # skrl decides single- vs multi-agent from the env type; this env is a
    # DirectMARLEnv, so it wraps as multi-agent.
    env = SkrlVecEnvWrapper(env, ml_framework="torch", wrapper="isaaclab")

    log_root = os.path.join(HERE, "logs", "skrl", agent_cfg["agent"]["experiment"]["directory"])
    run_name = args_cli.run_name or datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_ippo"
    agent_cfg["agent"]["experiment"]["directory"] = log_root
    agent_cfg["agent"]["experiment"]["experiment_name"] = run_name
    print(f"Logging to:   {os.path.join(log_root, run_name)}")
    print("===================================")
    print()

    runner = Runner(env, agent_cfg)

    if args_cli.checkpoint is not None:
        runner.agent.load(os.path.abspath(args_cli.checkpoint))

    runner.run()

    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
