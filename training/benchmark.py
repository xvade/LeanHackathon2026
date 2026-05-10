"""
benchmark.py - compare real `grind` vs real `neural_grind`.

This benchmarks the production tactics, not the collection tactics. Each
sampled problem is run twice in isolated Lean invocations:

  1. original problem with `grind`
  2. same problem with `neural_grind`

The primary metric is wall-clock elapsed time for successful Lean compilation.
Split traces are optional diagnostics; use `--no-trace-splits` for cleaner
timing runs.

Input sources:
  mathlib  - training/data/raw/grind_results_verified.jsonl
  workbook - training/data/raw/workbook_grind_solved_verified.jsonl
  numina   - training/data/raw/numina_finelean_grind_verified.jsonl
  numina-v2 - training/data/raw/numina_finelean_grind_v2.jsonl

Usage:
    python3 training/benchmark.py --sources mathlib,workbook,numina [options]
    python3 training/benchmark.py --benchmark-file training/data/split_active_benchmark.jsonl
    python3 training/benchmark.py --benchmark-file training/data/split_active_benchmark.jsonl --neural-no-model
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).parent.parent
TRAINING = Path(__file__).parent
RAW = TRAINING / "data" / "raw"
NEURAL_PROJECT = REPO / "NeuralTactic"

SOURCE_PATHS = {
    "mathlib": RAW / "grind_results_verified.jsonl",
    "workbook": RAW / "workbook_grind_solved_verified.jsonl",
    "numina": RAW / "numina_finelean_grind_verified.jsonl",
    "numina-v2": RAW / "numina_finelean_grind_v2.jsonl",
}

SPLIT_TRACE_RE = re.compile(r"\[grind\.split\]")


# ---------------------------------------------------------------------------
# Problem loading and sampling
# ---------------------------------------------------------------------------

def mathlib_module(file_path: str) -> str:
    return file_path.replace("Mathlib/", "").split("/")[0]


def difficulty(elapsed_s: float) -> str:
    if elapsed_s < 0.1:
        return "easy"
    if elapsed_s < 0.5:
        return "medium"
    return "hard"


def _read_jsonl(path: Path) -> list[dict]:
    records = []
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _strip_import_mathlib(text: str) -> str:
    return re.sub(r"^\s*import Mathlib\s*\n+", "", text.strip())


def _statement_to_snippet(statement: str) -> str:
    return "import Mathlib\n\n" + _strip_import_mathlib(statement) + "\n"


def _topic_group(record: dict, default: str) -> str:
    tags = record.get("tags") or []
    if tags and isinstance(tags, list) and str(tags[0]).strip():
        return str(tags[0]).strip()
    name = str(record.get("id") or record.get("name") or "")
    if "_" in name:
        return name.split("_", 1)[0]
    return default


def _numeric_id_bucket(record: dict, prefix: str, width: int = 10000) -> str:
    name = str(record.get("id") or record.get("name") or "")
    match = re.search(r"(\d+)$", name)
    if not match:
        return prefix
    start = int(match.group(1)) // width * width
    end = start + width - 1
    return f"{prefix}_{start:05d}_{end:05d}"


def normalize_mathlib(record: dict) -> dict:
    return {
        "source": "mathlib",
        "group": mathlib_module(record.get("file_path", "Mathlib/unknown")),
        "name": record.get("name") or "unknown",
        "file_path": record.get("file_path") or "Mathlib/unknown",
        "lean_snippet": record["lean_snippet"],
        "grind_call": record.get("grind_call", "grind"),
        "elapsed_s": float(record.get("elapsed_s", 0.0) or 0.0),
    }


def normalize_statement_record(record: dict, source: str) -> dict:
    statement = record.get("solved_formal_statement") or record.get("lean_snippet")
    if not statement:
        statement = record.get("original_formal_statement", "")
    if source == "workbook":
        group = _numeric_id_bucket(record, "workbook")
    else:
        group = _topic_group(record, record.get("split", source))
    name = record.get("id") or record.get("name") or "unknown"
    return {
        "source": source,
        "group": group,
        "name": name,
        "file_path": f"{source}/{group}",
        "lean_snippet": _statement_to_snippet(statement),
        "grind_call": record.get("grind_call", "grind"),
        "elapsed_s": float(record.get("elapsed_s", 0.0) or 0.0),
    }


def load_source(source: str, only_plain: bool) -> list[dict]:
    path = SOURCE_PATHS[source]
    normalized = []
    for record in _read_jsonl(path):
        if only_plain and record.get("grind_call", "grind") != "grind":
            continue
        try:
            if source == "mathlib":
                normalized.append(normalize_mathlib(record))
            else:
                normalized.append(normalize_statement_record(record, source))
        except Exception:
            continue
    return normalized


def _spread_sample(records: list[dict], n: int) -> list[dict]:
    if n <= 0 or len(records) <= n:
        return records[:]
    ordered = sorted(records, key=lambda r: r.get("elapsed_s", 0.0))
    step = len(ordered) / n
    return [ordered[int(i * step)] for i in range(n)]


def sample_problems(
    sources: list[str],
    n_per_group: int,
    max_per_source: int | None,
    only_plain: bool,
    seed: int,
) -> list[dict]:
    rng = random.Random(seed)
    sampled = []

    for source in sources:
        records = load_source(source, only_plain)
        by_group: dict[str, list[dict]] = defaultdict(list)
        for record in records:
            by_group[record["group"]].append(record)

        source_sample = []
        for group in sorted(by_group):
            source_sample.extend(_spread_sample(by_group[group], n_per_group))

        if max_per_source is not None:
            source_sample = _spread_sample(source_sample, max_per_source)

        sampled.extend(source_sample)

    rng.shuffle(sampled)
    return sampled


def load_benchmark_file(path: Path, only_plain: bool) -> list[dict]:
    records = []
    for record in _read_jsonl(path):
        if only_plain and record.get("grind_call", "grind") != "grind":
            continue
        required = {"source", "group", "name", "lean_snippet", "grind_call"}
        if required.issubset(record):
            records.append(record)
    return records


# ---------------------------------------------------------------------------
# Lean file construction
# ---------------------------------------------------------------------------

def transform_snippet(lean_snippet: str, grind_call: str, tactic: str) -> str:
    snippet = re.sub(r"^\s*import Mathlib\s*\n+", "", lean_snippet.strip())
    escaped = re.escape(grind_call)
    snippet = re.sub(
        r":=\s*by\s*\n\s*" + escaped + r"\b",
        f":= by {tactic}",
        snippet,
    )
    snippet = re.sub(
        r":=\s*by\s+" + escaped + r"\b",
        f":= by {tactic}",
        snippet,
    )
    return snippet.strip()


def build_lean_file(
    record: dict,
    tactic: str,
    import_neural: bool,
    trace_splits: bool,
) -> str:
    lines = ["import Mathlib"]
    if import_neural:
        lines.append("import NeuralTactic")
    lines.append("set_option maxHeartbeats 400000")
    if trace_splits:
        lines.append("set_option trace.grind.split true")
    lines.append("")
    lines.append(transform_snippet(record["lean_snippet"], record["grind_call"], tactic))
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tactic runner
# ---------------------------------------------------------------------------

def _first_error(stream: str) -> str | None:
    for line in stream.splitlines():
        if "lakefile.lean and lakefile.toml" in line:
            continue
        if ": error:" in line or line.startswith("error:"):
            return line.strip()[:500]
    for line in stream.splitlines():
        line = line.strip()
        if "lakefile.lean and lakefile.toml" in line:
            continue
        if line and not line.startswith("[grind.split]") and not line.startswith("info:"):
            return line[:500]
    return None


def _coerce_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _result(
    solved: bool,
    elapsed: float,
    stdout: str | bytes | None = "",
    stderr: str | bytes | None = "",
    error: str | None = None,
) -> dict:
    stdout = _coerce_text(stdout)
    stderr = _coerce_text(stderr)
    combined = stdout + "\n" + stderr
    splits = len(SPLIT_TRACE_RE.findall(combined))
    return {
        "solved": solved,
        "elapsed": elapsed,
        "splits": splits if splits > 0 else None,
        "error": None if solved else error or _first_error(stderr) or _first_error(stdout),
    }


def run_tactic(
    record: dict,
    tactic: str,
    import_neural: bool,
    env: dict[str, str],
    timeout: int,
    trace_splits: bool,
    keep_files: bool,
) -> dict:
    scratch = NEURAL_PROJECT / ".collect_scratch"
    scratch.mkdir(exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", record.get("name", "problem"))
    fname = scratch / f"bench_{tactic}_{os.getpid()}_{time.time_ns()}_{safe_name}.lean"
    fname.write_text(
        build_lean_file(record, tactic, import_neural, trace_splits),
        encoding="utf-8",
    )

    try:
        t0 = time.monotonic()
        proc = subprocess.run(
            ["lake", "env", "lean", str(fname)],
            cwd=str(NEURAL_PROJECT),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        elapsed = time.monotonic() - t0
        return _result(
            solved=proc.returncode == 0,
            elapsed=elapsed,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
    except subprocess.TimeoutExpired as e:
        return _result(
            solved=False,
            elapsed=float(timeout),
            stdout=e.stdout or "",
            stderr=e.stderr or "",
            error=f"timeout after {timeout}s",
        )
    except Exception as e:
        return _result(False, 0.0, error=str(e))
    finally:
        if not keep_files:
            try:
                fname.unlink()
            except OSError:
                pass


def neural_env(
    model_path: str,
    serve_path: str,
    no_model: bool,
    margin_milli: int,
    include_expr_text: bool,
) -> dict[str, str]:
    env = os.environ.copy()
    python_bin = str(Path(sys.executable).parent)
    if no_model:
        env["GRIND_NO_MODEL"] = "1"
        env.pop("GRIND_MODEL", None)
        env.pop("GRIND_SERVE", None)
        env.pop("GRIND_PYTHON", None)
    else:
        env.pop("GRIND_NO_MODEL", None)
        env["GRIND_MODEL"] = model_path
        env["GRIND_SERVE"] = serve_path
        env["GRIND_PYTHON"] = sys.executable
    env["PATH"] = python_bin + ":" + env.get("PATH", "")
    env["GRIND_MARGIN_MILLI"] = str(max(0, margin_milli))
    if include_expr_text:
        env["GRIND_INCLUDE_EXPR_TEXT"] = "1"
    else:
        env.pop("GRIND_INCLUDE_EXPR_TEXT", None)
    return env


def run_one(args_tuple: tuple[dict, str, str, int, bool, bool, bool, bool, int, bool]) -> dict:
    (
        record,
        model_path,
        serve_path,
        timeout,
        trace_splits,
        keep_files,
        grind_only,
        no_model,
        margin_milli,
        include_expr_text,
    ) = args_tuple
    grind = run_tactic(
        record=record,
        tactic="grind",
        import_neural=False,
        env=os.environ.copy(),
        timeout=timeout,
        trace_splits=trace_splits,
        keep_files=keep_files,
    )
    if grind_only:
        neural = {
            "solved": False,
            "elapsed": 0.0,
            "splits": None,
            "error": "skipped",
        }
    else:
        neural = run_tactic(
            record=record,
            tactic="neural_grind",
            import_neural=True,
            env=neural_env(
                model_path=model_path,
                serve_path=serve_path,
                no_model=no_model,
                margin_milli=margin_milli,
                include_expr_text=include_expr_text,
            ),
            timeout=timeout,
            trace_splits=trace_splits,
            keep_files=keep_files,
        )
    return {"record": record, "grind": grind, "neural": neural}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def result_label(result: dict) -> str:
    status = "ok" if result["solved"] else "fail"
    elapsed = f"{result['elapsed']:.2f}s" if result["elapsed"] > 0 else "0.00s"
    if result.get("splits") is not None:
        return f"{result['splits']}/{elapsed} {status}"
    return f"-/{elapsed} {status}"


def winner(grind: dict, neural: dict, tie_pct: float) -> str:
    if not grind["solved"] and not neural["solved"]:
        return "both-fail"
    if grind["solved"] and not neural["solved"]:
        return "grind"
    if neural["solved"] and not grind["solved"]:
        return "neural"

    if grind["elapsed"] <= 0 or neural["elapsed"] <= 0:
        return "tie"
    speed_delta = (grind["elapsed"] - neural["elapsed"]) / grind["elapsed"] * 100.0
    if speed_delta > tie_pct:
        return "neural"
    if speed_delta < -tie_pct:
        return "grind"
    return "tie"


def split_delta_label(grind: dict, neural: dict) -> str:
    if not (grind["solved"] and neural["solved"]):
        return ""
    if grind.get("splits") is not None and neural.get("splits") is not None:
        delta = neural["splits"] - grind["splits"]
        return f"{delta:+d}"
    return ""


def speed_delta_label(grind: dict, neural: dict) -> str:
    if not (grind["solved"] and neural["solved"]) or grind["elapsed"] <= 0:
        return ""
    delta = (grind["elapsed"] - neural["elapsed"]) / grind["elapsed"] * 100.0
    return f"{delta:+.1f}%"


def _empty_counts() -> dict[str, int]:
    return {"neural": 0, "grind": 0, "tie": 0, "both-fail": 0}


def print_report(results: list[dict], max_failures: int, time_tie_pct: float) -> None:
    print()
    print(
        f"{'Source':<10} {'Group':<16} {'Problem':<30} "
        f"{'grind':>16} {'neural':>16} {'splitΔ':>7} {'speedΔ':>8}  Faster"
    )
    print("-" * 124)

    wins = _empty_counts()
    by_source: dict[str, dict[str, int]] = defaultdict(_empty_counts)
    neural_failures = []

    for result in results:
        record = result["record"]
        grind = result["grind"]
        neural = result["neural"]
        win = winner(grind, neural, time_tie_pct)
        wins[win] += 1
        by_source[record["source"]][win] += 1
        if grind["solved"] and not neural["solved"]:
            neural_failures.append(result)

        print(
            f"{record['source'][:9]:<10} "
            f"{record['group'][:15]:<16} "
            f"{record['name'][:29]:<30} "
            f"{result_label(grind):>16} "
            f"{result_label(neural):>16} "
            f"{split_delta_label(grind, neural):>7} "
            f"{speed_delta_label(grind, neural):>8}  {win}"
        )

    n = len(results)
    print("-" * 124)
    print(f"\nSummary ({n} problems):")
    print(f"  Neural faster : {wins['neural']:3d} / {n} ({wins['neural']/n*100:.1f}%)")
    print(f"  Timing ties   : {wins['tie']:3d} / {n} ({wins['tie']/n*100:.1f}%)")
    print(f"  Grind faster  : {wins['grind']:3d} / {n} ({wins['grind']/n*100:.1f}%)")
    print(f"  Both failed   : {wins['both-fail']:3d} / {n}")
    print(f"  Tie tolerance : ±{time_tie_pct:.1f}% elapsed time")

    print("\nBy source:")
    for source in sorted(by_source):
        counts = by_source[source]
        total = sum(counts.values())
        print(
            f"  {source:<9} n={total:3d} "
            f"neural_faster={counts['neural']:3d} ties={counts['tie']:3d} "
            f"grind_faster={counts['grind']:3d} both-fail={counts['both-fail']:3d}"
        )

    timed = [
        (r["grind"]["elapsed"], r["neural"]["elapsed"])
        for r in results
        if r["grind"]["solved"] and r["neural"]["solved"]
    ]
    if timed:
        total_grind_time = sum(g for g, _ in timed)
        total_neural_time = sum(n for _, n in timed)
        reduction = (total_grind_time - total_neural_time) / max(total_grind_time, 1e-9) * 100.0
        ratio = total_grind_time / max(total_neural_time, 1e-9)
        print(
            "\nTotal elapsed on comparable solved problems: "
            f"grind={total_grind_time:.2f}s neural={total_neural_time:.2f}s "
            f"speed_delta={reduction:+.1f}% speed_ratio={ratio:.3f}x"
        )

    contested = [
        (r["grind"]["splits"], r["neural"]["splits"])
        for r in results
        if r["grind"]["solved"]
        and r["neural"]["solved"]
        and r["grind"].get("splits") is not None
        and r["neural"].get("splits") is not None
    ]
    if contested:
        total_grind = sum(g for g, _ in contested)
        total_neural = sum(n for _, n in contested)
        pct = (total_grind - total_neural) / max(total_grind, 1) * 100
        print(
            "\nTotal traced splits on comparable solved problems: "
            f"grind={total_grind} neural={total_neural} reduction={pct:+.1f}%"
        )

    if neural_failures and max_failures > 0:
        print(f"\nNeural failures where grind solved (first {max_failures}):")
        for result in neural_failures[:max_failures]:
            record = result["record"]
            error = result["neural"].get("error") or "unknown error"
            print(
                f"  {record['source']}/{record['group']}/{record['name']}: "
                f"{error}"
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_sources(raw: str) -> list[str]:
    sources = [s.strip() for s in raw.split(",") if s.strip()]
    unknown = [s for s in sources if s not in SOURCE_PATHS]
    if unknown:
        raise SystemExit(f"Unknown source(s): {', '.join(unknown)}")
    return sources


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=str(TRAINING / "model.pt"))
    parser.add_argument("--serve", default=str(TRAINING / "serve.py"))
    parser.add_argument("--sources", default="mathlib,workbook,numina")
    parser.add_argument("--benchmark-file", default=None,
                        help="JSONL file of normalized benchmark records")
    parser.add_argument("--n", type=int, default=1,
                        help="Problems sampled per source group")
    parser.add_argument("--max-per-source", type=int, default=12,
                        help="Cap sampled problems per source; use 0 for no cap")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--only-plain", action="store_true", default=True)
    parser.add_argument("--grind-only", action="store_true")
    parser.add_argument("--neural-no-model", action="store_true",
                        help="Run neural_grind with model inference disabled")
    parser.add_argument("--margin-milli", type=int, default=0,
                        help="Require model top-1/top-2 margin in milli-logits")
    parser.add_argument("--include-expr-text", action="store_true",
                        help="Send pretty-printed candidate expressions to the model")
    parser.add_argument("--no-trace-splits", action="store_true")
    parser.add_argument("--time-tie-pct", type=float, default=5.0,
                        help="Treat elapsed-time differences within this percent as ties")
    parser.add_argument("--keep-files", action="store_true")
    parser.add_argument("--max-failures", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_path = str(Path(args.model).resolve())
    serve_path = str(Path(args.serve).resolve())
    sources = parse_sources(args.sources)
    max_per_source = None if args.max_per_source == 0 else args.max_per_source

    uses_model = not args.grind_only and not args.neural_no_model

    if uses_model and not Path(model_path).exists():
        print(f"Model not found: {model_path}", file=sys.stderr)
        sys.exit(1)
    if uses_model and not Path(serve_path).exists():
        print(f"Serve script not found: {serve_path}", file=sys.stderr)
        sys.exit(1)

    if args.benchmark_file:
        problems = load_benchmark_file(Path(args.benchmark_file), args.only_plain)
    else:
        problems = sample_problems(
            sources=sources,
            n_per_group=args.n,
            max_per_source=max_per_source,
            only_plain=args.only_plain,
            seed=args.seed,
        )
    work = [
        (
            record,
            model_path,
            serve_path,
            args.timeout,
            not args.no_trace_splits,
            args.keep_files,
            args.grind_only,
            args.neural_no_model,
            args.margin_milli,
            args.include_expr_text,
        )
        for record in problems
    ]

    print("Benchmark: real grind vs real neural_grind")
    if args.benchmark_file:
        print(f"Input    : {args.benchmark_file}")
    else:
        print(f"Sources  : {', '.join(sources)}")
    print(f"Problems : {len(problems)}")
    if not args.benchmark_file:
        print(f"Sampling : n={args.n} per group, max_per_source={max_per_source or 'none'}")
    print(f"Workers  : {args.workers}")
    print(f"Timeout  : {args.timeout}s per tactic run")
    print(f"Trace    : {'off' if args.no_trace_splits else 'trace.grind.split'}")
    print(f"Metric   : elapsed time, ties within ±{max(0.0, args.time_tie_pct):.1f}%")
    if args.neural_no_model:
        print("Neural   : no-model fallback mode")
    elif not args.grind_only:
        print(f"Model    : {model_path}")
        print(f"Serve    : {serve_path}")
        print(f"Margin   : {max(0, args.margin_milli)} milli-logits")
        print(f"Expr text: {'on' if args.include_expr_text else 'off'}")
    print()

    results = []
    started = time.monotonic()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, item): item[0] for item in work}
        for idx, fut in enumerate(as_completed(futures), 1):
            result = fut.result()
            results.append(result)
            record = result["record"]
            print(
                f"  [{idx:3d}/{len(work)}] "
                f"{record['source']}/{record['group']}/{record['name']:<35} "
                f"grind={result_label(result['grind']):<16} "
                f"neural={result_label(result['neural']):<16}",
                flush=True,
            )
            if result["neural"].get("error") and not result["neural"]["solved"]:
                print(f"      neural error: {result['neural']['error']}", flush=True)

    results.sort(key=lambda r: (
        r["record"]["source"],
        r["record"]["group"],
        r["record"]["name"],
    ))
    print_report(
        results,
        max_failures=args.max_failures,
        time_tie_pct=max(0.0, args.time_tie_pct),
    )
    print(f"\nElapsed wall time: {time.monotonic() - started:.1f}s")


if __name__ == "__main__":
    main()
