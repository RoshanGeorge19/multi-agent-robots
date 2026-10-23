#!/usr/bin/env bash
# Stage 7: silent-tiebreak arm — draw resolves conflicts in the protocol layer
# but is never mentioned in the prompt. Tests whether deliberation survives.
cd "$(dirname "$0")/.."
PY=./.venv/bin/python
SERVE="$HOME/.nemoclaw/local-models/serve.sh"
LOG=studies/results_raw/llm/stage7.log

for kv in "nemotron-omni nemotron-3-nano-omni-30b-a3b-reasoning-nvfp4" \
          "nemotron-vl-12b nvidia-nemotron-nano-12b-v2-vl-nvfp4-qad" \
          "gemma4-26b gemma4-26b-a4b-nvfp4" \
          "qwen3.8-27b qwen3.8-27b-nvfp4"; do
  set -- $kv; tag=$1; mdl=$2
  echo "=== $tag-silent $(date -u +%H:%M) ===" >> "$LOG"
  $SERVE "$tag" >> "$LOG" 2>&1 || { echo "$tag SERVE FAILED" >> "$LOG"; continue; }
  $PY studies/llm_negotiation.py --tag "${tag}-silent" --model "$mdl" \
      --base-url http://localhost:8000/v1 --n 100 \
      --variants llm_agents_img llm_agents_silent \
      --think 0 --workers 4 --max-tokens 4096 --no-think >> "$LOG" 2>&1 \
    && echo "$tag OK" >> "$LOG" || echo "$tag FAILED" >> "$LOG"
done
$SERVE nemotron-lightning >> "$LOG" 2>&1 || true
echo "=== stage7 done $(date -u +%H:%M) ===" >> "$LOG"
