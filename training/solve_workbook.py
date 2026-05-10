"""Try to solve every Lean-Workbook-Plus problem with `grind` via AXLE.

Cascading strategy: try `by grind` first; if that fails, try `by grind only`;
if that also fails, try `by grind [simp]`. The first variant that closes the
goal is recorded. Failures are dropped on the floor (per user request -- if
grind can't solve it, we don't care about it).

Output: workbook_grind_solved.jsonl, one record per solved problem with
everything needed to reproduce / re-elaborate it.

Resume: re-running picks up where it left off by reading already-written ids
from the output file.

Usage:
    py -3.13 solve_workbook.py [LIMIT]
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
ENV_FILE = ROOT / ".env"
INPUT = ROOT / "data" / "lean_workbook.json"
OUTPUT = ROOT / "workbook_grind_solved_verified.jsonl"
SPLIT = "lean_workbook_plus"

# UTF-8 stdout so progress lines containing Lean's unicode never crash.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

for _line in ENV_FILE.read_text().splitlines():
    if "=" in _line and not _line.lstrip().startswith("#"):
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())

API_KEY = os.environ["AXLE_API_KEY"]
API_URL = os.environ["AXLE_API_URL"]
ENVIRONMENT = os.environ["AXLE_ENVIRONMENT"]

CONCURRENCY = 8
TIMEOUT_S = 30.0

# Cascading grind variants tried per problem, in order.
VARIANTS = ["by grind", "by grind only", "by grind [simp]"]

# Match `:= by sorry` (with arbitrary whitespace) at end of statement.
SORRY_RE = re.compile(r":=\s*by\s+sorry\s*\Z")


def make_snippet(formal_statement: str, variant: str) -> str:
    """Replace the trailing `:= by sorry` with `:= <variant>`."""
    body = SORRY_RE.sub(f":= {variant}", formal_statement.rstrip())
    return f"import Mathlib\n\n{body}\n"


def problem_id(formal_statement: str) -> str:
    # statements start with `theorem lean_workbook_plus_NNN ...`
    m = re.match(r"theorem\s+(\S+)", formal_statement)
    return m.group(1) if m else ""


def load_existing_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("id"):
            out.add(r["id"])
    return out


async def try_solve(client, rec: dict, idx: int, total: int) -> dict | None:
    """Cascade through VARIANTS. Return solved record on first success, else None."""
    pid = problem_id(rec["formal_statement"])
    t_total = time.monotonic()
    for variant in VARIANTS:
        snippet = make_snippet(rec["formal_statement"], variant)
        try:
            resp = await client.check(
                content=snippet,
                environment=ENVIRONMENT,
                timeout_seconds=TIMEOUT_S,
            )
        except Exception:
            continue
        if resp.okay:
            elapsed = time.monotonic() - t_total
            print(f"[{idx + 1}/{total}] OK ({elapsed:.1f}s) {pid}  variant: {variant}", flush=True)
            return {
                "id": pid,
                "split": rec["split"],
                "natural_language_statement": rec.get("natural_language_statement"),
                "answer": rec.get("answer"),
                "tags": rec.get("tags") or [],
                "original_formal_statement": rec["formal_statement"],
                "grind_call": variant.replace("by ", ""),
                "solved_formal_statement": SORRY_RE.sub(f":= {variant}", rec["formal_statement"].rstrip()),
                "axle_environment": ENVIRONMENT,
                "elapsed_s": round(elapsed, 2),
            }
    return None


async def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None

    with INPUT.open("r", encoding="utf-8") as f:
        data = json.load(f)
    problems = [r for r in data if r["split"] == SPLIT]

    done_ids = load_existing_ids(OUTPUT)
    todo = [r for r in problems if problem_id(r["formal_statement"]) not in done_ids]
    if limit is not None:
        todo = todo[:limit]
    print(
        f"split={SPLIT}  total={len(problems)}  already-solved={len(done_ids)}  "
        f"to-try={len(todo)}  env={ENVIRONMENT}  variants={VARIANTS}",
        flush=True,
    )
    if not todo:
        return

    from axle.client import AxleClient

    sem = asyncio.Semaphore(CONCURRENCY)
    out_f = OUTPUT.open("a", encoding="utf-8")
    write_lock = asyncio.Lock()
    n_solved = 0
    n_tried = 0

    async with AxleClient(api_key=API_KEY, url=API_URL, base_timeout_seconds=TIMEOUT_S) as client:

        async def run(idx: int, rec: dict) -> None:
            nonlocal n_solved, n_tried
            async with sem:
                solved = await try_solve(client, rec, idx, len(todo))
            async with write_lock:
                n_tried += 1
                if solved:
                    out_f.write(json.dumps(solved, ensure_ascii=False) + "\n")
                    out_f.flush()
                    n_solved += 1
                if n_tried % 50 == 0:
                    rate = n_solved * 100.0 / n_tried
                    print(
                        f"  ... progress: {n_tried}/{len(todo)}  solved {n_solved} ({rate:.1f}%)",
                        flush=True,
                    )

        await asyncio.gather(*(run(i, r) for i, r in enumerate(todo)))

    out_f.close()
    print(flush=True)
    print(
        f"summary: {n_solved} solved out of {n_tried} tried ({n_solved * 100.0 / max(n_tried, 1):.1f}%)",
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
