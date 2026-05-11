"""Line-oriented Python server for the exp09 neural-grind model."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from features import batch_numeric
from model import SplitRanker


def load_model(path: Path) -> SplitRanker:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = SplitRanker().to(device)
    model.load_state_dict(torch.load(path, map_location=device, weights_only=True))
    model.eval()
    return model


def score_margin_milli(scores: torch.Tensor) -> int:
    if scores.numel() < 2:
        return 1_000_000_000
    top = torch.topk(scores, k=2).values
    margin = float(top[0].item() - top[1].item())
    return max(0, int(round(margin * 1000)))


def serve(model: SplitRanker) -> None:
    device = next(model.parameters()).device
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            cands = req.get("candidates", [])
            if not cands:
                print("0 0", flush=True)
                continue
            with torch.no_grad():
                numeric = batch_numeric(
                    cands,
                    req.get("goalFeatures", {}),
                    req.get("grindState", []),
                ).to(device)
                scores = model(numeric)
            best_idx = int(scores.argmax().item())
            print(f"{cands[best_idx]['anchor']} {score_margin_milli(scores)}", flush=True)
        except Exception:
            print("0 0", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    serve(load_model(Path(args.model)))


if __name__ == "__main__":
    main()
