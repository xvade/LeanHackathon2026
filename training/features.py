"""
Shared feature extraction for training and serving.

Each split candidate produces:
  numeric features : [numCases, isRec, source_onehot(9), generation,
                      splitDepth, assertedCount, ematchRounds,
                      splitTraceLen, numCandidates]
                     → 17-dim float vector
  text features    : char-trigram hashing of exprText → sparse 65536-dim vector
                     summed into a dense 512-dim embedding lookup

Each split decision also produces two context vectors (shared across candidates):
  statePP context  : trigram embedding of tactic proof state (hyps + goal)
                     → CONTEXT_DIM-dim after projection
  grindState ctx   : trigram embedding of accumulated grind events
                     (assert/eqc/ematch) → CONTEXT_DIM-dim after projection

SOURCE_TAGS mirrors GrindExtraction.sourceTagStr:
  ematch, ext, mbtc, beta, forallProp, existsProp, input, inj, guard
"""

import torch

SOURCE_TAGS = ["ematch", "ext", "mbtc", "beta", "forallProp",
               "existsProp", "input", "inj", "guard"]
NUM_SOURCES  = len(SOURCE_TAGS)         # 9
TRIGRAM_VOCAB = 65536
NUMERIC_DIM  = 2 + NUM_SOURCES + 1 + 5 # 17  (added generation)
TEXT_EMB_DIM = 512
CONTEXT_DIM  = 128                      # projected dim for statePP / grindState

# Truncate grindState to the first N events before encoding.
# Early events are grind's foundational assertions about the problem structure;
# later events are cascading derived equalities that add noise.
GRIND_STATE_MAX_EVENTS = 30


def source_onehot(tag: str) -> list[float]:
    vec = [0.0] * NUM_SOURCES
    if tag in SOURCE_TAGS:
        vec[SOURCE_TAGS.index(tag)] = 1.0
    return vec


def trigram_ids(text: str, vocab: int = TRIGRAM_VOCAB) -> list[int]:
    """Return hashed trigram indices for `text`."""
    padded = "\x00\x00" + text + "\x00\x00"
    ids = [hash(padded[i:i+3]) % vocab for i in range(len(padded) - 2)]
    return ids if ids else [0]


def candidate_numeric(cand: dict, goal: dict) -> list[float]:
    """17-dim numeric feature vector for one candidate."""
    return [
        float(cand["numCases"]),
        1.0 if cand["isRec"] else 0.0,
        *source_onehot(cand.get("source", "")),
        float(cand.get("generation", 0)),
        float(goal.get("splitDepth", 0)),
        float(goal.get("assertedCount", 0)),
        float(goal.get("ematchRounds", 0)),
        float(goal.get("splitTraceLen", 0)),
        float(goal.get("numCandidates", 1)),
    ]


def batch_numeric(cands: list[dict], goal: dict) -> torch.Tensor:
    """(N, NUMERIC_DIM) float tensor for N candidates."""
    return torch.tensor([candidate_numeric(c, goal) for c in cands],
                        dtype=torch.float32)


def batch_trigrams(cands: list[dict], vocab: int = TRIGRAM_VOCAB) -> torch.Tensor:
    """(N, max_len) long tensor of trigram ids, padded with zeros."""
    seqs = [trigram_ids(c.get("exprText", ""), vocab) for c in cands]
    max_len = max(len(s) for s in seqs)
    padded = [s + [0] * (max_len - len(s)) for s in seqs]
    return torch.tensor(padded, dtype=torch.long)


def context_trigrams(strings: list[str], vocab: int = TRIGRAM_VOCAB,
                     max_events: int | None = None) -> torch.Tensor:
    """
    Encode a list of strings (statePP or grindState) as a single 1-D trigram
    tensor by joining with newlines.  Returns shape (L,) long tensor.
    Falls back to tensor([0]) when the list is empty.

    max_events: if set, truncate to the FIRST max_events strings before encoding.
    For grindState this keeps the foundational early assertions (core proof
    structure) and discards later derived equalities which tend to be noisy
    cascade follow-ons from the early facts.
    """
    if max_events is not None:
        strings = strings[:max_events]
    text = "\n".join(strings)
    return torch.tensor(trigram_ids(text, vocab), dtype=torch.long)
