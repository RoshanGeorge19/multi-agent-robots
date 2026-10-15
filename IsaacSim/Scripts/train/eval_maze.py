"""Evaluate a trained collision-avoidance policy on what actually matters.

Aggregate return and episode length cannot distinguish "learned to reach goals"
from "learned to sit still safely": both give long episodes, low per-step cost and
converged value estimates. This measures goal-reaching, collisions and movement
directly. Counting lives in maze_metrics.py, shared with llm_coordinator.py.
"""

from __future__ import annotations

import argparse
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Evaluate the collision-avoidance policies.")
parser.add_argument("--checkpoint", type=str, required=True)
parser.add_argument("--num_envs", type=int, default=128)
parser.add_argument("--steps", type=int, default=600)
parser.add_argument("--seed", type=int, default=0)
parser.add_argument("--json_out", type=str, default=None, help="Write the metrics summary here.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import json
import os

import torch
import yaml

from skrl.utils import set_seed
from skrl.utils.runner.torch import Runner
from isaaclab_rl.skrl import SkrlVecEnvWrapper

import collision_env as CE
from maze_metrics import MazeMetrics, fitness, print_table

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    with open(os.path.join(HERE, "agents", "skrl_ippo_cfg.yaml"), encoding="utf-8") as fh:
        agent_cfg = yaml.safe_load(fh)
    agent_cfg["trainer"]["timesteps"] = 0
    set_seed(args_cli.seed)

    env_cfg = CE.CollisionEnvRB3Cfg()
    env_cfg.scene.num_envs = args_cli.num_envs
    base = CE.CollisionAvoidanceEnv(cfg=env_cfg)
    env = SkrlVecEnvWrapper(base, ml_framework="torch", wrapper="isaaclab")

    runner = Runner(env, agent_cfg)
    runner.agent.load(os.path.abspath(args_cli.checkpoint))
    runner.agent.enable_training_mode(False)

    obs, _ = env.reset()
    metrics = MazeMetrics(base)

    for _ in range(args_cli.steps):
        with torch.inference_mode():
            # IPPO needs a per-agent states dict; unlike single-agent PPO it
            # indexes it by agent id, so None raises TypeError.
            actions = runner.agent.act(obs, env.state(), timestep=0, timesteps=0)[0]
        obs, _, terminated, truncated, _ = env.step(actions)
        metrics.update(terminated, truncated)

    summary = metrics.summary()
    summary["checkpoint"] = os.path.abspath(args_cli.checkpoint)
    summary["seed"] = args_cli.seed
    summary["fitness"] = fitness(summary)
    print_table(summary, "COLLISION AVOIDANCE EVALUATION")
    if args_cli.json_out:
        with open(args_cli.json_out, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
