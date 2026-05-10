#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SELF="$SCRIPT_DIR/test_exp09_model_steps.sh"

PROFILE="${PROFILE:-${1:-both}}"

if [[ "$PROFILE" == "both" ]]; then
  BASE_STAMP="${STAMP:-exp09_two_profile_$(date -u +%Y%m%d_%H%M%S)}"
  BASE_RESULT_DIR="${RESULT_DIR:-$SCRIPT_DIR/results/$BASE_STAMP}"
  COMPARISON_TXT="$BASE_RESULT_DIR/two_profile_summary.txt"
  mkdir -p "$BASE_RESULT_DIR"

  echo "running safe profile -> $BASE_RESULT_DIR/safe"
  env -u MODEL -u MARGIN PROFILE=safe STAMP=safe RESULT_DIR="$BASE_RESULT_DIR/safe" "$SELF" safe

  echo
  echo "running aggressive profile -> $BASE_RESULT_DIR/aggressive"
  env -u MODEL -u MARGIN PROFILE=aggressive STAMP=aggressive RESULT_DIR="$BASE_RESULT_DIR/aggressive" "$SELF" aggressive

  python3 - "$BASE_RESULT_DIR" "$COMPARISON_TXT" <<'PY'
import csv
import re
import sys
from pathlib import Path

base = Path(sys.argv[1])
out = Path(sys.argv[2])

def load(profile):
    path = base / profile / "steps.tsv"
    if not path.exists():
        raise SystemExit(f"missing steps file for {profile}: {path}")
    with path.open() as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    solved = [r for r in rows if r["status"] == "ok" and r["steps_saved_pct"] != "NA"]
    total = len(rows)
    ok = sum(r["status"] == "ok" for r in rows)
    fail = sum(r["status"] == "fail" for r in rows)
    timeout = sum(r["status"] == "timeout" for r in rows)
    saved = sum(float(r["steps_saved_pct"]) > 0.0 for r in solved)
    same = sum(abs(float(r["steps_saved_pct"])) < 1e-9 for r in solved)
    more = sum(float(r["steps_saved_pct"]) < 0.0 for r in solved)
    grind = sum(int(r["grind_collect_splits"]) for r in solved)
    neural = sum(int(r["neural_steps"]) for r in solved)
    pct = (grind - neural) / grind * 100.0 if grind else 0.0
    best = None
    positives = [r for r in solved if float(r["steps_saved_pct"]) > 0.0]
    if positives:
        best = max(positives, key=lambda r: float(r["steps_saved_pct"]))
    return {
        "profile": profile,
        "total": total,
        "ok": ok,
        "fail": fail,
        "timeout": timeout,
        "saved": saved,
        "same": same,
        "more": more,
        "grind": grind,
        "neural": neural,
        "pct": pct,
        "best": best,
    }

def bench_name(row):
    if not row:
        return "none"
    match = re.search(r"benchmark \d+:\s*(.*)", row["benchmark"])
    name = match.group(1).strip() if match else row["benchmark"].strip()
    return f"case {row['case']}: {row['grind_collect_splits']} -> {row['neural_steps']} splits ({float(row['steps_saved_pct']):.1f}% saved), {name}"

safe = load("safe")
aggr = load("aggressive")

lines = [
    "Two-profile hackathon summary",
    "",
    "Narrative:",
    "  Safe mode shows that neural grind can be made reliable by using a large confidence gate.",
    "  Aggressive mode shows the learned shortcut signal when the model is allowed to intervene more often.",
    "",
    "Profile comparison:",
    "  profile       solved   fail timeout   saved same more   neural/grind steps   aggregate",
]
for r in [safe, aggr]:
    lines.append(
        f"  {r['profile']:<11} {r['ok']:>2}/{r['total']:<2}   {r['fail']:>2}   {r['timeout']:>2}"
        f"      {r['saved']:>2}   {r['same']:>2}  {r['more']:>2}"
        f"      {r['neural']:>4}/{r['grind']:<4}        {r['pct']:+.2f}% saved"
    )
