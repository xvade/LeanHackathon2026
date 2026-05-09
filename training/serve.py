"""
Inference server for neural_grind's subprocess integration.

Usage:
    python3 training/serve.py --model model.pt

Protocol (line-oriented JSON over stdin/stdout):
  Lean writes one JSON line per split decision:
    {"goalFeatures": {...}, "candidates": [{anchor, exprText, numCases, isRec, source}, ...]}
  This server responds with one line containing the chosen anchor as a decimal integer:
    12345678901234

The server loops until stdin is closed (EOF).
"""

import argparse
import json
import os
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).parent))
from features import batch_numeric, batch_trigrams
from model import SplitRanker


def load_model(path: str) -> SplitRanker:
    m = SplitRanker()
    m.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
    m.eval()
    return m


def score_candidates(model: SplitRanker, req: dict) -> torch.Tensor:
    cands = req.get("candidates", [])
    goal  = req.get("goalFeatures", {})
    if not cands:
        return torch.zeros(0)
    with torch.no_grad():
        numeric  = batch_numeric(cands, goal)
        text_ids = batch_trigrams(cands)
        return model(numeric, text_ids)


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
            else:
                best_anchor = 0
            print(best_anchor, flush=True)
        except Exception as e:
            # On any error, print 0 (Lean falls back to heuristic)
            print(0, flush=True)
            print(f"[serve.py error] {e}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Path to model checkpoint (.pt)")
    serve(parser.parse_args())
