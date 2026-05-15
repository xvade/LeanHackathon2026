#!/usr/bin/env bash
# Branch-cost pipeline — laptop orchestrator.
#
# End-to-end: sample → collect → aggregate-not-needed-for-one-shard → analyse.
# Equivalent to running the four scripts in sequence; this just stamps a
# fresh output directory and wires the paths.
#
# Override env vars to customise:
#   PER_STRATUM   decisions per pool-size stratum (default 20)
#   SEED          sampling seed (default 0)
#   TIMEOUT       per-Lean-run timeout in seconds (default 90)
#   PYTHON        python interpreter
#   OUT_DIR       output directory (default training/data/run_<timestamp>)
#   TRACE         input trace JSONL (default: committed benchmark trace)
#   BENCHMARK     input benchmark .lean (default: committed benchmark file)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python}"
PER_STRATUM="${PER_STRATUM:-20}"
SEED="${SEED:-0}"
TIMEOUT="${TIMEOUT:-90}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${OUT_DIR:-$ROOT/training/data/run_$STAMP}"

TRACE="${TRACE:-$ROOT/training/data/clean/split_active_benchmark_traces_normalized.jsonl}"
BENCHMARK="${BENCHMARK:-$ROOT/training/benchmarks/split_active_timing_neural_grind.lean}"

PLAN="$OUT_DIR/sample_plan.jsonl"
COSTS="$OUT_DIR/branch_costs.jsonl"
LOGS="$OUT_DIR/logs"
REPORT="$OUT_DIR/report.md"
DECISIONS="$OUT_DIR/per_decision.jsonl"

mkdir -p "$OUT_DIR"

echo "[pipeline] writing into $OUT_DIR" >&2

echo "[pipeline] step 1/3 sampling decisions" >&2
"$PYTHON" "$ROOT/training/make_plan_benchmark.py" \
  --trace-jsonl "$TRACE" \
  --out "$PLAN" \
  --per-stratum "$PER_STRATUM" \
  --seed "$SEED"

echo "[pipeline] step 2/3 collecting branch costs (timeout=${TIMEOUT}s)" >&2
"$PYTHON" "$ROOT/training/collect_branch_costs.py" \
  --sample-plan "$PLAN" \
  --benchmark-file "$BENCHMARK" \
  --out "$COSTS" \
  --log-dir "$LOGS" \
  --python "$PYTHON" \
  --timeout "$TIMEOUT"

echo "[pipeline] step 3/3 analysing" >&2
"$PYTHON" "$ROOT/training/analyze_costs.py" \
  --in "$COSTS" \
  --out "$REPORT" \
  --decisions-out "$DECISIONS"

echo "[pipeline] done: $REPORT" >&2
