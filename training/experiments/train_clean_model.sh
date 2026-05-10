#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 EXPERIMENT_ID [extra train.py args...]" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ID="$1"
shift

EXP_DIR="$SCRIPT_DIR/$ID"
DATA="${DATA:-$ROOT/training/data/clean/train_splits.jsonl}"
OUT="${OUT:-$EXP_DIR/model_clean.pt}"
LOG="${LOG:-$EXP_DIR/train_clean.log}"
EPOCHS="${EPOCHS:-40}"
LR="${LR:-1e-3}"

DEFAULT_PYTHON="/home/ec2-user/miniconda3/envs/leanhack/bin/python3"
if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_BIN="$PYTHON"
elif [[ -x "$DEFAULT_PYTHON" ]]; then
  PYTHON_BIN="$DEFAULT_PYTHON"
else
  PYTHON_BIN="$(command -v python3)"
fi

if [[ ! -d "$EXP_DIR" ]]; then
  echo "unknown experiment: $ID" >&2
  exit 2
fi
if [[ ! -f "$EXP_DIR/train.py" ]]; then
  echo "missing train.py: $EXP_DIR/train.py" >&2
  exit 2
fi
if [[ ! -f "$DATA" ]]; then
  echo "missing clean data: $DATA" >&2
  echo "run: bash training/make_clean_training_data.sh" >&2
  exit 2
fi

echo "experiment : $ID"
echo "data       : $DATA"
echo "out        : $OUT"
echo "log        : $LOG"
echo "python     : $PYTHON_BIN"

"$PYTHON_BIN" "$EXP_DIR/train.py" \
  --data "$DATA" \
  --out "$OUT" \
  --epochs "$EPOCHS" \
  --lr "$LR" \
  "$@" | tee "$LOG"
