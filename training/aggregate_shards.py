"""Aggregate sharded branch-cost outputs.

When `collect_branch_costs.py` is run as multiple shards
(`--num-shards N --shard-id i`), each shard writes its own JSONL.
This script concatenates them, drops duplicate
(case, traceStep, anchor) rows from any resumed-after-failure runs, and
reports coverage gaps versus the original sample plan.

Example:
  python training/aggregate_shards.py \\
    --shards-glob 'training/data/phase1/shards/branch_costs_shard_*.jsonl' \\
    --plan training/data/phase1/sample_plan.jsonl \\
    --out training/data/phase1/branch_costs.jsonl

Exit code is non-zero if coverage is incomplete (some plan rows still have
zero successful runs); set --allow-incomplete to make it 0.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as h:
        for line in h:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shards-glob", required=True, help="Glob for shard JSONLs")
    parser.add_argument("--plan", type=Path, help="Original sample plan JSONL (for coverage check)")
    parser.add_argument("--out", type=Path, required=True, help="Merged output JSONL")
    parser.add_argument(
        "--prefer",
        choices=("first", "last", "success"),
        default="success",
        help="When duplicate (case, traceStep, anchor) rows are present: 'first' keeps earliest, 'last' keeps latest, 'success' prefers any success over failure/timeout (default)",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Don't exit non-zero if some plan rows have no covered anchors",
    )
    args = parser.parse_args()

    shard_paths = sorted(Path(p) for p in glob.glob(args.shards_glob))
    if not shard_paths:
        sys.exit(f"no shard files matched {args.shards_glob!r}")

    print(f"found {len(shard_paths)} shard files", file=sys.stderr)

    by_key: dict[tuple[str, int, int], dict[str, Any]] = {}
    rows_seen = 0
    for sp in shard_paths:
        for row in load_jsonl(sp):
            rows_seen += 1
            key = (
                str(row.get("case")),
                int(row.get("traceStep", -1)),
                int(row.get("anchor", 0)),
            )
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = row
                continue
            if args.prefer == "first":
                continue
            if args.prefer == "last":
                by_key[key] = row
                continue
            # prefer success
            existing_ok = existing.get("status") == "success"
            new_ok = row.get("status") == "success"
            if new_ok and not existing_ok:
                by_key[key] = row

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as h:
        for key in sorted(by_key.keys()):
            h.write(json.dumps(by_key[key], sort_keys=True) + "\n")
    print(
        f"wrote {len(by_key)} unique rows to {args.out}"
        f" (saw {rows_seen} total, {rows_seen - len(by_key)} duplicates collapsed)",
        file=sys.stderr,
    )

    if not args.plan:
        return

    plan = load_jsonl(args.plan)
    plan_anchors: set[tuple[str, int, int]] = set()
    for row in plan:
        case = str(row["case"])
        step = int(row["traceStep"])
        for a in row.get("forcedAnchors", []):
            try:
                plan_anchors.add((case, step, int(a)))
            except (ValueError, TypeError):
                continue

    have = set(by_key.keys())
    missing = plan_anchors - have
    extra = have - plan_anchors
    incomplete_decisions: dict[tuple[str, int], int] = defaultdict(int)
    for k in missing:
        incomplete_decisions[(k[0], k[1])] += 1

    print(
        f"\ncoverage: planned {len(plan_anchors)} anchors,"
        f" have {len(have & plan_anchors)} ({100.0*len(have & plan_anchors)/max(len(plan_anchors),1):.1f}%),"
        f" missing {len(missing)},"
        f" unexpected {len(extra)}",
        file=sys.stderr,
    )
    if incomplete_decisions:
        print(
            f"  {len(incomplete_decisions)} decisions have at least one missing anchor",
            file=sys.stderr,
        )
        for (case, step), n in sorted(incomplete_decisions.items())[:10]:
            print(f"    case={case} traceStep={step}: {n} missing", file=sys.stderr)
        if len(incomplete_decisions) > 10:
            print(f"    ... ({len(incomplete_decisions) - 10} more)", file=sys.stderr)

    if missing and not args.allow_incomplete:
        sys.exit(2)


if __name__ == "__main__":
    main()
