# LLM/VLM negotiator runs (paper 2)

There is no hand-written report for this study. The write-up is `papers/paper2_tase/main.tex`, and the plan is
`docs/llm_experiments.md`. This page indexes the runs.

- **Run outputs.** Each run tag has:
  - raw rows in `data/raw/llm/<tag>/rows.jsonl`, one line per policy × encounter, with the LLM answer, reasoning trace, latency and fallback cause;
  - run settings in `meta.json`;
  - a summary table in [`data/tables/llm/llm_<tag>.md`](../../data/tables/llm).
- **Encounters.** Every run uses encounter seeds from 100000, 100 per layout (single bay, two bays), so runs are paired encounter by encounter.
  - `n` = 100 means 200 encounters.
  - `n` = 25 means the first 50 encounters.

## Tag suffixes

| Suffix | Stage | Setting |
|---|---|---|
| *(none)* | 1, screen | mediator + plans, `think=0`, model's default reasoning, n = 100 |
| `-c1` / `-c2` / `-c3` / `-c4` | 2, config matrix | six text/image variants; `think` 0/0/measured/measured; JSON constraint on/off/on/off |
| `-off0` / `-on0` | 2b | reasoning off / on, `think=0` (on: n = 25) |
| `-offm` / `-onm` | 2b | reasoning off / on, measured latency, **concurrent** (4 episodes share the server) |
| `-offm-s` / `-onm-s` | 2c | as above, **serial** (one episode at a time, giving the deployed latency) |
| `-vlm` | 4, vision | mediator: text+plans vs global image only vs image + raw text |
| `-ego` | 5, egocentric agents | agents: raw text, plans, egocentric image |
| `-nonce` | 6, hidden draw | agents: random hash tiebreak instead of the rulebook fallback (prompt unchanged) |
| `-silent` | 7, visible draw | agents: the tiebreak rule and card values shown in the prompt |
| `-commit` | 7, commit-reveal | agents, raw text: commit-reveal tiebreak (`nemotron-lightning` only) |
| `-smoke`, `-smoke-think0` | 0, smoke test | Qwen2.5-1.5B on llama.cpp, n = 10 |

## Runs by model

| Model (served name) | Tags |
|---|---|
| Qwen3-30B-A3B (`qwen3-30b-a3b-nvfp4`) | `qwen3-30b`, `-c1`–`-c4`, `-off0`, `-on0`, `-offm`, `-onm`, `-offm-s`, `-onm-s` |
| Qwen3.8-27B (`qwen3.8-27b-nvfp4`) | `qwen3.8-27b`, `-c2`, `-c4`, `-off0`, `-on0`, `-offm`, `-offm-s`, `-onm-s`, `-vlm`, `-ego`, `-nonce`, `-silent` |
| Nemotron-3-Super-120B, hosted (`nvidia/nemotron-3-super-120b-a12b`) | `nemotron-3-super`, `-c1`–`-c4`, `-off0`, `-on0`, `-offm`, `-onm`, `-offm-s`, `-onm-s` |
| Nemotron-3-Nano-Omni (`nemotron-3-nano-omni-30b-a3b-reasoning-nvfp4`) | `nemotron-omni`, `-vlm`, `-ego`, `-nonce`, `-silent` |
| Gemma4-26B-A4B (`gemma4-26b-a4b-nvfp4`) | `gemma4-26b`, `-vlm`, `-ego`, `-nonce`, `-silent` |
| Nemotron-Nano-VL-12B (`nvidia-nemotron-nano-12b-v2-vl-nvfp4-qad`) | `nemotron-vl-12b`, `-vlm`, `-ego`, `-nonce`, `-silent` |
| Nemotron-3-Nano (`nvidia-nemotron-3-nano-30b-a3b-nvfp4`) | `nemotron-nano` |
| Nemotron-3.5-Lightning (`nvidia-nemotron-3.5-lightning-30b-a3b-nvfp4`) | `nemotron-lightning`, `-commit` |
| Llama-3.3-Nemotron-Super-49B (`llama-3-3-nemotron-super-49b-v1-5-nvfp4`) | `nemotron-super-49b` |
| Qwen2.5-1.5B (llama.cpp GGUF) | `qwen2.5-1.5b-smoke`, `-smoke-think0` |

**Excluded in the paper** (server errors or connection resets):
- every hosted `nemotron-3-super-*` run except the screen;
- `qwen3.8-27b-offm`, `qwen3.8-27b-c2`, `qwen3.8-27b-c4`;
- `qwen3-30b-c1`–`c4`.

`qwen3-30b-offm` is used only to measure server contention. The `stage*.log` files in `data/raw/llm/` are the original batch logs.
