# Running the LLM negotiator locally (llama.cpp, e.g. on a Dell Pro Max GB10)

The `llm` policy (`amr_negotiation/llm.py`) talks to any OpenAI-compatible chat endpoint. llama.cpp's
`llama-server` provides one, so no API key or internet access is needed. The 2D simulator is pure Python and
runs natively on the GB10's ARM (aarch64) CPU. Gazebo isn't needed for these experiments.

## 1. Get the code

```bash
git clone https://github.com/briandeegan82/multi-agent-robots.git
cd multi-agent-robots/amr_negotiation
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
python -m pytest -q tests          # the LLM tests use a fake server; the live one is skipped
```

## 2. Start llama-server

```bash
# in your llama.cpp build; -ngl 999 puts every layer on the GPU, --parallel = concurrent requests
./build/bin/llama-server -m /path/to/model.gguf --port 8080 -c 16384 --parallel 4 -ngl 999 --jinja
curl -s localhost:8080/v1/models     # check the server is up
```

Each request needs about 1.5k tokens of context (`-c` is shared across the `--parallel` slots). With 128 GB of
unified memory, anything from 7B up to a 70B model at Q4 (around 40 GB) fits.

## 3. One episode

```bash
export AMRNEG_LLM_URL=http://localhost:8080/v1 AMRNEG_LLM_MODEL=<label for logs>
AMRNEG_LLM_URL=$AMRNEG_LLM_URL python -m pytest -q tests/test_llm.py -k live    # end-to-end against the server
amrneg-run scenarios/corridor_single_bay.yaml --policy llm --events --json ep.json
amrneg-run scenarios/corridor_single_bay.yaml --policy llm --pset llm.mode=agents llm.info=plans
```

The decision record in `ep.json` (`decisions[*]`) has the model's answers and reasons (`llm_answers`), its
latency, and the rule used. That rule is `llm_mediator` or `llm_agents`. If the answer wasn't used, it is
`llm_fallback_<error|parse|disagree|infeasible>:<rulebook rule>`.

## 4. The study

```bash
python studies/llm_negotiation.py --tag <model> --model <model> --n 50 --workers 4
# -> studies/report/llm_<model>.md, studies/results_raw/llm/<model>/{rows,cache}.jsonl
python studies/llm_negotiation.py --tag <model>_think0 --model <model> --n 50 --think 0
```

- It runs `--n` random encounters per layout. In each one it compares four LLM variants against `fixed_priority`,
  the default rulebook, `cost_bid`, and the best forced yielder:
  - mediator or per-robot agents;
  - `raw` (positions and refuges only) or `plans` (the prompt also includes each robot's predicted yield delay).
- `--think measured` (the default) charges the real LLM latency as decision time in the sim, so a slow model pays
  for its own slowness. `--think 0` measures decision quality alone.
- Every answer is cached in `cache.jsonl`, keyed by model, prompt, temperature and seed. Re-running the same
  `--tag` replays the answers, so an interrupted run resumes and a finished one reproduces exactly.
- Reasoning models (gpt-oss, Qwen3, DeepSeek-R1 distills) think before they answer. Pass `--max-tokens 4096` so
  the answer isn't cut off. If an older llama.cpp build rejects `response_format`, add `--no-constrain`.
- Push the `report/` and `results_raw/llm/` outputs on a branch, or send them over, and they can go into the paper.

## Notes

- With temperature 0, both robots build identical prompts from the same frozen snapshots, so they reach the same
  decision without an extra message round, just like the other policies. In `agents` mode each robot gets its
  own point-of-view prompt. A natural-language dialogue over the comms channel would be the next step.
- In Gazebo, the agent node blocks for the length of the HTTP call, so real latency is already paid in sim time.
  Use `llm.think_time: 0` there to avoid charging it twice. The container also needs to reach the server
  (`--network host`).
