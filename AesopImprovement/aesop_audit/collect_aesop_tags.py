#!/usr/bin/env python3
"""
collect_aesop_tags.py — scan Mathlib source files for @[aesop …] attributes
and write one JSONL record per tagged declaration.

Usage:
    python3 collect_aesop_tags.py [--mathlib PATH] [--out FILE]

Defaults:
    --mathlib  ../../NeuralTactic/.lake/packages/mathlib
    --out      aesop_mathlib_rules.jsonl

Each JSONL record contains:
    name        fully-qualified declaration name as it appears in source
    file        path to the source file, relative to the Mathlib root
    line        1-based line number of the @[aesop] attribute
    aesop_attr  the full @[aesop …] text (may span multiple attributes on the line)
    phase       "norm" | "safe" | "unsafe" | "unknown"
    builders    list of builder names found in the tag  (may be empty)
    rule_sets   list of rule-set names if (rule_sets := [...]) present
    kind        "theorem" | "lemma" | "def" | "instance" | "abbrev" |
                "class" | "structure" | "inductive" | "unknown"
    decl_name   declaration name without namespace qualifiers
    statement   text from the declaration line up to `:=`, `where`, or `by`
                (or up to end-of-line if none found), stripped

Implementation notes
────────────────────
This script does NOT elaborate Lean 4 code; it works on raw source text.
That means:
  • It captures statically-attributed declarations; dynamic attribute applications
    (`attribute [aesop] foo` in a later file) are also captured if found.
  • Multi-line attribute blocks (rare in practice) may not be fully captured.
  • The statement field is the verbatim source text, not a pretty-printed type.
"""

import re
import sys
import json
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# Bracket-aware attribute scanner (handles nested brackets in rule_sets)
# ---------------------------------------------------------------------------

# Declaration keywords that can immediately follow an attribute block
def find_attr_blocks(line: str) -> list[tuple[str, str]]:
    """Return [(full_text, inner_content)] for every @[…] block in the line.
    Handles nested square brackets (e.g. rule_sets := [Foo])."""
    results = []
    i = 0
    while i < len(line):
        if line[i:i+2] == '@[':
            depth = 0
            j = i + 1          # j starts at '['
            while j < len(line):
                if line[j] == '[':
                    depth += 1
                elif line[j] == ']':
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if j < len(line):  # found matching ']'
                attr_text    = line[i:j+1]        # @[…]
                attr_content = line[i+2:j]        # content inside
                results.append((attr_text, attr_content))
            i = j + 1
        else:
            i += 1
    return results


DECL_KW = frozenset([
    "theorem", "lemma", "def", "noncomputable", "private", "protected",
    "instance", "abbrev", "class", "structure", "inductive", "opaque",
    "attribute",
])

# Phase keywords inside an aesop tag
PHASE_RE  = re.compile(r'\b(norm|safe|unsafe)\b')
# Builder keywords
BUILDER_RE = re.compile(
    r'\b(apply|cases|constructors|destruct|forward|simp|tactic|unfold)\b')
# Rule-set clause
RULE_SET_RE = re.compile(r'rule_sets\s*:=\s*\[([^\]]*)\]')

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_aesop_attr(attr_text: str) -> dict | None:
    """Extract phase, builders and rule_sets from the content of @[…].
    Returns None for erasure attributes (@[-aesop …])."""
    # Skip erasure: @[-aesop] or @[aesop -...]
    if re.search(r'-\s*aesop|aesop\s+-', attr_text):
        return None
    phases   = PHASE_RE.findall(attr_text)
    builders = BUILDER_RE.findall(attr_text)
    rs_match = RULE_SET_RE.search(attr_text)
    rule_sets = (
        [s.strip() for s in rs_match.group(1).split(",") if s.strip()]
        if rs_match else []
    )
    # Determine phase:
    # • bare percentage → unsafe
    # • simp builder with no explicit phase → norm (simp rules are always norm)
    # • default → unknown (bare @[aesop] is typically safe)
    if phases:
        phase = phases[0]
    elif re.search(r'\d+%', attr_text):
        phase = "unsafe"
    elif "simp" in builders:
        phase = "norm"
    else:
        phase = "unknown"
    return {
        "phase":     phase,
        "builders":  list(dict.fromkeys(builders)),
        "rule_sets": rule_sets,
    }


def classify_decl(decl_line: str) -> tuple[str, str]:
    """Return (kind, decl_name) for the declaration line."""
    tokens = decl_line.split()
    kind = "unknown"
    name = ""
    for i, tok in enumerate(tokens):
        bare = tok.lstrip("@").split(".")[0]
        if bare in DECL_KW:
            kind = bare
            # The declaration name is the next non-keyword token
            for j in range(i + 1, len(tokens)):
                candidate = tokens[j]
                if candidate and not candidate.startswith("@") and \
                        candidate not in DECL_KW and \
                        not candidate.startswith("{") and \
                        not candidate.startswith("["):
                    name = candidate.rstrip(":")
                    break
            break
    return kind, name


def extract_statement(decl_line: str, following_lines: list[str]) -> str:
    """
    Collect text from `decl_line` up to the first `:= `, `where`, or `by`
    token at the top indentation level. Stop at most after 8 lines.
    """
    text = decl_line
    # Try to find the boundary in the first line first
    for stop in [" := ", " where ", " by "]:
        idx = text.find(stop)
        if idx != -1:
            return text[:idx].strip()
    # Multi-line: accumulate, stopping at := / where / by
    for extra in following_lines[:7]:
        text += " " + extra.strip()
        for stop in [" := ", " where ", " by ", ":=", "where", "by"]:
            idx = text.find(stop)
            if idx != -1:
                return text[:idx].strip()
    return text.strip()


