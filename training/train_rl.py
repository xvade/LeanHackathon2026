"""
REINFORCE training for SplitRanker.

Unlike train.py (which imitates successful proofs only), this trainer uses
policy gradient on ALL proof attempts:
  reward = +reward_success for a successful proof
  reward = +reward_failure for a failed proof  (typically negative)

For each decision step in a proof, the gradient is:
  -log π(chosen | state) * (reward - baseline)

The baseline is the per-epoch mean reward, which is unbiased and requires no
extra hyperparameter.

Usage:
    python3 training/train_rl.py --data log.jsonl --out model.pt \\
        [--init existing.pt] [--epochs 30] [--lr 1e-3] \\
        [--reward-success 1.0] [--reward-failure -1.0]
"""

import argparse
import json
import random
import sys
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.optim import Adam

sys.path.insert(0, str(Path(__file__).parent))
from features import batch_numeric, batch_trigrams, context_trigrams, GRIND_STATE_MAX_EVENTS
from model import SplitRanker


def normalize_record(record: dict) -> dict | None:
    """
    Normalize to {outcome, steps} regardless of source schema:
      - neural_collect: {outcome, steps: [{candidates, chosenAnchor, goalFeatures}]}
      - grind_collect:  {solved,  splitDecisions: [{pool, chosenAnchor, goalFeatures}]}
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


def load_examples_rl(path: str, reward_success: float = 1.0,
                     reward_failure: float = -1.0) -> list[dict]:
    """
    Load all decision steps from JSONL, labelled with step-count-scaled rewards.
    Both successful and failed proofs are included (both schemas accepted).
    Steps with < 2 candidates are skipped (no real choice was made).

    Reward for success = reward_success / num_steps: shorter proofs score higher.
    Reward for failure = reward_failure (flat penalty regardless of steps taken).
    """
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
            if record is None:
                continue
            steps = record.get("steps", [])
            num_steps = max(len(steps), 1)
            if record.get("outcome") == "success":
                reward = reward_success / num_steps
            else:
                reward = reward_failure
            for step in steps:
                cands = step.get("candidates", [])
                chosen = step.get("chosenAnchor")
                if len(cands) < 2 or chosen is None:
                    continue
                # anchor may be int or string — compare as strings for safety
                chosen_s = str(chosen)
                target = next(
                    (i for i, c in enumerate(cands) if str(c["anchor"]) == chosen_s),
                    None,
                )
                if target is None:
                    continue
                examples.append({
                    "goalFeatures": step["goalFeatures"],
                    "candidates":   cands,
                    "target":       target,
                    "reward":       reward,
                    "statePP":      step.get("statePP", []),
                    "grindState":   step.get("grindState", []),
                })
    return examples


def train_rl(args) -> None:
    print(f"Loading data from {args.data} …", flush=True)
    examples = load_examples_rl(
        args.data,
        reward_success=args.reward_success,
        reward_failure=args.reward_failure,
    )
    if not examples:
        print("No multi-candidate decision steps found — nothing to train on.")
        return

    n_success = sum(1 for e in examples if e["reward"] > 0)
    n_failure = len(examples) - n_success
    print(f"Loaded {len(examples)} decision steps  "
          f"(+reward: {n_success}, -reward: {n_failure})", flush=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = SplitRanker().to(device)
    if args.init and Path(args.init).exists():
        print(f"Warm-starting from {args.init}", flush=True)
        model.load_state_dict(
            torch.load(args.init, map_location=device, weights_only=True)
        )
    optimizer = Adam(model.parameters(), lr=args.lr)
    print(f"device={device}", flush=True)

    for epoch in range(1, args.epochs + 1):
        random.shuffle(examples)

        # Per-epoch mean reward as baseline (unbiased, no extra hyperparameter)
        mean_reward = sum(e["reward"] for e in examples) / len(examples)

        model.train()
        optimizer.zero_grad()

        # Accumulate loss over all examples before stepping (batch update).
        # Per-example steps cause high-variance updates that diverge on small datasets.
        batch_loss = torch.zeros(1, device=device, requires_grad=False)
        updates = 0

        for ex in examples:
            advantage = ex["reward"] - mean_reward
            if abs(advantage) < 1e-6:
                continue

            cands    = ex["candidates"]
            goal     = ex["goalFeatures"]
            target   = ex["target"]

            numeric   = batch_numeric(cands, goal).to(device)
            text_ids  = batch_trigrams(cands).to(device)
            state_ids = context_trigrams(ex.get("statePP", [])).to(device)
            grind_ids = context_trigrams(ex.get("grindState", []),
                                         max_events=GRIND_STATE_MAX_EVENTS).to(device)

            scores    = model(numeric, text_ids, state_ids, grind_ids)   # (N,)
            log_probs = F.log_softmax(scores, dim=0)      # (N,)

            # REINFORCE: maximise E[log π(a) * advantage]; average over batch
            batch_loss = batch_loss + (-log_probs[target] * advantage)
            updates += 1

        if updates > 0:
            avg_loss_t = batch_loss / updates
            avg_loss_t.backward()
            # Clip gradients to prevent runaway updates on small datasets
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            avg_loss = avg_loss_t.item()
        else:
            avg_loss = 0.0

        print(
            f"Epoch {epoch:3d}/{args.epochs}  "
            f"loss={avg_loss:.4f}  baseline={mean_reward:+.3f}  "
            f"updates={updates}",
            flush=True,
        )

    torch.save(model.state_dict(), args.out)
    print(f"Model saved to {args.out}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="REINFORCE policy gradient training for SplitRanker."
    )
    parser.add_argument("--data",           required=True, help="JSONL log file")
    parser.add_argument("--out",            required=True, help="Output model checkpoint")
    parser.add_argument("--init",           default=None,  help="Warm-start checkpoint")
    parser.add_argument("--epochs",         type=int,   default=30)
    parser.add_argument("--lr",             type=float, default=1e-4)
    parser.add_argument("--reward-success", type=float, default=1.0)
    parser.add_argument("--reward-failure", type=float, default=-1.0)
    train_rl(parser.parse_args())
