"""Export an exp08 PyTorch checkpoint to the native C++ binary format."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import torch


def tensor_bytes(state: dict, key: str) -> bytes:
    return state[key].detach().cpu().contiguous().to(torch.float32).numpy().tobytes()


def export(model: Path, out: Path) -> None:
    state = torch.load(model, map_location="cpu", weights_only=True)
    fc1_w = state["fc1.weight"]
    fc2_w = state["fc2.weight"]
    fc3_w = state["fc3.weight"]
    input_dim = int(fc1_w.shape[1])
    hidden_dim = int(fc1_w.shape[0])
    if tuple(fc2_w.shape) != (hidden_dim, hidden_dim):
        raise SystemExit(f"unexpected fc2 shape: {tuple(fc2_w.shape)}")
    if tuple(fc3_w.shape) != (1, hidden_dim):
        raise SystemExit(f"unexpected fc3 shape: {tuple(fc3_w.shape)}")
    if input_dim != 27:
        raise SystemExit(f"expected exp08 input dim 27, got {input_dim}")

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        f.write(struct.pack("<8sIII", b"NGEXP08\0", 1, input_dim, hidden_dim))
        for key in ["fc1.weight", "fc1.bias", "fc2.weight", "fc2.bias", "fc3.weight"]:
            f.write(tensor_bytes(state, key))
        f.write(tensor_bytes(state, "fc3.bias"))
    print(f"wrote {out} ({out.stat().st_size} bytes)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="training/experiments/exp08_num_pool_counts/model.pt")
    parser.add_argument("--out", default="training/experiments/exp08_num_pool_counts/model.native.bin")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    export(Path(args.model), Path(args.out))


if __name__ == "__main__":
    main()