lines.extend([
    "",
    "Best shortcut examples:",
    f"  safe:       {bench_name(safe['best'])}",
    f"  aggressive: {bench_name(aggr['best'])}",
    "",
    "Slide wording:",
    "  We have two operating points. Safe mode is the demo: full-test-set stability and near parity.",
    "  Aggressive mode is the research signal: more learned shortcuts, including larger split reductions,",
    "  at the cost of less conservative behavior.",
])

out.write_text("\n".join(lines) + "\n")
print()
print("\n".join(lines))
print(f"\ncomparison: {out}")
PY

  echo
  echo "safe summary      : $BASE_RESULT_DIR/safe/presentation_summary.txt"
  echo "aggressive summary: $BASE_RESULT_DIR/aggressive/presentation_summary.txt"
  echo "comparison        : $COMPARISON_TXT"
  exit 0
fi

case "$PROFILE" in
  safe)
    DEFAULT_MODEL="$REPO_ROOT/training/experiments/exp09_heuristics/model_shortcut_latest.native.bin"
    DEFAULT_MARGIN="5000"
    PROFILE_DESC="safe confidence-gated mode: full held-out solve rate and near native split-count parity"
    ;;
  aggressive)
    DEFAULT_MODEL="$REPO_ROOT/training/experiments/exp09_heuristics/model_shortcut_final.native.bin"
    DEFAULT_MARGIN="1000"
    PROFILE_DESC="aggressive shortcut mode: more neural override choices and more visible learned shortcuts"
    ;;
  custom)
    DEFAULT_MODEL="$REPO_ROOT/training/experiments/exp09_heuristics/model.native.bin"
    DEFAULT_MARGIN="0"
    PROFILE_DESC="custom mode: caller-provided MODEL and MARGIN"
    ;;
  -h|--help|help)
    echo "usage: $0 [both|safe|aggressive|custom]" >&2
    echo "       PROFILE=both|safe|aggressive|custom MODEL=... MARGIN=... $0" >&2
    exit 0
    ;;
  *)
    echo "unknown profile: $PROFILE" >&2
    echo "usage: $0 [both|safe|aggressive|custom]" >&2
    exit 2
    ;;
esac

MODEL="${MODEL:-$DEFAULT_MODEL}"
SERVE="${SERVE:-$SCRIPT_DIR/native_serve}"
NATIVE_SRC="$SCRIPT_DIR/native/model.cpp"
RUNNER="$REPO_ROOT/training/benchmarks/run_split_active_cases.sh"
CXX="${CXX:-c++}"

MARGIN="${MARGIN:-$DEFAULT_MARGIN}"
JOBS="${JOBS:-4}"
TIMEOUT="${TIMEOUT:-90}"
STAMP="${STAMP:-exp09_${PROFILE}_m${MARGIN}_$(date -u +%Y%m%d_%H%M%S)}"
RESULT_DIR="${RESULT_DIR:-$SCRIPT_DIR/results/$STAMP}"
STEPS_TSV="$RESULT_DIR/steps.tsv"
DISTRIBUTION_TSV="$RESULT_DIR/steps_saved_distribution.tsv"
DISTRIBUTION_TXT="$RESULT_DIR/steps_saved_distribution.txt"
PRESENTATION_TXT="$RESULT_DIR/presentation_summary.txt"

if [[ ! -f "$MODEL" ]]; then
  echo "missing model: $MODEL" >&2
  echo "Set MODEL=/path/to/model.native.bin" >&2
  exit 2
fi

if [[ ! -x "$RUNNER" ]]; then
  echo "missing benchmark runner: $RUNNER" >&2
  exit 2
fi

if [[ ! -x "$SERVE" || "$NATIVE_SRC" -nt "$SERVE" ]]; then
  echo "building native server: $SERVE" >&2
  mkdir -p "$(dirname "$SERVE")"
  "$CXX" -DNEURAL_GRIND_STANDALONE -O3 -std=c++17 "$NATIVE_SRC" -o "$SERVE"
fi

