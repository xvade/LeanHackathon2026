#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PYTHON="${PYTHON:-python3}"
BENCHMARK="${BENCHMARK:-$ROOT/training/data/split_active_benchmark.jsonl}"
BENCHMARK_TRACES="${BENCHMARK_TRACES:-$ROOT/training/data/split_active_benchmark_traces.jsonl}"
OUT_DIR="${OUT_DIR:-$ROOT/training/data/clean}"

if [[ ! -f "$BENCHMARK_TRACES" || "$BENCHMARK" -nt "$BENCHMARK_TRACES" ]]; then
  "$PYTHON" "$ROOT/training/collect_benchmark_traces.py" \
    --benchmark "$BENCHMARK" \
    --out "$BENCHMARK_TRACES"
fi

"$PYTHON" "$ROOT/training/filter_training_data.py" \
  --benchmark "$BENCHMARK" \
  --benchmark-traces "$BENCHMARK_TRACES" \
  --out-dir "$OUT_DIR"
