"""
benchmark.py — compare grind's heuristic vs. our neural model.

For each sampled theorem:
  • Runs grind_collect (GrindExtraction, pure heuristic) → captures split-decision count
  • Runs neural_collect (NeuralTactic, model-guided)   → captures split-decision count

Primary metric: number of split decisions to close the proof.
Fewer steps = model found a better split ordering.

Usage:
    python3 training/benchmark.py [options]

Options:
  --model PATH      Model checkpoint (default: training/model.pt)
  --n N             Theorems to sample per module (default: 3)
  --workers N       Parallel Lean processes (default: 4)
  --timeout N       Seconds per theorem (default: 60)
  --seed N          Random seed for sampling (default: 42)
  --only-plain      Skip theorems that need grind hints (default: True)
"""

import argparse
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

REPO     = Path(__file__).parent.parent
TRAINING = Path(__file__).parent
GRIND_PROJECT   = REPO / "GrindExtraction"
NEURAL_PROJECT  = REPO / "NeuralTactic"


# ---------------------------------------------------------------------------
# Theorem sampling
# ---------------------------------------------------------------------------

def module_name(file_path: str) -> str:
    return file_path.replace("Mathlib/", "").split("/")[0]

def difficulty(elapsed_s: float) -> str:
    if elapsed_s < 0.1: return "easy"
    if elapsed_s < 0.5: return "medium"
    return "hard"

def sample_theorems(verified_path: Path, n_per_module: int,
                    only_plain: bool, seed: int) -> list[dict]:
    rng = random.Random(seed)
    records = []
    for line in verified_path.read_text().splitlines():
        line = line.strip()
        if not line: continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if only_plain and r.get("grind_call") != "grind":
            continue
        records.append(r)

    by_module = defaultdict(list)
    for r in records:
        by_module[module_name(r["file_path"])].append(r)

    sampled = []
    for mod, recs in sorted(by_module.items()):
        # Sort by elapsed_s to get spread of difficulty; sample evenly
        recs_sorted = sorted(recs, key=lambda r: r.get("elapsed_s", 0))
        # Take n_per_module evenly spaced across the sorted list
        if len(recs_sorted) <= n_per_module:
            chosen = recs_sorted
        else:
            step = len(recs_sorted) / n_per_module
            chosen = [recs_sorted[int(i * step)] for i in range(n_per_module)]
        sampled.extend(chosen)

    rng.shuffle(sampled)
    return sampled


# ---------------------------------------------------------------------------
# Snippet transformation
# ---------------------------------------------------------------------------

def make_grind_collect_file(snippet: str, grind_call: str) -> str:
    """Replace grind with grind_collect and add GrindExtraction import."""
    s = re.sub(r"^import Mathlib\s*\n", "", snippet)
    escaped = re.escape(grind_call)
    s = re.sub(r":=\s*by\s*\n\s*" + escaped + r"\b", ":= by grind_collect", s)
    s = re.sub(r":=\s*by\s+" + escaped + r"\b", ":= by grind_collect", s)
    return "import Mathlib\nimport GrindExtraction\nset_option maxHeartbeats 400000\n\n" + s.strip()

def make_neural_collect_file(snippet: str, grind_call: str) -> str:
    """Replace grind with neural_collect and add NeuralTactic import."""
    s = re.sub(r"^import Mathlib\s*\n", "", snippet)
    escaped = re.escape(grind_call)
    s = re.sub(r":=\s*by\s*\n\s*" + escaped + r"\b", ":= by neural_collect", s)
    s = re.sub(r":=\s*by\s+" + escaped + r"\b", ":= by neural_collect", s)
    return "import Mathlib\nimport NeuralTactic\nset_option maxHeartbeats 400000\n\n" + s.strip()


# ---------------------------------------------------------------------------
# Running one theorem (called in worker process)
# ---------------------------------------------------------------------------

