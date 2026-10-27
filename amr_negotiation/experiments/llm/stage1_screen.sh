#!/usr/bin/env bash
# Stage 1 model screen: every roster model x llm_med_plans x n=100 x --think 0.
# Waits for any running experiments/llm/llm_negotiation.py to finish before starting (Stage 0
# holds the GPU). Logs to data/raw/llm/stage1.log.
set -u
cd "$(dirname "$0")/../.."
PY=./.venv/bin/python
SERVE="$HOME/.nemoclaw/local-models/serve.sh"
LOG=data/raw/llm/stage1.log
mkdir -p data/raw/llm

while pgrep -f "llm_negotiation.py --tag" > /dev/null; do sleep 20; done

run() { # tag model_key_or_url served_model extra_args...
  local tag=$1 key=$2 model=$3; shift 3
  echo "=== $tag ($model) $(date -u +%H:%M) ===" >> "$LOG"
  if [ "$key" != "hosted" ]; then
    $SERVE "$key" >> "$LOG" 2>&1 || { echo "$tag SERVE FAILED" >> "$LOG"; return 1; }
  fi
  $PY experiments/llm/llm_negotiation.py --tag "$tag" --model "$model" \
      --base-url http://localhost:8000/v1 --n 100 --variants llm_med_plans \
      --think 0 --workers 4 --max-tokens 4096 "$@" >> "$LOG" 2>&1 \
    && echo "$tag OK" >> "$LOG" || echo "$tag FAILED" >> "$LOG"
}

run nemotron-nano nemotron-nano nvidia-nemotron-3-nano-30b-a3b-nvfp4
run nemotron-lightning nemotron-lightning nvidia-nemotron-3.5-lightning-30b-a3b-nvfp4
run nemotron-super-49b nemotron-super-49b llama-3-3-nemotron-super-49b-v1-5-nvfp4
run qwen3-30b qwen3-30b qwen3-30b-a3b-nvfp4
run gemma4-26b gemma4-26b gemma4-26b-a4b-nvfp4
run qwen3.8-27b qwen3.8-27b qwen3.8-27b-nvfp4
run nemotron-omni nemotron-omni nemotron-3-nano-omni-30b-a3b-reasoning-nvfp4
run nemotron-vl-12b nemotron-vl-12b nvidia-nemotron-nano-12b-v2-vl-nvfp4-qad
run muse-glimmer muse-glimmer muse-glimmer

# hosted reference — no container swap needed
echo "=== nemotron-3-super hosted $(date -u +%H:%M) ===" >> "$LOG"
AMRNEG_LLM_URL=https://integrate.api.nvidia.com/v1 \
AMRNEG_LLM_MODEL=nvidia/nemotron-3-super-120b-a12b \
AMRNEG_LLM_API_KEY="$NVIDIA_INFERENCE_API_KEY" \
$PY experiments/llm/llm_negotiation.py --tag nemotron-3-super \
    --model nvidia/nemotron-3-super-120b-a12b \
    --base-url https://integrate.api.nvidia.com/v1 --n 100 --variants llm_med_plans \
    --think 0 --workers 4 --max-tokens 4096 >> "$LOG" 2>&1 \
  && echo "nemotron-3-super OK" >> "$LOG" || echo "nemotron-3-super FAILED" >> "$LOG"

# leave lightning serving when done
$SERVE nemotron-lightning >> "$LOG" 2>&1 || true
echo "=== stage1 done $(date -u +%H:%M) ===" >> "$LOG"
