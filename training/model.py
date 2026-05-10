"""
SplitRanker: MLP that scores grind split candidates.

Architecture
  candidate text  : embedding lookup (TRIGRAM_VOCAB × TEXT_EMB_DIM)
                    → mean-pool over trigrams → TEXT_EMB_DIM
  numeric         : NUMERIC_DIM raw features (numCases, isRec, source×9,
                    generation, splitDepth, assertedCount, ematchRounds,
                    splitTraceLen, numCandidates)
  statePP context : trigram embedding of proof state (hyps + goal)
                    → mean-pool → Linear → ReLU → CONTEXT_DIM
                    shared across all candidates in a decision
  grindState ctx  : trigram embedding of grind events (assert/eqc/ematch)
                    → mean-pool → Linear → ReLU → CONTEXT_DIM
                    shared across all candidates in a decision
  combined        : Linear(TEXT_EMB_DIM + NUMERIC_DIM + 2×CONTEXT_DIM, hidden)
                    → ReLU → Linear(hidden, 1)

forward(numeric, text_ids, state_ids=None, grind_ids=None)
  numeric    – (N, NUMERIC_DIM) float32
  text_ids   – (N, max_seq_len) int64, trigram ids for each candidate's exprText
  state_ids  – (L,) int64, trigram ids for joined statePP strings  [optional]
  grind_ids  – (L,) int64, trigram ids for joined grindState strings [optional]

When state_ids / grind_ids are None or empty (e.g. during inference when the
Lean client does not yet send context), the corresponding context vector is
replaced with zeros so the model degrades gracefully.

Output: (N,) float32 scores; higher → better split candidate.
"""

import torch
import torch.nn as nn
from features import TRIGRAM_VOCAB, NUMERIC_DIM, TEXT_EMB_DIM, CONTEXT_DIM


class SplitRanker(nn.Module):
    def __init__(
        self,
        vocab:       int = TRIGRAM_VOCAB,
        emb_dim:     int = TEXT_EMB_DIM,
        numeric_dim: int = NUMERIC_DIM,
        context_dim: int = CONTEXT_DIM,
        hidden:      int = 256,
    ):
        super().__init__()
        self.context_dim = context_dim

        # Shared embedding table for all text inputs
        self.emb = nn.Embedding(vocab, emb_dim, padding_idx=0)

        # Per-decision context projections (compress shared proof / grind state)
        self.state_proj = nn.Linear(emb_dim, context_dim)
        self.grind_proj = nn.Linear(emb_dim, context_dim)

        combined_dim = emb_dim + numeric_dim + context_dim + context_dim
        self.fc1 = nn.Linear(combined_dim, hidden)
        self.fc2 = nn.Linear(hidden, 1)

    def _encode_context(self, ids: torch.Tensor | None,
                        proj: nn.Linear, N: int) -> torch.Tensor:
        """
        Embed a 1-D token sequence, mean-pool, project, and expand to (N, context_dim).
        Returns zeros when ids is None or empty.
        """
        if ids is not None and ids.numel() > 0:
            emb = self.emb(ids)          # (L, emb_dim)
            ctx = torch.relu(proj(emb.mean(dim=0, keepdim=True)))  # (1, context_dim)
        else:
            ctx = torch.zeros(1, self.context_dim, device=self.fc1.weight.device)
        return ctx.expand(N, -1)         # (N, context_dim)

    def forward(
        self,
        numeric:   torch.Tensor,
        text_ids:  torch.Tensor,
        state_ids: torch.Tensor | None = None,
        grind_ids: torch.Tensor | None = None,
    ) -> torch.Tensor:
        N = numeric.size(0)

        # Candidate text: (N, L) → (N, emb_dim)
        cand_emb = self.emb(text_ids).mean(dim=1)

        # Per-decision context: (N, context_dim) each
        state_ctx = self._encode_context(state_ids, self.state_proj, N)
        grind_ctx = self._encode_context(grind_ids, self.grind_proj, N)

        x = torch.cat([cand_emb, numeric, state_ctx, grind_ctx], dim=-1)
        x = torch.relu(self.fc1(x))
        return self.fc2(x).squeeze(-1)   # (N,)
