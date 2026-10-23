#!/usr/bin/env bash
# Tail cell: qwen3-30b serial thinking-off measured arm, after stage5 finishes.
cd "$(dirname "$0")/.."
while pgrep -f "stage5_ego.sh" > /dev/null; do sleep 60; done
while pgrep -f "llm_negotiation.py --tag" > /dev/null; do sleep 20; done
LOG=studies/results_raw/llm/stage2c.log
~/.nemoclaw/local-models/serve.sh qwen3-30b >> "$LOG" 2>&1 \
  && ./.venv/bin/python studies/llm_negotiation.py --tag qwen3-30b-offm-s \
       --model qwen3-30b-a3b-nvfp4 --base-url http://localhost:8000/v1 \
       --n 100 --think measured --workers 1 --max-tokens 4096 --no-think >> "$LOG" 2>&1
~/.nemoclaw/local-models/serve.sh nemotron-lightning >> "$LOG" 2>&1 || true
