"""EXP-08: Numeric + pool aggregates + grindState counts. No text at all."""
import importlib.util
import torch
from pathlib import Path

# Load base features by explicit path to avoid circular import (same filename)
_spec = importlib.util.spec_from_file_location(
    "_features_base", Path(__file__).parent.parent.parent / "features.py")
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

candidate_numeric = _base.candidate_numeric

# 7 pool aggregates + 3 grindState counts on top of base 17
NUMERIC_DIM = 17 + 7 + 3  # 27


def pool_aggregates(cands: list[dict]) -> list[list[float]]:
    n = len(cands)
    cases = [c["numCases"] for c in cands]
    gens  = [c.get("generation", 0) for c in cands]
    min_c = min(cases)
    min_g = min(gens)
    sorted_cases = sorted(set(cases))
    sorted_gens  = sorted(set(gens))
    result = []
    for c in cands:
        nc = c["numCases"]
        g  = c.get("generation", 0)
        result.append([
            float(sorted_cases.index(nc)),
            float(sorted_gens.index(g)),
            1.0 if nc == min_c else 0.0,
            1.0 if g == min_g else 0.0,
            float(n),
            sum(1 for x in cases if x == nc) / n,
            sum(1 for x in cands if x.get("source") == "input") / n,
        ])
    return result


def grindstate_counts(grind_events: list[str]) -> list[float]:
    return [
        float(sum(1 for e in grind_events if "grind.assert" in e)),
        float(sum(1 for e in grind_events if "grind.eqc" in e)),
        float(sum(1 for e in grind_events if "grind.ematch" in e)),
    ]


def batch_numeric(cands: list[dict], goal: dict,
                  grind_events: list[str] | None = None) -> torch.Tensor:
    base   = [candidate_numeric(c, goal) for c in cands]
    agg    = pool_aggregates(cands)
    counts = grindstate_counts(grind_events or [])
    combined = [b + a + counts for b, a in zip(base, agg)]
    return torch.tensor(combined, dtype=torch.float32)
