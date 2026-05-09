"""
Shared feature extraction for training and serving.

Each split candidate produces:
  numeric features : [numCases, isRec, source_onehot(9), splitDepth,
                      assertedCount, ematchRounds, splitTraceLen, numCandidates]
                     → 16-dim float vector
  text features    : char-trigram hashing of exprText → sparse 65536-dim vector
                     summed into a dense 512-dim embedding lookup

SOURCE_TAGS mirrors NeuralTactic.sourceTagStr:
  ematch, ext, mbtc, beta, forallProp, existsProp, input, inj, guard
"""

import torch
import torch.nn.functional as F

SOURCE_TAGS = ["ematch", "ext", "mbtc", "beta", "forallProp",
               "existsProp", "input", "inj", "guard"]
NUM_SOURCES = len(SOURCE_TAGS)          # 9
TRIGRAM_VOCAB = 65536
NUMERIC_DIM = 2 + NUM_SOURCES + 5      # 16
TEXT_EMB_DIM = 512


def source_onehot(tag: str) -> list[float]:
    vec = [0.0] * NUM_SOURCES
    if tag in SOURCE_TAGS:
        vec[SOURCE_TAGS.index(tag)] = 1.0
    return vec


def trigram_ids(text: str, vocab: int = TRIGRAM_VOCAB) -> list[int]:
    """Return hashed trigram indices for `text`."""
    ids = []
    padded = "\x00\x00" + text + "\x00\x00"
    for i in range(len(padded) - 2):
        tri = padded[i:i+3]
        ids.append(hash(tri) % vocab)
    return ids if ids else [0]


def candidate_numeric(cand: dict, goal: dict) -> list[float]:
    """16-dim numeric feature vector for one candidate."""
    return [
        float(cand["numCases"]),
        1.0 if cand["isRec"] else 0.0,
        *source_onehot(cand.get("source", "input")),
        float(goal.get("splitDepth", 0)),
        float(goal.get("assertedCount", 0)),
        float(goal.get("ematchRounds", 0)),
        float(goal.get("splitTraceLen", 0)),
        float(goal.get("numCandidates", 1)),
    ]


def batch_numeric(cands: list[dict], goal: dict) -> torch.Tensor:
    """(N, NUMERIC_DIM) float tensor for N candidates."""
    rows = [candidate_numeric(c, goal) for c in cands]
    return torch.tensor(rows, dtype=torch.float32)


def batch_trigrams(cands: list[dict], vocab: int = TRIGRAM_VOCAB) -> torch.Tensor:
    """(N, max_len) long tensor of trigram ids, padded with zeros."""
    seqs = [trigram_ids(c.get("exprText", ""), vocab) for c in cands]
    max_len = max(len(s) for s in seqs)
    padded = [s + [0] * (max_len - len(s)) for s in seqs]
    return torch.tensor(padded, dtype=torch.long)
