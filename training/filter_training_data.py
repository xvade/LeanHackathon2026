"""Filter fixed benchmark problems out of split-decision training data.

This script never modifies source datasets. It writes clean snapshots under an
output directory so active collectors can continue writing their own files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TRAINING = Path(__file__).parent

DEFAULT_INPUTS = [
    TRAINING / "data" / "verified_splits.jsonl",
    TRAINING / "data" / "workbook_splits.jsonl",
    TRAINING / "data" / "numina_finelean_combined_splits.jsonl",
    TRAINING / "data" / "numina_finelean_v2_splits.jsonl",
    TRAINING / "data" / "herald_splits.jsonl",
]


def normalize_text(s: str) -> str:
    """Normalize pretty-printed Lean text for conservative equality checks."""
    return re.sub(r"\s+", "", s)


def fingerprint(s: str) -> str:
    return hashlib.sha256(normalize_text(s).encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def source_name_keys(record: dict) -> set[tuple[str, str]]:
    sources = [
        record.get("source"),
        record.get("dataset"),
        record.get("benchmark_source"),
    ]
    names = [
        record.get("name"),
        record.get("id"),
        record.get("source_id"),
        record.get("benchmark_name"),
        record.get("theoremName"),
    ]
    return {
        (str(source), str(name))
        for source in sources
        for name in names
        if source is not None and name is not None
    }


def benchmark_keys(benchmark_path: Path, traces_path: Path) -> tuple[set[tuple[str, str]], set[str]]:
    keys: set[tuple[str, str]] = set()
    goal_fps: set[str] = set()

    for record in read_jsonl(benchmark_path):
        keys.update(source_name_keys(record))

    for trace in read_jsonl(traces_path):
        keys.update(source_name_keys(trace))
        goal = trace.get("goalPP")
        if isinstance(goal, str) and goal.strip():
            goal_fps.add(fingerprint(goal))

    return keys, goal_fps


def record_goal_fingerprints(record: dict) -> set[str]:
    fps = set()
    goal = record.get("goalPP")
    if isinstance(goal, str) and goal.strip():
        fps.add(fingerprint(goal))
    for step in record.get("steps", []):
        step_goal = step.get("goalPP")
        if isinstance(step_goal, str) and step_goal.strip():
            fps.add(fingerprint(step_goal))
    return fps


def should_drop(record: dict, bench_keys: set[tuple[str, str]], bench_goal_fps: set[str]) -> bool:
    if source_name_keys(record) & bench_keys:
        return True
    if record_goal_fingerprints(record) & bench_goal_fps:
        return True
    return False


def filter_file(path: Path, out_dir: Path, bench_keys: set[tuple[str, str]], bench_goal_fps: set[str]) -> dict:
    out_path = out_dir / path.name
    total = 0
    kept = 0
    dropped = 0
    with path.open(encoding="utf-8", errors="replace") as inp, out_path.open("w", encoding="utf-8") as out:
        for line in inp:
            raw = line.strip()
            if not raw:
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            total += 1
            if should_drop(record, bench_keys, bench_goal_fps):
                dropped += 1
                continue
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            kept += 1
    return {
        "input": str(path),
        "output": str(out_path),
        "total": total,
        "kept": kept,
        "dropped": dropped,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--benchmark",
        default=str(TRAINING / "data" / "split_active_benchmark.jsonl"),
    )
    parser.add_argument(
        "--benchmark-traces",
        default=str(TRAINING / "data" / "split_active_benchmark_traces.jsonl"),
    )
    parser.add_argument("--out-dir", default=str(TRAINING / "data" / "clean"))
    parser.add_argument("--input", action="append", default=None)
    parser.add_argument(
        "--combined-out",
        default="train_splits.jsonl",
        help="Write a concatenated clean training file in out-dir; empty disables it.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    benchmark = Path(args.benchmark)
    benchmark_traces = Path(args.benchmark_traces)
    if not benchmark.exists():
        raise SystemExit(f"Missing benchmark file: {benchmark}")
    if not benchmark_traces.exists():
        raise SystemExit(
            f"Missing benchmark trace file: {benchmark_traces}\n"
            "Run training/collect_benchmark_traces.py first."
        )

    inputs = [Path(p) for p in args.input] if args.input else DEFAULT_INPUTS
    inputs = [path for path in inputs if path.exists()]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    bench_keys, bench_goal_fps = benchmark_keys(benchmark, benchmark_traces)
    summaries = [
        filter_file(path, out_dir, bench_keys, bench_goal_fps)
        for path in inputs
    ]

    combined_path = None
    if args.combined_out:
        combined_path = out_dir / args.combined_out
        with combined_path.open("w", encoding="utf-8") as out:
            for summary in summaries:
                with Path(summary["output"]).open(encoding="utf-8") as inp:
                    for line in inp:
                        out.write(line)

    manifest = {
        "benchmark": str(benchmark),
        "benchmark_traces": str(benchmark_traces),
        "benchmark_key_count": len(bench_keys),
        "benchmark_goal_fingerprint_count": len(bench_goal_fps),
        "outputs": summaries,
        "combined_output": str(combined_path) if combined_path else None,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    for summary in summaries:
        print(
            f"{summary['input']} -> {summary['output']}: "
            f"kept={summary['kept']} dropped={summary['dropped']} total={summary['total']}"
        )
    if combined_path:
        print(f"Combined clean data: {combined_path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
