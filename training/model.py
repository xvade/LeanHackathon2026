"""
SplitRanker: MLP that scores grind split candidates.

Architecture
  text branch   : embedding lookup (TRIGRAM_VOCAB × TEXT_EMB_DIM) → mean-pool → TEXT_EMB_DIM
  numeric branch: NUMERIC_DIM raw features
  combined      : Linear(TEXT_EMB_DIM + NUMERIC_DIM, hidden) → ReLU → Linear(hidden, 1)

Input (per forward call, all candidates for one decision point):
  numeric  – (N, NUMERIC_DIM) float32 tensor
  text_ids – (N, max_seq_len) int64 tensor of trigram hash indices

Output:
  (N,) float32 scores; higher → better split candidate
"""

import torch
import torch.nn as nn
from features import TRIGRAM_VOCAB, NUMERIC_DIM, TEXT_EMB_DIM


class SplitRanker(nn.Module):
    def __init__(
        self,
        vocab: int = TRIGRAM_VOCAB,
        emb_dim: int = TEXT_EMB_DIM,
        numeric_dim: int = NUMERIC_DIM,
        hidden: int = 128,
    ):
        super().__init__()
        self.emb = nn.Embedding(vocab, emb_dim, padding_idx=0)
        self.fc1 = nn.Linear(emb_dim + numeric_dim, hidden)
        self.fc2 = nn.Linear(hidden, 1)

    def forward(self, numeric: torch.Tensor, text_ids: torch.Tensor) -> torch.Tensor:
        # text_ids: (N, L) → embed → (N, L, emb_dim) → mean over L → (N, emb_dim)
        text_emb = self.emb(text_ids).mean(dim=1)
        x = torch.cat([text_emb, numeric], dim=-1)
        x = torch.relu(self.fc1(x))
        return self.fc2(x).squeeze(-1)   # (N,)