def run_grind_collect(lean_src: str, project: str, timeout: int) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".lean", mode="w", delete=False,
                                    dir="/tmp") as f:
        f.write(lean_src)
        fname = f.name
    try:
        t0 = time.monotonic()
        proc = subprocess.run(
            ["lake", "env", "lean", fname],
            cwd=project, capture_output=True, text=True, timeout=timeout,
            env=os.environ.copy(),
        )
        elapsed = time.monotonic() - t0
        # Parse JSON lines from stdout
        json_lines = [l for l in proc.stdout.splitlines() if l.strip().startswith("{")]
        decisions = 0
        solved = False
        for line in json_lines:
            try:
                r = json.loads(line)
                solved = bool(r.get("solved", False))
                decisions = len(r.get("splitDecisions", []))
            except Exception:
                pass
        return {"solved": solved, "steps": decisions, "elapsed": elapsed, "error": None}
    except subprocess.TimeoutExpired:
        return {"solved": False, "steps": -1, "elapsed": timeout, "error": "timeout"}
    except Exception as e:
        return {"solved": False, "steps": -1, "elapsed": 0.0, "error": str(e)}
    finally:
        try: os.unlink(fname)
        except: pass


def run_neural_collect(lean_src: str, project: str, model_path: str,
                       serve_path: str, timeout: int) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".lean", mode="w", delete=False,
                                    dir="/tmp") as f:
        f.write(lean_src)
        fname = f.name
    with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False,
                                     dir="/tmp") as lf:
        log_path = lf.name

    env = os.environ.copy()
    env["GRIND_LOG"]   = log_path
    env["GRIND_MODEL"] = model_path
    env["GRIND_SERVE"] = serve_path
    # Ensure the correct python is found for serve.py
    python_bin = str(Path(sys.executable).parent)
    env["PATH"] = python_bin + ":" + env.get("PATH", "")

    try:
        t0 = time.monotonic()
        proc = subprocess.run(
            ["lake", "env", "lean", fname],
            cwd=project, capture_output=True, text=True, timeout=timeout, env=env,
        )
        elapsed = time.monotonic() - t0
        # Success is determined by exit code; log gives step count
        solved = proc.returncode == 0
        decisions = 0
        try:
            for line in Path(log_path).read_text().splitlines():
                line = line.strip()
                if not line: continue
                r = json.loads(line)
                decisions = len(r.get("steps", []))
        except Exception:
            pass
        return {"solved": solved, "steps": decisions, "elapsed": elapsed, "error": None}
    except subprocess.TimeoutExpired:
        return {"solved": False, "steps": -1, "elapsed": timeout, "error": "timeout"}
    except Exception as e:
        return {"solved": False, "steps": -1, "elapsed": 0.0, "error": str(e)}
    finally:
        try: os.unlink(fname)
        except: pass
        try: os.unlink(log_path)
        except: pass


def run_one(args_tuple):
    """Worker: run one theorem through both tactics."""
    rec, model_path, serve_path, grind_proj, neural_proj, timeout = args_tuple

    snippet    = rec["lean_snippet"]
    grind_call = rec["grind_call"]

    gc_src  = make_grind_collect_file(snippet, grind_call)
    nc_src  = make_neural_collect_file(snippet, grind_call)

    gc  = run_grind_collect(gc_src,  str(grind_proj),  timeout)
    nc  = run_neural_collect(nc_src, str(neural_proj), model_path, serve_path, timeout)

    return {"record": rec, "grind": gc, "neural": nc}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def winner(grind_steps: int, neural_steps: int,
           grind_solved: bool, neural_solved: bool) -> str:
    if not grind_solved and not neural_solved: return "both-fail"
    if grind_solved and not neural_solved:     return "grind"
    if neural_solved and not grind_solved:     return "neural"
    # Both solved
    if neural_steps < grind_steps:  return "neural"
    if grind_steps  < neural_steps: return "grind"
    return "tie"


