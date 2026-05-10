#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROJECT="$ROOT/NeuralTactic"

GRIND_FILE="${GRIND_FILE:-$SCRIPT_DIR/split_active_timing_grind.lean}"
NEURAL_FILE="${NEURAL_FILE:-$SCRIPT_DIR/split_active_timing_neural_grind.lean}"
REPEAT="${REPEAT:-1}"
MODE="${1:-both}"
OUT="${OUT:-$SCRIPT_DIR/timing_$(date -u +%Y%m%d_%H%M%S).log}"
TIMEOUT="${TIMEOUT:-0}"

case "$MODE" in
  grind|neural|both) ;;
  *)
    echo "usage: $0 [grind|neural|both]" >&2
    exit 2
    ;;
esac

if ! command -v /usr/bin/time >/dev/null 2>&1; then
  echo "/usr/bin/time is required" >&2
  exit 2
fi

: > "$OUT"

run_file() {
  local label="$1"
  local file="$2"

  if [[ ! -f "$file" ]]; then
    echo "missing benchmark file: $file" >&2
    exit 2
  fi

  for ((i = 1; i <= REPEAT; i++)); do
    echo "[$label $i/$REPEAT] $file"
    (
      cd "$PROJECT"
      if [[ "$TIMEOUT" == "0" ]]; then
        /usr/bin/time \
          -f "$label run=$i real_s=%e user_s=%U sys_s=%S maxrss_kb=%M" \
          -o "$OUT" \
          -a \
          lake env lean "$file"
      else
        /usr/bin/time \
          -f "$label run=$i real_s=%e user_s=%U sys_s=%S maxrss_kb=%M" \
          -o "$OUT" \
          -a \
          timeout "$TIMEOUT" lake env lean "$file"
      fi
    )
    echo "$label run=$i status=ok" >> "$OUT"
  done
}

echo "Lean batch timing"
echo "  mode        : $MODE"
echo "  repeat      : $REPEAT"
echo "  timeout     : $TIMEOUT"
echo "  grind file  : $GRIND_FILE"
echo "  neural file : $NEURAL_FILE"
echo "  log         : $OUT"
echo "  GRIND_NO_MODEL=${GRIND_NO_MODEL:-}"
echo "  GRIND_MODEL=${GRIND_MODEL:-}"
echo "  GRIND_SERVE=${GRIND_SERVE:-}"
echo "  GRIND_SERVE_NATIVE=${GRIND_SERVE_NATIVE:-}"
echo "  GRIND_MARGIN_MILLI=${GRIND_MARGIN_MILLI:-}"
echo "  GRIND_INCLUDE_EXPR_TEXT=${GRIND_INCLUDE_EXPR_TEXT:-}"
echo

if [[ "$MODE" == "grind" || "$MODE" == "both" ]]; then
  run_file grind "$GRIND_FILE"
fi

if [[ "$MODE" == "neural" || "$MODE" == "both" ]]; then
  run_file neural "$NEURAL_FILE"
fi

echo
echo "Timing log:"
cat "$OUT"
