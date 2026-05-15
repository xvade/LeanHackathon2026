"""Prepare a FineLean Phase 1 collection job.

Given:
  - A FineLean trace JSONL (`finelean_splits.jsonl` or equivalent)
  - The batch source directory (`GrindExtraction/.collect_scratch/`)

Produces:
  - A `benchmark.lean` mega-file with one `/- benchmark NNN: -/` block per
    sampled theorem, with `grind_collect` rewritten to `neural_grind`.
  - A `sample_plan.jsonl` whose `case` field matches the mega-benchmark's
    NNN indices, so `collect_branch_costs.py` can drive it without changes.

We require records with `theoremName` of the form
`«.collect_scratch».batch_NNNN` (FineLean batch tracer output). Records from
other sources (verified, workbook, numina) are skipped.

Mapping: trace records from batch_NNNN appear in groups of 20 in the JSONL,
in the order grind_collect processed them, which matches the order of the
20 theorems inside batch_NNNN.lean.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


THEOREM_NAME_RE = re.compile(r"batch_(\d{4})")


def parse_batch_id(theorem_name: str) -> int | None:
    m = THEOREM_NAME_RE.search(theorem_name or "")
    return int(m.group(1)) if m else None


def stratum_for(pool_size: int) -> str | None:
    if pool_size < 2:
        return None
    if pool_size == 2:
        return "2"
    if pool_size == 3:
        return "3"
    if pool_size <= 5:
        return "4-5"
    if pool_size <= 10:
        return "6-10"
    return "11+"


def anchor_str(value: Any) -> str | None:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def load_records_with_multi(trace_path: Path) -> list[dict[str, Any]]:
    """Return records that (a) have a batch_NNNN theoremName and (b) at least
    one multi-candidate decision. Each record is annotated with `batchId` and
    `recordIndexInTrace`."""
    records: list[dict[str, Any]] = []
    with trace_path.open() as h:
        for idx, line in enumerate(h):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            batch_id = parse_batch_id(r.get("theoremName", ""))
            if batch_id is None:
                continue
            has_multi = any(len(d.get("pool", [])) >= 2 for d in r.get("splitDecisions", []))
            if not has_multi:
                continue
            r["_batchId"] = batch_id
            r["_recordIndexInTrace"] = idx
            records.append(r)
    return records


def assign_batch_positions(records: list[dict[str, Any]]) -> None:
    """Set `_batchPos` (0..19) to each record based on its order within its batch.

    The trace JSONL groups records by batch, in the order grind_collect emitted
    them, which matches the source-file order of theorems in each batch."""
    counters: dict[int, int] = defaultdict(int)
    for r in records:
        bid = r["_batchId"]
        r["_batchPos"] = counters[bid]
        counters[bid] += 1


def find_theorem_blocks(batch_path: Path) -> list[str]:
    """Return the 20 raw text blocks (theorem + body) from a batch lean file,
    in source order. Each block starts at `section\\n` and ends at `end`.

    The structure of every batch file is, from collect_verified.py:
        import Mathlib
        import GrindExtraction
        set_option ...
        section
        theorem grind_collect_NNNNNN ... := by grind_collect
        end
        section
        theorem grind_collect_NNNNNN ... := by grind_collect
        end
        ...
    """
    text = batch_path.read_text()
    # Find every `section\n...end` block
    blocks: list[str] = []
    pattern = re.compile(r"^section\s*\n(.*?)^end\s*$", re.MULTILINE | re.DOTALL)
    for m in pattern.finditer(text):
        body = m.group(1)
        blocks.append(body)
    return blocks


def transform_block_to_neural(body: str, case_id: str, original_theorem_name: str) -> str:
    """Rewrite a `theorem ... := by grind_collect` block into a benchmark case
    suitable for the neural_grind pipeline:

      /- benchmark NNN: ... -/
      section bench_NNN
      <body with `by grind_collect` -> `by neural_grind`>
      end bench_NNN
    """
    # Replace the tactic; tolerate any whitespace
    body = re.sub(r":=\s*by\s+grind_collect\b", ":= by neural_grind", body)
    return (
        f"/- benchmark {case_id}: {original_theorem_name}\n"
        f"   source: finelean (batch source)\n"
        f"-/\n"
        f"section bench_{case_id}\n"
        f"{body.rstrip()}\n"
        f"end bench_{case_id}\n"
    )


def render_benchmark_lean(prep_rows: list[dict[str, Any]]) -> str:
    """Assemble the mega-benchmark .lean."""
    header = (
        "/-\n"
        "Generated FineLean mega-benchmark.\n"
        "Do not edit by hand; regenerate with training/make_plan_finelean.py.\n"
        "-/\n"
        "import Mathlib\n"
        "import NeuralTactic\n"
        "\n"
        "set_option maxHeartbeats 400000\n"
        "set_option linter.unusedVariables false\n"
        "set_option trace.grind.split false\n"
        "\n"
    )
    body_parts = [header]
    for row in prep_rows:
        body_parts.append(row["_caseBlock"])
        body_parts.append("\n")
    return "".join(body_parts)


def first_theorem_name(body: str) -> str:
    m = re.search(r"theorem\s+(\S+)", body)
    return m.group(1) if m else "?"


def build_sample_plan(
    records: list[dict[str, Any]],
    *,
    target_decisions: int,
    cap_per_decision: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Pick decisions stratified by pool size up to `target_decisions`.

    Returns a list of plan rows. Each row also carries the original record
    (annotated with _batchId / _batchPos) so we can later emit the matching
    Lean case block. case_id is assigned in order of selection (000000, 000001,
    ...) so the mega-benchmark and the plan stay in sync.
    """
    rng = random.Random(seed)

    # Build candidate plan rows (one per multi-cand decision)
    candidate_rows: list[dict[str, Any]] = []
    for rec in records:
        multi_idx = 0
        for d in rec.get("splitDecisions", []):
            pool = d.get("pool", [])
            if len(pool) < 2:
                continue
            multi_idx += 1
            anchors = [anchor_str(c.get("anchor")) for c in pool]
            anchors = [a for a in anchors if a is not None]
            if len(anchors) < 2:
                continue
            stratum = stratum_for(len(pool))
            if stratum is None:
                continue
            stock = anchor_str(d.get("chosenAnchor"))
            # cap-N: stock first, then candidates in pool order until cap reached
            forced: list[str] = []
            seen: set[str] = set()
            if stock and stock in anchors:
                forced.append(stock)
                seen.add(stock)
            for a in anchors:
                if len(forced) >= cap_per_decision:
                    break
                if a not in seen:
                    forced.append(a)
                    seen.add(a)
            candidate_rows.append({
                "_record": rec,
                "_multiStepIndex": multi_idx,
                "_traceStep": int(d.get("step", 0)),
                "_poolSize": len(pool),
                "_anchors": anchors,
                "_stockAnchor": stock,
                "_stratum": stratum,
                "_forcedAnchors": forced,
            })

    print(f"Available candidate-rows (multi-cand decisions in FineLean): {len(candidate_rows)}")

    # Group by stratum then sample
    by_strat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        by_strat[row["_stratum"]].append(row)
    for k, v in by_strat.items():
        rng.shuffle(v)
        print(f"  stratum {k}: {len(v)} available")

    # Allocate target across strata proportionally to availability
    strata_order = ["2", "3", "4-5", "6-10", "11+"]
    total_avail = sum(len(by_strat[s]) for s in strata_order)
    selected: list[dict[str, Any]] = []
    for s in strata_order:
        if not by_strat[s]:
            continue
        # Proportional but never more than available
        share = int(round(target_decisions * len(by_strat[s]) / total_avail))
        share = min(share, len(by_strat[s]))
        selected.extend(by_strat[s][:share])

    # If we underfilled due to rounding, top up uniformly
    if len(selected) < target_decisions:
        remaining_pool: list[dict[str, Any]] = []
        for s in strata_order:
            remaining_pool.extend(by_strat[s][int(round(target_decisions * len(by_strat[s]) / total_avail)):])
        rng.shuffle(remaining_pool)
        for row in remaining_pool:
            if len(selected) >= target_decisions:
                break
            selected.append(row)

    # Each selected row needs a unique theorem (case_id) in the mega-benchmark.
    # Multiple decisions can come from the same theorem — we still only emit
    # ONE benchmark case per theorem, but the plan rows for all its decisions
    # point at the same case_id.
    # Group by (batch_id, batch_pos) → unique theorem
    by_theorem: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        rec = row["_record"]
        by_theorem[(rec["_batchId"], rec["_batchPos"])].append(row)

    # Assign sequential case_ids (000000, 000001, ...) per theorem
    plan: list[dict[str, Any]] = []
    case_assigner = {}
    next_case_idx = 0
    for theorem_key in by_theorem:  # insertion order = first-seen order
        case_id = f"{next_case_idx:06d}"
        case_assigner[theorem_key] = case_id
        next_case_idx += 1
        # Each row in this theorem gets the same case_id
        for row in by_theorem[theorem_key]:
            plan.append({
                "case": case_id,
                "recordIndex": int(row["_record"]["_recordIndexInTrace"]),
                "traceStep": row["_traceStep"],
                "multiStepIndex": row["_multiStepIndex"],
                "poolSize": row["_poolSize"],
                "anchors": row["_anchors"],
                "stockAnchor": row["_stockAnchor"],
                "stratum": row["_stratum"],
                "forcedAnchors": row["_forcedAnchors"],
                "_batchId": row["_record"]["_batchId"],
                "_batchPos": row["_record"]["_batchPos"],
            })

    print(f"Selected {len(by_theorem)} unique theorems covering {len(plan)} decisions")
    return plan


