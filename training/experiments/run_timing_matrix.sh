#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TIMING_RUNNER="$ROOT/training/benchmarks/run_split_active_timing.sh"
MATRIX="${MATRIX:-$SCRIPT_DIR/experiments.tsv}"
STAMP="${STAMP:-$(date -u +%Y%m%d_%H%M%S)}"
RESULT_DIR="${RESULT_DIR:-$SCRIPT_DIR/results/$STAMP}"
REPEAT="${REPEAT:-1}"
TIMEOUT="${TIMEOUT:-180}"
ONLY="${ONLY:-}"
RUN_DISABLED="${RUN_DISABLED:-0}"
DECISION_LOG="${DECISION_LOG:-0}"

DEFAULT_PYTHON="/home/ec2-user/miniconda3/envs/leanhack/bin/python3"
if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_BIN="$PYTHON"
elif [[ -x "$DEFAULT_PYTHON" ]]; then
  PYTHON_BIN="$DEFAULT_PYTHON"
else
  PYTHON_BIN="$(command -v python3)"
fi
CXX="${CXX:-c++}"

mkdir -p "$RESULT_DIR"

SUMMARY="$RESULT_DIR/summary.tsv"
BASELINE_LOG="$RESULT_DIR/grind.timing.log"

avg_real_s() {
  awk '
    {
      for (i = 1; i <= NF; i++) {
        if ($i ~ /^real_s=/) {
          split($i, a, "=")
          sum += a[2]
          n += 1
        }
      }
    }
    END {
      if (n > 0) {
        printf "%.3f", sum / n
      } else {
        printf "NA"
      }
    }
  ' "$1"
}

pct_delta() {
  local baseline="$1"
  local actual="$2"
  awk -v b="$baseline" -v a="$actual" 'BEGIN {
    if (b == "NA" || a == "NA" || b == 0) {
      printf "NA"
    } else {
      printf "%+.2f", (b - a) / b * 100.0
    }
  }'
}

matches_only() {
  local id="$1"
  if [[ -z "$ONLY" ]]; then
    return 0
  fi
  case ",$ONLY," in
    *",$id,"*) return 0 ;;
    *) return 1 ;;
  esac
}

