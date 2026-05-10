"""
Step 6: Compare `aesop_with_overrides` against the default on the held-out
test set.

For each record in `aesop_data_split/test.jsonl`:
  1. Take the original `solved_formal_statement` (which ends with `by aesop`).
  2. Rewrite to use `aesop_with_overrides` and enable `trace.aesop.stats`.
  3. Run twice via `lake env lean` from the aesop_with_overrides project:
       - default:   AESOP_OVERRIDES_JSON unset
       - custom:    AESOP_OVERRIDES_JSON=<our overrides file>
  4. Capture wall-clock elapsed time, success/failure, and parsed stats lines.

Output:
  - per_theorem.jsonl    — one record per theorem with both conditions' results
  - summary.json         — aggregate stats: success rates, mean elapsed,
                           mean rule-application counts, paired wins/losses.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).parent
PROJECT_ROOT = (ROOT.parent.parent / "aesop_with_overrides").resolve()
DEFAULT_OVERRIDES = (ROOT / "aesop_overrides.json").resolve()
TEST_FILE = (ROOT.parent / "aesop_data_split" / "test.jsonl").resolve()
DEFAULT_OUT_DIR = ROOT / "comparison"

HEADER = """\
import Mathlib
import AesopWithOverrides

set_option maxHeartbeats 400000
set_option trace.aesop.stats true
"""

# Rewrite "by aesop" -> "by aesop_with_overrides"
AESOP_RE = re.compile(r":=\s*by\s+aesop\b\s*$", re.MULTILINE)


def rewrite(src: str) -> str:
    body = src
    # Strip leading `import Mathlib` if present.
    body = re.sub(r"^import Mathlib\s*\n", "", body)
    # Replace trailing `by aesop` with `by aesop_with_overrides`.
    body = AESOP_RE.sub(":= by aesop_with_overrides", body)
    return body.rstrip() + "\n"


# Parse trace.aesop.stats output.  Lines we care about:
#   "Total: 123ms"
#   "Search: 100ms"
#   "Rule applications: 80ms [total / successful / failed]"
#   one line per rule:  "[N total_ms / S succ_ms / F fail_ms] <rule_name>"
TIME_LINE_RE = re.compile(
    r"\[aesop\.stats\]\s*(?:[✅❌️\s]*)?(Total|Search|Rule applications):\s*(\d+(?:\.\d+)?(?:e[+-]?\d+)?)([a-zµ]+)"
)
RULE_LINE_RE = re.compile(
    r"\[aesop\.stats\]\s*\[(\d+)\s+\S+\s+/\s+(\d+)\s+\S+\s+/\s+(\d+)\s+\S+\]\s+(\S+)"
)


def to_ms(value: float, unit: str) -> float:
    unit = unit.lower()
    if unit in ("ns",):
        return value / 1e6
    if unit in ("µs", "us"):
        return value / 1e3
    if unit in ("ms",):
        return value
    if unit in ("s",):
        return value * 1000
    return value  # unknown, keep raw


def parse_stats(stdout: str) -> dict:
    total_ms = None
    search_ms = None
    rule_apps_ms = None
    total_apps = 0
    succ_apps = 0
    fail_apps = 0
    rule_count = 0
    for line in stdout.splitlines():
        m = TIME_LINE_RE.search(line)
        if m:
            kind, val, unit = m.group(1), float(m.group(2)), m.group(3)
            ms = to_ms(val, unit)
            if kind == "Total":
                total_ms = ms
            elif kind == "Search":
                search_ms = ms
            elif kind == "Rule applications":
                rule_apps_ms = ms
            continue
        m = RULE_LINE_RE.search(line)
        if m:
            t, s, f = int(m.group(1)), int(m.group(2)), int(m.group(3))
            total_apps += t
            succ_apps += s
            fail_apps += f
            rule_count += 1
    return {
        "total_ms": total_ms,
        "search_ms": search_ms,
        "rule_apps_ms": rule_apps_ms,
        "total_rule_applications": total_apps,
        "successful_rule_applications": succ_apps,
        "failed_rule_applications": fail_apps,
        "distinct_rules_invoked": rule_count,
    }


def get_lake_env() -> dict:
    proc = subprocess.run(
        ["lake", "env"], cwd=str(PROJECT_ROOT), text=True,
        capture_output=True, timeout=60,
    )
    env = os.environ.copy()
    for line in proc.stdout.splitlines():
        k, sep, v = line.partition("=")
        if sep:
            env[k] = v
    return env


def run_once(lean_file: Path, env: dict, lean_binary: str, timeout: int) -> dict:
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            [lean_binary, str(lean_file)],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        wall = time.monotonic() - t0
        return {
            "exit_code": proc.returncode,
            "wall_seconds": wall,
            "stdout": proc.stdout,
            "stderr": proc.stderr[:2000],
            **parse_stats(proc.stdout),
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "wall_seconds": time.monotonic() - t0,
            "stdout": "", "stderr": f"timeout after {timeout}s",
            "total_ms": None, "search_ms": None, "rule_apps_ms": None,
            "total_rule_applications": 0, "successful_rule_applications": 0,
            "failed_rule_applications": 0, "distinct_rules_invoked": 0,
        }


# --- worker ----------------------------------------------------------------

def _worker(record_str: str, scratch_dir: str, env_default: dict, env_custom: dict,
            lean_binary: str, timeout: int) -> dict:
    record = json.loads(record_str)
    rid = record["jsonl_id"]
    src = record.get("file") and Path(record["file"]).read_text() if False else None
    # We need the original source.  The JSONL records from collect step include
    # the rewritten file path but not necessarily the source.  We pull from the
    # `solved_formal_statement` field of the matching jsonl_id in
    # finecorpus / parts files.  Easier: the test.jsonl already has the file
    # contents indirectly via stored fields — let us pass solved_formal_statement.
    body = record["__src"]
    rewritten = rewrite(body)
    full = HEADER + "\n" + rewritten

    lean_file = Path(scratch_dir) / f"{rid}.lean"
    lean_file.write_text(full)

    default_run = run_once(lean_file, env_default, lean_binary, timeout)
    custom_run = run_once(lean_file, env_custom, lean_binary, timeout)

    return {
        "jsonl_id": rid,
        "default": {k: v for k, v in default_run.items() if k != "stdout"},
        "custom":  {k: v for k, v in custom_run.items()  if k != "stdout"},
        "default_success": default_run["exit_code"] == 0,
        "custom_success":  custom_run["exit_code"] == 0,
    }


# --- main -----------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200,
                    help="number of test records to process (default: 200)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--source", default=None,
                    help="JSONL containing solved_formal_statement keyed by id "
                         "(default: training/finecorpus_numina_workbook_aesop_stable.jsonl)")
    ap.add_argument("--overrides", default=str(DEFAULT_OVERRIDES),
                    help="Path to aesop overrides JSON (default: aesop_overrides.json)")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR),
                    help="Output directory for per_theorem.jsonl and summary.json")
    args = ap.parse_args()

    overrides_file = Path(args.overrides).resolve()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    per_theorem_path = out_dir / "per_theorem.jsonl"
    summary_path = out_dir / "summary.json"

    src_file = Path(args.source) if args.source else \
        (ROOT.parent / "finecorpus_numina_workbook_aesop_stable.jsonl")
    print(f"Source theorems: {src_file}")
    sources: dict = {}
    with src_file.open() as f:
        for line in f:
            r = json.loads(line)
            sources[r["id"]] = r.get("solved_formal_statement", "")

    # Add the parts and the new file too, in case test set IDs are spread.
    extras = [
        ROOT.parent / "aesop_parts_combined.jsonl",
        ROOT.parent / "finecorpus_numina_workbook_aesop.jsonl",
    ]
    for p in extras:
        if p.exists():
            with p.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    r = json.loads(line)
                    sources.setdefault(r["id"], r.get("solved_formal_statement", ""))
    print(f"Loaded source for {len(sources)} ids")

    test_records = []
    with TEST_FILE.open() as f:
        for line in f:
            r = json.loads(line)
            rid = r["jsonl_id"]
            body = sources.get(rid)
            if not body:
                continue
            r["__src"] = body
            test_records.append(r)
            if len(test_records) >= args.limit:
                break
    print(f"Test records to process: {len(test_records)}")

    env_default = get_lake_env()
    env_default.pop("AESOP_OVERRIDES_JSON", None)
    env_custom = dict(env_default)
    env_custom["AESOP_OVERRIDES_JSON"] = str(overrides_file)
    lean_binary = env_default.get("LEAN", "lean")

    scratch = tempfile.mkdtemp(prefix="aesop_compare_")
    print(f"Scratch dir: {scratch}")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Overrides:   {overrides_file}")
    print(f"Out dir:     {out_dir}")
    print()

    results = []
    t_start = time.monotonic()
    try:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [
                pool.submit(_worker, json.dumps(r), scratch,
                            env_default, env_custom, lean_binary, args.timeout)
                for r in test_records
            ]
            done = 0
            for fut in as_completed(futures):
                res = fut.result()
                results.append(res)
                done += 1
                d_ok = "OK " if res["default_success"] else "FAIL"
                c_ok = "OK " if res["custom_success"]  else "FAIL"
                d_t = res["default"]["wall_seconds"]
                c_t = res["custom"]["wall_seconds"]
                d_apps = res["default"]["total_rule_applications"]
                c_apps = res["custom"]["total_rule_applications"]
                el = int(time.monotonic() - t_start)
                print(f"  [{done}/{len(test_records)}] elapsed={el}s "
                      f"def={d_ok} {d_t:5.1f}s apps={d_apps:4d}  "
                      f"cus={c_ok} {c_t:5.1f}s apps={c_apps:4d}  {res['jsonl_id'][:50]}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    per_theorem_path.write_text("\n".join(json.dumps(r) for r in results) + "\n")

    # Aggregate
    n = len(results)
    def_succ = sum(1 for r in results if r["default_success"])
    cus_succ = sum(1 for r in results if r["custom_success"])
    both_ok  = [r for r in results if r["default_success"] and r["custom_success"]]

    def mean(xs):
        xs = [x for x in xs if x is not None]
        return sum(xs) / len(xs) if xs else None

    def sum_field(rs, side, field):
        return sum(r[side][field] or 0 for r in rs)

    def_wall = [r["default"]["wall_seconds"] for r in both_ok]
    cus_wall = [r["custom"]["wall_seconds"]  for r in both_ok]
    def_apps = [r["default"]["total_rule_applications"] for r in both_ok]
    cus_apps = [r["custom"]["total_rule_applications"]  for r in both_ok]
    def_fail = [r["default"]["failed_rule_applications"] for r in both_ok]
    cus_fail = [r["custom"]["failed_rule_applications"]  for r in both_ok]
    def_succ_apps = [r["default"]["successful_rule_applications"] for r in both_ok]
    cus_succ_apps = [r["custom"]["successful_rule_applications"]  for r in both_ok]
    def_total_ms = [r["default"]["total_ms"] for r in both_ok]
    cus_total_ms = [r["custom"]["total_ms"]  for r in both_ok]

    cus_faster = sum(1 for r in both_ok if r["custom"]["wall_seconds"] < r["default"]["wall_seconds"])
    cus_fewer_apps = sum(1 for r in both_ok if r["custom"]["total_rule_applications"]
                                              < r["default"]["total_rule_applications"])
    cus_fewer_fail = sum(1 for r in both_ok if r["custom"]["failed_rule_applications"]
                                              < r["default"]["failed_rule_applications"])

    summary = {
        "n_records": n,
        "default_success": def_succ,
        "custom_success":  cus_succ,
        "both_succeed":    len(both_ok),
        "comparison_basis": "both_succeed",
        "wall_seconds": {
            "default_mean":  mean(def_wall),
            "custom_mean":   mean(cus_wall),
            "custom_faster": cus_faster,
            "tie_or_default_faster": len(both_ok) - cus_faster,
        },
        "aesop_total_ms": {
            "default_mean":  mean(def_total_ms),
            "custom_mean":   mean(cus_total_ms),
        },
        "rule_applications": {
            "default_mean":  mean(def_apps),
            "custom_mean":   mean(cus_apps),
            "custom_fewer":  cus_fewer_apps,
        },
        "failed_rule_applications": {
            "default_mean":  mean(def_fail),
            "custom_mean":   mean(cus_fail),
            "custom_fewer":  cus_fewer_fail,
        },
        "successful_rule_applications": {
            "default_mean":  mean(def_succ_apps),
            "custom_mean":   mean(cus_succ_apps),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2))

    print()
    print("=== Summary ===")
    print(json.dumps(summary, indent=2))
    print()
    print(f"Wrote per-theorem results to {per_theorem_path}")
    print(f"Wrote summary to            {summary_path}")


if __name__ == "__main__":
    main()
