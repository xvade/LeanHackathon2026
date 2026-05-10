"""EXP-08 train — numeric + pool aggregates + grindState counts, no text."""
import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.append(str(HERE.parent.parent))  # training/ fallback

import torch
import torch.nn as nn
from torch.optim import Adam
from features import batch_numeric
from model import SplitRanker


def normalize_record(record: dict) -> dict | None:
    if "outcome" in record:
        return record
    if "solved" in record and "splitDecisions" in record:
        return {
            "outcome": "success" if record["solved"] else "failure",
            "steps": [
                {"step": d.get("step", i), "goalFeatures": d.get("goalFeatures", {}),
                 "candidates": d.get("pool", []), "chosenAnchor": d.get("chosenAnchor"),
                 "grindState": d.get("grindState", [])}
                for i, d in enumerate(record["splitDecisions"])
            ],
        }
    return None


def load_examples_from_path(path: str) -> list[dict]:
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
            
            steps = record.get("steps", [])
            total_splits = len(steps)
            if total_splits == 0:
                continue
            
            # Efficiency weight: bias toward shorter proofs.
            # 2 splits -> weight ~0.71
            # 100 splits -> weight ~0.1
            # Using 1 / sqrt(total_splits) for a moderate bias.
            sample_weight = 1.0 / (total_splits ** 0.5)

            for step in steps:
                cands = step.get("candidates", [])
                chosen = step.get("chosenAnchor")
                if len(cands) < 2 or chosen is None:
                    continue
                chosen_s = str(chosen)
                target_idx = next(
                    (i for i, c in enumerate(cands) if str(c["anchor"]) == chosen_s), None)
                if target_idx is None:
                    continue
                examples.append({
                    "goalFeatures": step["goalFeatures"],
                    "candidates":   cands,
                    "target":       target_idx,
                    "grindState":   step.get("grindState", []),
                    "weight":       sample_weight,
                })
    return examples


def load_examples(paths: list[str]) -> list[dict]:
    examples = []
    for path in paths:
        loaded = load_examples_from_path(path)
        print(f"  {path}: {len(loaded)} decision steps", flush=True)
        examples.extend(loaded)
    return examples


def train(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Loading data:", flush=True)
    examples = load_examples(args.data)
    if not examples:
        print("No training examples found.")
        return
    print(f"Loaded {len(examples)} decision steps.  device={device}", flush=True)

    print("Precomputing numeric features …", flush=True)
    groups: dict[int, list[tuple[torch.Tensor, int, float]]] = defaultdict(list)
    for ex in examples:
        numeric = batch_numeric(
            ex["candidates"],
            ex["goalFeatures"],
            ex.get("grindState", []),
        ).contiguous()
        groups[int(numeric.shape[0])].append((numeric, int(ex["target"]), float(ex["weight"])))
    print(
        "Candidate-pool groups: " +
        ", ".join(f"{n}×{len(v)}" for n, v in sorted(groups.items())),
        flush=True,
    )

    model = SplitRanker(hidden=args.hidden_dim).to(device)
    optimizer = Adam(model.parameters(), lr=args.lr)
    loss_fn = nn.CrossEntropyLoss(reduction='none')

    for epoch in range(1, args.epochs + 1):
        total_loss = 0.0
        weighted_total_loss = 0.0
        correct = 0
        total = 0
        model.train()
        batches: list[list[tuple[torch.Tensor, int, float]]] = []
        for group in groups.values():
            random.shuffle(group)
            for i in range(0, len(group), args.batch_size):
                batches.append(group[i:i + args.batch_size])
        random.shuffle(batches)

        for batch in batches:
            batch_size = len(batch)
            num_candidates = int(batch[0][0].shape[0])
            feature_dim = int(batch[0][0].shape[1])
            numeric = torch.stack([x for x, _, _ in batch], dim=0).to(device)
            target_t = torch.tensor(
                [target for _, target, _ in batch],
                dtype=torch.long,
                device=device,
            )
            weight_t = torch.tensor(
                [w for _, _, w in batch],
                dtype=torch.float32,
                device=device,
            )

            scores = model(numeric.reshape(batch_size * num_candidates, feature_dim))
            scores = scores.reshape(batch_size, num_candidates)
            
            raw_losses = loss_fn(scores, target_t)
            weighted_loss = (raw_losses * weight_t).mean()

            optimizer.zero_grad()
            weighted_loss.backward()
            optimizer.step()

            total_loss += raw_losses.mean().item() * batch_size
            weighted_total_loss += weighted_loss.item() * batch_size
            correct += int((scores.argmax(dim=1) == target_t).sum().item())
            total += batch_size

        acc = correct / total * 100
        print(f"Epoch {epoch:3d}/{args.epochs}  "
              f"loss={total_loss/total:.4f}  weighted_loss={weighted_total_loss/total:.4f}  acc={acc:.1f}%", flush=True)

    torch.save(model.state_dict(), args.out)
    print(f"Model saved to {args.out}", flush=True)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data",   required=True, nargs="+")
    p.add_argument("--out",    required=True)
    p.add_argument("--epochs", type=int, default=40)
    p.add_argument("--lr",     type=float, default=1e-3)
    p.add_argument("--batch-size", type=int, default=512)
    p.add_argument("--hidden-dim", type=int, default=256)
    return p.parse_args()


if __name__ == "__main__":
    train(parse_args())