# ---------------------------------------------------------------------------
# File scanner
# ---------------------------------------------------------------------------

def scan_file(path: Path, mathlib_root: Path) -> list[dict]:
    records = []
    rel_path = str(path.relative_to(mathlib_root))

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as e:
        print(f"  [warning] could not read {rel_path}: {e}", file=sys.stderr)
        return records

    # Track block-comment depth so we skip lines inside /- … -/
    block_depth = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Update block-comment depth
        opens  = line.count("/-")
        closes = line.count("-/")
        if block_depth > 0:
            block_depth += opens - closes
            if block_depth < 0:
                block_depth = 0
            i += 1
            continue
        block_depth += opens - closes
        if block_depth < 0:
            block_depth = 0

        # Skip single-line comments and blank lines
        if not stripped or stripped.startswith("--"):
            i += 1
            continue

        # Find all @[...] blocks on this line using bracket-aware scanner
        blocks = find_attr_blocks(line)
        aesop_blocks = [(t, c) for t, c in blocks if re.search(r'\baesop\b', c)]
        if not aesop_blocks:
            i += 1
            continue

        attr_texts    = [t for t, _ in aesop_blocks]
        attr_contents = [c for _, c in aesop_blocks]
        attr_line_no  = i + 1  # 1-based

        # Also scan the next few lines for additional attribute lines
        j = i + 1
        while j < len(lines) and j < i + 6:
            next_line = lines[j].strip()
            if not next_line.startswith("@[") and not next_line.startswith("["):
                break
            more = [(t, c) for t, c in find_attr_blocks(next_line)
                    if re.search(r'\baesop\b', c)]
            if more:
                attr_texts    += [t for t, _ in more]
                attr_contents += [c for _, c in more]
            j += 1

        # Find the declaration line (first non-attr, non-blank, non-comment line)
        decl_line = ""
        decl_line_no = j
        while j < len(lines):
            stripped = lines[j].strip()
            if stripped and not stripped.startswith("--") and \
                    not stripped.startswith("@[") and not stripped.startswith("["):
                decl_line = stripped
                decl_line_no = j + 1
                break
            j += 1

        if not decl_line:
            i += 1
            continue

        # Check that the declaration line is actually a declaration
        kind, decl_name = classify_decl(decl_line)
        if kind == "unknown" or not decl_name:
            i += 1
            continue

        # Skip `attribute [aesop] name` lines (handled separately below)
        if kind == "attribute":
            i += 1
            continue

        statement = extract_statement(decl_line, lines[decl_line_no:decl_line_no + 8])

        # Build one record per aesop tag
        for attr_text, attr_content in zip(attr_texts, attr_contents):
            if "aesop" not in attr_content:
                continue
            parsed = parse_aesop_attr(attr_content)
            if parsed is None:
                continue  # erasure attribute, skip
            records.append({
                "name":       decl_name,
                "file":       rel_path,
                "line":       attr_line_no,
                "aesop_attr": attr_text,
                "phase":      parsed["phase"],
                "builders":   parsed["builders"],
                "rule_sets":  parsed["rule_sets"],
                "kind":       kind,
                "decl_name":  decl_name,
                "statement":  statement,
            })

        i = max(i + 1, j + 1)

    # Also scan for standalone `attribute [aesop ...] name` lines
    for i, line in enumerate(lines):
        stripped = line.strip()
        m = re.match(
            r'(?:local\s+|scoped\s+)?attribute\s+\[([^\]]*\baesop\b[^\]]*)\]\s+(.+)',
            stripped, re.DOTALL)
        if not m:
            continue
        attr_content = m.group(1)
        names_str    = m.group(2).strip()
        parsed = parse_aesop_attr(attr_content)
        if parsed is None:
            continue
        for name in re.split(r'\s+', names_str):
            name = name.strip().rstrip(".")
            if name:
                records.append({
                    "name":       name,
                    "file":       rel_path,
                    "line":       i + 1,
                    "aesop_attr": f"@[{attr_content}]",
                    "phase":      parsed["phase"],
                    "builders":   parsed["builders"],
                    "rule_sets":  parsed["rule_sets"],
                    "kind":       "attribute",
                    "decl_name":  name,
                    "statement":  "",
                })

    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    here = Path(__file__).parent
    parser.add_argument("--mathlib",
        default=str(here / "../../NeuralTactic/.lake/packages/mathlib"),
        help="Path to the Mathlib source root")
    parser.add_argument("--out",
        default=str(here / "aesop_mathlib_rules.jsonl"),
        help="Output JSONL path")
    args = parser.parse_args()

    mathlib_root = Path(args.mathlib).resolve()
    out_path     = Path(args.out)

    if not mathlib_root.exists():
        sys.exit(f"Error: Mathlib root not found at {mathlib_root}")

    lean_files = sorted(mathlib_root.rglob("*.lean"))
    print(f"Scanning {len(lean_files)} Lean files under {mathlib_root} …",
          file=sys.stderr)

    all_records = []
    for path in lean_files:
        all_records.extend(scan_file(path, mathlib_root))

    print(f"Found {len(all_records)} @[aesop]-tagged declarations.",
          file=sys.stderr)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for rec in all_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Wrote {len(all_records)} records to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
