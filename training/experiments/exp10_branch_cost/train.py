"""EXP-10: train a split ranker from branch-cost labels.

Loads:
  - branch_costs.jsonl  (Phase 1 output: per (case, decision, anchor) splitsToClose)
  - trace.jsonl         (source split-active benchmark traces with full pool features)

For each multi-candidate decision, joins the branch-cost rows back to the trace
pool to recover per-candidate features (numCases, generation, source, etc.).
The training target per candidate is `splitsToClose` (lower = better) when the
forced run succeeded; failures and timeouts are dropped.

Loss is pairwise: for every pair of successful candidates (i, j) at the same
decision, train `score(i) > score(j)` iff `splitsToClose_i < splitsToClose_j`.
Equal splits are skipped (no signal).

Train/eval split is by **theorem** (case_id), 80/20, so same-decision rows
never leak across split.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
# Order matters: exp09_heuristics/features.py extends the base features and
# defines IS_GRIND_CHOICE_FEATURE_INDEX; we want it to win over the top-level
# features.py. So put exp09 directory first.
sys.path.insert(0, str(HERE.parent.parent))                  # for top-level features.py (base)
sys.path.insert(0, str(HERE.parent / "exp09_heuristics"))   # for exp09 features.py (overrides)

import torch
import torch.nn as nn
from torch.optim import Adam

from features import batch_numeric, NUMERIC_DIM, IS_GRIND_CHOICE_FEATURE_INDEX
from model import SplitRanker


def load_trace_index(trace_path: Path) -> dict[tuple[str, int], dict[str, Any]]:
    """Map (case_id, multiStepIndex) -> decision info: pool, goalFeatures, grindState."""
    out: dict[tuple[str, int], dict[str, Any]] = {}
    with trace_path.open() as h:
        for record_index, line in enumerate(h):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            case_id = f"{record_index:03d}"
            multi = 0
            for d in r.get("splitDecisions", []):
                pool = d.get("pool", [])
                if len(pool) < 2:
                    continue
                multi += 1
                out[(case_id, multi)] = {
                    "goalFeatures": d.get("goalFeatures", {}),
                    "grindState": d.get("grindState", []),
                    "pool": pool,
                    "chosenAnchor": d.get("chosenAnchor"),
                    "traceStep": d.get("step"),
                }
    return out


def load_branch_costs(
    paths: list[Path],
) -> dict[tuple[str, int], dict[str, int]]:
    """Map (case_id, multiStepIndex) -> {anchor_str: splitsToClose} for successful rows."""
    out: dict[tuple[str, int], dict[str, int]] = defaultdict(dict)
    for path in paths:
        with path.open() as h:
            for line in h:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if r.get("status") != "success":
                    continue
                splits = r.get("splitsToClose")
                if not isinstance(splits, int):
                    continue
                key = (str(r["case"]), int(r["multiStepIndex"]))
                anchor = str(r["anchor"])
                # If duplicate (shouldn't happen, but be safe), keep the smaller cost
                prev = out[key].get(anchor)
                if prev is None or splits < prev:
                    out[key][anchor] = splits
    return out


def build_examples(
    trace_index: dict[tuple[str, int], dict[str, Any]],
    cost_index: dict[tuple[str, int], dict[str, int]],
    ablate_is_grind_choice: bool,
) -> list[dict[str, Any]]:
    """Return one training example per decision with measured costs."""
    examples: list[dict[str, Any]] = []
    for key, td in trace_index.items():
        costs = cost_index.get(key, {})
        if not costs:
            continue
        # Build candidate list ordered as in the trace pool; keep only those with cost.
        pool = td["pool"]
        cands_with_costs: list[tuple[dict[str, Any], int]] = []
        for c in pool:
            a = str(c.get("anchor"))
            if a in costs:
                cands_with_costs.append((c, costs[a]))
        if len(cands_with_costs) < 2:
            # Need at least two measured candidates to form a pair.
            continue
        cands = [c for c, _ in cands_with_costs]
        labels = [s for _, s in cands_with_costs]
        # Pre-compute numeric features for this decision.
        numeric = batch_numeric(
            cands,
            td["goalFeatures"],
            td["grindState"],
            mask_grind_choice=ablate_is_grind_choice,
        ).contiguous()
        examples.append({
            "case": key[0],
            "multiStepIndex": key[1],
            "numeric": numeric,        # (N, NUMERIC_DIM)
            "splits": labels,          # list[int], length N
            "stockAnchor": td.get("chosenAnchor"),
            "anchors": [str(c.get("anchor")) for c in cands],
            "poolSize": len(pool),
        })
    return examples


def pairwise_loss_for_decision(
    scores: torch.Tensor,
    splits: list[int],
) -> torch.Tensor:
    """Sum of binary cross-entropy over candidate pairs with strict cost diff.

    For each (i, j) with splits_i < splits_j, target=1 (i should rank higher);
    we minimize BCE-with-logits on (score_i - score_j).
    """
    n = scores.shape[0]
    losses = []
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if splits[i] >= splits[j]:
                continue
            diff = scores[i] - scores[j]
            losses.append(torch.nn.functional.softplus(-diff))  # = -log(sigmoid(diff))
    if not losses:
        return scores.new_zeros(())
    return torch.stack(losses).mean()


def split_train_eval(
    examples: list[dict[str, Any]],
    eval_frac: float,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases = sorted({ex["case"] for ex in examples})
    rng = random.Random(seed)
    rng.shuffle(cases)
    cutoff = int(len(cases) * (1.0 - eval_frac))
    train_cases = set(cases[:cutoff])
    train = [ex for ex in examples if ex["case"] in train_cases]
    evl = [ex for ex in examples if ex["case"] not in train_cases]
    return train, evl


def zero_input_feature(model: SplitRanker, idx: int) -> None:
    with torch.no_grad():
        model.fc1.weight[:, idx].zero_()


def evaluate(
    model: SplitRanker,
    examples: list[dict[str, Any]],
    device: torch.device,
) -> dict[str, float]:
    """Compute eval metrics: pairwise accuracy and best@1 metrics vs stock."""
    model.eval()
    n_pairs = 0
    n_pairs_correct = 0
    decisions_total = 0
    stock_present = 0
    model_picks_best = 0
    model_picks_stock = 0
    model_beats_stock = 0  # model's pick has strictly fewer splits than stock's measured cost
    model_ties_stock = 0
    total_splits_saved = 0
    with torch.no_grad():
        for ex in examples:
            scores = model(ex["numeric"].to(device)).cpu().numpy().tolist()
            splits = ex["splits"]
            n = len(splits)
            # Pairwise accuracy on strict pairs.
            for i in range(n):
                for j in range(i + 1, n):
                    if splits[i] == splits[j]:
                        continue
                    n_pairs += 1
                    better = i if splits[i] < splits[j] else j
                    pred_better = i if scores[i] > scores[j] else j
                    if pred_better == better:
                        n_pairs_correct += 1
            decisions_total += 1
            # Model's argmax pick
            best_score_idx = max(range(n), key=lambda i: scores[i])
            best_actual_idx = min(range(n), key=lambda i: splits[i])
            if splits[best_score_idx] == splits[best_actual_idx]:
                model_picks_best += 1
            # Stock comparison
            stock_anchor = ex.get("stockAnchor")
            if stock_anchor and stock_anchor in ex["anchors"]:
                stock_idx = ex["anchors"].index(stock_anchor)
                stock_present += 1
                if best_score_idx == stock_idx:
                    model_picks_stock += 1
                elif splits[best_score_idx] < splits[stock_idx]:
                    model_beats_stock += 1
                    total_splits_saved += splits[stock_idx] - splits[best_score_idx]
                elif splits[best_score_idx] == splits[stock_idx]:
                    model_ties_stock += 1
    pct = lambda a, b: (100.0 * a / b) if b > 0 else float("nan")
    return {
        "pairwise_pairs": n_pairs,
        "pairwise_acc": pct(n_pairs_correct, n_pairs),
        "decisions": decisions_total,
        "pick_best_pct": pct(model_picks_best, decisions_total),
        "stock_present": stock_present,
        "pick_stock_pct": pct(model_picks_stock, stock_present),
        "beats_stock_pct": pct(model_beats_stock, stock_present),
        "ties_stock_pct": pct(model_ties_stock, stock_present),
        "splits_saved_total": total_splits_saved,
        "splits_saved_per_decision_with_stock": (
            total_splits_saved / stock_present if stock_present else 0.0
        ),
    }


def train(args: argparse.Namespace) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={device}", flush=True)

    print("Loading trace index...", flush=True)
    trace_index = load_trace_index(Path(args.trace))
    print(f"  {len(trace_index)} multi-candidate decisions in trace", flush=True)

    print("Loading branch costs...", flush=True)
    cost_index = load_branch_costs([Path(p) for p in args.data])
    print(f"  {len(cost_index)} decisions with at least one successful cost row", flush=True)

    examples = build_examples(trace_index, cost_index, args.ablate_is_grind_choice)
    print(f"  {len(examples)} usable training examples (≥2 measured candidates)", flush=True)
    if not examples:
        print("No examples — bailing.")
        return

    train_exs, eval_exs = split_train_eval(examples, args.eval_frac, args.seed)
    print(f"  train: {len(train_exs)} decisions across {len({e['case'] for e in train_exs})} theorems")
    print(f"  eval:  {len(eval_exs)} decisions across {len({e['case'] for e in eval_exs})} theorems")

    model = SplitRanker(hidden=args.hidden_dim).to(device)
    if args.ablate_is_grind_choice:
        zero_input_feature(model, IS_GRIND_CHOICE_FEATURE_INDEX)
        print(f"Ablating isGrindChoice at index {IS_GRIND_CHOICE_FEATURE_INDEX}.")

    optimizer = Adam(model.parameters(), lr=args.lr)

    for epoch in range(1, args.epochs + 1):
        random.seed(args.seed + epoch)
        random.shuffle(train_exs)
        model.train()
        total_loss = 0.0
        nonzero_batches = 0
        for ex in train_exs:
            numeric = ex["numeric"].to(device)
            scores = model(numeric)
            loss = pairwise_loss_for_decision(scores, ex["splits"])
            if float(loss.item()) == 0.0:
                continue
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            if args.ablate_is_grind_choice:
                zero_input_feature(model, IS_GRIND_CHOICE_FEATURE_INDEX)
            total_loss += float(loss.item())
            nonzero_batches += 1

        if epoch == 1 or epoch % args.eval_every == 0 or epoch == args.epochs:
            train_metrics = evaluate(model, train_exs, device)
            eval_metrics = evaluate(model, eval_exs, device)
            print(
                f"Epoch {epoch:3d}  loss={total_loss/max(nonzero_batches,1):.4f}  "
                f"train_pairwise={train_metrics['pairwise_acc']:.1f}%  "
                f"eval_pairwise={eval_metrics['pairwise_acc']:.1f}%  "
                f"eval_pick_best={eval_metrics['pick_best_pct']:.1f}%  "
                f"eval_beats_stock={eval_metrics['beats_stock_pct']:.1f}%  "
                f"eval_splits_saved={eval_metrics['splits_saved_total']}",
                flush=True,
            )

    # Final detailed eval
    print("\n=== Final eval ===")
    em = evaluate(model, eval_exs, device)
    for k, v in em.items():
        print(f"  {k}: {v}")

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "state_dict": model.state_dict(),
            "hidden": args.hidden_dim,
            "ablate_is_grind_choice": args.ablate_is_grind_choice,
            "eval_metrics": em,
        }, args.out)
        print(f"Model saved to {args.out}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", nargs="+", required=True,
                   help="One or more branch_costs.jsonl paths")
    p.add_argument(
        "--trace",
        default=str(Path(__file__).resolve().parents[2] /
                    "data" / "clean" /
                    "split_active_benchmark_traces_normalized.jsonl"),
    )
    p.add_argument("--out", help="Output checkpoint path (optional)")
    p.add_argument("--epochs", type=int, default=200)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--hidden-dim", type=int, default=128)
    p.add_argument("--eval-frac", type=float, default=0.2)
    p.add_argument("--eval-every", type=int, default=10)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument(
        "--ablate-is-grind-choice",
        action="store_true",
        default=True,
        help="Mask isGrindChoice (default: True; required for honest training)",
    )
    return p.parse_args()


if __name__ == "__main__":
    train(parse_args())
