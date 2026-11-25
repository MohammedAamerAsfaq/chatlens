#!/bin/sh
set -eu
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 CANDIDATES_JSONL NEW_RUN_DIRECTORY" >&2
  exit 2
fi
candidates=$1
run=$2
model=${TRADING_MODEL:-mlx-community/Qwen3-4B-Instruct-2507-4bit}
max_tokens=${TRADING_MAX_SEQ_LENGTH:-2048}
if [ -e "$run" ]; then
  echo "Run directory already exists: $run" >&2
  exit 1
fi
mkdir -p "$run"
python3 "$(dirname "$0")/filter_mlx_data.py" --input "$candidates" --output-dir "$run/data" --model "$model" --max-seq-length "$max_tokens"
python3 -m mlx_lm.lora --model "$model" --train --data "$run/data" --adapter-path "$run/adapters" --iters "${TRADING_ITERS:-300}" --batch-size 1 --max-seq-length "$max_tokens" --grad-checkpoint --mask-prompt
