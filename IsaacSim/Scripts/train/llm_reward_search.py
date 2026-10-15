"""Experiment 1: an LLM designs the maze reward, judged by a fixed task metric.

Eureka-style outer loop around the existing trainer. Each iteration:

    1. the LLM reads the reward code, the search space, and every previous trial
       (weights, task metrics, measured per-term reward magnitudes, fitness)
    2. it proposes a full set of weights plus a diagnosis and a hypothesis
    3. train_rl.py trains IPPO from scratch with those weights (subprocess)
    4. eval_maze.py scores the final checkpoint on the fixed task metric

Trial 0 is always the current defaults, so every result has a baseline trained
under the same budget and seed. The fitness (llm.reward_space.fitness) is not a
reward: the LLM cannot game it by rescaling terms.

This automates the loop the recent commits did by hand ("rebalance maze rewards
against measured term magnitudes").

Runs in any Python: the simulator only ever runs in the subprocesses.

Usage:
    # smoke-test the LLM loop on a synthetic landscape -- no simulator, minutes
    python3 llm_reward_search.py --dry_run --iterations 3

    # real search: ~8 trials of 4800 steps x 512 envs each
    python3 llm_reward_search.py --name qwen_v1 --iterations 8
    python3 llm_reward_search.py --name opus_v1 --llm claude:claude-opus-5-5

Re-running with the same --name resumes after the last completed trial.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

from llm.backends import add_backend_args, backend_from_args
from llm.reward_space import REWARD_SPACE, clamp_overrides, fitness, proposal_schema

HERE = Path(__file__).resolve().parent
DEFAULT_ISAAC_PYTHON = Path.home() / "IsaacLab" / "_isaac_sim" / "python.sh"

SYSTEM_PROMPT = """\
You are tuning the reward function of a two-robot reinforcement-learning task in a \
small maze. A wheeled rover and a quadruped (XGO) each have their own PPO policy \
(IPPO) and their own goal; goals respawn when reached. Contact with anything, or \
the XGO falling, ends the episode for both robots.

You choose reward weights. You do not choose the objective. Each trial trains both \
policies from scratch with your weights, under a fixed budget, and is then scored by \
a task metric you cannot change:

    fitness = mean over both robots of (goals per env-minute - failures per env-minute)

where failures are collisions and falls. A reward that helps one robot by starving \
the other scores poorly.

Training is expensive and you get few trials. Work like an experimentalist: \
diagnose the previous results from the measured numbers, state one clear hypothesis, \
and change only what that hypothesis needs, so the next result is interpretable. \
Per-term reward magnitudes are measured per step; multiply by episode length to \
compare them with one-off bonuses. Values outside the stated bounds are clamped."""


def read_defaults() -> dict[str, float]:
    """Current weights, read from the env config source -- no Isaac import needed."""
    source = (HERE / "collision_env.py").read_text(encoding="utf-8")
    defaults = {}
    for name in REWARD_SPACE:
        match = re.search(rf"^\s+{name}\s*=\s*([-0-9.e]+)", source, re.MULTILINE)
        if match is None:
            raise RuntimeError(f"default for {name} not found in collision_env.py")
        defaults[name] = float(match.group(1))
    return defaults


def reward_code_excerpt() -> str:
    """The reward function as the LLM should read it: the real source."""
    source = (HERE / "collision_env.py").read_text(encoding="utf-8")
    start = source.index("    def _get_rewards(self)")
    end = source.index("    # ---", start)
    return source[start:end].rstrip()


def describe_trial(trial: dict) -> str:
    lines = [f"## Trial {trial['index']}" + (" (baseline: current defaults)" if trial["index"] == 0 else "")]
    if trial.get("hypothesis"):
        lines.append(f"Hypothesis: {trial['hypothesis']}")
    changed = {k: v for k, v in trial["weights"].items() if v != trial["defaults"][k]}
    lines.append(f"Weights changed from defaults: {json.dumps(changed) if changed else 'none'}")
    if trial.get("notes"):
        lines.append(f"Clamping notes: {'; '.join(trial['notes'])}")
    if trial.get("error"):
        lines.append(f"FAILED: {trial['error']}")
        return "\n".join(lines)
    s = trial["summary"]
    for agent, a in s["agents"].items():
        lines.append(
            f"- {agent}: {a['goals_per_env_min']:.3f} goals/env-min, "
            f"{a['failures_per_env_min']:.3f} failures/env-min "
            f"({a['collisions']} collisions, {a['falls']} falls), "
            f"{a['travelled_m_per_env_min']:.2f} m travelled/env-min"
        )
    lines.append(
        f"- close encounters: {s['close_encounter_fraction']:.2%} of env-steps; "
        f"{s['episodes']} episodes over {s['sim_env_minutes']:.0f} env-minutes"
    )
    terms = ", ".join(f"{k} {v:+.4f}" for k, v in sorted(s["rover_reward_terms"].items()))
    lines.append(f"- rover reward terms, mean per step: {terms or 'n/a'}")
    lines.append(f"- FITNESS: {trial['fitness']:+.4f}")
    return "\n".join(lines)


def build_prompt(trials: list[dict], defaults: dict, iteration: int, total: int, args) -> str:
    space = "\n".join(
        f"- {name} in [{lo}, {hi}] (default {defaults[name]}): {doc}"
        for name, (lo, hi, doc) in REWARD_SPACE.items()
    )
    episode_steps = 540  # 18 s at 30 Hz
    best = max((t for t in trials if "fitness" in t), key=lambda t: t["fitness"], default=None)
    return f"""\
