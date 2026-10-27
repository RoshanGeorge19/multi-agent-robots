[↑ Project hierarchy](../../PROJECT_HIERARCHY.md) · [Parent: experiments](../README.md)

# `experiments/llm/`: LLM/VLM negotiator study (paper 2)

## `llm_negotiation.py`: the study script

```bash
python experiments/llm/llm_negotiation.py --tag qwen3-30b --model qwen3-30b-a3b-nvfp4 \
    --base-url http://localhost:8000/v1 --n 100 --variants llm_med_plans --think 0 --max-tokens 4096
```

- **Encounters.** It draws `--n` encounters per layout (single bay, two bays) from seed 100000, so every run is paired with every other.
- **What it runs.** For each encounter it runs both forced outcomes (the best forced yielder is the reference), fixed priority, the rulebook, `cost_bid`, and the chosen LLM variants.
- **Outputs:**
  - `data/raw/llm/<tag>/rows.jsonl` and `meta.json` (see [`data/raw/llm/`](../../data/raw/llm/README.md));
  - `data/tables/llm/llm_<tag>.md`;
  - a git-ignored prompt cache `cache.jsonl`. Rerunning the same tag replays cached answers, so interrupted runs resume.
- **Options:**
  - `--think 0|measured`: charge no decision time, or the real latency;
  - `--no-think`: disable the reasoning trace;
  - `--no-constrain`: drop the JSON schema;
  - `--workers`: episodes in parallel.
- **Server.** It needs an OpenAI-compatible server; see [`docs/llm_local.md`](../../docs/llm_local.md). It imports the encounter generator from `experiments/classical/learned_negotiator.py`.

| Variant | Mode | Input | Tiebreak on disagreement |
|---|---|---|---|
| `llm_med_raw` / `llm_med_plans` | mediator (one call) | text / text + planner delays | — |
| `llm_med_img` / `llm_med_imgtext` | mediator | global image / image + raw text | — |
| `llm_agents_raw` / `llm_agents_plans` | agents (one call per robot) | text / text + planner delays | rulebook |
| `llm_agents_img` | agents | egocentric image + broadcast text | rulebook |
| `llm_agents_nonce` / `llm_agents_img_nonce` | agents | text / ego image, with the draw rule and cards in the prompt | visible hash draw |
| `llm_agents_silent` | agents | ego image, prompt unchanged | hidden hash draw |
| `llm_agents_commit` / `llm_agents_csilent` | agents | text | commit-reveal draw (visible / hidden) |

## Batch drivers: what actually ran

These are a record, not portable tooling. They assume the GB10 machine: `./.venv`, `~/.nemoclaw/local-models/serve.sh` for
switching models, and `$NVIDIA_INFERENCE_API_KEY` for the hosted model.

| Script | Stage |
|---|---|
| `stage1_screen.sh` | 1: screen every model on mediator + plans |
| `stage2_matrix.sh`, `stage2b_matrix.sh` | 2: config matrix for the top models; reasoning on/off × cost mode |
| `stage2c_measured.sh`, `tail_offm.sh` | 2c: serial measured-latency runs |
| `stage4_vlm.sh` | 4: vision arms |
| `stage5_ego.sh` | 5: egocentric decentralised agents |
| `stage6_nonce.sh`, `stage7_silent.sh` | 6–7: visible / hidden tiebreak draws |
| `orchestrate.sh`, `run_rest.sh` | chain stages |

The stage plan is in [`docs/llm_experiments.md`](../../docs/llm_experiments.md), and the run index is in
[`reports/llm/`](../../reports/llm/README.md).
