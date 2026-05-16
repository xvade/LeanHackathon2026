#!/usr/bin/env python3
"""
Run Lean over a directory of files and collect all messages.

This is intended for batches of files where each file contains one proof using
`aesop`. When `--rewrite-aesop` is passed, the script runs a temporary copy of
each file where the first tactic occurrence of `aesop` is replaced by
`aesop_collect`, leaving the original files untouched.

Output is JSONL: one record per Lean file.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


AESOP_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_'.])aesop(?![A-Za-z0-9_'?])")


def strip_comments_mask(lines: list[str]) -> list[str]:
    """Return lines where Lean comments are replaced by spaces.

    This is only a lightweight lexer. It handles nested block comments and line
    comments, which is enough to avoid rewriting most non-code `aesop` text.
    """
    masked: list[str] = []
    depth = 0
    for line in lines:
        out: list[str] = []
        i = 0
        while i < len(line):
            pair = line[i : i + 2]
            if depth == 0 and pair == "--":
                out.extend(" " for _ in line[i:])
                break
            if pair == "/-":
                depth += 1
                out.extend("  ")
                i += 2
                continue
            if depth > 0:
                if pair == "-/":
                    depth -= 1
                    out.extend("  ")
                    i += 2
                else:
                    out.append(" ")
                    i += 1
                continue
            out.append(line[i])
            i += 1
        masked.append("".join(out))
    return masked


def rewrite_first_aesop(source: str) -> tuple[str, int]:
    """Replace the first tactic-looking `aesop` token with `aesop_collect`.

    Returns `(rewritten_source, candidate_count)`, where `candidate_count` is
    the number of code tokens that looked like standalone `aesop` calls.
    """
    lines = source.splitlines(keepends=True)
    masked = strip_comments_mask(lines)
    candidates: list[tuple[int, int, int]] = []

    for idx, code_line in enumerate(masked):
        if "attribute [aesop" in code_line or "@[aesop" in code_line:
            continue
        if "set_option trace.aesop" in code_line:
            continue
        for match in AESOP_TOKEN_RE.finditer(code_line):
            candidates.append((idx, match.start(), match.end()))

    if not candidates:
        return source, 0

    line_idx, start, end = candidates[0]
    line = lines[line_idx]
    lines[line_idx] = line[:start] + "aesop_collect" + line[end:]
    return "".join(lines), len(candidates)


def extract_aesop_collect_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] | None = None
    bracket_balance = 0

    for line in text.splitlines():
        stripped = line.strip()
        starts_block = stripped.startswith("aesop_collect:") or stripped.startswith(
            "info: aesop_collect:"
        )

        if current is None:
            if not starts_block:
                continue
            current = [line]
            bracket_balance = line.count("[") - line.count("]")
            if bracket_balance <= 0:
                blocks.append("\n".join(current))
                current = None
            continue

        current.append(line)
        bracket_balance += line.count("[") - line.count("]")
        if bracket_balance <= 0:
            blocks.append("\n".join(current))
            current = None

    if current is not None:
        blocks.append("\n".join(current))
    return blocks


def lean_files(root: Path, pattern: str) -> list[Path]:
    return sorted(p for p in root.glob(pattern) if p.is_file() and p.suffix == ".lean")


def run_lean(
    file_path: Path,
    project_root: Path,
    lake: str,
    timeout: float,
) -> tuple[int | None, str, str, float, str | None]:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [lake, "env", "lean", str(file_path)],
            cwd=project_root,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        elapsed = time.monotonic() - start
        return proc.returncode, proc.stdout, proc.stderr, elapsed, None
    except subprocess.TimeoutExpired as e:
        elapsed = time.monotonic() - start
        stdout = e.stdout if isinstance(e.stdout, str) else (e.stdout or b"").decode(errors="replace")
        stderr = e.stderr if isinstance(e.stderr, str) else (e.stderr or b"").decode(errors="replace")
        return None, stdout, stderr, elapsed, f"timeout after {timeout}s"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Lean over a folder of files and collect emitted messages."
    )
    parser.add_argument("folder", type=Path, help="Folder containing Lean files.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Lake project root to run `lake env lean` from. Defaults to cwd.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("aesop_collect_messages.jsonl"),
        help="Output JSONL path.",
    )
    parser.add_argument(
        "--glob",
        default="**/*.lean",
        help="Glob under folder. Defaults to '**/*.lean'.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Per-file timeout in seconds.",
    )
    parser.add_argument(
        "--lake",
        default="lake",
        help="Lake executable. Defaults to 'lake'.",
    )
    parser.add_argument(
        "--rewrite-aesop",
        action="store_true",
        help="Run temporary copies where the first standalone `aesop` token is rewritten to `aesop_collect`.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temporary rewritten files.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first file that fails or times out.",
    )
    args = parser.parse_args()

    folder = args.folder.resolve()
    project_root = args.project_root.resolve()
    output = args.output.resolve()

    files = lean_files(folder, args.glob)
    output.parent.mkdir(parents=True, exist_ok=True)

    temp_dir: Path | None = None
    if args.rewrite_aesop:
        temp_dir = Path(tempfile.mkdtemp(prefix="aesop_collect_inputs_"))

    failures = 0
    try:
        with output.open("w", encoding="utf-8") as out:
            for index, original in enumerate(files, start=1):
                run_path = original
                rewrite_candidate_count: int | None = None
                rewrite_error: str | None = None

                if args.rewrite_aesop:
                    assert temp_dir is not None
                    rel = original.relative_to(folder)
                    run_path = temp_dir / rel
                    run_path.parent.mkdir(parents=True, exist_ok=True)
                    source = original.read_text(encoding="utf-8")
                    rewritten, rewrite_candidate_count = rewrite_first_aesop(source)
                    if rewrite_candidate_count != 1:
                        rewrite_error = (
                            "expected exactly one standalone aesop token, "
                            f"found {rewrite_candidate_count}"
                        )
                    run_path.write_text(rewritten, encoding="utf-8")

                exit_code, stdout, stderr, elapsed, run_error = run_lean(
                    run_path, project_root, args.lake, args.timeout
                )
                combined = stdout + stderr
                record = {
                    "file": str(original),
                    "index": index,
                    "total_files": len(files),
                    "run_file": str(run_path),
                    "rewritten": bool(args.rewrite_aesop),
                    "rewrite_candidate_count": rewrite_candidate_count,
                    "rewrite_error": rewrite_error,
                    "exit_code": exit_code,
                    "elapsed_seconds": elapsed,
                    "error": run_error,
                    "stdout": stdout,
                    "stderr": stderr,
                    "messages": combined,
                    "aesop_collect_messages": extract_aesop_collect_blocks(combined),
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()

                status = "ok" if exit_code == 0 and run_error is None and rewrite_error is None else "fail"
                print(f"[{index}/{len(files)}] {status}: {original}", file=sys.stderr)
                if status == "fail":
                    failures += 1
                    if args.fail_fast:
                        break
    finally:
        if temp_dir is not None and not args.keep_temp:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
