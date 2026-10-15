"""Experiment 2: an LLM coordinates the two trained robots from a map.

The IPPO policies are reactive: each sees a lidar scan, its goal bearing and the
other robot's position -- no map, and no way to agree on who goes first. Every
--decide_every steps a coordinator reads an ASCII map of the maze with both
robots and goals on it, and gives each robot one directive:

    go_to_goal          the policy steers to its true goal (no intervention)
    waypoint row col    the policy observes this cell as its goal until it
                        arrives (env.nav_target); the true goal still scores
    yield               the robot holds still until the next decision

Four conditions, identical seeds and checkpoint:

    --mode baseline     no coordinator; the policies alone
    --mode random       random directives. Control: separates "the LLM's
                        judgement helps" from "any intervention changes things"
    --mode planner      BFS on the same map: waypoint to the farthest path cell in
                        line of sight, never yields. Control: separates "the LLM
                        helps" from "a map helps", which 30 lines of BFS also give
    --mode llm          the LLM decides

The interesting comparison is llm against planner. The LLM's distinctive
capability is the yield/negotiation decision the planner cannot make.

Scored by the same MazeMetrics as eval_maze.py.

Usage:
    python.sh llm_coordinator.py --headless --checkpoint <ippo .pt> --mode baseline
    python.sh llm_coordinator.py --headless --checkpoint <ippo .pt> --mode random
    python.sh llm_coordinator.py --headless --checkpoint <ippo .pt> --mode planner
    python.sh llm_coordinator.py --headless --checkpoint <ippo .pt> --mode llm \\
        --llm ollama:qwen3.6:35b
"""

from __future__ import annotations

import argparse
from pathlib import Path

from isaaclab.app import AppLauncher

from llm.backends import add_backend_args, backend_from_args

parser = argparse.ArgumentParser(description="LLM coordination of the trained maze policies.")
parser.add_argument("--checkpoint", type=str, required=True, help="IPPO checkpoint from train_rl.py.")
parser.add_argument("--mode", choices=("baseline", "random", "planner", "llm"), required=True)
parser.add_argument("--num_envs", type=int, default=8)
parser.add_argument("--steps", type=int, default=1080, help="Env steps (30 per simulated second).")
parser.add_argument("--decide_every", type=int, default=30, help="Steps between coordinator decisions.")
parser.add_argument("--seed", type=int, default=0)
parser.add_argument("--name", type=str, default="default", help="Experiment name for the output directory.")
parser.add_argument("--llm_workers", type=int, default=4, help="Concurrent LLM requests per decision round.")
add_backend_args(parser)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
import warp as wp  # noqa: E402
import yaml  # noqa: E402

from skrl.utils import set_seed  # noqa: E402
from skrl.utils.runner.torch import Runner  # noqa: E402
from isaaclab_rl.skrl import SkrlVecEnvWrapper  # noqa: E402

import collision_env as CE  # noqa: E402
from llm.maze_map import MazeMap  # noqa: E402
from maze_metrics import MazeMetrics, fitness, print_table  # noqa: E402

HERE = Path(__file__).resolve().parent
AGENTS = (CE.ROVER_AGENT, CE.XGO_AGENT)
DIRECTIVES = ("go_to_goal", "waypoint", "yield")
WAYPOINT_REACHED_M = 0.15

