# LLM experiments

Two experiments put a language model in the loop of the two-robot maze task.
Every LLM exchange is appended to a JSONL transcript next to the results, so
any number can be traced to the exact prompt and reply that produced it.

| | Experiment 1: reward designer | Experiment 2: coordinator |
|---|---|---|
| Script | `llm_reward_search.py` | `llm_coordinator.py` |
| LLM decides | the reward weights for a training run | per-robot directives every second, from a map |
| Runs in | any Python (Isaac only in subprocesses) | Isaac's Python |
| Cost per data point | one full train + eval (tens of minutes) | one eval rollout, plus LLM latency |
| Judged by | `fitness` on held-out eval rollouts | the same metrics, against 3 control conditions |
| Output | `logs/llm/reward_search/<name>/` | `logs/llm/coordinator/<name>/` |

Both use the same task metrics (`maze_metrics.py`, also used by `eval_maze.py`):
goals and failures (collisions and falls) per env-minute for each robot, the
close-encounter rate, and

    fitness = mean over both robots of (goals/env-min - failures/env-min)

## Backends

`--llm` takes a backend spec (`llm/backends.py`):

- `ollama:qwen3.6:35b` (default). Uses the local Ollama, with no extra
  dependencies. `deepseek-r1:32b` is also installed.
- `claude:claude-opus-5-5`. Uses the Anthropic API with structured outputs and
  server-side refusal fallbacks. It needs the SDK in Isaac's Python
  (`~/IsaacLab/_isaac_sim/python.sh -m pip install anthropic`) and either
  `ANTHROPIC_API_KEY` or an `ant auth login` profile. `--llm_effort` sets the
  effort level.

Answers are constrained by a JSON schema on both backends. Values outside the
allowed range are clamped by the caller, and the clamping is recorded.

**Ollama on this machine:** with Ollama's default `num_batch` (512),
qwen3.6:35b intermittently crashes on prompts of about 1.3k to 1.8k tokens
("CUDA error: an illegal memory access"). After a crash every request fails
until the runner reloads. The backend therefore sends `num_batch=256`, which ran
the failing prompts cleanly.

## Experiment 1: LLM reward design

This is a Eureka-style loop that automates what the recent commits did by hand
("rebalance maze rewards against measured term magnitudes"). Each trial runs
four steps:

1. The LLM reads the actual `_get_rewards` source, the search space
   (`llm/reward_space.py`: 11 weights, each with bounds that fix its sign), and
   every earlier trial: its weights, task metrics, the measured mean per-step
   reward terms, and its fitness.
2. It returns a diagnosis, one hypothesis, and a full set of weights.
3. `train_rl.py --reward_overrides` trains IPPO from scratch with the same seed
   and the same budget.
4. `eval_maze.py` scores the **final** checkpoint. skrl's `best_agent.pt` is
   chosen by training return, and training return is exactly what changes
   meaning from one trial to the next.

Trial 0 always uses the current defaults, so every result is compared with a
baseline trained under the same conditions. The run can be resumed: re-running
with the same `--name` continues after the last finished trial.

```bash
cd IsaacSim/Scripts/train
python3 llm_reward_search.py --dry_run --iterations 3        # tests the loop on a synthetic landscape; no simulator
python3 llm_reward_search.py --name qwen_v1 --iterations 8   # real search
python3 llm_reward_search.py --name opus_v1 --llm claude:claude-opus-5-5
```

The budget defaults to 4800 steps × 512 envs per trial for training and
1080 steps × 128 envs for evaluation (`--timesteps`, `--num_envs`,
`--eval_steps`, `--eval_envs`).

**Read the results with care.** Each trial is one seed. Before you believe that
trial *k* beats the baseline, retrain both on 2–3 more seeds (`--seed`). A
fitness gap smaller than the spread across seeds is noise.

## Experiment 2: LLM coordination

The IPPO policies are reactive. They see the lidar, the bearing to their goal
and the other robot, but no map, and nothing lets them agree who goes first.
Every `--decide_every` steps (30 by default, which is 1 s of simulation), a
coordinator gives each robot one directive:

- `go_to_goal`: no intervention.
- `waypoint row col`: until the robot reaches the cell, the policy *observes*
  that cell as its goal (`env.nav_target`). Rewards and goal counting still use
  the true goal.
- `yield`: the robot holds still until the next decision.

Run the four conditions on the same checkpoint and seeds:

```bash
for mode in baseline random planner llm; do
  for seed in 0 1 2; do
    ~/IsaacLab/_isaac_sim/python.sh llm_coordinator.py --headless \
      --checkpoint <ippo checkpoint> --mode $mode --seed $seed --name cmp_v1
  done
done
```

| Mode | Purpose |
|---|---|
| `baseline` | the policies alone |
| `random` | random directives. Separates "the LLM's judgement helps" from "intervening at all changes things". |
| `planner` | BFS on the same map, steering toward the farthest point on the path that is in line of sight; never yields. Separates "the LLM helps" from "having a map helps". |
| `llm` | the model decides from an ASCII map plus each robot's state, including its path length through the maze and whether it has line of sight to its goal |

**The comparison that matters is `llm` against `planner`.** Any gain over
`baseline` that `planner` also achieves came from the map, not from the
language model. The one thing the LLM can do that the planner cannot is decide
who yields.

### What the probes showed so far (synthetic maze, before any simulator runs)

On a maze where the rover's goal sits behind a wall, with qwen3.6:35b:

- **Thinking off, no path hint:** it reasoned at length inside the `rationale`
  field (48 s), worked out the correct route, and then sent the rover
  `go_to_goal`, straight into the wall.
- **Thinking on (`--llm_think`):** each call took several minutes, which is
  far too slow for decisions every second, and one call returned empty
  content.
- **Thinking off, with the path hint (now the default):** 5–7 s per call, and
  in 3 of 3 runs it diagnosed correctly that the rover was blocked and the XGO
  was clear. But its waypoint was a cell just in front of the wall every time,
  not the gap that BFS finds.

In short, the model can tell from the ASCII grid that something is wrong but
cannot plan a route on it. The `planner` condition measures how much that costs.

Worth trying next:

- Give the LLM a short list of candidate waypoints (for example the planner's
  route point and the junction cells) to choose from, so it arbitrates between
  options instead of inventing coordinates.
- Compare `claude:claude-opus-5-5` on the same prompts.

### Latency

The simulator waits while the LLM decides, so latency costs wall-clock time,
not simulated time. Decision rounds are sent in parallel across envs
(`--llm_workers`). With 8 envs and the local model, expect roughly 10–20 s per
round.
