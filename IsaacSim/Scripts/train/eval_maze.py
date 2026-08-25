"""Evaluate a trained collision-avoidance policy on what actually matters.

Aggregate return and episode length cannot distinguish "learned to reach goals"
from "learned to sit still safely": both give long episodes, low per-step cost and
converged value estimates. This measures goal-reaching, collisions and movement
directly.
"""

from __future__ import annotations

import argparse
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Evaluate the collision-avoidance policies.")
parser.add_argument("--checkpoint", type=str, required=True)
parser.add_argument("--num_envs", type=int, default=128)
parser.add_argument("--steps", type=int, default=600)
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

import collision_env as CE

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    with open(os.path.join(HERE, "agents", "skrl_ippo_cfg.yaml"), encoding="utf-8") as fh:
        agent_cfg = yaml.safe_load(fh)
    agent_cfg["trainer"]["timesteps"] = 0

    env_cfg = CE.CollisionEnvRB3Cfg()
    env_cfg.scene.num_envs = args_cli.num_envs
    base = CE.CollisionAvoidanceEnv(cfg=env_cfg)
    env = SkrlVecEnvWrapper(base, ml_framework="torch", wrapper="isaaclab")

    runner = Runner(env, agent_cfg)
    runner.agent.load(os.path.abspath(args_cli.checkpoint))

    n = args_cli.num_envs
    dev = base.device
    stats = {
        a: {"goals": 0, "collisions": 0, "episodes": 0, "dist": torch.zeros(n, device=dev)}
        for a in base.possible_agents
    }
    obs, _ = env.reset()

    # Captured *after* reset: before it, previous_distance is still the zeros from
    # __init__, which silently makes every "closed gap" come out as 0.000 m.
    start_gap = {
        CE.ROVER_AGENT: base.previous_distance.clone(),
        CE.XGO_AGENT: base.xgo_previous_distance.clone(),
    }
    best_gap = {k: v.clone() for k, v in start_gap.items()}
    prev_pos = {
        CE.ROVER_AGENT: wp.to_torch(base.rover_rb3.data.root_pos_w)[:, :2].clone(),
        CE.XGO_AGENT: wp.to_torch(base.xgo_lite.data.root_pos_w)[:, :2].clone(),
    }

    for _ in range(args_cli.steps):
        with torch.inference_mode():
            # IPPO needs a per-agent states dict; unlike single-agent PPO it
            # indexes it by agent id, so None raises TypeError.
            actions = runner.agent.act(obs, env.state(), timestep=0, timesteps=0)[0]
        obs, _, terminated, truncated, _ = env.step(actions)

        for agent, robot, gap in (
            (CE.ROVER_AGENT, base.rover_rb3, base.previous_distance),
            (CE.XGO_AGENT, base.xgo_lite, base.xgo_previous_distance),
        ):
            pos = wp.to_torch(robot.data.root_pos_w)[:, :2]
            stats[agent]["dist"] += torch.linalg.vector_norm(pos - prev_pos[agent], dim=-1)
            prev_pos[agent] = pos.clone()
            best_gap[agent] = torch.minimum(best_gap[agent], gap)

        # Read the environment's own pre-reset flags. Deriving this from
        # previous_distance after step() returns cannot work: a successful episode
        # has already reset by then, overwriting the distance with the next
        # episode's starting value, so the counter reads zero however well the
        # policy performs.
        stats[CE.ROVER_AGENT]["goals"] += int(base._goal_hits.sum())
        stats[CE.XGO_AGENT]["goals"] += int(base._xgo_goal_hits.sum())
        stats[CE.ROVER_AGENT]["collisions"] += int(base.collisions_array.sum())
        stats[CE.XGO_AGENT]["collisions"] += int(base.xgo_collisions.sum())

        done = (terminated[CE.ROVER_AGENT] | terminated[CE.XGO_AGENT]
                | truncated[CE.ROVER_AGENT])
        stats[CE.ROVER_AGENT]["episodes"] += int(done.sum())

    episodes = max(stats[CE.ROVER_AGENT]["episodes"], 1)
    print("\n===== COLLISION AVOIDANCE EVALUATION =====")
    print(f"  {args_cli.steps} steps, {n} envs, {episodes} episodes completed\n")
    print(f"  {'agent':>6} {'goal hits':>10} {'collisions':>11} {'travelled':>11} {'closed gap':>11}")
    for agent in base.possible_agents:
        s = stats[agent]
        closed = (start_gap[agent] - best_gap[agent]).clamp(min=0.0).mean()
        print(
            f"  {agent:>6} {s['goals']:>10d} {s['collisions']:>11d} "
            f"{float(s['dist'].mean()):>10.2f}m {float(closed):>10.3f}m"
        )
    print(f"\n  start gap to goal: rover {float(start_gap[CE.ROVER_AGENT].mean()):.3f}m "
          f"xgo {float(start_gap[CE.XGO_AGENT].mean()):.3f}m")
    print(f"  robot separation:  min {float(base.robot_separation.min()):.3f}m "
          f"mean {float(base.robot_separation.mean()):.3f}m")
    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