abs_path() {
  local path="$1"
  if [[ "$path" == "-" ]]; then
    printf "%s" "-"
  elif [[ "$path" = /* ]]; then
    printf "%s" "$path"
  else
    printf "%s/%s" "$ROOT" "$path"
  fi
}

build_native_server() {
  local native_model="$1"
  if [[ "$native_model" != "exp08" ]]; then
    echo "unknown native model: $native_model" >&2
    return 1
  fi

  local src="$ROOT/NeuralTactic/native/model.cpp"
  local out="$SCRIPT_DIR/exp08_num_pool_counts/native_serve"
  if [[ ! -x "$out" || "$src" -nt "$out" ]]; then
    echo "building native server: $out" >&2
    "$CXX" -DNEURAL_GRIND_STANDALONE -O3 -std=c++17 "$src" -o "$out"
  fi
  printf "%s" "$out"
}

write_manifest() {
  {
    echo "timestamp=$STAMP"
    echo "root=$ROOT"
    echo "matrix=$MATRIX"
    echo "repeat=$REPEAT"
    echo "timeout=$TIMEOUT"
    echo "only=$ONLY"
    echo "run_disabled=$RUN_DISABLED"
    echo "decision_log=$DECISION_LOG"
    echo "python=$PYTHON_BIN"
    echo "timing_runner=$TIMING_RUNNER"
  } > "$RESULT_DIR/manifest.txt"
}

run_grind_baseline() {
  echo "=== grind baseline ==="
  OUT="$BASELINE_LOG" REPEAT="$REPEAT" TIMEOUT="$TIMEOUT" bash "$TIMING_RUNNER" grind \
    > "$RESULT_DIR/grind.stdout.log" 2>&1
  cat "$BASELINE_LOG"
}

run_experiment() {
  local id="$1"
  local no_model="$2"
  local model="$3"
  local serve="$4"
  local margin="$5"
  local include_expr="$6"
  local notes="$7"

  local log="$RESULT_DIR/${id}.timing.log"
  local stdout_log="$RESULT_DIR/${id}.stdout.log"
  local decision_log="$RESULT_DIR/${id}.decisions.jsonl"
  local model_abs
  local serve_abs
  model_abs="$(abs_path "$model")"
  serve_abs="$(abs_path "$serve")"

  local decision_env=()
  if [[ "$DECISION_LOG" == "1" ]]; then
    rm -f "$decision_log"
    decision_env=(GRIND_DECISION_LOG="$decision_log")
  fi

  echo "=== $id ==="
  echo "$notes"

  if [[ "$no_model" == "1" ]]; then
    if env -u GRIND_MODEL -u GRIND_SERVE -u GRIND_PYTHON \
      OUT="$log" REPEAT="$REPEAT" TIMEOUT="$TIMEOUT" GRIND_NO_MODEL=1 \
      GRIND_MARGIN_MILLI="$margin" \
      "${decision_env[@]}" \
      bash "$TIMING_RUNNER" neural > "$stdout_log" 2>&1; then
      echo "ok"
      return 0
    fi
    echo "failed"
    return 1
  fi

  if [[ ! -f "$model_abs" ]]; then
    echo "missing model: $model_abs"
    return 1
  fi
  if [[ ! -f "$serve_abs" ]]; then
    if [[ "$serve" != native:* ]]; then
      echo "missing serve script: $serve_abs"
      return 1
    fi
  fi

  local expr_env=()
  if [[ "$include_expr" == "1" ]]; then
    expr_env=(GRIND_INCLUDE_EXPR_TEXT=1)
  fi

  if [[ "$serve" == native:* ]]; then
    local native_model="${serve#native:}"
    local native_server
    native_server="$(build_native_server "$native_model")" || return 1
    if [[ ! -f "$model_abs" ]]; then
      echo "missing native weights: $model_abs"
      return 1
    fi
    if env -u GRIND_NO_MODEL -u GRIND_MODEL -u GRIND_SERVE -u GRIND_PYTHON \
      OUT="$log" REPEAT="$REPEAT" TIMEOUT="$TIMEOUT" \
      GRIND_MODEL="$model_abs" \
      GRIND_SERVE="$native_server" \
      GRIND_SERVE_NATIVE=1 \
      GRIND_MARGIN_MILLI="$margin" \
      "${expr_env[@]}" \
      "${decision_env[@]}" \
      bash "$TIMING_RUNNER" neural > "$stdout_log" 2>&1; then
      echo "ok"
      return 0
    fi

    echo "failed"
    return 1
  fi

  if env -u GRIND_NO_MODEL -u GRIND_NATIVE_MODEL -u GRIND_NATIVE_WEIGHTS -u GRIND_SERVE_NATIVE \
    OUT="$log" REPEAT="$REPEAT" TIMEOUT="$TIMEOUT" \
    GRIND_MODEL="$model_abs" \
    GRIND_SERVE="$serve_abs" \
    GRIND_PYTHON="$PYTHON_BIN" \
    GRIND_MARGIN_MILLI="$margin" \
    "${expr_env[@]}" \
    "${decision_env[@]}" \
    bash "$TIMING_RUNNER" neural > "$stdout_log" 2>&1; then
    echo "ok"
    return 0
  fi

  echo "failed"
  return 1
}

main() {
  if [[ ! -f "$MATRIX" ]]; then
    echo "missing matrix: $MATRIX" >&2
    exit 2
  fi
  if [[ ! -x "$TIMING_RUNNER" ]]; then
    echo "missing timing runner: $TIMING_RUNNER" >&2
    exit 2
  fi

  write_manifest
  run_grind_baseline
  local baseline
  baseline="$(avg_real_s "$BASELINE_LOG")"

  printf "id\tstatus\truns\tavg_real_s\tvs_grind_pct\tmargin_milli\tinclude_expr_text\tmodel\tserve\tnotes\tlog\tdecision_log\n" \
    > "$SUMMARY"

  while IFS='|' read -r id enabled no_model model serve margin include_expr notes; do
    [[ -z "${id:-}" ]] && continue
    [[ "$id" == \#* ]] && continue
    if [[ "$enabled" != "1" && "$RUN_DISABLED" != "1" ]]; then
      continue
    fi
    if ! matches_only "$id"; then
      continue
    fi

    status="ok"
    if ! run_experiment "$id" "$no_model" "$model" "$serve" "$margin" "$include_expr" "$notes"; then
      status="fail"
    fi

    log="$RESULT_DIR/${id}.timing.log"
    if [[ -f "$log" ]]; then
      avg="$(avg_real_s "$log")"
    else
      avg="NA"
    fi
    decision_log="$RESULT_DIR/${id}.decisions.jsonl"
    if [[ "$DECISION_LOG" != "1" || ! -f "$decision_log" ]]; then
      decision_log="-"
    fi
    delta="$(pct_delta "$baseline" "$avg")"
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
      "$id" "$status" "$REPEAT" "$avg" "$delta" "$margin" "$include_expr" \
      "$model" "$serve" "$notes" "$log" "$decision_log" >> "$SUMMARY"
  done < "$MATRIX"

  echo
  echo "Summary: $SUMMARY"
  column -t -s $'\t' "$SUMMARY" || cat "$SUMMARY"
}

main "$@"
