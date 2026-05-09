"""
RL training loop for neural_grind.

Each iteration:
  1. Collect proof rollouts from mathlib (using current model + temperature sampling)
  2. Merge all accumulated data
  3. Train model with REINFORCE (train_rl.py)
  4. Save updated model checkpoint

Iteration 0 runs with the heuristic scorer (no model) to bootstrap data.
Subsequent iterations use the current model with temperature sampling for exploration.

Usage:
    python3 training/rl_loop.py [options]

Options:
  --iterations N      RL iterations (default: 10)
  --max-files N       Mathlib files to scan per iteration (default: 200)
  --batch-size N      Examples per Lean batch file (default: 20)
  --workers N         Parallel Lean processes (default: 4)
  --timeout N         Seconds per Lean batch (default: 120)
  --temperature T     Softmax sampling temperature for exploration (default: 1.0)
  --epochs N          Training epochs per iteration (default: 30)
  --lr LR             Learning rate (default: 1e-3)
  --model PATH        Model checkpoint path (default: training/model.pt)
  --data-dir PATH     Directory for per-iteration JSONL files (default: training/data/rl/)
  --reward-success F  Reward for successful proof (default: 1.0)
  --reward-failure F  Reward for failed proof (default: -1.0)
  --no-accumulate     Use only the current iteration's data (default: accumulate all)
  --start-iter N      Resume from this iteration number (default: 0)
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent / "NeuralTactic"


def run_collect(args, iteration: int, out_path: Path, model_path: Path) -> dict:
    """Run collect.py for one iteration. Returns summary stats."""
    env = os.environ.copy()

    # Iteration 0: bootstrap with heuristic (no model)
    if iteration > 0 and model_path.exists():
        env["GRIND_MODEL"] = str(model_path)
        env["GRIND_TEMPERATURE"] = str(args.temperature)
    else:
        env.pop("GRIND_MODEL", None)
        env.pop("GRIND_TEMPERATURE", None)

    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "collect.py"),
        "--max-files",  str(args.max_files),
        "--batch-size", str(args.batch_size),
        "--workers",    str(args.workers),
        "--timeout",    str(args.timeout),
        "--out",        str(out_path),
    ]
    print(f"  $ {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, env=env, cwd=str(PROJECT_DIR))
    if result.returncode != 0:
        print(f"  WARNING: collect.py exited with code {result.returncode}", flush=True)

    # Parse the output file for stats
    stats = {"total": 0, "success": 0, "multi_cand": 0}
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                stats["total"] += 1
                if r.get("outcome") == "success":
                    stats["success"] += 1
                if any(len(s.get("candidates", [])) >= 2 for s in r.get("steps", [])):
                    stats["multi_cand"] += 1
            except json.JSONDecodeError:
                pass
    return stats


def merge_data(data_dir: Path, out_path: Path, accumulate: bool, current_iter: int) -> int:
    """Merge per-iteration JSONL files into one accumulated file. Returns record count."""
    lines = []
    if accumulate:
        for f in sorted(data_dir.glob("iter_*.jsonl")):
            lines.extend(l for l in f.read_text().splitlines() if l.strip())
    else:
        current = data_dir / f"iter_{current_iter:03d}.jsonl"
        if current.exists():
            lines = [l for l in current.read_text().splitlines() if l.strip()]

    out_path.write_text("\n".join(lines) + ("\n" if lines else ""))
    return len(lines)


def run_train_rl(args, data_path: Path, model_path: Path) -> None:
    """Run train_rl.py."""
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "train_rl.py"),
        "--data",           str(data_path),
        "--out",            str(model_path),
        "--epochs",         str(args.epochs),
        "--lr",             str(args.lr),
        "--reward-success", str(args.reward_success),
        "--reward-failure", str(args.reward_failure),
    ]
    if model_path.exists():
        cmd += ["--init", str(model_path)]
    print(f"  $ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=str(PROJECT_DIR))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RL training loop for neural_grind (REINFORCE)."
    )
    parser.add_argument("--iterations",     type=int,   default=10)
    parser.add_argument("--max-files",      type=int,   default=200)
    parser.add_argument("--batch-size",     type=int,   default=20)
    parser.add_argument("--workers",        type=int,   default=4)
    parser.add_argument("--timeout",        type=int,   default=120)
    parser.add_argument("--temperature",    type=float, default=1.0)
    parser.add_argument("--epochs",         type=int,   default=30)
    parser.add_argument("--lr",             type=float, default=1e-4)
    parser.add_argument("--model",          default="training/model_rl.pt")
    parser.add_argument("--data-dir",       default="training/data/rl")
    parser.add_argument("--reward-success", type=float, default=1.0)
    parser.add_argument("--reward-failure", type=float, default=-1.0)
    parser.add_argument("--no-accumulate",  action="store_true")
    parser.add_argument("--start-iter",     type=int,   default=0)
    args = parser.parse_args()

    model_path = Path(args.model)
    data_dir   = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    accumulated = data_dir / "accumulated.jsonl"

    print(f"RL loop: {args.iterations} iterations, model={model_path}", flush=True)
    print(f"  collect: max_files={args.max_files} workers={args.workers} "
          f"timeout={args.timeout}s temperature={args.temperature}", flush=True)
    print(f"  train:   epochs={args.epochs} lr={args.lr} "
          f"reward=+{args.reward_success}/-{abs(args.reward_failure)}", flush=True)
    print()

    for iteration in range(args.start_iter, args.start_iter + args.iterations):
        print(f"{'='*60}", flush=True)
        mode = "heuristic" if (iteration == 0 or not model_path.exists()) \
               else f"model+T={args.temperature}"
        print(f"Iteration {iteration}  [{mode}]", flush=True)
        print(f"{'='*60}", flush=True)

        # Step 1: collect rollouts
        iter_data = data_dir / f"iter_{iteration:03d}.jsonl"
        print(f"\n[1/3] Collecting rollouts → {iter_data}", flush=True)
        stats = run_collect(args, iteration, iter_data, model_path)
        print(f"  records={stats['total']}  success={stats['success']}  "
              f"multi-cand={stats['multi_cand']}", flush=True)

        if stats["total"] == 0:
            print("  No data collected this iteration — skipping training.", flush=True)
            continue

        # Step 2: merge
        print(f"\n[2/3] Merging data → {accumulated}", flush=True)
        n_records = merge_data(data_dir, accumulated, not args.no_accumulate, iteration)
        print(f"  {n_records} total records in accumulated set", flush=True)

        # Step 3: train
        print(f"\n[3/3] Training REINFORCE on {accumulated}", flush=True)
        run_train_rl(args, accumulated, model_path)

        print(f"\nIteration {iteration} done. Model: {model_path}", flush=True)

    print(f"\n{'='*60}", flush=True)
    print(f"RL loop complete. Final model: {model_path}", flush=True)


if __name__ == "__main__":
    main()
