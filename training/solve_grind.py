"""Try to solve theorems with `grind` via AXLE, but ONLY if `simp` fails.

Logic:
1. Try `by simp`.
2. If `simp` closes the goal (AXLE returns okay=True), skip this theorem.
3. If `simp` fails, try `by grind`, then `by grind only`, then `by grind [simp]`.
4. If any grind variant closes the goal, record it.

Output: grind_solved_no_simp.jsonl
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
INPUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "combined_huge_v2.jsonl"
OUTPUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "grind_solved_no_simp.jsonl"
LIMIT = int(sys.argv[3]) if len(sys.argv) > 3 else None

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

if ENV_FILE.exists():
    for _line in ENV_FILE.read_text().splitlines():
        if "=" in _line and not _line.lstrip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

API_KEY = os.environ.get("AXLE_API_KEY")
API_URL = os.environ.get("AXLE_API_URL")
ENVIRONMENT = os.environ.get("AXLE_ENVIRONMENT")

if not API_KEY or not API_URL or not ENVIRONMENT:
    print("Error: AXLE credentials not found in environment or .env file.")
    sys.exit(1)

CONCURRENCY = 32
TIMEOUT_S = 30.0
VARIANTS = ["by grind", "by grind only", "by grind [simp]"]
SORRY_RE = re.compile(r":=\s*by(?:\s+sorry)?\s*\Z")


def make_snippet(formal_statement: str, tactic_call: str) -> str:
    body = SORRY_RE.sub(f":= {tactic_call}", formal_statement.rstrip())
    if "import Mathlib" in body:
        return f"{body}\n"
    return f"import Mathlib\n\n{body}\n"


def problem_id(formal_statement: str, rec_id: str = None) -> str:
    m = re.search(r"theorem\s+(\S+)", formal_statement)
    if m:
        return m.group(1)
    return rec_id or "unknown"


def load_existing_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            try:
                r = json.loads(line)
                if r.get("id"): out.add(r["id"])
            except: continue
    return out


async def try_solve(client, rec: dict, idx: int, total: int) -> dict | None:
    pid = problem_id(rec["formal_statement"], rec.get("id"))
    
    # 1. Try simp
    snippet_simp = make_snippet(rec["formal_statement"], "by simp")
    try:
        resp_simp = await client.check(
            content=snippet_simp,
            environment=ENVIRONMENT,
            timeout_seconds=TIMEOUT_S,
        )
        if resp_simp.okay:
            return None
    except:
        pass

    # 2. Try grind variants
    t_start = time.monotonic()
    for variant in VARIANTS:
        snippet = make_snippet(rec["formal_statement"], variant)
        try:
            resp = await client.check(
                content=snippet,
                environment=ENVIRONMENT,
                timeout_seconds=TIMEOUT_S,
            )
            if resp.okay:
                elapsed = time.monotonic() - t_start
                print(f"[{idx + 1}/{total}] OK (grind) {pid} variant: {variant} ({elapsed:.1f}s)", flush=True)
                return {
                    "id": pid,
                    "split": rec.get("split", "combined"),
                    "natural_language_statement": rec.get("natural_language_statement"),
                    "answer": rec.get("answer"),
                    "tags": rec.get("tags") or [],
                    "original_formal_statement": rec["formal_statement"],
                    "grind_call": variant.replace("by ", ""),
                    "solved_formal_statement": SORRY_RE.sub(f":= {variant}", rec["formal_statement"].rstrip()),
                    "axle_environment": ENVIRONMENT,
                    "elapsed_s": round(elapsed, 2),
                }
        except:
            continue
    return None


async def main() -> None:
    print(f"Loading input from {INPUT}...")
    done_ids = load_existing_ids(OUTPUT)
    
    todo = []
    with INPUT.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            try:
                rec = json.loads(line)
                if problem_id(rec["formal_statement"], rec.get("id")) not in done_ids:
                    todo.append(rec)
            except: continue
    
    if LIMIT is not None:
        todo = todo[:LIMIT]
    
    print(f"total_to_try={len(todo)}  env={ENVIRONMENT}  concurrency={CONCURRENCY}", flush=True)
    if not todo: return

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
                    print(f"  ... progress: {n_tried}/{len(todo)}  solved {n_solved} ({n_solved*100/n_tried:.1f}%)", flush=True)

        await asyncio.gather(*(run(i, r) for i, r in enumerate(todo)))

    out_f.close()
    print(f"\nsummary: {n_solved} solved by grind (no-simp) out of {n_tried} tried.")


if __name__ == "__main__":
    asyncio.run(main())
