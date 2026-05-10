"""EXP-02: SplitRanker with pool-aggregate numeric features (no text change)."""
import torch
import torch.nn as nn
from features import NUMERIC_DIM, TRIGRAM_VOCAB, TEXT_EMB_DIM, CONTEXT_DIM


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
        self.emb        = nn.Embedding(vocab, emb_dim, padding_idx=0)
        self.state_proj = nn.Linear(emb_dim, context_dim)
        self.grind_proj = nn.Linear(emb_dim, context_dim)
        combined_dim = emb_dim + numeric_dim + context_dim + context_dim
        self.fc1 = nn.Linear(combined_dim, hidden)
        self.fc2 = nn.Linear(hidden, 1)

    def _encode_context(self, ids, proj, N):
        if ids is not None and ids.numel() > 0:
            emb = self.emb(ids)
            ctx = torch.relu(proj(emb.mean(dim=0, keepdim=True)))
        else:
            ctx = torch.zeros(1, self.context_dim, device=self.fc1.weight.device)
        return ctx.expand(N, -1)

    def forward(self, numeric, text_ids, state_ids=None, grind_ids=None):
        N = numeric.size(0)
        cand_emb  = self.emb(text_ids).mean(dim=1)
        state_ctx = self._encode_context(state_ids, self.state_proj, N)
        grind_ctx = self._encode_context(grind_ids, self.grind_proj, N)
        x = torch.cat([cand_emb, numeric, state_ctx, grind_ctx], dim=-1)
        x = torch.relu(self.fc1(x))
        return self.fc2(x).squeeze(-1)
