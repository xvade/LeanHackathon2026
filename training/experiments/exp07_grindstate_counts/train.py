"""EXP-07 train — passes grindState events to batch_numeric as counts."""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.append(str(HERE.parent))  # training/

import torch
import torch.nn as nn
from torch.optim import Adam
from features import batch_numeric, batch_trigrams, context_trigrams
from model import SplitRanker

sys.path.append(str(HERE.parent.parent))
from train import normalize_record


def load_examples(path: str) -> list[dict]:
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
                chosen_s = str(chosen)
                target_idx = next(
                    (i for i, c in enumerate(cands) if str(c["anchor"]) == chosen_s), None)
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
        print("No training examples found.")
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

            numeric   = batch_numeric(cands, goal, ex.get("grindState", [])).to(device)
            text_ids  = batch_trigrams(cands).to(device)
            state_ids = context_trigrams(ex.get("statePP", [])).to(device)
            target_t  = torch.tensor([target], dtype=torch.long, device=device)

            scores = model(numeric, text_ids, state_ids)
            loss   = loss_fn(scores.unsqueeze(0), target_t)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            if scores.argmax().item() == target:
                correct += 1

        acc = correct / len(examples) * 100
        print(f"Epoch {epoch:3d}/{args.epochs}  "
              f"loss={total_loss/len(examples):.4f}  acc={acc:.1f}%", flush=True)

    torch.save(model.state_dict(), args.out)
    print(f"Model saved to {args.out}", flush=True)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data",   required=True)
    p.add_argument("--out",    required=True)
    p.add_argument("--epochs", type=int, default=40)
    p.add_argument("--lr",     type=float, default=1e-3)
    return p.parse_args()


if __name__ == "__main__":
    train(parse_args())
