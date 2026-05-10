#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROJECT="$ROOT/NeuralTactic"

GRIND_FILE="${GRIND_FILE:-$SCRIPT_DIR/split_active_timing_grind.lean}"
NEURAL_FILE="${NEURAL_FILE:-$SCRIPT_DIR/split_active_timing_neural_grind.lean}"
STAMP="${STAMP:-$(date -u +%Y%m%d_%H%M%S)}"
RESULT_DIR="${RESULT_DIR:-$SCRIPT_DIR/case_results/$STAMP}"
TIMEOUT="${TIMEOUT:-90}"
JOBS="${JOBS:-4}"
MODE="${1:-neural}"
DECISION_LOG="${DECISION_LOG:-0}"
CASES="${CASES:-}"

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

mkdir -p "$RESULT_DIR"

abs_path() {
  local path="$1"
  if [[ -z "$path" ]]; then
    printf "%s" ""
  elif [[ "$path" = /* ]]; then
    printf "%s" "$path"
  else
    printf "%s/%s" "$ROOT" "$path"
  fi
}

normalize_runtime_paths() {
  if [[ -n "${GRIND_MODEL:-}" ]]; then
    export GRIND_MODEL="$(abs_path "$GRIND_MODEL")"
  fi
  if [[ -n "${GRIND_SERVE:-}" && "${GRIND_SERVE:-}" != native:* ]]; then
    export GRIND_SERVE="$(abs_path "$GRIND_SERVE")"
  fi
}

write_manifest() {
  {
    echo "timestamp=$STAMP"
    echo "root=$ROOT"
    echo "project=$PROJECT"
    echo "mode=$MODE"
    echo "timeout=$TIMEOUT"
    echo "jobs=$JOBS"
    echo "cases=$CASES"
    echo "decision_log=$DECISION_LOG"
    echo "grind_file=$GRIND_FILE"
    echo "neural_file=$NEURAL_FILE"
    echo "GRIND_NO_MODEL=${GRIND_NO_MODEL:-}"
    echo "GRIND_MODEL=${GRIND_MODEL:-}"
    echo "GRIND_SERVE=${GRIND_SERVE:-}"
    echo "GRIND_SERVE_NATIVE=${GRIND_SERVE_NATIVE:-}"
    echo "GRIND_MARGIN_MILLI=${GRIND_MARGIN_MILLI:-}"
    echo "GRIND_INCLUDE_EXPR_TEXT=${GRIND_INCLUDE_EXPR_TEXT:-}"
  } > "$RESULT_DIR/manifest.txt"
}

case_selected() {
  local case_id="$1"
  if [[ -z "$CASES" ]]; then
    return 0
  fi
  case ",$CASES," in
    *",$case_id,"*) return 0 ;;
    *) return 1 ;;
  esac
}

split_cases() {
  local src="$1"
  local dest="$2"
  rm -rf "$dest"
  mkdir -p "$dest"

  awk -v outdir="$dest" '
    BEGIN {
      header = ""
      in_case = 0
      file = ""
    }
    /^\/- benchmark [0-9][0-9][0-9]:/ {
      case_id = $3
      sub(":", "", case_id)
      file = outdir "/case_" case_id ".lean"
      printf "%s\n", header > file
      print $0 >> file
      in_case = 1
      next
    }
    {
      if (in_case) {
        print $0 >> file
      } else {
        header = header $0 "\n"
      }
    }
  ' "$src"
}

time_value() {
  local key="$1"
  local file="$2"
  awk -v k="$key" '
    {
      for (i = 1; i <= NF; i++) {
        if ($i ~ "^" k "=") {
          split($i, a, "=")
          print a[2]
          exit
        }
      }
    }
  ' "$file"
}

run_one() {
  local label="$1"
  local lean_file="$2"
  local case_id="$3"
  local row="$RESULT_DIR/rows/${label}_${case_id}.tsv"
  local stdout_log="$RESULT_DIR/${label}_${case_id}.stdout.log"
  local time_log="$RESULT_DIR/${label}_${case_id}.time.log"
  local decision_path="$RESULT_DIR/${label}_${case_id}.decisions.jsonl"
  local code

  mkdir -p "$RESULT_DIR/rows"
  rm -f "$stdout_log" "$time_log" "$decision_path"

  set +e
  (
    cd "$PROJECT"
    if [[ "$DECISION_LOG" == "1" ]]; then
      export GRIND_DECISION_LOG="$decision_path"
    fi
    if [[ "$TIMEOUT" == "0" ]]; then
      /usr/bin/time \
        -f "$label case=$case_id real_s=%e user_s=%U sys_s=%S maxrss_kb=%M" \
        -o "$time_log" \
        lake env lean "$lean_file" > "$stdout_log" 2>&1
    else
      /usr/bin/time \
        -f "$label case=$case_id real_s=%e user_s=%U sys_s=%S maxrss_kb=%M" \
        -o "$time_log" \
        timeout "$TIMEOUT" lake env lean "$lean_file" > "$stdout_log" 2>&1
    fi
  )
  code=$?
  set -e

  local status="fail"
  if [[ "$code" == "0" ]]; then
    status="ok"
  elif [[ "$code" == "124" ]]; then
    status="timeout"
  fi

  local real_s="NA"
  local user_s="NA"
  local sys_s="NA"
  local maxrss="NA"
  if [[ -f "$time_log" ]]; then
    real_s="$(time_value real_s "$time_log")"
    user_s="$(time_value user_s "$time_log")"
    sys_s="$(time_value sys_s "$time_log")"
    maxrss="$(time_value maxrss_kb "$time_log")"
  fi
  [[ -n "$real_s" ]] || real_s="NA"
  [[ -n "$user_s" ]] || user_s="NA"
  [[ -n "$sys_s" ]] || sys_s="NA"
  [[ -n "$maxrss" ]] || maxrss="NA"

  if [[ "$DECISION_LOG" != "1" || ! -f "$decision_path" ]]; then
    decision_path="-"
  fi

  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$label" "$case_id" "$status" "$code" "$real_s" "$user_s" "$sys_s" \
    "$maxrss" "$stdout_log" "$decision_path" > "$row"
}

run_mode() {
  local label="$1"
  local src="$2"
  local cases_dir="$RESULT_DIR/${label}_cases"

  if [[ ! -f "$src" ]]; then
    echo "missing benchmark file: $src" >&2
    exit 2
  fi

  echo "=== split $label cases ==="
  split_cases "$src" "$cases_dir"

  echo "=== run $label cases ==="
  local active=0
  local case_file
  for case_file in "$cases_dir"/case_*.lean; do
    local base
    local case_id
    base="$(basename "$case_file")"
    case_id="${base#case_}"
    case_id="${case_id%.lean}"
    if ! case_selected "$case_id"; then
      continue
    fi
    run_one "$label" "$case_file" "$case_id" &
    active=$((active + 1))
    if (( active >= JOBS )); then
      wait -n || true
      active=$((active - 1))
    fi
  done
  wait || true
}

write_summary() {
  local summary="$RESULT_DIR/summary.tsv"
  printf "mode\tcase\tstatus\texit_code\treal_s\tuser_s\tsys_s\tmaxrss_kb\tstdout_log\tdecision_log\n" \
    > "$summary"
  if compgen -G "$RESULT_DIR/rows/*.tsv" >/dev/null; then
    sort "$RESULT_DIR"/rows/*.tsv >> "$summary"
  fi

  echo
  echo "Summary: $summary"
  awk -F '\t' '
    NR == 1 { next }
    {
      key = $1 "\t" $3
      count[key] += 1
      total[$1] += 1
      if ($5 != "NA") {
        real[$1] += $5
      }
    }
    END {
      for (mode in total) {
        ok = count[mode "\tok"] + 0
        fail = count[mode "\tfail"] + 0
        timeout = count[mode "\ttimeout"] + 0
        printf "%s total=%d ok=%d fail=%d timeout=%d summed_real_s=%.2f\n",
          mode, total[mode], ok, fail, timeout, real[mode]
      }
    }
  ' "$summary" | sort
}

normalize_runtime_paths
write_manifest

if [[ "$MODE" == "grind" || "$MODE" == "both" ]]; then
  run_mode grind "$GRIND_FILE"
fi

if [[ "$MODE" == "neural" || "$MODE" == "both" ]]; then
  run_mode neural "$NEURAL_FILE"
fi

write_summary
