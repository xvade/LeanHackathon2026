#!/usr/bin/env bash
set -euo pipefail

# collect_grind.sh
# Thin wrapper around training/collect.py.
#
# Usage:
#   ./collect_grind.sh [training/collect.py args...]
#
# Defaults:
#   --project  NeuralTactic
#   --out      training/data/collected.jsonl
#
# Any explicit flags you pass override these defaults because they come later
# on the command line.

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$SCRIPT_DIR
COLLECT_PY="$REPO_ROOT/training/collect.py"

if [[ ! -f "$COLLECT_PY" ]]; then
  echo "collect.py not found at $COLLECT_PY" >&2
  exit 1
fi

exec python3 "$COLLECT_PY" \
  --project "$REPO_ROOT/NeuralTactic" \
  --out "$REPO_ROOT/training/data/collected.jsonl" \
  "$@"
