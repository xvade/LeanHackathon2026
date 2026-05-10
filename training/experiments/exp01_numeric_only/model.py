"""EXP-01: Numeric-only SplitRanker — no text embeddings, no context."""
import torch
import torch.nn as nn
from features import NUMERIC_DIM


class SplitRanker(nn.Module):
    def __init__(self, numeric_dim: int = NUMERIC_DIM, hidden: int = 256):
        super().__init__()
        self.fc1 = nn.Linear(numeric_dim, hidden)
        self.fc2 = nn.Linear(hidden, hidden)
        self.fc3 = nn.Linear(hidden, 1)

    def forward(self, numeric, text_ids=None, state_ids=None, grind_ids=None):
        x = torch.relu(self.fc1(numeric))
        x = torch.relu(self.fc2(x))
        return self.fc3(x).squeeze(-1)
