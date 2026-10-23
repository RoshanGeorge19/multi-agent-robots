#!/usr/bin/env bash
# Chains: lightning re-screen (post-fix) -> stage2 matrix -> stage4 VLM.
cd "$(dirname "$0")/.."
while pgrep -f "stage1_screen.sh" > /dev/null; do sleep 60; done
~/.nemoclaw/local-models/serve.sh nemotron-lightning >> studies/results_raw/llm/stage1.log 2>&1
./.venv/bin/python studies/llm_negotiation.py --tag nemotron-lightning \
  --model nvidia-nemotron-3.5-lightning-30b-a3b-nvfp4 \
  --base-url http://localhost:8000/v1 --n 100 --variants llm_med_plans \
  --think 0 --workers 4 --max-tokens 4096 >> studies/results_raw/llm/stage1.log 2>&1
bash studies/stage2_matrix.sh
bash studies/stage4_vlm.sh
