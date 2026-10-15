"""Task metrics for the two-robot maze, shared by every evaluation harness.

Reads the env's per-step event flags (CollisionAvoidanceEnv.step_events), which
are latched in _get_dones and so survive the reset that follows a termination in
the same step(). Earlier eval code read _goal_hits and collisions_array after
step() instead. That over-counted goals: _goal_hits accumulates over an episode,
so summing it every step counted one goal once per remaining step. It also
under-counted collisions, because the reset has already cleared that flag.

Rates are per env-minute of simulated time, so runs with different env counts
and lengths are comparable.
"""

from __future__ import annotations

import torch
import warp as wp

import collision_env as CE
from llm.reward_space import fitness  # noqa: F401  (re-exported for the eval scripts)

# separation below which the robots count as a close encounter
CLOSE_ENCOUNTER_M = 0.30


class MazeMetrics:
    def __init__(self, env: CE.CollisionAvoidanceEnv):
        self.env = env
        n, dev = env.num_envs, env.device
        self.steps = 0
        self.episodes = 0
        self.counts = {name: 0 for name in env.step_events}
        self.close_steps = 0
        self.min_separation = float("inf")
        self.robots = {CE.ROVER_AGENT: env.rover_rb3, CE.XGO_AGENT: env.xgo_lite}
        self.travelled = {a: torch.zeros(n, device=dev) for a in self.robots}
        self._prev_pos = {a: self._pos(r) for a, r in self.robots.items()}
        self._reward_sums: dict[str, float] = {}

    @staticmethod
    def _pos(robot) -> torch.Tensor:
        return wp.to_torch(robot.data.root_pos_w)[:, :2].clone()

    def update(self, terminated: dict, truncated: dict) -> None:
        env = self.env
        self.steps += 1
        for name, flags in env.step_events.items():
            self.counts[name] += int(flags.sum())

        # the skrl wrapper returns these as (num_envs, 1)
        done = (terminated[CE.ROVER_AGENT] | truncated[CE.ROVER_AGENT]).reshape(-1)
        self.episodes += int(done.sum())

        sep = env.robot_separation
        self.close_steps += int((sep < CLOSE_ENCOUNTER_M).sum())
        self.min_separation = min(self.min_separation, float(sep.min()))

        for agent, robot in self.robots.items():
            pos = self._pos(robot)
            step = torch.linalg.vector_norm(pos - self._prev_pos[agent], dim=-1)
            # a reset teleports the robot; that jump is not distance travelled
            self.travelled[agent] += torch.where(done, torch.zeros_like(step), step)
            self._prev_pos[agent] = pos

        for key, value in env.extras.get("log", {}).items():
            if key.startswith("reward_terms/"):
                self._reward_sums[key] = self._reward_sums.get(key, 0.0) + float(value)

    def summary(self) -> dict:
        env = self.env
        env_minutes = self.steps * env.step_dt * env.num_envs / 60.0
        per_min = lambda count: count / env_minutes if env_minutes else 0.0  # noqa: E731
        agents = {}
        for agent in self.robots:
            fell = self.counts["xgo_fell"] if agent == CE.XGO_AGENT else 0
            agents[agent] = {
                "goals": self.counts[f"{agent}_goal"],
                "collisions": self.counts[f"{agent}_collision"],
                "falls": fell,
                "goals_per_env_min": per_min(self.counts[f"{agent}_goal"]),
                "failures_per_env_min": per_min(self.counts[f"{agent}_collision"] + fell),
                "travelled_m_per_env_min": float(self.travelled[agent].mean())
                / (env_minutes / env.num_envs) if env_minutes else 0.0,
            }
        return {
            "steps": self.steps,
            "num_envs": env.num_envs,
            "sim_env_minutes": env_minutes,
            "episodes": self.episodes,
            "agents": agents,
            "close_encounter_fraction": self.close_steps / max(self.steps * env.num_envs, 1),
            "min_separation_m": self.min_separation,
            # mean per-step value of each rover reward term, over the whole run
            "rover_reward_terms": {
                k.split("/", 1)[1]: v / max(self.steps, 1) for k, v in self._reward_sums.items()
            },
        }


def print_table(summary: dict, title: str) -> None:
    print(f"\n===== {title} =====")
    print(f"  {summary['steps']} steps, {summary['num_envs']} envs, "
          f"{summary['episodes']} episodes, {summary['sim_env_minutes']:.1f} env-min\n")
    print(f"  {'agent':>6} {'goals':>7} {'goals/min':>10} {'collisions':>11} {'falls':>6} {'m/min':>7}")
    for agent, a in summary["agents"].items():
        print(f"  {agent:>6} {a['goals']:>7d} {a['goals_per_env_min']:>10.3f} "
              f"{a['collisions']:>11d} {a['falls']:>6d} {a['travelled_m_per_env_min']:>7.2f}")
    print(f"\n  close encounters (<{CLOSE_ENCOUNTER_M} m): "
          f"{summary['close_encounter_fraction']:.2%} of env-steps, "
          f"min separation {summary['min_separation_m']:.3f} m")
    print(f"  fitness: {fitness(summary):+.3f}")
