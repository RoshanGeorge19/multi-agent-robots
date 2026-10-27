#!/usr/bin/env bash
# Stage 2c: serial (workers=1) rerun of measured-latency cells for clean
# deployed-latency numbers. offm n=100 thinking-off, onm n=25 thinking-on.
cd "$(dirname "$0")/../.."
PY=./.venv/bin/python
SERVE="$HOME/.nemoclaw/local-models/serve.sh"
LOG=data/raw/llm/stage2c.log

declare -A KEY MODEL
KEY[qwen3.8-27b]=qwen3.8-27b;   MODEL[qwen3.8-27b]=qwen3.8-27b-nvfp4
KEY[qwen3-30b]=qwen3-30b;       MODEL[qwen3-30b]=qwen3-30b-a3b-nvfp4
KEY[nemotron-3-super]=hosted;   MODEL[nemotron-3-super]=nvidia/nemotron-3-super-120b-a12b

cell() {
  local tag=$1 label=$2 n=$3; shift 3
  echo "=== ${tag}-${label} $(date -u +%H:%M) ===" >> "$LOG"
  if [ "${KEY[$tag]}" != "hosted" ]; then
    $SERVE "${KEY[$tag]}" >> "$LOG" 2>&1 || { echo "$tag SERVE FAILED" >> "$LOG"; return 1; }
    $PY experiments/llm/llm_negotiation.py --tag "${tag}-${label}" --model "${MODEL[$tag]}" \
        --base-url http://localhost:8000/v1 --n "$n" --think measured \
        --workers 1 --max-tokens 4096 "$@" >> "$LOG" 2>&1 \
      && echo "${tag}-${label} OK" >> "$LOG" || echo "${tag}-${label} FAILED" >> "$LOG"
  else
    AMRNEG_LLM_API_KEY="$NVIDIA_INFERENCE_API_KEY" $PY experiments/llm/llm_negotiation.py \
        --tag "${tag}-${label}" --model "${MODEL[$tag]}" \
        --base-url https://integrate.api.nvidia.com/v1 --n "$n" --think measured \
        --workers 1 --max-tokens 4096 "$@" >> "$LOG" 2>&1 \
      && echo "${tag}-${label} OK" >> "$LOG" || echo "${tag}-${label} FAILED" >> "$LOG"
  fi
}

for tag in nemotron-3-super qwen3.8-27b qwen3-30b; do
  cell "$tag" offm-s 100 --no-think
  cell "$tag" onm-s  25
done
$SERVE nemotron-lightning >> "$LOG" 2>&1 || true
echo "=== stage2c done $(date -u +%H:%M) ===" >> "$LOG"