def print_report(results: list[dict]) -> None:
    print()
    print(f"{'Theorem':<28} {'Module':<18} {'Diff':<7} "
          f"{'heuristic':>10} {'neural':>7} {'Δ':>4}  {'Winner'}")
    print("─" * 85)

    wins = {"neural": 0, "grind": 0, "tie": 0, "both-fail": 0}

    for res in results:
        rec   = res["record"]
        gc    = res["grind"]
        nc    = res["neural"]
        name  = rec["name"][:27]
        mod   = module_name(rec["file_path"])[:17]
        diff  = difficulty(rec.get("elapsed_s", 0))

        g_steps = gc["steps"] if gc["solved"] else "✗"
        n_steps = nc["steps"] if nc["solved"] else "✗"
        delta   = ""
        if gc["solved"] and nc["solved"]:
            d = nc["steps"] - gc["steps"]
            delta = f"{d:+d}" if d != 0 else "0"

        w = winner(gc["steps"], nc["steps"], gc["solved"], nc["solved"])
        wins[w] += 1
        marker = {"neural": "◀ neural", "grind": "grind ▶", "tie": "tie",
                  "both-fail": "FAIL"}.get(w, w)

        print(f"{name:<28} {mod:<18} {diff:<7} "
              f"{str(g_steps):>10} {str(n_steps):>7} {delta:>4}  {marker}")

    n = len(results)
    print("─" * 85)
    print(f"\nSummary ({n} theorems):")
    print(f"  Neural wins  (fewer splits): {wins['neural']:3d} / {n}  "
          f"({wins['neural']/n*100:.1f}%)")
    print(f"  Tie          (same splits) : {wins['tie']:3d} / {n}  "
          f"({wins['tie']/n*100:.1f}%)")
    print(f"  Grind wins   (fewer splits): {wins['grind']:3d} / {n}  "
          f"({wins['grind']/n*100:.1f}%)")
    print(f"  Both failed               : {wins['both-fail']:3d} / {n}")

    # Step-count improvement on theorems both solved with >0 splits
    contested = [(res["grind"]["steps"], res["neural"]["steps"])
                 for res in results
                 if res["grind"]["solved"] and res["neural"]["solved"]
                 and max(res["grind"]["steps"], res["neural"]["steps"]) > 0]
    if contested:
        total_g = sum(g for g, _ in contested)
        total_n = sum(n for _, n in contested)
        pct = (total_g - total_n) / max(total_g, 1) * 100
        print(f"\n  Total splits on contested theorems: "
              f"heuristic={total_g}  neural={total_n}  "
              f"reduction={pct:+.1f}%")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--model",      default=str(TRAINING / "model.pt"))
    p.add_argument("--serve",      default=str(TRAINING / "serve.py"),
                   help="Path to serve.py (override for experiments)")
    p.add_argument("--n",          type=int, default=3,
                   help="Theorems to sample per Mathlib module")
    p.add_argument("--workers",    type=int, default=4)
    p.add_argument("--timeout",    type=int, default=60)
    p.add_argument("--seed",       type=int, default=42)
    p.add_argument("--only-plain", action="store_true", default=True)
    return p.parse_args()


def main():
    args = parse_args()
    model_path = str(Path(args.model).resolve())
    serve_path = str(Path(args.serve).resolve())
    verified   = TRAINING / "grind_results_verified.jsonl"

    if not Path(model_path).exists():
        print(f"Model not found: {model_path}", file=sys.stderr); sys.exit(1)

    theorems = sample_theorems(verified, args.n, args.only_plain, args.seed)
    print(f"Benchmark: grind heuristic vs. neural model")
    print(f"Model    : {model_path}")
    print(f"Theorems : {len(theorems)} across "
          f"{len({module_name(r['file_path']) for r in theorems})} modules")
    print(f"Workers  : {args.workers}  timeout={args.timeout}s")

    work = [(r, model_path, serve_path, GRIND_PROJECT, NEURAL_PROJECT, args.timeout)
            for r in theorems]

    results = []
    done = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(run_one, w): w for w in work}
        for fut in as_completed(futs):
            res = fut.result()
            done += 1
            name = res["record"]["name"]
            g = res["grind"]
            n = res["neural"]
            g_s = f"{g['steps']}✓" if g["solved"] else "✗"
            n_s = f"{n['steps']}✓" if n["solved"] else "✗"
            print(f"  [{done:3d}/{len(work)}] {name:<35} "
                  f"grind={g_s:<5} neural={n_s}", flush=True)
            results.append(res)

    # Sort by module then name for clean output
    results.sort(key=lambda r: (module_name(r["record"]["file_path"]),
                                r["record"]["name"]))
    print_report(results)


if __name__ == "__main__":
    main()
