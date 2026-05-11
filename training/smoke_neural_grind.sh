#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
CXX="${CXX:-c++}"
TMPDIR="${TMPDIR:-/tmp}/neural_grind_smoke_$$"

cleanup() {
  rm -rf "$TMPDIR"
}
trap cleanup EXIT

mkdir -p "$TMPDIR"

DATA="$TMPDIR/branching.jsonl"
MODEL_PT="$TMPDIR/model.pt"
MODEL_NATIVE="$TMPDIR/model.native.bin"
SERVE="$TMPDIR/native_serve"
QUERY="$TMPDIR/query.jsonl"
LEAN_FILE="$TMPDIR/Smoke.lean"
DECISIONS="$TMPDIR/decisions.jsonl"

cat > "$DATA" <<'JSON'
{"outcome":"success","steps":[{"goalFeatures":{"splitDepth":0,"assertedCount":2,"ematchRounds":0,"splitTraceLen":0,"numCandidates":2},"candidates":[{"anchor":111,"exprText":"","numCases":2,"isRec":false,"source":"input","generation":1,"tryPostpone":true,"variant":"default","isGrindChoice":false},{"anchor":222,"exprText":"","numCases":1,"isRec":false,"source":"input","generation":0,"tryPostpone":false,"variant":"default","isGrindChoice":true}],"chosenAnchor":222,"grindState":[]}]}
JSON

"$PYTHON" "$ROOT/training/experiments/exp09_heuristics/train.py" \
  --data "$DATA" \
  --out "$MODEL_PT" \
  --epochs 80 \
  --lr 0.01 \
  --batch-size 1 \
  --hidden-dim 32

"$PYTHON" "$ROOT/training/export_exp09_native.py" \
  --model "$MODEL_PT" \
  --out "$MODEL_NATIVE"

"$CXX" -DNEURAL_GRIND_STANDALONE -O3 -std=c++17 \
  "$ROOT/NeuralTactic/native/model.cpp" \
  -o "$SERVE"

cat > "$QUERY" <<'JSON'
{"goalFeatures":{"splitDepth":0,"assertedCount":2,"ematchRounds":0,"splitTraceLen":0,"numCandidates":2},"candidates":[{"anchor":111,"exprText":"","numCases":2,"isRec":false,"source":"input","generation":1,"tryPostpone":true,"variant":"default","isGrindChoice":false},{"anchor":222,"exprText":"","numCases":1,"isRec":false,"source":"input","generation":0,"tryPostpone":false,"variant":"default","isGrindChoice":true}],"statePP":[],"grindState":[]}
JSON

choice="$("$SERVE" --model "$MODEL_NATIVE" < "$QUERY" | head -n 1 | awk '{print $1}')"
if [[ "$choice" != "222" ]]; then
  echo "native smoke expected anchor 222, got ${choice:-<empty>}" >&2
  exit 1
fi

cat > "$LEAN_FILE" <<'LEAN'
import NeuralTactic

example (p q : Prop) [Decidable p] [Decidable q] : (if p then q else q) = q := by
  neural_grind
LEAN

(
  cd "$ROOT/NeuralTactic"
  GRIND_MODEL="$MODEL_NATIVE" \
  GRIND_SERVE="$SERVE" \
  GRIND_SERVE_NATIVE=1 \
  GRIND_MARGIN_MILLI=0 \
  GRIND_DECISION_LOG="$DECISIONS" \
  lake env lean "$LEAN_FILE"
)

if ! grep -q '"action":"model"' "$DECISIONS"; then
  echo "neural_grind smoke did not record a model action" >&2
  echo "decision log: $DECISIONS" >&2
  sed -n '1,20p' "$DECISIONS" >&2 || true
  exit 1
fi

echo "neural_grind smoke passed"