def assemble_benchmark(
    plan: list[dict[str, Any]],
    batch_dir: Path,
) -> tuple[str, list[dict[str, Any]]]:
    """Build the mega-benchmark Lean text. Drop plan rows whose source block
    couldn't be located (e.g., malformed batch file).
    """
    # One block per unique theorem
    by_case: dict[str, dict[str, Any]] = {}
    for row in plan:
        by_case.setdefault(row["case"], row)

    blocks_cache: dict[int, list[str]] = {}
    prep_rows: list[dict[str, Any]] = []
    skipped_cases: set[str] = set()
    for case_id, sample_row in sorted(by_case.items()):
        batch_id = sample_row["_batchId"]
        pos = sample_row["_batchPos"]
        if batch_id not in blocks_cache:
            batch_path = batch_dir / f"batch_{batch_id:04d}.lean"
            if not batch_path.exists():
                skipped_cases.add(case_id)
                continue
            blocks_cache[batch_id] = find_theorem_blocks(batch_path)
        blocks = blocks_cache[batch_id]
        if pos >= len(blocks):
            skipped_cases.add(case_id)
            continue
        body = blocks[pos]
        original_name = first_theorem_name(body)
        case_block = transform_block_to_neural(body, case_id, original_name)
        prep_rows.append({"case": case_id, "_caseBlock": case_block,
                          "_batchId": batch_id, "_batchPos": pos,
                          "_originalName": original_name})

    if skipped_cases:
        print(f"WARN: dropped {len(skipped_cases)} cases whose source block could not be located")

    # Filter plan to only kept cases
    plan_kept = [r for r in plan if r["case"] not in skipped_cases]
    lean_text = render_benchmark_lean(prep_rows)
    return lean_text, plan_kept


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trace", type=Path, required=True,
                   help="finelean_splits.jsonl or equivalent")
    p.add_argument("--batch-dir", type=Path, required=True,
                   help="GrindExtraction/.collect_scratch/")
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--target-decisions", type=int, default=10000)
    p.add_argument("--cap-per-decision", type=int, default=16)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Reading trace: {args.trace}")
    records = load_records_with_multi(args.trace)
    print(f"  {len(records)} multi-candidate records from batch sources")

    assign_batch_positions(records)

    plan = build_sample_plan(
        records,
        target_decisions=args.target_decisions,
        cap_per_decision=args.cap_per_decision,
        seed=args.seed,
    )

    print("Assembling benchmark .lean ...")
    lean_text, plan_kept = assemble_benchmark(plan, args.batch_dir)

    bench_path = args.out_dir / "benchmark.lean"
    bench_path.write_text(lean_text)
    print(f"  wrote {bench_path} ({len(lean_text)//1024} KB)")

    plan_path = args.out_dir / "sample_plan.jsonl"
    with plan_path.open("w") as h:
        for row in plan_kept:
            # Strip private underscore-prefixed fields
            clean = {k: v for k, v in row.items() if not k.startswith("_")}
            h.write(json.dumps(clean, sort_keys=True) + "\n")
    print(f"  wrote {plan_path} ({len(plan_kept)} rows)")

    total_forced = sum(len(r["forcedAnchors"]) for r in plan_kept)
    print(f"  total forced runs in plan: {total_forced}")


if __name__ == "__main__":
    main()
