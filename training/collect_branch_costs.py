"""Collect local branch-cost labels by forcing one split candidate.

This script is intentionally separate from imitation data collection.  It takes
existing `grind_collect` traces to learn which anchors are available, then runs
the corresponding `neural_grind` benchmark case multiple times while forcing one
candidate at one split step.  All other split steps use the stock grind choice.

The default benchmark mapping is order-based: trace record 0 maps to benchmark
case 000, trace record 1 maps to case 001, and so on.  This matches the fixed
split-active benchmark generated for neural_grind timing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK = ROOT / "training" / "benchmarks" / "split_active_timing_neural_grind.lean"
DEFAULT_PROJECT = ROOT / "NeuralTactic"
FORCED_SERVER = ROOT / "training" / "serve_forced_choice.py"
BENCHMARK_RE = re.compile(r"^/- benchmark ([0-9]+):")


def normalize_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    if "splitDecisions" in record:
        return [
            {
                "step": decision.get("step", idx),
                "candidates": decision.get("pool", []),
                "chosenAnchor": decision.get("chosenAnchor"),
            }
            for idx, decision in enumerate(record.get("splitDecisions", []))
        ]
    return [
        {
            "step": step.get("step", idx),
            "candidates": step.get("candidates", []),
            "chosenAnchor": step.get("chosenAnchor"),
        }
        for idx, step in enumerate(record.get("steps", []))
    ]


def load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def split_benchmark(src: Path, dest: Path) -> dict[str, Path]:
    header: list[str] = []
    current: list[str] | None = None
    current_case: str | None = None
    cases: dict[str, Path] = {}

    for line in src.read_text().splitlines():
        match = BENCHMARK_RE.match(line)
        if match:
            if current is not None and current_case is not None:
                out = dest / f"case_{current_case}.lean"
                out.write_text("\n".join(current) + "\n")
                cases[current_case] = out
            current_case = match.group(1)
            current = [*header, line]
        elif current is None:
            header.append(line)
        else:
            current.append(line)

    if current is not None and current_case is not None:
        out = dest / f"case_{current_case}.lean"
        out.write_text("\n".join(current) + "\n")
        cases[current_case] = out
    return cases


def summarize_decisions(path: Path) -> dict[str, Any]:
    actions: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    total = 0
    if not path.exists():
        return {"actions": {}, "reasons": {}, "totalLines": 0}
    with path.open() as handle:
        for line in handle:
            if not line.strip():
                continue
            total += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            actions[str(row.get("action", ""))] += 1
            reasons[str(row.get("reason", ""))] += 1
    return {"actions": dict(actions), "reasons": dict(reasons), "totalLines": total}


def run_forced_candidate(
    *,
    project: Path,
    case_file: Path,
    log_dir: Path,
    python_bin: str,
    timeout_s: float,
    case_id: str,
    step_query_index: int,
    anchor: int,
    multi_step_index: int | None = None,
) -> dict[str, Any]:
    target_label = f"multi{multi_step_index:03d}" if multi_step_index else f"step_{step_query_index:03d}"
    stem = f"case_{case_id}_{target_label}_anchor_{anchor}"
    stdout_path = log_dir / f"{stem}.stdout.log"
    decision_path = log_dir / f"{stem}.decisions.jsonl"
    if decision_path.exists():
        decision_path.unlink()
    env = os.environ.copy()
    env.update(
        {
            "GRIND_MODEL": "forced-choice",
            "GRIND_SERVE": str(FORCED_SERVER),
            "GRIND_PYTHON": python_bin,
            "GRIND_FORCE_ANCHOR": str(anchor),
            "GRIND_FORCE_AFTER": "stock",
            "GRIND_MARGIN_MILLI": "0",
            "GRIND_DECISION_LOG": str(decision_path),
        }
    )
    if multi_step_index is not None and multi_step_index > 0:
        env["GRIND_FORCE_MULTI_STEP"] = str(multi_step_index)
    else:
        env["GRIND_FORCE_STEP"] = str(step_query_index)

    start = time.monotonic()
    status = "failure"
    exit_code: int | None = None
    try:
        completed = subprocess.run(
            ["lake", "-R", "env", "lean", str(case_file)],
            cwd=project,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        exit_code = completed.returncode
        stdout_path.write_text(completed.stdout)
        status = "success" if completed.returncode == 0 else "failure"
    except subprocess.TimeoutExpired as exc:
        def _to_str(x: Any) -> str:
            if x is None:
                return ""
            if isinstance(x, bytes):
                return x.decode("utf-8", errors="replace")
            return x
        stdout_path.write_text(_to_str(exc.stdout) + _to_str(exc.stderr))
        status = "timeout"
        exit_code = 124

    elapsed = time.monotonic() - start
    summary = summarize_decisions(decision_path)
    total_decisions = summary.get("totalLines", 0)
    splits_to_close = total_decisions if status == "success" else None
    return {
        "status": status,
        "exitCode": exit_code,
        "elapsed_s": round(elapsed, 6),
        "stdoutLog": str(stdout_path),
        "decisionLog": str(decision_path),
        "decisionSummary": summary,
        "totalDecisions": total_decisions,
        "splitsToClose": splits_to_close,
    }


def anchor_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def load_plan(path: Path) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if line:
                plan.append(json.loads(line))
    return plan


def collect_from_plan(args: argparse.Namespace, plan: list[dict[str, Any]]) -> None:
    args.out.parent.mkdir(parents=True, exist_ok=True)
    log_dir = args.log_dir or args.out.with_suffix(args.out.suffix + ".logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    num_shards = max(1, int(getattr(args, "num_shards", 1) or 1))
    shard_id = int(getattr(args, "shard_id", 0) or 0)
    if not (0 <= shard_id < num_shards):
        raise SystemExit(
            f"--shard-id {shard_id} must be in [0, {num_shards}); got num-shards={num_shards}"
        )

    # Build a deterministic flat task list of (plan_row_idx, anchor) so load
    # balancing is independent of how many anchors each plan row carries.
    flat_tasks: list[tuple[int, int]] = []
    for plan_idx, plan_row in enumerate(plan):
        for raw_anchor in plan_row.get("forcedAnchors", []):
            anchor = anchor_int(raw_anchor)
            if anchor == 0:
                continue
            flat_tasks.append((plan_idx, anchor))

    # Round-robin partition keeps adjacent tasks (likely similar cost) across
    # shards rather than within one shard.
    my_tasks = [t for i, t in enumerate(flat_tasks) if i % num_shards == shard_id]
    by_plan_row: dict[int, list[int]] = {}
    for plan_idx, anchor in my_tasks:
        by_plan_row.setdefault(plan_idx, []).append(anchor)

    skip_existing = bool(getattr(args, "skip_existing", False))
    existing_keys: set[tuple[str, int, int]] = set()
    if skip_existing and args.out.exists():
        try:
            with args.out.open() as h:
                for line in h:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    key = (str(row.get("case")), int(row.get("traceStep", -1)), int(row.get("anchor", 0)))
                    existing_keys.add(key)
            print(
                f"[shard {shard_id}/{num_shards}] resuming: {len(existing_keys)} rows already in {args.out}",
                file=sys.stderr,
            )
        except OSError:
            existing_keys = set()

    print(
        f"[shard {shard_id}/{num_shards}] {len(my_tasks)} forced runs across"
        f" {len(by_plan_row)} plan rows (of {len(flat_tasks)} total runs across {len(plan)} plan rows)",
        file=sys.stderr,
    )

    out_mode = "a" if (skip_existing and args.out.exists()) else "w"

    tmp_root = os.environ.get("NEURAL_GRIND_TMPDIR") or None
    with tempfile.TemporaryDirectory(prefix="neural_grind_branch_cost_", dir=tmp_root) as tmp:
        cases = split_benchmark(args.benchmark_file, Path(tmp))
        selected = set(args.case_ids.split(",")) if args.case_ids else None

        # Fail loud if the benchmark file and the sample plan are out of
        # sync. Previously a typo in either could cause every plan row to
        # "skip with warning" and the run would write 0 rows silently.
        plan_cases = {str(r["case"]) for r in plan if "case" in r}
        if not cases:
            raise SystemExit(
                f"benchmark file {args.benchmark_file} contains no parseable "
                f"`/- benchmark NNN: -/` markers"
            )
        if plan_cases and not (plan_cases & set(cases)):
            sample_plan_cases = sorted(plan_cases)[:3]
            sample_bench_cases = sorted(cases.keys())[:3]
            raise SystemExit(
                f"sample plan and benchmark file have NO matching cases.\n"
                f"  plan has {len(plan_cases)} cases (first 3: {sample_plan_cases})\n"
                f"  benchmark has {len(cases)} cases (first 3: {sample_bench_cases})\n"
                f"  did you pass the right --benchmark-file?"
            )

        written = 0
        with args.out.open(out_mode) as out:
            for plan_idx, plan_row in enumerate(plan):
                if plan_idx not in by_plan_row:
                    continue
                shard_anchors_for_row = by_plan_row[plan_idx]
                case_id = str(plan_row["case"])
                if selected is not None and case_id not in selected:
                    continue
                case_file = cases.get(case_id)
                if case_file is None:
                    print(f"warning: no benchmark case for {case_id}; skipping", file=sys.stderr)
                    continue
                trace_step = int(plan_row["traceStep"])
                forced_query_index = trace_step + 1
                multi_step_index = plan_row.get("multiStepIndex")
                multi_step_index_int = (
                    int(multi_step_index) if multi_step_index is not None else None
                )
                stock_anchor = anchor_int(plan_row.get("stockAnchor"))
                anchors_in_pool = [anchor_int(a) for a in plan_row.get("anchors", [])]
                pool_size = int(plan_row.get("poolSize", len(anchors_in_pool)))
                for anchor in shard_anchors_for_row:
                    if anchor == 0:
                        continue
                    if skip_existing and (case_id, trace_step, anchor) in existing_keys:
                        continue
                    result = run_forced_candidate(
                        project=args.project,
                        case_file=case_file,
                        log_dir=log_dir,
                        python_bin=args.python,
                        timeout_s=args.timeout,
                        case_id=case_id,
                        step_query_index=forced_query_index,
                        anchor=anchor,
                        multi_step_index=multi_step_index_int,
                    )
                    row = {
                        "case": case_id,
                        "recordIndex": int(plan_row.get("recordIndex", int(case_id))),
                        "traceStep": trace_step,
                        "forcedQueryIndex": forced_query_index,
                        "multiStepIndex": multi_step_index_int,
                        "anchor": anchor,
                        "isGrindChoice": anchor == stock_anchor,
                        "poolSize": pool_size,
                        "stratum": plan_row.get("stratum"),
                        **result,
                    }
                    out.write(json.dumps(row, sort_keys=True) + "\n")
                    out.flush()
                    written += 1
    print(f"wrote {written} branch-cost rows to {args.out}")


def collect(args: argparse.Namespace) -> None:
    if args.sample_plan is not None:
        plan = load_plan(args.sample_plan)
        collect_from_plan(args, plan)
        return

    records = load_records(args.trace_jsonl)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    log_dir = args.log_dir or args.out.with_suffix(args.out.suffix + ".logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    tmp_root = os.environ.get("NEURAL_GRIND_TMPDIR") or None
    with tempfile.TemporaryDirectory(prefix="neural_grind_branch_cost_", dir=tmp_root) as tmp:
        cases = split_benchmark(args.benchmark_file, Path(tmp))
        selected = set(args.case_ids.split(",")) if args.case_ids else None
        written = 0
        with args.out.open("w") as out:
            for record_index, record in enumerate(records):
                if args.max_records is not None and record_index >= args.max_records:
                    break
                case_id = f"{record_index:03d}"
                if selected is not None and case_id not in selected:
                    continue
                case_file = cases.get(case_id)
                if case_file is None:
                    continue

                steps = [s for s in normalize_record(record) if len(s.get("candidates", [])) >= 2]
                if args.max_steps_per_case is not None:
                    steps = steps[: args.max_steps_per_case]

                for step in steps:
                    trace_step = int(step.get("step", 0))
                    forced_query_index = trace_step + 1
                    chosen = anchor_int(step.get("chosenAnchor"))
                    for candidate in step.get("candidates", []):
                        anchor = anchor_int(candidate.get("anchor"))
                        if anchor == 0:
                            continue
                        result = run_forced_candidate(
                            project=args.project,
                            case_file=case_file,
                            log_dir=log_dir,
                            python_bin=args.python,
                            timeout_s=args.timeout,
                            case_id=case_id,
                            step_query_index=forced_query_index,
                            anchor=anchor,
                        )
                        row = {
                            "case": case_id,
                            "recordIndex": record_index,
                            "traceStep": trace_step,
                            "forcedQueryIndex": forced_query_index,
                            "anchor": anchor,
                            "isGrindChoice": anchor == chosen,
                            "candidate": candidate,
                            **result,
                        }
                        out.write(json.dumps(row, sort_keys=True) + "\n")
                        out.flush()
                        written += 1
    print(f"wrote {written} branch-cost rows to {args.out}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trace-jsonl",
        type=Path,
        help="Trace JSONL (required unless --sample-plan is provided)",
    )
    parser.add_argument(
        "--sample-plan",
        type=Path,
        help="Sample plan JSONL emitted by phase0_sample.py",
    )
    parser.add_argument("--benchmark-file", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--out", type=Path, default=ROOT / "training" / "data" / "branch_costs.jsonl")
    parser.add_argument("--log-dir", type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--case-ids", help="Comma-separated benchmark case ids, e.g. 000,011")
    parser.add_argument("--max-records", type=int)
    parser.add_argument("--max-steps-per-case", type=int, default=1)
    parser.add_argument(
        "--num-shards",
        type=int,
        default=1,
        help="Partition flat task list into N round-robin shards (default 1)",
    )
    parser.add_argument(
        "--shard-id",
        type=int,
        default=0,
        help="Process only tasks where (task_index %% num_shards) == shard_id",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="If --out already exists, append and skip rows whose (case, traceStep, anchor) is already present (idempotent resume after pre-emption)",
    )
    args = parser.parse_args()
    if args.sample_plan is None and args.trace_jsonl is None:
        parser.error("must provide either --trace-jsonl or --sample-plan")
    return args


if __name__ == "__main__":
    collect(parse_args())