SYSTEM_PROMPT = """\
You coordinate two robots in a small maze. Each robot is driven by its own trained \
neural policy, which steers toward a target using a 360-degree lidar and the \
target's bearing. The policies have no map: a target behind a wall looks the same \
to them as one in open space, so they can push into dead ends. They also do not \
negotiate: in a narrow passage both may advance and collide.

Robots:
- rover (R): wheeled, up to 0.25 m/s. Its goal is r.
- xgo (X): small quadruped, slower (about 0.1 m/s in practice). Its goal is x.

Any contact with a wall or the other robot, or the quadruped falling, ends the \
episode for BOTH robots and respawns them. Reached goals respawn elsewhere.

For each robot, choose one directive. It holds until your next decision:
- go_to_goal: steer to its own goal. Correct whenever the way is clear.
- waypoint: steer to the free cell (row, col) you give instead, e.g. the mouth of \
the corridor that actually leads to the goal. Cleared when reached. Must be a '.' cell.
- yield: stop in place, e.g. to let the other robot through a passage first.

Each robot's state includes its shortest path length to its goal through the maze \
and whether the goal is in direct line of sight. A path much longer than the \
straight-line distance means a wall is in the way.

Objective: as many goals as possible for both robots, and no collisions. Intervene \
only when the map shows a reason to; for directives other than waypoint, set row \
and col to -1. Keep the rationale to two sentences."""


def decision_schema() -> dict:
    robot = {
        "type": "object",
        "properties": {
            "directive": {"type": "string", "enum": list(DIRECTIVES)},
            "row": {"type": "integer"},
            "col": {"type": "integer"},
        },
        "required": ["directive", "row", "col"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"rationale": {"type": "string"}, "rover": robot, "xgo": robot},
        "required": ["rationale", "rover", "xgo"],
        "additionalProperties": False,
    }


def yaw_deg(quat_xyzw: torch.Tensor) -> torch.Tensor:
    x, y, z, w = quat_xyzw.unbind(-1)
    return torch.rad2deg(torch.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))


