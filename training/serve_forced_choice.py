"""Forced-choice server for branch-cost data collection.

The server ignores the model path that Lean passes and chooses a configured
anchor at one split step.  All other steps default to stock grind's marked
choice, which lets branch-cost runs isolate the downstream effect of one forced
candidate.

Configuration is via environment variables because `neural_grind` starts
servers as:

  python serve_forced_choice.py --model <ignored>

Override target — exactly one of the following:
  GRIND_FORCE_MULTI_STEP  1-based count of multi-candidate queries (preferred —
                          aligns with trace's multi-candidate decision indices,
                          robust to single-candidate queries reordering)
  GRIND_FORCE_STEP        1-based raw query index (legacy)

Required:
  GRIND_FORCE_ANCHOR      anchor to return at the target query

Optional:
  GRIND_FORCE_AFTER       stock (default) or fallback
"""

from __future__ import annotations

import argparse
import json
import os
import sys


BIG_MARGIN = 1_000_000_000


def env_int(name: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def stock_choice(req: dict) -> int:
    for cand in req.get("candidates", []):
        flag = cand.get("isGrindChoice", False)
        if flag is True or (isinstance(flag, str) and flag.lower() == "true"):
            return int(cand.get("anchor", 0))
    return 0


def num_candidates(req: dict) -> int:
    gf = req.get("goalFeatures") or {}
    n = gf.get("numCandidates")
    if isinstance(n, int):
        return n
    cands = req.get("candidates") or []
    return len(cands)


def serve() -> None:
    target_step = env_int("GRIND_FORCE_STEP")
    target_multi_step = env_int("GRIND_FORCE_MULTI_STEP")
    target_anchor = env_int("GRIND_FORCE_ANCHOR")
    after = os.environ.get("GRIND_FORCE_AFTER", "stock").strip().lower()
    step = 0
    multi_step = 0

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        step += 1
        try:
            req = json.loads(line)
            ncands = num_candidates(req)
            if ncands >= 2:
                multi_step += 1
            if target_multi_step > 0:
                hit = (ncands >= 2 and multi_step == target_multi_step)
            else:
                hit = (step == target_step)
            if hit and target_anchor != 0:
                print(f"{target_anchor} {BIG_MARGIN}", flush=True)
            elif after == "fallback":
                print("0 0", flush=True)
            else:
                print(f"{stock_choice(req)} {BIG_MARGIN}", flush=True)
        except Exception as exc:
            print("0 0", flush=True)
            print(f"[serve_forced_choice.py error] {exc}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Ignored; accepted for neural_grind compatibility.")
    parser.parse_args()
    serve()
