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
import importlib.util

import torch.nn.functional as F
from torch.optim import Adam

TRAINING = Path(__file__).parent
EXPERIMENTS = TRAINING / "experiments"


def load_exp_modules(exp_dir: Path | None):
    """Load features and model modules from an experiment dir (or base training/)."""
    base = TRAINING
    feat_path  = (exp_dir / "features.py") if exp_dir and (exp_dir / "features.py").exists() \
                 else base / "features.py"
    model_path = (exp_dir / "model.py")    if exp_dir and (exp_dir / "model.py").exists()    \
                 else base / "model.py"

    spec = importlib.util.spec_from_file_location("_rl_features", feat_path)
    feat_mod = importlib.util.module_from_spec(spec)
    sys.modules["features"] = feat_mod
    spec.loader.exec_module(feat_mod)

    spec = importlib.util.spec_from_file_location("_rl_model", model_path)
    mod_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod_mod)

    sys.modules.pop("features", None)
    return feat_mod, mod_mod


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


def load_examples_rl(path: str | list[str], reward_success: float = 1.0,
                     reward_failure: float = -1.0) -> list[dict]:
    """
    Load all decision steps from JSONL, labelled with step-count-scaled rewards.
    Both successful and failed proofs are included (both schemas accepted).
    Steps with < 2 candidates are skipped (no real choice was made).
    Accepts a single path or a list of paths.

    Reward for success = reward_success / num_steps: shorter proofs score higher.
    Reward for failure = reward_failure (flat penalty regardless of steps taken).
    """
    paths = [path] if isinstance(path, str) else path
    examples = []
    for path in paths:
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
    exp_dir = Path(args.exp) if args.exp else EXPERIMENTS / "exp08_num_pool_counts"
    feat_mod, mod_mod = load_exp_modules(exp_dir)
    batch_numeric = feat_mod.batch_numeric
    has_text      = hasattr(feat_mod, "batch_trigrams")
    has_context   = hasattr(feat_mod, "context_trigrams")
    grind_max     = getattr(feat_mod, "GRIND_STATE_MAX_EVENTS", 30)
    SplitRanker   = mod_mod.SplitRanker
    print(f"Experiment: {exp_dir.name}  text={has_text}  context={has_context}", flush=True)

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

            cands  = ex["candidates"]
            goal   = ex["goalFeatures"]
            target = ex["target"]

            try:
                try:
                    numeric = batch_numeric(cands, goal, ex.get("grindState", [])).to(device)
                except TypeError:
                    numeric = batch_numeric(cands, goal).to(device)
                kwargs = {"numeric": numeric}
                if has_text:
                    kwargs["text_ids"] = feat_mod.batch_trigrams(cands).to(device)
                if has_context:
                    kwargs["state_ids"] = feat_mod.context_trigrams(
                        ex.get("statePP", [])).to(device)
                    kwargs["grind_ids"] = feat_mod.context_trigrams(
                        ex.get("grindState", []), max_events=grind_max).to(device)
                scores = model(**kwargs)   # (N,)
            except Exception:
                continue

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
    parser.add_argument("--data",           required=True, action="append",
                        help="JSONL data file (repeatable for multiple files)")
    parser.add_argument("--out",            required=True, help="Output model checkpoint")
    parser.add_argument("--init",           default=None,  help="Warm-start checkpoint")
    parser.add_argument("--exp",            default=None,
                        help="Experiment dir for features/model (default: exp08_num_pool_counts)")
    parser.add_argument("--epochs",         type=int,   default=30)
    parser.add_argument("--lr",             type=float, default=1e-4)
    parser.add_argument("--reward-success", type=float, default=1.0)
    parser.add_argument("--reward-failure", type=float, default=-1.0)
    train_rl(parser.parse_args())