# Reward code (collision_env.py)
```python
{reward_code_excerpt()}
```

# Search space
{space}

Episodes last at most {episode_steps} steps. Each trial trains for {args.timesteps} \
steps x {args.num_envs} envs, seed {args.seed}, then evaluates the final policies \
for {args.eval_steps} steps x {args.eval_envs} envs.

# Trials so far
{chr(10).join(describe_trial(t) for t in trials)}

Best so far: trial {best['index'] if best else '-'} (fitness {best['fitness'] if best else float('nan'):+.4f}).

# Your turn
This is proposal {iteration} of {total}. Give your diagnosis of the results so far, \
one hypothesis, and the complete set of weights for the next trial."""


def latest_checkpoint(run_dir: Path) -> Path:
    """The final checkpoint, not best_agent.pt.

    skrl picks best_agent by training return, and return is exactly what changes
    meaning between trials -- so it would select on the thing being varied.
    """
    paths = glob.glob(str(run_dir / "checkpoints" / "agent_*.pt"))
    if not paths:
        raise FileNotFoundError(f"no checkpoints in {run_dir}")
    return Path(max(paths, key=lambda p: int(re.search(r"agent_(\d+)\.pt", p).group(1))))


def run_logged(cmd: list[str], log_path: Path) -> None:
    print(f"    $ {' '.join(cmd)}\n      (log: {log_path})", flush=True)
    with log_path.open("w", encoding="utf-8") as log:
        result = subprocess.run(cmd, cwd=HERE, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-15:]
        raise RuntimeError(f"exit {result.returncode}: " + " | ".join(tail))


def run_trial(trial_dir: Path, weights: dict, args, run_name: str) -> dict:
    overrides_path = trial_dir / "overrides.json"
    overrides_path.write_text(json.dumps(weights, indent=2))
    python = str(args.isaac_python)
    run_logged(
        [python, "train_rl.py", "--headless",
         "--num_envs", str(args.num_envs), "--timesteps", str(args.timesteps),
         "--seed", str(args.seed), "--reward_overrides", str(overrides_path),
         "--run_name", run_name],
        trial_dir / "train.log",
    )
    checkpoint = latest_checkpoint(HERE / "logs" / "skrl" / "collision_avoidance" / run_name)
    eval_path = trial_dir / "eval.json"
    run_logged(
        [python, "eval_maze.py", "--headless", "--checkpoint", str(checkpoint),
         "--num_envs", str(args.eval_envs), "--steps", str(args.eval_steps),
         "--seed", str(args.seed), "--json_out", str(eval_path)],
        trial_dir / "eval.log",
    )
    return json.loads(eval_path.read_text())


def synthetic_trial(weights: dict) -> dict:
    """Dry-run stand-in for train+eval: a smooth made-up landscape.

    Its optimum is deliberately away from the defaults, so a working loop should
    show fitness rising. It says nothing about the real task.
    """
    w = weights
    progress = math.tanh(w["rew_gets_closer_to_goal"] / 40.0)
    caution = math.tanh(-w["rew_wall_collision"] / 60.0) + math.tanh(-w["rew_wall_proximity_penalty"] * 3)
    timid = max(0.0, caution - 1.2)
    goals = 2.0 * progress * (1.0 - 0.6 * timid) * (1 + 0.2 * math.tanh(w["rew_reach_goal"] / 200))
    failures = 1.2 * (1.0 - 0.45 * caution) * (1.0 - 0.3 * math.tanh(-w["rew_xgo_fell"] / 80))
    agent = lambda g, f: {  # noqa: E731
        "goals": int(g * 100), "collisions": int(f * 80), "falls": int(f * 20),
        "goals_per_env_min": g, "failures_per_env_min": f, "travelled_m_per_env_min": 3 * progress,
    }
    return {
        "steps": 600, "num_envs": 128, "sim_env_minutes": 42.7, "episodes": 300,
        "agents": {"rover": agent(goals, failures), "xgo": agent(goals * 0.6, failures * 1.1)},
        "close_encounter_fraction": 0.02, "min_separation_m": 0.2,
        "rover_reward_terms": {"progress": 0.01 * w["rew_gets_closer_to_goal"] / 20,
                               "collision": failures / 1800 * w["rew_wall_collision"]},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", default="dry_run", help="Experiment name (resumable).")
    parser.add_argument("--iterations", type=int, default=8, help="LLM proposals after the baseline.")
    parser.add_argument("--num_envs", type=int, default=512)
    parser.add_argument("--timesteps", type=int, default=4800)
    parser.add_argument("--eval_envs", type=int, default=128)
    parser.add_argument("--eval_steps", type=int, default=1080)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--isaac_python", type=Path, default=DEFAULT_ISAAC_PYTHON)
    parser.add_argument("--dry_run", action="store_true",
                        help="Replace training with a synthetic landscape to test the loop.")
    add_backend_args(parser)
    args = parser.parse_args()

    exp_dir = HERE / "logs" / "llm" / "reward_search" / args.name
    exp_dir.mkdir(parents=True, exist_ok=True)
    state_path = exp_dir / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"args": {}, "trials": []}
    state["args"] = {k: str(v) for k, v in vars(args).items()}
    trials: list[dict] = state["trials"]

    llm = backend_from_args(args, exp_dir / "transcript.jsonl")
    defaults = read_defaults()
    schema = proposal_schema()
    print(f"Reward search '{args.name}' with {llm.name} -> {exp_dir}")
    if trials:
        print(f"Resuming after {len(trials)} completed trial(s).")

    for index in range(len(trials), args.iterations + 1):
        trial = {"index": index, "defaults": defaults}
        if index == 0:
            trial["weights"] = dict(defaults)
        else:
            reply = llm.complete_json(
                SYSTEM_PROMPT, build_prompt(trials, defaults, index, args.iterations, args),
                schema, tag=f"trial_{index}",
            )
            if reply is None:
                sys.exit(f"LLM failed to produce a proposal; see {llm.log_path}")
            weights, notes = clamp_overrides(reply["weights"])
            trial.update(weights={**defaults, **weights}, notes=notes,
                         diagnosis=reply["diagnosis"], hypothesis=reply["hypothesis"])
            print(f"\n[trial {index}] {reply['hypothesis']}")

        trial_dir = exp_dir / f"trial_{index:02d}"
        trial_dir.mkdir(exist_ok=True)
        try:
            if args.dry_run:
                summary = synthetic_trial(trial["weights"])
            else:
                summary = run_trial(trial_dir, trial["weights"], args, f"llm_{args.name}_t{index:02d}")
            trial.update(summary=summary, fitness=fitness(summary))
            print(f"[trial {index}] fitness {trial['fitness']:+.4f}")
        except Exception as exc:  # noqa: BLE001 - a crashed trial is a result the LLM should see
            trial["error"] = f"{type(exc).__name__}: {exc}"[:600]
            print(f"[trial {index}] FAILED: {trial['error']}")

        trials.append(trial)
        state["llm_stats"] = llm.stats()
        state_path.write_text(json.dumps(state, indent=2))

    scored = [t for t in trials if "fitness" in t]
    print("\n===== REWARD SEARCH RESULTS =====")
    for t in trials:
        mark = f"{t['fitness']:+.4f}" if "fitness" in t else "failed"
        print(f"  trial {t['index']:2d}  {mark:>8}  {t.get('hypothesis', 'baseline')[:90]}")
    if scored:
        best = max(scored, key=lambda t: t["fitness"])
        print(f"\n  best: trial {best['index']} ({best['fitness']:+.4f}); "
              f"baseline {trials[0].get('fitness', float('nan')):+.4f}")
        (exp_dir / "best_weights.json").write_text(json.dumps(best["weights"], indent=2))
    print(f"  LLM: {llm.stats()}")


if __name__ == "__main__":
    main()
