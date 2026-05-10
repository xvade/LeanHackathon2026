"""
Inference server for neural_grind's subprocess integration.

Usage:
    python3 training/serve.py --model model.pt

Protocol (line-oriented JSON over stdin/stdout):
  Lean writes one JSON line per split decision:
    {"goalFeatures": {...}, "candidates": [{anchor, exprText, numCases, isRec, source}, ...]}
  This server responds with one line containing the chosen anchor and top-1/top-2
  score margin in milli-logits:
    12345678901234 271

The server loops until stdin is closed (EOF).
"""

import argparse
import json
import os
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent.parent))  # training/ fallback
from features import batch_numeric
from model import SplitRanker


def load_model(path: str) -> SplitRanker:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    state = torch.load(path, map_location=device, weights_only=True)
    hidden_dim = int(state["fc1.weight"].shape[0])
    m = SplitRanker(hidden=hidden_dim).to(device)
    m.load_state_dict(state)
    m.eval()
    return m


def score_candidates(model: SplitRanker, req: dict) -> torch.Tensor:
    cands = req.get("candidates", [])
    goal  = req.get("goalFeatures", {})
    if not cands:
        return torch.zeros(0)
    device = next(model.parameters()).device
    with torch.no_grad():
        grind_events = req.get("grindState", [])
        numeric = batch_numeric(cands, goal, grind_events).to(device)
        return model(numeric)


def score_margin_milli(scores: torch.Tensor) -> int:
    if scores.numel() < 2:
        return 1_000_000_000
    top = torch.topk(scores, k=2).values
    margin = float(top[0].item() - top[1].item())
    return max(0, int(round(margin * 1000)))


def serve(args):
    model = load_model(args.model)
    # GRIND_TEMPERATURE > 0 enables stochastic sampling (for RL exploration).
    temperature = float(os.environ.get("GRIND_TEMPERATURE", "0.0"))
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req    = json.loads(line)
            scores = score_candidates(model, req)
            cands  = req.get("candidates", [])
            if cands and scores.numel() > 0:
                if temperature > 0:
                    probs    = torch.softmax(scores / temperature, dim=0)
                    best_idx = int(torch.multinomial(probs, 1).item())
                else:
                    best_idx = int(scores.argmax().item())
                best_anchor = cands[best_idx]["anchor"]
                margin_milli = score_margin_milli(scores)
            else:
                best_anchor = 0
                margin_milli = 0
            print(f"{best_anchor} {margin_milli}", flush=True)
        except Exception as e:
            # On any error, print 0 (Lean falls back to heuristic)
            print("0 0", flush=True)
            print(f"[serve.py error] {e}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Path to model checkpoint (.pt)")
    serve(parser.parse_args())
