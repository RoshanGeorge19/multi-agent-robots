#!/usr/bin/env bash
# Stage 2 config matrix: mode x info x constrain x think on the top-3 Stage-1 models.
# Auto-selects top 3 from data/tables/llm/llm_<tag>.md 'llm_med_plans' excess column.
# Waits for experiments/llm/stage1_screen.sh to finish. Logs to stage2.log.
set -u
cd "$(dirname "$0")/../.."
PY=./.venv/bin/python
SERVE="$HOME/.nemoclaw/local-models/serve.sh"
LOG=data/raw/llm/stage2.log

while pgrep -f "stage1_screen.sh" > /dev/null; do sleep 60; done
while pgrep -f "llm_negotiation.py --tag" > /dev/null; do sleep 20; done

# Re-screen the two models whose Stage-1 serve failed before the args were fixed.
for kv in "nemotron-super-49b llama-3-3-nemotron-super-49b-v1-5-nvfp4" "qwen3-30b qwen3-30b-a3b-nvfp4"; do
  set -- $kv; tag=$1; mdl=$2
  echo "=== rescreen $tag $(date -u +%H:%M) ===" >> "$LOG"
  $SERVE "$tag" >> "$LOG" 2>&1 || { echo "$tag SERVE FAILED" >> "$LOG"; continue; }
  $PY experiments/llm/llm_negotiation.py --tag "$tag" --model "$mdl" \
      --base-url http://localhost:8000/v1 --n 100 --variants llm_med_plans \
      --think 0 --workers 4 --max-tokens 4096 >> "$LOG" 2>&1 \
    && echo "$tag rescreen OK" >> "$LOG" || echo "$tag rescreen FAILED" >> "$LOG"
done

# tag -> serve key mapping (hosteds have none)
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

TOP3=$(for f in data/tables/llm/llm_*.md; do tag=$(basename "$f" .md); tag=${tag#llm_};
  [ -f "data/raw/llm/$tag/rows.jsonl" ] || continue
  grep -q stage1 < /dev/null; # noop
  ex=$(python3 -c "
import json,sys
rs=[json.loads(l) for l in open('data/raw/llm/$tag/rows.jsonl') if '\"llm_med_plans\"' in l]
v=[r['excess'] for r in rs if r['label']=='llm_med_plans' and r['success']]
print(sum(v)/len(v) if v else 999)" 2>/dev/null)
  echo "$ex $tag"; done | sort -n | awk '{print $2}' | grep -v "smoke" | head -3)
echo "TOP3: $TOP3" >> "$LOG"

for tag in $TOP3; do
  for cfg in "c1 --think 0" "c2 --think 0 --no-constrain" "c3 --think measured" "c4 --think measured --no-constrain"; do
    set -- $cfg; label=$1; shift
    echo "=== ${tag}-${label} $(date -u +%H:%M) ===" >> "$LOG"
    if [ "${KEY[$tag]}" != "hosted" ]; then
      $SERVE "${KEY[$tag]}" >> "$LOG" 2>&1 || { echo "$tag SERVE FAILED" >> "$LOG"; continue; }
      BASE=http://localhost:8000/v1; KEYARG=""
    else
      BASE=https://integrate.api.nvidia.com/v1
      KEYARG="x"
    fi
    if [ -n "$KEYARG" ]; then
      AMRNEG_LLM_API_KEY="$NVIDIA_INFERENCE_API_KEY" $PY experiments/llm/llm_negotiation.py \
        --tag "${tag}-${label}" --model "${MODEL[$tag]}" --base-url "$BASE" \
        --n 100 --workers 4 --max-tokens 4096 "$@" >> "$LOG" 2>&1 \
        && echo "${tag}-${label} OK" >> "$LOG" || echo "${tag}-${label} FAILED" >> "$LOG"
    else
      $PY experiments/llm/llm_negotiation.py --tag "${tag}-${label}" --model "${MODEL[$tag]}" \
        --base-url "$BASE" --n 100 --workers 4 --max-tokens 4096 "$@" >> "$LOG" 2>&1 \
        && echo "${tag}-${label} OK" >> "$LOG" || echo "${tag}-${label} FAILED" >> "$LOG"
    fi
  done
done
echo "=== stage2 done $(date -u +%H:%M) ===" >> "$LOG"