echo "testing model on split-active test set"
echo "  profile    : $PROFILE"
echo "  intent     : $PROFILE_DESC"
echo "  model      : $MODEL"
echo "  server     : $SERVE"
echo "  margin     : $MARGIN"
echo "  jobs       : $JOBS"
echo "  timeout    : $TIMEOUT"
echo "  result dir : $RESULT_DIR"

RESULT_DIR="$RESULT_DIR" \
STAMP="$STAMP" \
JOBS="$JOBS" \
TIMEOUT="$TIMEOUT" \
DECISION_LOG=1 \
GRIND_MODEL="$MODEL" \
GRIND_SERVE="$SERVE" \
GRIND_SERVE_NATIVE=1 \
GRIND_MARGIN_MILLI="$MARGIN" \
bash "$RUNNER" neural

python3 - "$RESULT_DIR" "$STEPS_TSV" "$DISTRIBUTION_TSV" "$DISTRIBUTION_TXT" "$PRESENTATION_TXT" "$PROFILE" "$PROFILE_DESC" <<'PY'
import csv
import json
import re
import sys
from pathlib import Path

run = Path(sys.argv[1])
out = Path(sys.argv[2])
distribution_tsv = Path(sys.argv[3])
distribution_txt = Path(sys.argv[4])
presentation_txt = Path(sys.argv[5])
profile = sys.argv[6]
profile_desc = sys.argv[7]
summary = run / "summary.tsv"
cases_dir = run / "neural_cases"

if not summary.exists():
    raise SystemExit(f"missing summary: {summary}")

rows = []
with summary.open() as f:
    for row in csv.DictReader(f, delimiter="\t"):
        cid = row["case"]
        decision_path = Path(row["decision_log"]) if row["decision_log"] != "-" else None

        neural_steps = 0
        model_overrides = 0
        fallbacks = 0
        fallback_reasons = {}
        max_candidates = 0

        if decision_path and decision_path.exists():
            for line in decision_path.read_text().splitlines():
                if not line.strip():
                    continue
                neural_steps += 1
                rec = json.loads(line)
                action = rec.get("action")
                if action == "model":
                    model_overrides += 1
                elif action == "fallback":
                    fallbacks += 1
                    reason = rec.get("reason", "unknown")
                    fallback_reasons[reason] = fallback_reasons.get(reason, 0) + 1
                max_candidates = max(max_candidates, int(rec.get("numCandidates") or 0))

        case_file = cases_dir / f"case_{cid}.lean"
        header = ""
        grind_splits = "NA"
        multi_candidate_steps = "NA"
        max_pool_size = "NA"
        if case_file.exists():
            lines = case_file.read_text(errors="replace").splitlines()
            header = next((line for line in lines if line.startswith("/- benchmark")), "")
            meta = next((line for line in lines if "grind_collect_splits=" in line), "")
            m = re.search(r"grind_collect_splits=(\d+)", meta)
            if m:
                grind_splits = m.group(1)
            m = re.search(r"multi_candidate_steps=(\d+)", meta)
            if m:
                multi_candidate_steps = m.group(1)
            m = re.search(r"max_pool_size=(\d+)", meta)
            if m:
                max_pool_size = m.group(1)

        delta = "NA"
        saved_pct = "NA"
        if grind_splits != "NA":
            grind_steps = int(grind_splits)
            delta = str(neural_steps - grind_steps)
            if grind_steps != 0:
                saved_pct = f"{(grind_steps - neural_steps) / grind_steps * 100.0:.6f}"

        rows.append({
            "case": cid,
            "status": row["status"],
            "real_s": row["real_s"],
            "neural_steps": str(neural_steps),
            "grind_collect_splits": str(grind_splits),
            "step_delta": delta,
            "steps_saved_pct": saved_pct,
            "model_overrides": str(model_overrides),
            "fallbacks": str(fallbacks),
            "fallback_reasons": ",".join(f"{k}:{v}" for k, v in sorted(fallback_reasons.items())),
            "max_candidates_seen": str(max_candidates),
            "multi_candidate_steps": str(multi_candidate_steps),
            "max_pool_size_grind_collect": str(max_pool_size),
            "benchmark": header,
            "stdout_log": row["stdout_log"],
            "decision_log": row["decision_log"],
        })

