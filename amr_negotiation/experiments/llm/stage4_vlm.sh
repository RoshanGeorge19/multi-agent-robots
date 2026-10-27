#!/usr/bin/env bash
# Stage 4 VLM arm: text vs image vs text+image on VL models, mediator mode, n=100.
# Waits for running studies; logs to data/raw/llm/stage4.log.
set -u
cd "$(dirname "$0")/../.."
PY=./.venv/bin/python
SERVE="$HOME/.nemoclaw/local-models/serve.sh"
LOG=data/raw/llm/stage4.log

while pgrep -f "llm_negotiation.py --tag" > /dev/null; do sleep 20; done

run() {
  local tag=$1 key=$2 model=$3
  echo "=== $tag $(date -u +%H:%M) ===" >> "$LOG"
  $SERVE "$key" >> "$LOG" 2>&1 || { echo "$tag SERVE FAILED" >> "$LOG"; return 1; }
  $PY experiments/llm/llm_negotiation.py --tag "${tag}-vlm" --model "$model" \
      --base-url http://localhost:8000/v1 --n 100 \
      --variants llm_med_plans llm_med_img llm_med_imgtext \
      --think 0 --workers 4 --max-tokens 4096 --no-think >> "$LOG" 2>&1 \
    && echo "$tag OK" >> "$LOG" || echo "$tag FAILED" >> "$LOG"
}

run nemotron-omni nemotron-omni nemotron-3-nano-omni-30b-a3b-reasoning-nvfp4
run nemotron-vl-12b nemotron-vl-12b nvidia-nemotron-nano-12b-v2-vl-nvfp4-qad
run gemma4-26b gemma4-26b gemma4-26b-a4b-nvfp4
run qwen3.8-27b qwen3.8-27b qwen3.8-27b-nvfp4

# Re-screen models whose Stage-1 serve failed, now that their args are fixed.
for kv in "nemotron-super-49b llama-3-3-nemotron-super-49b-v1-5-nvfp4" "nemotron-vl-12b nvidia-nemotron-nano-12b-v2-vl-nvfp4-qad" "muse-glimmer muse-glimmer"; do
  set -- $kv; tag=$1; mdl=$2
  echo "=== rescreen $tag $(date -u +%H:%M) ===" >> "$LOG"
  $SERVE "$tag" >> "$LOG" 2>&1 || { echo "$tag SERVE FAILED" >> "$LOG"; continue; }
  $PY experiments/llm/llm_negotiation.py --tag "$tag" --model "$mdl" \
      --base-url http://localhost:8000/v1 --n 100 --variants llm_med_plans \
      --think 0 --workers 4 --max-tokens 4096 >> "$LOG" 2>&1 \
    && echo "$tag rescreen OK" >> "$LOG" || echo "$tag rescreen FAILED" >> "$LOG"
done

$SERVE nemotron-lightning >> "$LOG" 2>&1 || true
echo "=== stage4 done $(date -u +%H:%M) ===" >> "$LOG"