class Coordinator:
    """Holds per-env directives and applies them to the env and the actions."""

    def __init__(self, base: CE.CollisionAvoidanceEnv, maze: MazeMap, mode: str, llm=None):
        self.base, self.maze, self.mode, self.llm = base, maze, mode, llm
        n, dev = base.num_envs, base.device
        self.hold = {a: torch.zeros(n, dtype=torch.bool, device=dev) for a in AGENTS}
        self.directive = {a: ["go_to_goal"] * n for a in AGENTS}
        # goal distance at the previous decision; NaN until there is one, and again
        # after a reset or a goal respawn, when the old distance is to another goal
        self.last_goal_dist = {a: torch.full((n,), float("nan"), device=dev) for a in AGENTS}
        self.counts = {d: 0 for d in DIRECTIVES} | {"invalid_waypoint": 0, "llm_fallback": 0}
        self.rng = np.random.default_rng(args_cli.seed)
        self.robots = {CE.ROVER_AGENT: base.rover_rb3, CE.XGO_AGENT: base.xgo_lite}
        self.goals = {CE.ROVER_AGENT: base.goal_pos, CE.XGO_AGENT: base.xgo_goal_pos}
        self.origins = base.scene.env_origins[:, :2]

    # -- state ---------------------------------------------------------------

    def _local(self, xy_w: torch.Tensor) -> np.ndarray:
        return (xy_w - self.origins).cpu().numpy()

    def snapshot(self) -> list[str]:
        """One text description per env."""
        pos, yaw, goal, dist = {}, {}, {}, {}
        for a, robot in self.robots.items():
            pos_w = wp.to_torch(robot.data.root_pos_w)[:, :2]
            pos[a] = self._local(pos_w)
            yaw[a] = yaw_deg(wp.to_torch(robot.data.root_quat_w)).cpu().numpy()
            goal[a] = self._local(self.goals[a])
            dist[a] = torch.linalg.vector_norm(self.goals[a] - pos_w, dim=-1)
        walls = {CE.ROVER_AGENT: self.base.nearest_wall, CE.XGO_AGENT: self.base.xgo_nearest_wall}
        sep = self.base.robot_separation.cpu().numpy()

        texts = []
        for i in range(self.base.num_envs):
            markers = {"r": goal["rover"][i], "x": goal["xgo"][i]}
            for a in AGENTS:
                if self.base.nav_override[a][i]:
                    markers["+"] = self._local(self.base.nav_target[a])[i]
            markers |= {"R": pos["rover"][i], "X": pos["xgo"][i]}
            lines = [
                "Map (cell 0.1 m; '#' wall or too close to one, '.' free; R/X robots, r/x their goals, + active waypoint).",
                "Headings: 0 deg = increasing col (east), 90 deg = decreasing row (north).",
                self.maze.render(markers),
                "",
            ]
            for a in AGENTS:
                row, col = self.maze.to_cell(pos[a][i])
                grow, gcol = self.maze.to_cell(goal[a][i])
                progress = float(self.last_goal_dist[a][i] - dist[a][i])
                progress_text = "n/a (new goal)" if math.isnan(progress) else f"{progress:+.2f} m"
                path = self.maze.path((row, col), (grow, gcol))
                path_m = f"{self.maze.path_length_m(path):.2f} m" if path else "no path"
                sight = "yes" if self.maze.line_of_sight((row, col), (grow, gcol)) else "no"
                lines.append(
                    f"{a}: at (row {row}, col {col}), heading {yaw[a][i]:.0f} deg; goal at "
                    f"(row {grow}, col {gcol}), {float(dist[a][i]):.2f} m straight-line, "
                    f"{path_m} through the maze, line of sight {sight}; "
                    f"nearest wall {float(walls[a][i]):.2f} m; closed {progress_text} toward "
                    f"its goal since the last decision; current directive {self.directive[a][i]}"
                )
            lines.append(f"Robot separation: {sep[i]:.2f} m.")
            texts.append("\n".join(lines))
        for a in AGENTS:
            self.last_goal_dist[a] = torch.linalg.vector_norm(
                self.goals[a] - wp.to_torch(self.robots[a].data.root_pos_w)[:, :2], dim=-1
            )
        return texts

    # -- deciding ------------------------------------------------------------

    def _random_decision(self) -> dict:
        decision = {}
        for a in AGENTS:
            directive = DIRECTIVES[int(self.rng.integers(len(DIRECTIVES)))]
            row, col = self.maze.random_free(self.rng) if directive == "waypoint" else (-1, -1)
            decision[a] = {"directive": directive, "row": row, "col": col}
        return decision

    def _planner_decisions(self) -> list[dict]:
        decisions = []
        pos = {a: self._local(wp.to_torch(r.data.root_pos_w)[:, :2]) for a, r in self.robots.items()}
        goal = {a: self._local(g) for a, g in self.goals.items()}
        for i in range(self.base.num_envs):
            decision = {}
            for a in AGENTS:
                start, end = self.maze.to_cell(pos[a][i]), self.maze.to_cell(goal[a][i])
                path = self.maze.path(start, end)
                if path is None or self.maze.line_of_sight(start, end):
                    decision[a] = {"directive": "go_to_goal", "row": -1, "col": -1}
                    continue
                visible = [cell for cell in path if self.maze.line_of_sight(start, cell)]
                row, col = visible[-1] if len(visible) > 1 else path[min(1, len(path) - 1)]
                decision[a] = {"directive": "waypoint", "row": row, "col": col}
            decisions.append(decision)
        return decisions

    def decide(self, step: int) -> list[dict]:
        if self.mode == "random":
            return [self._random_decision() for _ in range(self.base.num_envs)]
        if self.mode == "planner":
            return self._planner_decisions()
        texts = self.snapshot()
        schema = decision_schema()
        with ThreadPoolExecutor(max_workers=args_cli.llm_workers) as pool:
            replies = list(pool.map(
                lambda it: self.llm.complete_json(SYSTEM_PROMPT, it[1], schema, tag=f"step{step}_env{it[0]}"),
                enumerate(texts),
            ))
        decisions = []
        for reply in replies:
            if reply is None:
                # the LLM failed outright: do not intervene
                self.counts["llm_fallback"] += 1
                reply = {a: {"directive": "go_to_goal", "row": -1, "col": -1} for a in AGENTS}
            decisions.append(reply)
        return decisions

    def apply(self, decisions: list[dict]) -> None:
        base = self.base
        for i, decision in enumerate(decisions):
            for a in AGENTS:
                d = decision[a]
                directive = d["directive"]
                self.counts[directive] += 1
                self.directive[a][i] = directive
                self.hold[a][i] = directive == "yield"
                base.nav_override[a][i] = directive == "waypoint"
                if directive == "waypoint":
                    row, col = self.maze.nearest_free(int(d["row"]), int(d["col"]))
                    if (row, col) != (int(d["row"]), int(d["col"])):
                        self.counts["invalid_waypoint"] += 1
                    xy = torch.as_tensor(self.maze.to_xy(row, col), device=base.device)
                    base.nav_target[a][i] = xy + self.origins[i]

    # -- every step ----------------------------------------------------------

    def step_update(self, done: torch.Tensor) -> None:
        """Clear reached waypoints; drop directives for envs that just reset."""
        base = self.base
        for a, robot in self.robots.items():
            pos = wp.to_torch(robot.data.root_pos_w)[:, :2]
            reached = torch.linalg.vector_norm(base.nav_target[a] - pos, dim=-1) < WAYPOINT_REACHED_M
            base.nav_override[a] &= ~reached
            self.hold[a] &= ~done
            stale = done | base.step_events[f"{a}_goal"]
            self.last_goal_dist[a][stale] = float("nan")
            for i in done.nonzero().flatten().tolist():
                self.directive[a][i] = "go_to_goal"

    def mask_actions(self, actions: dict) -> dict:
        actions = {a: v.clone() for a, v in actions.items()}
        for a in AGENTS:
            # zero is "stop": the rover's wheels stop, the XGO is commanded to stand
            actions[a][self.hold[a]] = 0.0
        return actions


