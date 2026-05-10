"""
Collect split-decision data from pre-verified Mathlib theorems.

Reads grind_results_verified.jsonl, which contains lean_snippet fields
(standalone Lean files using `import Mathlib` + grind). Transforms each snippet
to use `grind_collect` instead, batches them into temporary Lean files, runs
them under the GrindExtraction project, and captures split decisions from stdout.

Usage:
    python3 training/collect_verified.py [options]

Options:
  --input PATH      Verified theorems JSONL (default: training/grind_results_verified.jsonl)
  --out PATH        Output JSONL (default: training/data/verified_splits.jsonl)
  --project PATH    GrindExtraction project dir (default: auto-detect)
  --batch-size N    Snippets per Lean batch file (default: 20)
  --workers N       Parallel Lean processes (default: 4)
  --timeout N       Seconds per batch (default: 180)
  --only-plain      Skip theorems that use grind with hints/options
  --dry-run         Show batch files without running Lean
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


# ---------------------------------------------------------------------------
# Project detection
# ---------------------------------------------------------------------------

def find_grind_extraction_root(start=None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        for lf in ["lakefile.toml", "lakefile.lean"]:
            p = candidate / lf
            if p.exists() and "GrindExtraction" in p.read_text():
                return candidate
    raise FileNotFoundError(
        "Could not find GrindExtraction project root. Pass --project explicitly."
    )


# ---------------------------------------------------------------------------
# Snippet transformation
# ---------------------------------------------------------------------------

def transform_snippet(lean_snippet: str, grind_call: str) -> str:
    """
    Take a standalone lean_snippet and return a version suitable for batching:
      - Strips the `import Mathlib` line (added once in the batch header)
      - Replaces the grind call with grind_collect
    """
    # Remove import Mathlib (may appear with or without trailing blank line)
    snippet = re.sub(r"^import Mathlib\s*\n", "", lean_snippet)

    # Replace the grind call with grind_collect.
    # The grind_call field gives us the exact tactic text, e.g. "grind [mem_sup]".
    # We replace `:= by <grind_call>` with `:= by grind_collect` (dropping hints).
    # Also handle the two-line form `:= by\n  <grind_call>`.
    escaped = re.escape(grind_call)
    snippet = re.sub(r":=\s*by\s*\n\s*" + escaped + r"\b", ":= by grind_collect", snippet)
    snippet = re.sub(r":=\s*by\s+" + escaped + r"\b", ":= by grind_collect", snippet)

    return snippet.strip()


def build_batch_file(snippets: list[str]) -> str:
    """
    Combine multiple transformed snippets into one Lean file.
    Each snippet is wrapped in `section`/`end` to scope its opens/variables.
    """
    header = (
        "import Mathlib\n"
        "import GrindExtraction\n\n"
        "set_option maxHeartbeats 400000\n\n"
    )
    blocks = []
    for s in snippets:
        block = "section\n" + s + "\nend\n"
        blocks.append(block)
    return header + "\n".join(blocks)


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def run_batch(lean_file_str: str, log_file_str: str,
              project_root_str: str, timeout: int) -> dict:
    lean_file = Path(lean_file_str)
    log_file  = Path(log_file_str)
    project_root = Path(project_root_str)

    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            ["lake", "env", "lean", str(lean_file)],
            cwd=str(project_root),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = time.monotonic() - t0
        # grind_collect writes JSON to stdout; filter to lines starting with '{'
        json_lines = [l for l in proc.stdout.splitlines() if l.strip().startswith("{")]
        log_file.write_text("\n".join(json_lines) + ("\n" if json_lines else ""),
                            encoding="utf-8")
        return {
            "lean_file": str(lean_file),
            "log_file":  str(log_file),
            "success":   proc.returncode == 0,
            "records":   len(json_lines),
            "duration":  duration,
            "error":     proc.stderr[:2000] if proc.returncode != 0 else None,
        }
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - t0
        return {
            "lean_file": str(lean_file),
            "log_file":  str(log_file),
            "success":   False,
            "records":   0,
            "duration":  duration,
            "error":     f"timeout after {timeout}s",
        }
    except Exception as e:
        return {
            "lean_file": str(lean_file),
            "log_file":  str(log_file),
            "success":   False,
            "records":   0,
            "duration":  0.0,
            "error":     str(e),
        }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate(log_files: list[Path], out_path: Path) -> dict:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    solved = 0
    multi_cand = 0

    with out_path.open("w", encoding="utf-8") as out:
        for lf in log_files:
            if not lf.exists():
                continue
            for line in lf.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                record["dataset"] = "mathlib"
                out.write(json.dumps(record) + "\n")
                total += 1
                if record.get("solved"):
                    solved += 1
                decisions = record.get("splitDecisions", [])
                if any(len(d.get("pool", [])) >= 2 for d in decisions):
                    multi_cand += 1

    return {"total": total, "solved": solved, "multi_candidate": multi_cand}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Collect grind_collect split decisions from verified Mathlib theorems."
    )
    p.add_argument("--input",      default=None,
                   help="Input JSONL (default: training/grind_results_verified.jsonl)")
    p.add_argument("--out",        default=None,
                   help="Output JSONL (default: training/data/verified_splits.jsonl)")
    p.add_argument("--project",    default=None,
                   help="GrindExtraction project dir")
    p.add_argument("--batch-size", type=int, default=20)
    p.add_argument("--workers",    type=int, default=4)
    p.add_argument("--timeout",    type=int, default=180)
    p.add_argument("--only-plain", action="store_true",
                   help="Skip theorems that use grind with hints/options")
    p.add_argument("--dry-run",    action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    script_dir = Path(__file__).parent
    repo_root  = script_dir.parent

    input_path = Path(args.input) if args.input else script_dir / "data" / "raw" / "grind_results_verified.jsonl"
    out_path   = Path(args.out)   if args.out   else script_dir / "data" / "verified_splits.jsonl"

    if args.project:
        project_root = Path(args.project).resolve()
    else:
        project_root = find_grind_extraction_root(repo_root / "GrindExtraction")

    print(f"Input  : {input_path}  ({input_path.stat().st_size // 1024}KB)")
    print(f"Output : {out_path}")
    print(f"Project: {project_root}")

    # Load verified records
    records = []
    for line in input_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    print(f"Loaded {len(records)} verified theorems.")

    if args.only_plain:
        records = [r for r in records if r.get("grind_call") == "grind"]
        print(f"After --only-plain filter: {len(records)} theorems.")

    if not records:
        print("Nothing to process.")
        return

    # Transform snippets
    snippets = []
    for r in records:
        try:
            s = transform_snippet(r["lean_snippet"], r["grind_call"])
            snippets.append(s)
        except Exception as e:
            print(f"  WARNING: Could not transform snippet for {r.get('name')}: {e}")

    print(f"Transformed {len(snippets)} snippets.")

    if args.dry_run:
        for i, s in enumerate(snippets[:3]):
            print(f"\n--- Snippet {i} ---\n{s}\n")
        print(f"[dry-run] Would run {len(snippets)} snippets in "
              f"{(len(snippets) + args.batch_size - 1) // args.batch_size} batches.")
        return

    # Write batch files and run
    # Files go inside the project so lake uses its build cache for imports
    scratch = project_root / ".collect_scratch"
    scratch.mkdir(exist_ok=True)

    try:
        # Group into batches
        batches = [snippets[i:i+args.batch_size]
                   for i in range(0, len(snippets), args.batch_size)]
        print(f"Writing {len(batches)} batch files…")

        batch_args = []
        for idx, batch in enumerate(batches):
            lean_file = scratch / f"batch_{idx:04d}.lean"
            log_file  = scratch / f"batch_{idx:04d}.jsonl"
            lean_file.write_text(build_batch_file(batch), encoding="utf-8")
            batch_args.append((str(lean_file), str(log_file), str(project_root), args.timeout))

        print(f"Running {len(batches)} batches with {args.workers} worker(s), "
              f"timeout={args.timeout}s…")

        log_files = []
        completed = 0
        t_start = time.monotonic()
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(run_batch, *a): a for a in batch_args}
            for fut in as_completed(futures):
                result = fut.result()
                completed += 1
                elapsed = int(time.monotonic() - t_start)
                status = "OK " if result["success"] else "FAIL"
                lf = Path(result["log_file"])
                log_files.append(lf)
                name = Path(result["lean_file"]).name
                print(f"  [{completed}/{len(batches)}] {status} {name} "
                      f"({result['records']} records, {result['duration']:.1f}s "
                      f"elapsed={elapsed}s)")
                if not result["success"] and result["error"]:
                    first_error = result["error"].strip().splitlines()[0]
                    print(f"    error: {first_error}")

        # Aggregate
        print(f"\nAggregating JSONL into {out_path} …")
        stats = aggregate(log_files, out_path)

    finally:
        # Clean up batch files from project tree
        import shutil
        shutil.rmtree(scratch, ignore_errors=True)

    print(f"\nDone.")
    print(f"  Total records        : {stats['total']}")
    print(f"  Solved               : {stats['solved']}")
    print(f"  Multi-candidate steps: {stats['multi_candidate']}")
    print(f"  Output               : {out_path}")


if __name__ == "__main__":
    main()
