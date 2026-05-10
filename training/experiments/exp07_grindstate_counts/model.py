"""EXP-07: grindState as counts in numeric; keeps exprText + statePP, drops grindState text."""
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
        self.emb        = nn.Embedding(vocab, emb_dim, padding_idx=0)
        self.state_proj = nn.Linear(emb_dim, context_dim)
        # grindState text path removed; grind_ctx slot is zeros
        combined_dim = emb_dim + numeric_dim + context_dim + context_dim
        self.fc1 = nn.Linear(combined_dim, hidden)
        self.fc2 = nn.Linear(hidden, 1)

    def forward(self, numeric, text_ids, state_ids=None, grind_ids=None):
        N = numeric.size(0)
        cand_emb = self.emb(text_ids).mean(dim=1)
        if state_ids is not None and state_ids.numel() > 0:
            emb = self.emb(state_ids)
            state_ctx = torch.relu(self.state_proj(emb.mean(dim=0, keepdim=True))).expand(N, -1)
        else:
            state_ctx = torch.zeros(N, self.context_dim, device=self.fc1.weight.device)
        grind_ctx = torch.zeros(N, self.context_dim, device=self.fc1.weight.device)
        x = torch.cat([cand_emb, numeric, state_ctx, grind_ctx], dim=-1)
        x = torch.relu(self.fc1(x))
        return self.fc2(x).squeeze(-1)
