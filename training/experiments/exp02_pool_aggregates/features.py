"""EXP-02: Adds 7 pool-level aggregate features to numeric vector."""
import torch

# Re-export everything from base features, then override batch_numeric
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))  # training/ dir

from features import (
    SOURCE_TAGS, NUM_SOURCES, TRIGRAM_VOCAB, TEXT_EMB_DIM, CONTEXT_DIM,
    GRIND_STATE_MAX_EVENTS, source_onehot, trigram_ids, candidate_numeric,
    batch_trigrams, context_trigrams,
)

# EXP-02 adds 7 pool-level features: rank_numCases, rank_generation,
# is_min_cases, is_min_generation, pool_size, frac_same_cases, frac_input_source
POOL_AGG_DIM = 7
NUMERIC_DIM = 17 + POOL_AGG_DIM  # 24


def pool_aggregates(cands: list[dict]) -> list[list[float]]:
    n = len(cands)
    cases  = [c["numCases"] for c in cands]
    gens   = [c.get("generation", 0) for c in cands]
    min_c  = min(cases)
    min_g  = min(gens)

    sorted_cases = sorted(set(cases))
    sorted_gens  = sorted(set(gens))

    result = []
    for c in cands:
        nc = c["numCases"]
        g  = c.get("generation", 0)
        result.append([
            float(sorted_cases.index(nc)),              # rank_numCases (0=best)
            float(sorted_gens.index(g)),                # rank_generation
            1.0 if nc == min_c else 0.0,               # is_min_cases
            1.0 if g == min_g else 0.0,                # is_min_generation
            float(n),                                   # pool_size
            sum(1 for x in cases if x == nc) / n,      # frac_same_cases
            sum(1 for x in cands if x.get("source") == "input") / n,  # frac_input_source
        ])
    return result


def batch_numeric(cands: list[dict], goal: dict) -> torch.Tensor:
    base = [candidate_numeric(c, goal) for c in cands]
    agg  = pool_aggregates(cands)
    combined = [b + a for b, a in zip(base, agg)]
    return torch.tensor(combined, dtype=torch.float32)
