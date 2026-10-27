#!/usr/bin/env bash
# Runs the revised pipeline: stage2b matrix (thinking on/off arms) then stage4 VLM.
cd "$(dirname "$0")/../.."
bash experiments/llm/stage2b_matrix.sh
bash experiments/llm/stage4_vlm.sh