def main() -> None:
    with open(HERE / "agents" / "skrl_ippo_cfg.yaml", encoding="utf-8") as fh:
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

    out_dir = HERE / "logs" / "llm" / "coordinator" / args_cli.name
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{args_cli.mode}_seed{args_cli.seed}"

    llm = None
    if args_cli.mode == "llm":
        llm = backend_from_args(args_cli, out_dir / f"{tag}_transcript.jsonl")
        print(f"Coordinator LLM: {llm.name}")

    maze = MazeMap(base.spawn_points.cpu().numpy())
    print(f"Maze map: {maze.rows} x {maze.cols} cells, {int(maze.free.sum())} free")
    coordinator = Coordinator(base, maze, args_cli.mode, llm)

    obs, _ = env.reset()
    metrics = MazeMetrics(base)
    decisions_made = 0

    for step in range(args_cli.steps):
        if args_cli.mode != "baseline" and step % args_cli.decide_every == 0:
            coordinator.apply(coordinator.decide(step))
            decisions_made += 1
            if decisions_made % 5 == 0:
                print(f"  step {step}/{args_cli.steps}: {decisions_made} decision rounds, "
                      f"directives {coordinator.counts}", flush=True)

        with torch.inference_mode():
            actions = runner.agent.act(obs, env.state(), timestep=0, timesteps=0)[0]
        # The policy acted on the observation from the end of the previous step, so a
        # new waypoint takes effect one step (33 ms) late. Negligible against the
        # 1 s decision interval.
        obs, _, terminated, truncated, _ = env.step(coordinator.mask_actions(actions))
        metrics.update(terminated, truncated)
        # the skrl wrapper returns these as (num_envs, 1)
        coordinator.step_update((terminated[CE.ROVER_AGENT] | truncated[CE.ROVER_AGENT]).reshape(-1))

    summary = metrics.summary()
    summary |= {
        "mode": args_cli.mode,
        "seed": args_cli.seed,
        "checkpoint": os.path.abspath(args_cli.checkpoint),
        "decide_every": args_cli.decide_every,
        "decision_rounds": decisions_made,
        "directives": coordinator.counts,
        "llm": llm.stats() if llm else None,
        "fitness": fitness(summary),
    }
    print_table(summary, f"COORDINATOR: {args_cli.mode.upper()}")
    print(f"  directives: {coordinator.counts}")
    out_path = out_dir / f"{tag}.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"  wrote {out_path}")
    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