fields = [
    "case",
    "status",
    "real_s",
    "neural_steps",
    "grind_collect_splits",
    "step_delta",
    "steps_saved_pct",
    "model_overrides",
    "fallbacks",
    "fallback_reasons",
    "max_candidates_seen",
    "multi_candidate_steps",
    "max_pool_size_grind_collect",
    "benchmark",
    "stdout_log",
    "decision_log",
]

with out.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
    writer.writeheader()
    writer.writerows(rows)

def pct(row):
    value = row["steps_saved_pct"]
    return None if value == "NA" else float(value)

solved = [row for row in rows if row["status"] == "ok" and pct(row) is not None]
bins = [
    ("<= -100%", lambda x: x <= -100.0),
    ("-100 to -50%", lambda x: -100.0 < x < -50.0),
    ("-50 to -25%", lambda x: -50.0 <= x < -25.0),
    ("-25 to -10%", lambda x: -25.0 <= x < -10.0),
    ("-10 to <0%", lambda x: -10.0 <= x < 0.0),
    ("0%", lambda x: abs(x) < 1e-9),
    ("0 to 10%", lambda x: 0.0 < x <= 10.0),
    ("10 to 25%", lambda x: 10.0 < x <= 25.0),
    ("25 to 50%", lambda x: 25.0 < x <= 50.0),
    ("> 50%", lambda x: x > 50.0),
]
bin_rows = []
for label, pred in bins:
    count = sum(1 for row in solved if pred(pct(row)))
    bin_rows.append((label, count))

with distribution_tsv.open("w", newline="") as f:
    writer = csv.writer(f, delimiter="\t")
    writer.writerow(["bin", "count"])
    writer.writerows(bin_rows)

total = len(rows)
ok = sum(1 for r in rows if r["status"] == "ok")
fail = sum(1 for r in rows if r["status"] == "fail")
timeout = sum(1 for r in rows if r["status"] == "timeout")
neural_sum = sum(int(r["neural_steps"]) for r in rows)
grind_known = [int(r["grind_collect_splits"]) for r in rows if r["grind_collect_splits"] != "NA"]
grind_sum = sum(grind_known)
print(f"\nsteps tsv: {out}")
print(f"cases: total={total} ok={ok} fail={fail} timeout={timeout}")
print(f"steps: neural={neural_sum} grind_collect={grind_sum} delta={neural_sum - grind_sum}")

solved_neural_sum = sum(int(r["neural_steps"]) for r in solved)
solved_grind_sum = sum(int(r["grind_collect_splits"]) for r in solved)
weighted_saved = (
    (solved_grind_sum - solved_neural_sum) / solved_grind_sum * 100.0
    if solved_grind_sum
    else 0.0
)
saved_cases = sum(1 for r in solved if pct(r) > 0.0)
same_cases = sum(1 for r in solved if abs(pct(r)) < 1e-9)
more_cases = sum(1 for r in solved if pct(r) < 0.0)

max_count = max((count for _, count in bin_rows), default=0)
hist_lines = [
    "% steps saved distribution for solved cases",
    "negative = neural_grind used more split steps",
    "positive = neural_grind saved split steps",
    "",
]
for label, count in bin_rows:
    bar_len = 0 if max_count == 0 else round(count / max_count * 40)
    hist_lines.append(f"{label:>12}  {'#' * bar_len:<40} {count}")
hist_lines.extend([
    "",
    f"Solved cases: {len(solved)}",
    f"Saved steps:  {saved_cases}",
    f"Same steps:   {same_cases}",
    f"More steps:   {more_cases}",
    "",
    "Total solved-case steps:",
    f"  grind_collect: {solved_grind_sum}",
    f"  neural_grind:  {solved_neural_sum}",
    f"  steps saved:   {weighted_saved:+.2f}%",
])

