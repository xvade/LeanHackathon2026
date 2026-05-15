"""Stratified sampler for Phase 0 branch-cost viability test.

Reads benchmark trace records (default: the committed split-active benchmark
traces) and emits a sample plan JSONL.  Each plan row identifies one
multi-candidate decision and the anchors that should be forced at that
decision.

Stratification is by pool size.  For pools of size <= max_full_pool_size, every
candidate anchor is included.  For larger pools, the stock-grind anchor is
always included plus up to max_alts_per_decision randomly-chosen alternatives.

The output is consumed by collect_branch_costs.py --sample-plan.

Example:
  python training/make_plan_benchmark.py \\
    --trace-jsonl training/data/clean/split_active_benchmark_traces_normalized.jsonl \\
    --out training/data/phase0_sample.jsonl \\
    --per-stratum 20 \\
    --seed 0
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRACE = (
    ROOT / "training" / "data" / "clean" / "split_active_benchmark_traces_normalized.jsonl"
)
DEFAULT_OUT = ROOT / "training" / "data" / "phase0_sample.jsonl"


STRATA: list[tuple[str, int, int]] = [
    # (name, min_pool, max_pool_inclusive)
    ("2", 2, 2),
    ("3", 3, 3),
    ("4-5", 4, 5),
    ("6-10", 6, 10),
    ("11+", 11, 10_000),
]


def anchor_str(value: Any) -> str | None:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def normalize_decisions(record: dict[str, Any]) -> list[dict[str, Any]]:
    decisions = record.get("splitDecisions") or record.get("steps") or []
    out: list[dict[str, Any]] = []
    for idx, decision in enumerate(decisions):
        pool = decision.get("pool") or decision.get("candidates") or []
        out.append(
            {
                "step": decision.get("step", idx),
                "pool": pool,
                "chosenAnchor": anchor_str(decision.get("chosenAnchor")),
            }
        )
    return out


def stratum_for(pool_size: int) -> str | None:
    for name, lo, hi in STRATA:
        if lo <= pool_size <= hi:
            return name
    return None


def collect_multi_candidate_decisions(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record_index, record in enumerate(records):
        case_id = f"{record_index:03d}"
        multi_index = 0
        for decision in normalize_decisions(record):
            pool = decision["pool"]
            pool_size = len(pool)
            if pool_size < 2:
                continue
            multi_index += 1  # 1-based index among the trace's multi-candidate decisions
            anchors = [anchor_str(c.get("anchor")) for c in pool]
            anchors = [a for a in anchors if a is not None]
            if len(anchors) < 2:
                continue
            stratum = stratum_for(pool_size)
            if stratum is None:
                continue
            rows.append(
                {
                    "case": case_id,
                    "recordIndex": record_index,
                    "traceStep": int(decision["step"]),
                    "multiStepIndex": multi_index,
                    "poolSize": pool_size,
                    "anchors": anchors,
                    "stockAnchor": decision["chosenAnchor"],
                    "stratum": stratum,
                }
            )
    return rows


def sample_plan(
    rows: list[dict[str, Any]],
    *,
    per_stratum: int,
    max_full_pool_size: int,
    max_alts_per_decision: int,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    by_stratum: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_stratum[row["stratum"]].append(row)

    selected: list[dict[str, Any]] = []
    for name, _lo, _hi in STRATA:
        bucket = by_stratum.get(name, [])
        rng.shuffle(bucket)
        take = bucket[:per_stratum]
        for row in take:
            pool_size = row["poolSize"]
            anchors = list(row["anchors"])
            stock = row["stockAnchor"]
            if pool_size <= max_full_pool_size:
                forced = anchors
            else:
                non_stock = [a for a in anchors if a != stock]
                rng.shuffle(non_stock)
                forced_alts = non_stock[:max_alts_per_decision]
                forced = ([stock] if stock and stock in anchors else []) + forced_alts
            seen: set[str] = set()
            dedup: list[str] = []
            for a in forced:
                if a and a not in seen:
                    dedup.append(a)
                    seen.add(a)
            plan_row = dict(row)
            plan_row["forcedAnchors"] = dedup
            selected.append(plan_row)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-jsonl", type=Path, default=DEFAULT_TRACE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--per-stratum",
        type=int,
        default=20,
        help="Number of decisions sampled per pool-size stratum",
    )
    parser.add_argument(
        "--max-full-pool-size",
        type=int,
        default=5,
        help="Pools at or below this size force every candidate",
    )
    parser.add_argument(
        "--max-alts-per-decision",
        type=int,
        default=4,
        help="For larger pools, force stock plus this many random alternatives",
    )
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    records = [json.loads(l) for l in args.trace_jsonl.read_text().splitlines() if l.strip()]
    rows = collect_multi_candidate_decisions(records)

    by_stratum_total: dict[str, int] = defaultdict(int)
    for row in rows:
        by_stratum_total[row["stratum"]] += 1

    plan = sample_plan(
        rows,
        per_stratum=args.per_stratum,
        max_full_pool_size=args.max_full_pool_size,
        max_alts_per_decision=args.max_alts_per_decision,
        seed=args.seed,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as h:
        for row in plan:
            h.write(json.dumps(row, sort_keys=True) + "\n")

    total_forced = sum(len(r["forcedAnchors"]) for r in plan)
    print(f"available multi-candidate decisions by stratum:")
    for name, _lo, _hi in STRATA:
        print(f"  {name:>5}: {by_stratum_total.get(name, 0)} total")
    selected_by_stratum: dict[str, int] = defaultdict(int)
    forced_by_stratum: dict[str, int] = defaultdict(int)
    for r in plan:
        selected_by_stratum[r["stratum"]] += 1
        forced_by_stratum[r["stratum"]] += len(r["forcedAnchors"])
    print("selected per stratum (decisions / total forced runs):")
    for name, _lo, _hi in STRATA:
        d = selected_by_stratum.get(name, 0)
        f = forced_by_stratum.get(name, 0)
        print(f"  {name:>5}: {d} decisions, {f} forced runs")
    print(f"plan written to {args.out}: {len(plan)} decisions, {total_forced} forced runs")


if __name__ == "__main__":
    main()
