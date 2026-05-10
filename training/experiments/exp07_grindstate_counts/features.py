"""EXP-07: Replace grindState text with 3 event-count features in numeric."""
import torch
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from features import (
    SOURCE_TAGS, NUM_SOURCES, TRIGRAM_VOCAB, TEXT_EMB_DIM, CONTEXT_DIM,
    GRIND_STATE_MAX_EVENTS, source_onehot, trigram_ids, candidate_numeric,
    batch_trigrams, context_trigrams,
)

# 3 extra numeric features: n_asserts, n_eqc, n_ematch
NUMERIC_DIM = 17 + 3  # 20


def grindstate_counts(grind_events: list[str]) -> list[float]:
    n_asserts = sum(1 for e in grind_events if "grind.assert" in e)
    n_eqc     = sum(1 for e in grind_events if "grind.eqc" in e)
    n_ematch  = sum(1 for e in grind_events if "grind.ematch" in e)
    return [float(n_asserts), float(n_eqc), float(n_ematch)]


def batch_numeric(cands: list[dict], goal: dict,
                  grind_events: list[str] | None = None) -> torch.Tensor:
    counts = grindstate_counts(grind_events or [])
    rows = [candidate_numeric(c, goal) + counts for c in cands]
    return torch.tensor(rows, dtype=torch.float32)