bad = [r for r in rows if r["status"] != "ok"]
if bad:
    hist_lines.extend(["", "Non-ok cases:"])
    for r in bad:
        hist_lines.append(
            f"  case={r['case']} status={r['status']} "
            f"steps_saved_pct={r['steps_saved_pct']} "
            f"neural_steps={r['neural_steps']} "
            f"grind_collect_splits={r['grind_collect_splits']} "
            f"{r['benchmark']}"
        )

distribution_txt.write_text("\n".join(hist_lines) + "\n")

def benchmark_name(row):
    match = re.search(r"benchmark \d+:\s*(.*)", row["benchmark"])
    return match.group(1).strip() if match else row["benchmark"].strip()

top_saved = sorted(
    [row for row in solved if pct(row) and pct(row) > 0.0],
    key=lambda row: (pct(row), int(row["grind_collect_splits"])),
    reverse=True,
)[:5]

total_overrides = sum(int(row["model_overrides"]) for row in rows)
total_fallbacks = sum(int(row["fallbacks"]) for row in rows)
equal_or_better = saved_cases + same_cases
extra_steps = solved_neural_sum - solved_grind_sum

presentation_lines = [
    "Hackathon presentation summary",
    "",
    f"Profile: {profile}",
    f"Intent: {profile_desc}",
    "",
    "Recommended framing:",
    "  We surgically replaced one decision inside Lean grind: which split to try next.",
    "  The neural policy keeps grind's native machinery and only changes split ordering.",
    "  Safe mode is the reliability slide; aggressive mode is the shortcut-learning slide.",
    "",
    "Headline numbers:",
    f"  solved: {ok}/{total} cases",
    f"  failures: {fail}, timeouts: {timeout}",
    f"  equal-or-better split count: {equal_or_better}/{len(solved)} solved cases",
    f"  fewer split steps: {saved_cases}",
    f"  same split steps: {same_cases}",
    f"  more split steps: {more_cases}",
    f"  total solved-case split steps: neural_grind={solved_neural_sum}, grind_collect={solved_grind_sum}",
    f"  aggregate split-step delta: {extra_steps:+d} ({weighted_saved:+.2f}% saved)",
    f"  model overrides: {total_overrides}",
    f"  native fallbacks: {total_fallbacks}",
    "",
    "Best shortcut examples:",
]

if top_saved:
    for row in top_saved:
        presentation_lines.append(
            f"  case {row['case']}: {row['grind_collect_splits']} -> {row['neural_steps']} "
            f"splits ({pct(row):.1f}% saved), {benchmark_name(row)}"
        )
else:
    presentation_lines.append("  no positive split-saving examples in this run")

presentation_lines.extend(["", "Suggested wording:"])
if profile == "safe":
    presentation_lines.extend([
        "  This is the conservative reliability mode: a neural guidance layer inside Lean's",
        "  grind that keeps the native engine in charge unless the model has a large margin.",
        "  It is the demo setting for full-test-set stability and near split-count parity.",
    ])
elif profile == "aggressive":
    presentation_lines.extend([
        "  This is the research-mode shortcut setting: the model is allowed to override native",
        "  split order more often, exposing more learned proof-search shortcuts. It is useful",
        "  for showing the signal that future confidence calibration should preserve safely.",
    ])
else:
    presentation_lines.extend([
        "  This custom run uses caller-provided settings. Compare its solve rate, failures,",
        "  and split-step distribution against the safe and aggressive profiles.",
    ])

presentation_txt.write_text("\n".join(presentation_lines) + "\n")

print()
print("\n".join(hist_lines))
print(f"\ndistribution tsv: {distribution_tsv}")
print(f"distribution txt: {distribution_txt}")
print(f"presentation : {presentation_txt}")

bad = [r for r in rows if r["status"] != "ok"]
if bad:
    print("\nnon-ok cases:")
    for r in bad:
        print(
            f"  case={r['case']} status={r['status']} neural_steps={r['neural_steps']} "
            f"grind_collect_splits={r['grind_collect_splits']} {r['benchmark']}"
        )
PY

echo
echo "summary: $RESULT_DIR/summary.tsv"
echo "steps  : $STEPS_TSV"
echo "dist   : $DISTRIBUTION_TXT"
echo "talk   : $PRESENTATION_TXT"
