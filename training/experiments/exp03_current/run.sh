#!/bin/bash
set -euo pipefail
EXP_DIR="$(cd "$(dirname "$0")" && pwd)"
TRAINING_DIR="$(dirname "$EXP_DIR")"
DATA="$TRAINING_DIR/data/verified_splits.jsonl"
CHECKPOINT="$EXP_DIR/model.pt"
PYTHON="/home/ec2-user/miniconda3/envs/cse579a1/bin/python3"

echo "=== $(basename $EXP_DIR) — train ==="
"$PYTHON" "$EXP_DIR/train.py" \
  --data "$DATA" --out "$CHECKPOINT" --epochs 40 --lr 1e-3 \
  2>&1 | tee "$EXP_DIR/train.log"

echo ""
echo "=== $(basename $EXP_DIR) — benchmark ==="
"$PYTHON" "$TRAINING_DIR/benchmark.py" \
  --model "$CHECKPOINT" \
  --serve "$EXP_DIR/serve.py" \
  --n 3 --workers 8 --timeout 60 --seed 42 \
  2>&1 | tee "$EXP_DIR/benchmark.log"
