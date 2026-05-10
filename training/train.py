"""
Train SplitRanker from JSONL data collected by neural_grind.

Usage:
    python3 training/train.py --data log.jsonl --out model.pt [--epochs 20] [--lr 1e-3]

Each JSONL line is one proof record:
    {"proofId": N, "outcome": "success"|"failure", "steps": [
        {"step": N, "goalFeatures": {...}, "candidates": [...], "chosenAnchor": N},
        ...
    ]}

Only successful proofs are used for training. For each decision step, the chosen
candidate is the positive example; all others are negatives. We train with a
softmax cross-entropy (list-wise ranking) loss.
"""

import argparse
import json
import sys
from pathlib import Path

import torch
import torch.nn as nn
from torch.optim import Adam

# Allow imports from this directory
sys.path.insert(0, str(Path(__file__).parent))
from features import batch_numeric, batch_trigrams, context_trigrams, GRIND_STATE_MAX_EVENTS
from model import SplitRanker


def normalize_record(record: dict) -> dict | None:
    """
    Normalize a proof record to a common schema regardless of source:
      - neural_collect:  {outcome, steps: [{candidates, chosenAnchor, goalFeatures}]}
      - grind_collect:   {solved,  splitDecisions: [{pool, chosenAnchor, goalFeatures}]}
    Returns a dict with {outcome, steps} or None if unrecognized.
    """
    if "outcome" in record:
        return record
    if "solved" in record and "splitDecisions" in record:
        return {
            "outcome": "success" if record["solved"] else "failure",
            "steps": [
                {
                    "step":         d.get("step", i),
                    "goalFeatures": d.get("goalFeatures", {}),
                    "candidates":   d.get("pool", []),
                    "chosenAnchor": d.get("chosenAnchor"),
                    "statePP":      d.get("statePP", []),
                    "grindState":   d.get("grindState", []),
                }
                for i, d in enumerate(record["splitDecisions"])
            ],
        }
    return None


def load_examples(path: str) -> list[dict]:
    """Return list of decision steps from successful proofs (both schemas)."""
    examples = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            record = normalize_record(record)
            if record is None or record.get("outcome") != "success":
                continue
            for step in record.get("steps", []):
                cands = step.get("candidates", [])
                chosen = step.get("chosenAnchor")
                if len(cands) < 2 or chosen is None:
                    continue
                # anchor may be int or string — compare as strings for safety
                chosen_s = str(chosen)
                target_idx = next(
                    (i for i, c in enumerate(cands) if str(c["anchor"]) == chosen_s),
                    None,
                )
                if target_idx is None:
                    continue
                examples.append({
                    "goalFeatures": step["goalFeatures"],
                    "candidates":   cands,
                    "target":       target_idx,
                    "statePP":      step.get("statePP", []),
                    "grindState":   step.get("grindState", []),
                })
    return examples


def train(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Loading data from {args.data} …", flush=True)
    examples = load_examples(args.data)
    if not examples:
        print("No training examples found (need successful proofs with ≥2 candidates).")
        return

    print(f"Loaded {len(examples)} decision steps.  device={device}", flush=True)
    model = SplitRanker().to(device)
    optimizer = Adam(model.parameters(), lr=args.lr)
    loss_fn = nn.CrossEntropyLoss()

    for epoch in range(1, args.epochs + 1):
        total_loss = 0.0
        correct = 0
        model.train()
        for ex in examples:
            cands  = ex["candidates"]
            goal   = ex["goalFeatures"]
            target = ex["target"]

            numeric   = batch_numeric(cands, goal).to(device)
            text_ids  = batch_trigrams(cands).to(device)
            state_ids = context_trigrams(ex.get("statePP", [])).to(device)
            grind_ids = context_trigrams(ex.get("grindState", []),
                                         max_events=GRIND_STATE_MAX_EVENTS).to(device)
            target_t  = torch.tensor([target], dtype=torch.long, device=device)

            scores = model(numeric, text_ids, state_ids, grind_ids)
            loss   = loss_fn(scores.unsqueeze(0), target_t)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            if scores.argmax().item() == target:
                correct += 1

        acc = correct / len(examples) * 100
        print(f"Epoch {epoch:3d}/{args.epochs}  loss={total_loss/len(examples):.4f}  acc={acc:.1f}%", flush=True)

    torch.save(model.state_dict(), args.out)
    print(f"Model saved to {args.out}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data",   required=True, help="Path to JSONL log file")
    parser.add_argument("--out",    required=True, help="Output model checkpoint path")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--lr",     type=float, default=1e-3)
    train(parser.parse_args())
