#!/usr/bin/env bash
# Stage 2b config matrix on the top-3 Stage-1 models.
# Per model: mode x info (all 4 variants) x think_time {0, measured} x thinking {off,on}
#   off cells at n=100 (main), on cells at n=25 (diagnostic, traces saved in llm_answers).
# Re-derives top-3 from screen rows.jsonl (excess, asc). Logs to stage2b.log.
set -u
cd "$(dirname "$0")/../.."
PY=./.venv/bin/python
SERVE="$HOME/.nemoclaw/local-models/serve.sh"
LOG=data/raw/llm/stage2b.log

declare -A KEY MODEL
KEY[nemotron-nano]=nemotron-nano;            MODEL[nemotron-nano]=nvidia-nemotron-3-nano-30b-a3b-nvfp4
KEY[nemotron-lightning]=nemotron-lightning;  MODEL[nemotron-lightning]=nvidia-nemotron-3.5-lightning-30b-a3b-nvfp4
KEY[nemotron-super-49b]=nemotron-super-49b;  MODEL[nemotron-super-49b]=llama-3-3-nemotron-super-49b-v1-5-nvfp4
KEY[qwen3-30b]=qwen3-30b;                    MODEL[qwen3-30b]=qwen3-30b-a3b-nvfp4
KEY[qwen3.8-27b]=qwen3.8-27b;                MODEL[qwen3.8-27b]=qwen3.8-27b-nvfp4
KEY[gemma4-26b]=gemma4-26b;                  MODEL[gemma4-26b]=gemma4-26b-a4b-nvfp4
KEY[nemotron-omni]=nemotron-omni;            MODEL[nemotron-omni]=nemotron-3-nano-omni-30b-a3b-reasoning-nvfp4
KEY[nemotron-vl-12b]=nemotron-vl-12b;        MODEL[nemotron-vl-12b]=nvidia-nemotron-nano-12b-v2-vl-nvfp4-qad
KEY[muse-glimmer]=muse-glimmer;              MODEL[muse-glimmer]=muse-glimmer
KEY[nemotron-3-super]=hosted;                MODEL[nemotron-3-super]=nvidia/nemotron-3-super-120b-a12b

TOP3=$(for f in data/raw/llm/*/rows.jsonl; do tag=$(basename "$(dirname "$f")");
  case "$tag" in *-c[0-9]|*-off*|*-on*|*smoke*|*-vlm) continue;; esac
  ex=$($PY -c "
import json
rs=[json.loads(l) for l in open('$f')]
v=[r['excess'] for r in rs if r['label']=='llm_med_plans' and r['success']]
print(sum(v)/len(v) if v else 999)" 2>/dev/null)
  [ -n "$ex" ] && echo "$ex $tag"; done | sort -n | awk '{print $2}' | head -3)
echo "TOP3: $TOP3 $(date -u +%H:%M)" >> "$LOG"

cell() { # tag label n think extra...
  local tag=$1 label=$2 n=$3 think=$4; shift 4
  echo "=== ${tag}-${label} $(date -u +%H:%M) ===" >> "$LOG"
  if [ "${KEY[$tag]}" != "hosted" ]; then
    $SERVE "${KEY[$tag]}" >> "$LOG" 2>&1 || { echo "$tag SERVE FAILED" >> "$LOG"; return 1; }
    $PY experiments/llm/llm_negotiation.py --tag "${tag}-${label}" --model "${MODEL[$tag]}" \
        --base-url http://localhost:8000/v1 --n "$n" --think "$think" \
        --workers 4 --max-tokens 4096 "$@" >> "$LOG" 2>&1 \
      && echo "${tag}-${label} OK" >> "$LOG" || echo "${tag}-${label} FAILED" >> "$LOG"
  else
    AMRNEG_LLM_API_KEY="$NVIDIA_INFERENCE_API_KEY" $PY experiments/llm/llm_negotiation.py \
        --tag "${tag}-${label}" --model "${MODEL[$tag]}" \
        --base-url https://integrate.api.nvidia.com/v1 --n "$n" --think "$think" \
        --workers 4 --max-tokens 4096 "$@" >> "$LOG" 2>&1 \
      && echo "${tag}-${label} OK" >> "$LOG" || echo "${tag}-${label} FAILED" >> "$LOG"
  fi
}

for tag in $TOP3; do
  cell "$tag" off0  100 0        --no-think
  cell "$tag" offm  100 measured --no-think
  cell "$tag" on0   25  0
  cell "$tag" onm   25  measured
done
echo "=== stage2b done $(date -u +%H:%M) ===" >> "$LOG"
