"""
Collect training data from Mathlib theorems proved by plain `grind`.

Usage:
    python3 training/collect.py [options]

For each mathlib file containing sole-proof `grind` calls, this script:
  1. Extracts the theorem signatures (via a text-level state machine)
  2. Generates anonymous `example` blocks proved by `neural_grind`
  3. Runs them under `GRIND_LOG` to collect split decisions
  4. Aggregates all JSONL records into one output file

Options:
  --mathlib PATH     Mathlib/ directory (default: auto-detect)
  --project PATH     NeuralTactic/ project (default: auto-detect)
  --out PATH         Output JSONL (default: training/data/collected.jsonl)
  --max-files N      Max mathlib files to scan (default: 200)
  --batch-size N     Examples per Lean file (default: 20)
  --workers N        Parallel Lean processes (default: 2)
  --timeout N        Seconds per batch file (default: 120)
  --filter-success   Keep only success records
  --dry-run          Print extracted theorems, don't run Lean
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def find_project_root(start=None) -> Path:
    """Walk up from start looking for a lakefile.toml that belongs to NeuralTactic."""
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        lf = candidate / "lakefile.toml"
        if lf.exists() and "NeuralTactic" in lf.read_text():
            return candidate
        lf2 = candidate / "lakefile.lean"
        if lf2.exists() and "NeuralTactic" in lf2.read_text():
            return candidate
    raise FileNotFoundError(
        "Could not find NeuralTactic project root. "
        "Run from inside the NeuralTactic/ directory or pass --project."
    )


def find_mathlib(project_root: Path) -> Path:
    candidate = project_root / ".lake" / "packages" / "mathlib" / "Mathlib"
    if candidate.is_dir():
        return candidate
    raise FileNotFoundError(
        f"Mathlib not found at {candidate}. "
        "Run `lake update` inside the NeuralTactic project first."
    )


# ---------------------------------------------------------------------------
# File scanning
# ---------------------------------------------------------------------------

def scan_files(mathlib_root: Path, max_files: int) -> list[tuple[Path, int]]:
    """
    Find .lean files with sole-proof grind calls, sorted by density descending.
    Returns list of (path, count) tuples, capped at max_files.
    """
    try:
        result = subprocess.run(
            ["grep", "-rn", r"\bgrind\b", "--include=*.lean", str(mathlib_root)],
            capture_output=True, text=True, timeout=60
        )
        lines = result.stdout.splitlines()
    except subprocess.TimeoutExpired:
        print("WARNING: grep timed out; falling back to empty list", file=sys.stderr)
        return []

    # Count hits per file
    counts: dict[Path, int] = {}
    for line in lines:
        parts = line.split(":", 1)
        if parts:
            p = Path(parts[0])
            counts[p] = counts.get(p, 0) + 1

    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return ranked[:max_files]


# ---------------------------------------------------------------------------
# Extraction state machine
# ---------------------------------------------------------------------------

DECL_START_RE = re.compile(
    r"^\s*(?:@\[.*?\]\s*)?(?:private\s+|protected\s+)?(?:theorem|lemma)\s+\w"
)
# Match := by grind (optionally followed by [...] hints or end of line)
BY_GRIND_INLINE_RE = re.compile(r":=\s*by\s+grind\b")
BY_KEYWORD_RE = re.compile(r":=\s*by\s*$")
GRIND_ONLY_RE = re.compile(r"^\s*grind\b")
ATTR_LINE_RE = re.compile(r"^\s*@\[")
WHERE_RE = re.compile(r"\bwhere\b")
TERMINATION_RE = re.compile(r"\btermination_by\b")
OPEN_BRACKET_RE = re.compile(r"[(\[{]")
CLOSE_BRACKET_RE = re.compile(r"[)\]}]")


def _bracket_delta(line: str) -> int:
    return len(OPEN_BRACKET_RE.findall(line)) - len(CLOSE_BRACKET_RE.findall(line))


_SORT_TYPE_RE = re.compile(r"^(?:Sort|Type|Prop|Universe|outParam)")


def _has_term_binder(variable_line: str) -> bool:
    """True if a `variable` line introduces any term-level binding (not Sort/Type/Prop)."""
    for m in re.finditer(r"\{([^}]+)\}|\(([^)]+)\)|\[([^\]]+)\]", variable_line):
        binder = m.group(1) or m.group(2) or m.group(3)
        colon = binder.find(":")
        if colon < 0:
            continue
        type_part = binder[colon + 1:].strip()
        if not _SORT_TYPE_RE.match(type_part):
            return True
    return False


def has_variable_block(lines: list[str], theorem_lineno: int) -> bool:
    """
    True if any `variable` block before the theorem introduces term-level bindings
    (i.e. variables whose type is not Sort/Type/Prop — those are auto-bound by Lean).
    """
    for line in lines[:theorem_lineno]:
        if re.match(r"^\s*variable\b", line) and _has_term_binder(line):
            return True
    return False


def extract_variable_context(lines: list[str], theorem_lineno: int) -> str:
    """
    Return all variable bindings before the theorem as an explicit-parameter string.
    Both sort-level ({α : Type*}) and term-level ((e : α ≃ β)) bindings are included.
    Lean auto-bounds sort-level ones anyway, but including them is harmless and explicit.
    """
    params: list[str] = []
    for line in lines[:theorem_lineno]:
        if not re.match(r"^\s*variable\b", line):
            continue
        rest = re.sub(r"^\s*variable\s*", "", re.sub(r"--.*$", "", line)).strip()
        # Extract binders: (x : T), {x : T}, [x : T]
        for m in re.finditer(r'(\()([^()]*?)(\))|(\{)([^{}]*?)(\})|(\[)([^\[\]]*?)(\])', rest):
            if m.group(1):  # round bracket
                inner, open_b, close_b = m.group(2), "(", ")"
            elif m.group(4):  # curly bracket
                inner, open_b, close_b = m.group(5), "{", "}"
            else:  # square bracket
                inner, open_b, close_b = m.group(8), "[", "]"
            if ":" in inner:
                params.append(f"{open_b}{inner}{close_b}")
    return " ".join(params)


def extract_opens(lines: list[str], theorem_lineno: int) -> list[str]:
    """Return all `open X` identifiers active before theorem_lineno (non-scoped opens)."""
    opens: list[str] = []
    for line in lines[:theorem_lineno]:
        stripped = re.sub(r"--.*$", "", line).strip()
        # Match: open Foo Bar (but not `open X in` scoped opens that end with ' in')
        m = re.match(r"^open\s+((?:\w[\w.]*\s*)+)$", stripped)
        if m:
            opens.extend(m.group(1).split())
    return opens


def extract_sole_grind_theorems(file_path: Path) -> list[dict]:
    """
    Return list of {source, signature_text, var_context, opens, line} dicts for
    theorems/lemmas proved by `grind` (with or without hints).
    Variable context and open identifiers are tracked incrementally as we scan.
    """
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines()
    results: list[dict] = []

    state = "IDLE"
    decl_start_line = 0
    sig_lines: list[str] = []
    bracket_depth = 0
    in_block_comment = False

    # Track variable context and opens incrementally (avoids O(n²) re-scan)
    current_var_params: list[str] = []
    current_opens: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Track block comments (/-  -/)
        if in_block_comment:
            if "-/" in line:
                in_block_comment = False
            i += 1
            continue
        if "/-" in line and "-/" not in line[line.index("/-") + 2:]:
            in_block_comment = True
            i += 1
            continue

        # Strip line comments for parsing
        stripped = re.sub(r"--.*$", "", line)

        # Incrementally track variable context and opens while in IDLE state
        if state == "IDLE":
            s = stripped.strip()
            if re.match(r"^variable\b", s):
                # Accumulate term-level variable bindings
                rest = re.sub(r"^variable\s*", "", s)
                for m in re.finditer(r'(\()([^()]*?)(\))|(\{)([^{}]*?)(\})|(\[)([^\[\]]*?)(\])', rest):
                    if m.group(1):
                        inner, ob, cb = m.group(2), "(", ")"
                    elif m.group(4):
                        inner, ob, cb = m.group(5), "{", "}"
                    else:
                        inner, ob, cb = m.group(8), "[", "]"
                    if ":" in inner:
                        current_var_params.append(f"{ob}{inner}{cb}")
            elif re.match(r"^open\s+((?:\w[\w.]*\s*)+)$", s):
                # Accumulate non-scoped opens
                m = re.match(r"^open\s+((?:\w[\w.]*\s*)+)$", s)
                if m:
                    current_opens.extend(m.group(1).split())
            elif re.match(r"^(namespace|section|end)\b", s):
                # Reset context on namespace/section boundaries
                current_var_params = []
                current_opens = []

        if state == "IDLE":
            # Skip attribute lines
            if ATTR_LINE_RE.match(stripped):
                i += 1
                continue
            if DECL_START_RE.match(stripped):
                # Snapshot current context for this theorem
                snap_var = " ".join(current_var_params)
                snap_opens = list(dict.fromkeys(current_opens))  # deduplicated

                # Start collecting a declaration
                decl_start_line = i
                sig_lines = [stripped]
                bracket_depth = _bracket_delta(stripped)
                # Inline pattern: := by grind on same line
                if BY_GRIND_INLINE_RE.search(stripped):
                    sig = " ".join(sig_lines).strip()
                    if not WHERE_RE.search(sig) and not TERMINATION_RE.search(sig):
                        # Extract just the signature up to ':= by grind[...]'
                        sig_clean = re.sub(r"\s*:=\s*by\s+grind\b.*$", "", sig)
                        results.append({
                            "source": f"{file_path}:{decl_start_line + 1}",
                            "signature_text": sig_clean.strip(),
                            "var_context": snap_var,
                            "opens": snap_opens,
                            "line": decl_start_line + 1,
                        })
                    state = "IDLE"
                    i += 1
                    continue
                # Check for := by at end (Pattern B start)
                if BY_KEYWORD_RE.search(stripped) and bracket_depth <= 0:
                    state = "IN_PROOF"
                elif re.search(r":=\s*$", stripped) and bracket_depth <= 0:
                    # Bare := at EOL → term-mode proof on next line; skip
                    state = "IDLE"
                elif re.search(r":=\s*\S", stripped) and not BY_GRIND_INLINE_RE.search(stripped):
                    # := something non-by on same line → term-mode proof inline; skip
                    state = "IDLE"
                else:
                    state = "IN_DECL"

        elif state == "IN_DECL":
            # A new declaration starting means the previous one had a term-mode proof — bail.
            if DECL_START_RE.match(stripped):
                state = "IDLE"
                continue  # re-process without incrementing i

            sig_lines.append(stripped)
            bracket_depth += _bracket_delta(stripped)

            # Inline := by grind[...]
            if BY_GRIND_INLINE_RE.search(stripped):
                sig = " ".join(sig_lines).strip()
                if not WHERE_RE.search(sig) and not TERMINATION_RE.search(sig):
                    sig_clean = re.sub(r"\s*:=\s*by\s+grind\b.*$", "", sig)
                    results.append({
                        "source": f"{file_path}:{decl_start_line + 1}",
                        "signature_text": sig_clean.strip(),
                        "var_context": snap_var,
                        "opens": snap_opens,
                        "line": decl_start_line + 1,
                    })
                state = "IDLE"
                i += 1
                continue

            # := by at end with balanced brackets → Pattern B
            if BY_KEYWORD_RE.search(stripped) and bracket_depth <= 0:
                state = "IN_PROOF"
                i += 1
                continue

            # Bare := at EOL (term-mode proof on next line) — bail
            if re.search(r":=\s*$", stripped):
                state = "IDLE"
                i += 1
                continue

            # := followed by non-by content on same line — bail
            if re.search(r":=\s*\S", stripped) and not BY_KEYWORD_RE.search(stripped):
                state = "IDLE"
                i += 1
                continue

        elif state == "IN_PROOF":
            if GRIND_ONLY_RE.match(line):
                sig = " ".join(sig_lines).strip()
                # Strip the trailing ':= by'
                sig_clean = re.sub(r"\s*:=\s*by\s*$", "", sig).strip()
                if not WHERE_RE.search(sig_clean) and not TERMINATION_RE.search(sig_clean):
                    results.append({
                        "source": f"{file_path}:{decl_start_line + 1}",
                        "signature_text": sig_clean,
                        "var_context": snap_var,
                        "opens": snap_opens,
                        "line": decl_start_line + 1,
                    })
            # Whether or not this was 'grind', we're done with this proof
            state = "IDLE"

        i += 1

    return results


# ---------------------------------------------------------------------------
# Example generation
# ---------------------------------------------------------------------------

_DECL_NAME_RE = re.compile(
    r"^\s*(?:private\s+|protected\s+)?(?:theorem|lemma)\s+\w[\w.']*"
)


def signature_to_example(sig: str, var_context: str = "") -> str:
    """
    Strip the declaration keyword and name, keep params + type.
    Prepends var_context (extracted variable bindings) if provided.
    E.g. 'theorem foo (h : P) : Q' → 'example (h : P) : Q := by neural_grind'
    """
    sig = re.sub(r"^\s*(?:private\s+|protected\s+)?", "", sig)
    sig = re.sub(r"^(?:theorem|lemma)\s+\w[\w.']*\s*", "", sig)
    prefix = f"{var_context} " if var_context else ""
    return f"example {prefix}{sig.strip()} := by neural_collect"


def generate_batch_file(examples: list[dict]) -> str:
    header = (
        "import Mathlib\n"
        "import NeuralTactic\n\n"
        "set_option maxHeartbeats 400000\n\n"
    )
    blocks = []
    for ex in examples:
        try:
            example_line = signature_to_example(
                ex["signature_text"], ex.get("var_context", "")
            )
        except Exception:
            continue
        opens = ex.get("opens", [])
        if opens:
            open_stmt = "open " + " ".join(dict.fromkeys(opens))  # deduplicated, ordered
            block = (
                f"-- source: {ex['source']}\n"
                f"section\n"
                f"{open_stmt}\n"
                f"{example_line}\n"
                f"end\n"
            )
        else:
            block = f"-- source: {ex['source']}\n{example_line}\n"
        blocks.append(block)
    return header + "\n".join(blocks)


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def run_batch(lean_file_str: str, log_file_str: str,
              project_root_str: str, timeout: int) -> dict:
    lean_file = Path(lean_file_str)
    log_file = Path(log_file_str)
    project_root = Path(project_root_str)

    env = os.environ.copy()
    env["GRIND_LOG"] = str(log_file)
    # If GRIND_MODEL is set, also expose GRIND_SERVE so CollectTactic can find
    # a model server. Defaults to the exp09 server if not explicitly provided.
    if "GRIND_MODEL" in env and "GRIND_SERVE" not in env:
        serve_default = Path(__file__).parent / "experiments" / "exp09_heuristics" / "serve.py"
        env["GRIND_SERVE"] = str(serve_default)
    # Set GRIND_PYTHON so Lean's subprocess uses the conda/venv python explicitly.
    # Also prepend to PATH as fallback for older code paths.
    env["GRIND_PYTHON"] = sys.executable
    python_bin = str(Path(sys.executable).parent)
    env["PATH"] = python_bin + ":" + env.get("PATH", "")

    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            ["lake", "env", "lean", str(lean_file)],
            cwd=str(project_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = time.monotonic() - t0
        # lake exits non-zero when individual theorems fail — that's expected.
        # A real failure is when stderr contains an error other than the
        # "lakefile.lean and lakefile.toml" coexistence warning.
        stderr_clean = "\n".join(
            l for l in proc.stderr.splitlines()
            if "lakefile" not in l.lower() and l.strip()
        )
        hard_fail = proc.returncode != 0 and bool(stderr_clean)
        return {
            "lean_file": lean_file,
            "log_file": log_file,
            "success": not hard_fail,
            "duration": duration,
            "error": stderr_clean[:2000] if hard_fail else None,
        }
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - t0
        return {
            "lean_file": lean_file,
            "log_file": log_file,
            "success": False,
            "duration": duration,
            "error": f"timeout after {timeout}s",
        }
    except Exception as e:
        return {
            "lean_file": lean_file,
            "log_file": log_file,
            "success": False,
            "duration": 0.0,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate(log_files: list[Path], out_path: Path,
              filter_success: bool = False) -> dict:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with_steps = 0
    with_multi = 0

    with out_path.open("w") as out:
        for lf in log_files:
            if not lf.exists():
                continue
            try:
                content = lf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if filter_success and record.get("outcome") != "success":
                    continue
                out.write(line + "\n")
                total += 1
                steps = record.get("steps", [])
                if steps:
                    with_steps += 1
                if any(len(s.get("candidates", [])) >= 2 for s in steps):
                    with_multi += 1

    return {"total": total, "with_steps": with_steps,
            "with_multiple_candidates": with_multi}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Collect neural_grind training data from Mathlib theorems."
    )
    p.add_argument("--mathlib",  default=None, help="Path to Mathlib/ directory")
    p.add_argument("--project",  default=None, help="Path to NeuralTactic/ project")
    p.add_argument("--out",      default="training/data/collected.jsonl",
                   help="Output JSONL file")
    p.add_argument("--max-files", type=int, default=200,
                   help="Max mathlib files to scan")
    p.add_argument("--batch-size", type=int, default=20,
                   help="Examples per Lean batch file")
    p.add_argument("--workers",  type=int, default=2,
                   help="Parallel Lean processes")
    p.add_argument("--timeout",  type=int, default=120,
                   help="Seconds per batch file")
    p.add_argument("--filter-success", action="store_true",
                   help="Keep only success records in output")
    p.add_argument("--dry-run",  action="store_true",
                   help="Print extracted theorems without running Lean")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # Resolve project and mathlib roots
    if args.project:
        project_root = Path(args.project).resolve()
    else:
        project_root = find_project_root()

    if args.mathlib:
        mathlib_root = Path(args.mathlib).resolve()
    else:
        mathlib_root = find_mathlib(project_root)

    print(f"Project root : {project_root}")
    print(f"Mathlib root : {mathlib_root}")

    # Phase 1: discover files
    print(f"Scanning mathlib for grind-heavy files (top {args.max_files})…")
    ranked_files = scan_files(mathlib_root, args.max_files)
    print(f"  Found {len(ranked_files)} candidate files.")

    # Phase 2: extract sole-grind theorems
    all_examples: list[dict] = []
    for file_path, count in ranked_files:
        found = extract_sole_grind_theorems(file_path)
        all_examples.extend(found)

    print(f"Extracted {len(all_examples)} sole-grind theorem signatures.")

    if args.dry_run:
        print("\n--- First 20 extracted signatures ---")
        for ex in all_examples[:20]:
            print(f"  [{ex['source']}]")
            print(f"  {signature_to_example(ex['signature_text'], ex.get('var_context', ''))}")
            print()
        return

    if not all_examples:
        print("No examples found — nothing to do.")
        return

    # Phase 3: batch into Lean files inside the project (so lake uses .olean cache)
    batch_size = args.batch_size
    batches = [
        all_examples[i:i + batch_size]
        for i in range(0, len(all_examples), batch_size)
    ]
    tmpdir = project_root / ".collect_scratch"
    tmpdir.mkdir(exist_ok=True)
    print(f"Writing {len(batches)} batch files to {tmpdir} …")

    batch_pairs: list[tuple[Path, Path]] = []
    for i, batch in enumerate(batches):
        lean_path = tmpdir / f"batch_{i:04d}.lean"
        log_path = tmpdir / f"batch_{i:04d}.jsonl"
        lean_path.write_text(generate_batch_file(batch), encoding="utf-8")
        batch_pairs.append((lean_path, log_path))

    # Phase 4: run in parallel
    print(f"Running {len(batch_pairs)} batches with {args.workers} worker(s), "
          f"timeout={args.timeout}s each …")

    results: list[dict] = []
    completed = 0
    t_start = time.monotonic()

    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                run_batch,
                str(lp), str(lq),
                str(project_root),
                args.timeout
            ): (lp, lq)
            for lp, lq in batch_pairs
        }
        for fut in as_completed(futures):
            r = fut.result()
            results.append(r)
            completed += 1
            elapsed = time.monotonic() - t_start
            status = "OK" if r["success"] else "FAIL"
            print(f"  [{completed}/{len(batch_pairs)}] {status} "
                  f"{r['lean_file'].name} ({r['duration']:.1f}s elapsed={elapsed:.0f}s)")
            if not r["success"] and r.get("error"):
                # Print first line of error for quick diagnosis
                first_err = r["error"].splitlines()[0] if r["error"] else ""
                print(f"    error: {first_err[:120]}")

    # Phase 5: aggregate
    log_files = [r["log_file"] for r in results]
    out_path = Path(args.out)
    print(f"\nAggregating JSONL into {out_path} …")
    stats = aggregate(log_files, out_path, filter_success=args.filter_success)

    print(f"\nDone.")
    print(f"  Total records        : {stats['total']}")
    print(f"  With splits          : {stats['with_steps']}")
    print(f"  Multi-candidate steps: {stats['with_multiple_candidates']}")
    print(f"  Output               : {out_path}")


if __name__ == "__main__":
    main()
