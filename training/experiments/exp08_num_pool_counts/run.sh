#!/usr/bin/env bash
set -euo pipefail

EXP_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$EXP_DIR/../../.." && pwd)"
ID="$(basename "$EXP_DIR")"

ONLY="${ONLY:-$ID}" exec "$ROOT/training/experiments/run_timing_matrix.sh"
