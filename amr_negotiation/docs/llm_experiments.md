# Agentic negotiator experiments — plan

Companion to [docs/llm_local.md](llm_local.md). Goal: characterize how LLM and VLM negotiators compare
with the classical policies (`cost_bid`, rulebook, fixed priority) and the best-forced-yielder reference
on the corridor benchmark. All runs use the 2D simulator (`experiments/llm/llm_negotiation.py`), the same seed
draws for every model (paired comparisons), and the existing report generator.

Models are served locally on the GB10 by the `nemoclaw-vllm` container (OpenAI-compatible at
`http://localhost:8000/v1`, switched with `~/.nemoclaw/local-models/serve.sh`), plus one hosted NVIDIA
endpoint reference (`AMRNEG_LLM_API_KEY` = `$NVIDIA_INFERENCE_API_KEY`).

## Research questions

1. Decision quality vs. the forced-yielder reference (`excess`, `right yielder`) across model scale and
   reasoning style.
2. Whether `plans` info (predicted delays in-prompt) matters vs. `raw` geometry-only prompts.
3. Mediator vs. per-robot agents: decision quality vs. disagreement-fallback rate.
4. Deployed cost: `think_time: 0` (decision quality alone) vs. `measured` (model pays its own latency).
5. VLM arm: does a rendered top-down image of the encounter beat a numeric text state?

## Model roster

Local (vLLM, `serve.sh` keys):

| tag | served name | class |
|---|---|---|
| nemotron-lightning | nvidia-nemotron-3.5-lightning-30b-a3b-nvfp4 | 30B hybrid-MoE, reasoning (step3p5) |
| nemotron-nano | nvidia-nemotron-3-nano-30b-a3b-nvfp4 | 30B MoE, reasoning (nemotron_v3) |
| nemotron-omni | nemotron-3-nano-omni-30b-a3b-reasoning-nvfp4 | 30B multimodal, reasoning |
| nemotron-super-49b | llama-3-3-nemotron-super-49b-v1-5-nvfp4 | 49B dense, reasoning |
| qwen3-30b | qwen3-30b-a3b-nvfp4 | 30B MoE, reasoning optional |
| qwen3.8-27b | qwen3.8-27b-nvfp4 | 27B (multimodal arch) |
| gemma4-26b | gemma4-26b-a4b-nvfp4 | 26B multimodal |
| nemotron-vl-12b | nvidia-nemotron-nano-12b-v2-vl-nvfp4-qad | 12B vision-language |
| muse-glimmer | muse-glimmer | 30B experimental |

Hosted reference:

| tag | model | endpoint |
|---|---|---|
| nemotron-3-super | nvidia/nemotron-3-super-120b-a12b | https://integrate.api.nvidia.com/v1 |

## Stages

**Stage 0 — validation.** `nemotron-nano` × all 4 harness variants × n=20, `--max-tokens 4096`.
Confirms endpoint, JSON-schema constraint, parsers and report generation end to end.

**Stage 1 — model screen.** Every roster model × `llm_med_plans` only × n=100 × `--think 0`.
Isolates the model main effect cheaply (1 call per encounter).

**Stage 2 — config matrix.** Top 3 models by excess delay (ties broken by right-yielder rate):
`mode {med, agents} × info {raw, plans} × constrain {on, off} × think {0, measured}` → 16 cells
(4 study invocations per model), n=100 per cell.

**Stage 3 — prompt ablations (deferred).** Objective framing (min weighted delay / fairness / safety),
CoT on/off, few-shot, selfish personas. Needs a configurable prompt template.

**Stage 4 — VLM arm.** Render the encounter to a top-down image; arms = {text-only, image-only,
text+image} on VL models (nemotron-omni, nemotron-vl-12b, gemma4-26b, qwen3.8-27b if vision confirmed),
mediator mode, n=100. Needs a `llm.vision` option in `llm.py`.

**Stage 5 — stress & frontier (deferred).** Comms degradation under S8b-like loss/latency, selfish
per-robot prompting (ties to S9), multi-turn natural-language dialogue over the bus, tool use
(`plan_times` as a tool call).

## Practical notes

- Reasoning models need `--max-tokens 4096` so answers are not truncated.
- The vLLM container serves with `--max-num-seqs 1`; use `--workers 1` (extra workers just queue).
- `--seed0` stays at 100000 for every run: model comparisons are paired on identical encounters.
- Hosted model: `AMRNEG_LLM_URL=https://integrate.api.nvidia.com/v1 AMRNEG_LLM_MODEL=nvidia/nemotron-3-super-120b-a12b AMRNEG_LLM_API_KEY=$NVIDIA_INFERENCE_API_KEY`; add `--no-constrain` if the endpoint rejects `response_format`.
- Outputs land in `data/raw/llm/<tag>/` + `data/tables/llm/llm_<tag>.md`; prompt caches make
  reruns replay-free.
- Review checkpoint after stages 0–2 + 4: pick Stage 3/5 scope from the results.
