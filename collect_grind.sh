#!/usr/bin/env bash
set -euo pipefail

# collect_grind.sh
# Thin wrapper around training/collect.py.
#
# Usage:
#   ./collect_grind.sh [training/collect.py args...]
#
# Defaults:
#   --project  GrindExtraction
#   --out      training/data/collected.jsonl
#
# Any explicit flags you pass override these defaults because they come later
# on the command line.

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$SCRIPT_DIR
COLLECT_PY="$REPO_ROOT/training/collect.py"
GRIND_ROOT="$REPO_ROOT/GrindExtraction"
MATHLIB_OLEAN="$GRIND_ROOT/.lake/packages/mathlib/.lake/build/lib/lean/Mathlib.olean"

if [[ ! -f "$COLLECT_PY" ]]; then
  echo "collect.py not found at $COLLECT_PY" >&2
  exit 1
fi

if [[ ! -f "$MATHLIB_OLEAN" ]]; then
  echo "Building Mathlib for GrindExtraction..." >&2
  (cd "$GRIND_ROOT" && lake build Mathlib)
fi

exec python3 "$COLLECT_PY" \
  --project "$GRIND_ROOT" \
  --out "$REPO_ROOT/training/data/collected.jsonl" \
  "$@"
