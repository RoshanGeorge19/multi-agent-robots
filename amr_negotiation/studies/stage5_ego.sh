#!/usr/bin/env bash
# Stage 5 egocentric-VLM arm: each agent sees only its own forward view + peer
# broadcast text. Runs after stage2c finishes. LLM_VISION=ego via llm_agents_img.
cd "$(dirname "$0")/.."
PY=./.venv/bin/python
SERVE="$HOME/.nemoclaw/local-models/serve.sh"
LOG=studies/results_raw/llm/stage5.log

while pgrep -f "stage2c_measured.sh" > /dev/null; do sleep 60; done
while pgrep -f "llm_negotiation.py --tag" > /dev/null; do sleep 20; done

for kv in "nemotron-omni nemotron-3-nano-omni-30b-a3b-reasoning-nvfp4" \
          "nemotron-vl-12b nvidia-nemotron-nano-12b-v2-vl-nvfp4-qad" \
          "gemma4-26b gemma4-26b-a4b-nvfp4" \
          "qwen3.8-27b qwen3.8-27b-nvfp4"; do
  set -- $kv; tag=$1; mdl=$2
  echo "=== $tag-ego $(date -u +%H:%M) ===" >> "$LOG"
  $SERVE "$tag" >> "$LOG" 2>&1 || { echo "$tag SERVE FAILED" >> "$LOG"; continue; }
  $PY studies/llm_negotiation.py --tag "${tag}-ego" --model "$mdl" \
      --base-url http://localhost:8000/v1 --n 100 \
      --variants llm_agents_raw llm_agents_plans llm_agents_img \
      --think 0 --workers 4 --max-tokens 4096 --no-think >> "$LOG" 2>&1 \
    && echo "$tag OK" >> "$LOG" || echo "$tag FAILED" >> "$LOG"
done
$SERVE nemotron-lightning >> "$LOG" 2>&1 || true
echo "=== stage5 done $(date -u +%H:%M) ===" >> "$LOG"
