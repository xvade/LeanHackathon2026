#!/usr/bin/env python3
"""
Generate .lean files from grind_results_verified.jsonl and collect data with grind_collect.

Usage:
    python3 training/gen_and_collect.py [--verified PATH] [--workers N]
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse


def run_batch(batch_info, project_root, timeout):
    """Run a single batch through grind_collect."""
    batch_idx, batch = batch_info
    
    # Generate Lean code: just statements from theorem records
    lines = ["import Mathlib"]
    for record in batch:
        # For now, just use grind on a placeholder example
        lines.append(f"example : True := by grind_collect")
    
    lean_code = "\n".join(lines)
    
    # Run through lake env lean from project root
    cmd = ["lake", "env", "lean", "-"]
    try:
        result = subprocess.run(
            cmd,
            input=lean_code,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=project_root
        )
        # Collect JSON lines from stdout
        output_lines = []
        for line in result.stdout.splitlines():
            if line.startswith("{"):
                output_lines.append(line)
        return batch_idx, output_lines
    except subprocess.TimeoutExpired:
        print(f"  [{batch_idx + 1}] TIMEOUT", file=sys.stderr)
        return batch_idx, []
    except Exception as e:
        print(f"  [{batch_idx + 1}] ERROR: {e}", file=sys.stderr)
        return batch_idx, []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verified", default="training/grind_results_verified.jsonl")
    parser.add_argument("--project", default="GrindExtraction")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--out", default="training/data/collected.jsonl")
    args = parser.parse_args()
    
    verified_path = Path(args.verified).resolve()
    project_root = Path(args.project).resolve()
    out_path = Path(args.out).resolve()
    
    if not verified_path.exists():
        print(f"ERROR: {verified_path} not found", file=sys.stderr)
        sys.exit(1)
    
    if not project_root.exists():
        print(f"ERROR: {project_root} not found", file=sys.stderr)
        sys.exit(1)
    
    # Load theorems
    print(f"Loading theorems from {verified_path}…")
    theorems = []
    with open(verified_path) as f:
        for line in f:
            if line.strip():
                theorems.append(json.loads(line))
    
    print(f"  Loaded {len(theorems)} theorems")
    
    # Group into batches
    batches = []
    for i in range(0, len(theorems), args.batch_size):
        batch = theorems[i:i + args.batch_size]
        batches.append(batch)
    
    print(f"  Created {len(batches)} batches (size {args.batch_size})")
    
    print(f"Running batches with {args.workers} workers…")
    all_jsonl = []
    
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(run_batch, (i, batch), project_root, args.timeout): i
            for i, batch in enumerate(batches)
        }
        
        for future in as_completed(futures):
            batch_idx, output_lines = future.result()
            all_jsonl.extend(output_lines)
            print(f"  [{batch_idx + 1}/{len(batches)}] Done ({len(output_lines)} records)")
    
    # Write output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for line in all_jsonl:
            f.write(line + "\n")
    
    print(f"\nDone. Wrote {len(all_jsonl)} records to {out_path}")


if __name__ == "__main__":
    main()

