#!/usr/bin/env python3
"""
Extract 747 verified theorems from Mathlib and write each to an individual .lean file.

Usage:
    python3 training/extract_verified_problems.py \
        --verified training/grind_results_verified.jsonl \
        --mathlib GrindExtraction/.lake/packages/mathlib/Mathlib \
        --out GrindExtraction/verified_problems
"""

import json
import re
import sys
from pathlib import Path
import argparse


def extract_theorem_from_file(file_path: Path, theorem_name: str) -> str:
    """Extract a theorem's full source from a Mathlib file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    
    lines = content.splitlines()
    
    # Find the theorem/lemma declaration
    pattern = rf"\b(theorem|lemma)\s+{re.escape(theorem_name)}\b"
    
    for i, line in enumerate(lines):
        if re.search(pattern, line):
            # Found it. Now extract the full declaration (may span multiple lines)
            result_lines = []
            bracket_depth = 0
            found_assign = False
            
            j = i
            while j < len(lines):
                curr_line = lines[j]
                result_lines.append(curr_line)
                
                # Track brackets
                bracket_depth += len(re.findall(r'[(\[{]', curr_line))
                bracket_depth -= len(re.findall(r'[)\]}]', curr_line))
                
                # Check for := by
                if ":= by" in curr_line:
                    found_assign = True
                
                # If we found := by and bracket depth is back to 0, we're done
                if found_assign and bracket_depth == 0:
                    break
                
                j += 1
            
            return "\n".join(result_lines)
    
    return ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verified", default="training/grind_results_verified.jsonl")
    parser.add_argument("--mathlib", default="GrindExtraction/.lake/packages/mathlib/Mathlib")
    parser.add_argument("--out", default="GrindExtraction/verified_problems")
    args = parser.parse_args()
    
    verified_path = Path(args.verified).resolve()
    mathlib_root = Path(args.mathlib).resolve()
    out_dir = Path(args.out).resolve()
    
    if not verified_path.exists():
        print(f"ERROR: {verified_path} not found", file=sys.stderr)
        sys.exit(1)
    
    if not mathlib_root.exists():
        print(f"ERROR: {mathlib_root} not found", file=sys.stderr)
        sys.exit(1)
    
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Load verified theorems
    theorems = []
    with open(verified_path) as f:
        for line in f:
            if line.strip():
                theorems.append(json.loads(line))
    
    print(f"Loaded {len(theorems)} verified theorems")
    print(f"Extracting to {out_dir}…")
    
    success = 0
    missing_files = []
    missing_theorems = []
    
    for idx, record in enumerate(theorems, 1):
        file_path_rel = record.get("file_path", "")
        theorem_name = record.get("name", "")
        
        file_path = mathlib_root / file_path_rel
        
        if not file_path.exists():
            missing_files.append((theorem_name, file_path))
            continue
        
        # Extract theorem from source
        theorem_source = extract_theorem_from_file(file_path, theorem_name)
        
        if not theorem_source:
            missing_theorems.append((theorem_name, file_path))
            continue
        
        # Write to individual file
        out_file = out_dir / f"{theorem_name}.lean"
        out_file.write_text(f"import Mathlib\n\n{theorem_source}\n")
        
        success += 1
        if idx % 100 == 0:
            print(f"  [{idx}/{len(theorems)}] Extracted {success} theorems")
    
    print(f"\n✓ Extracted {success} theorems to {out_dir}")
    
    if missing_files:
        print(f"⚠ {len(missing_files)} files not found (first 5):")
        for name, path in missing_files[:5]:
            print(f"    {name}: {path}")
    
    if missing_theorems:
        print(f"⚠ {len(missing_theorems)} theorems not extracted (first 5):")
        for name, path in missing_theorems[:5]:
            print(f"    {name} in {path.name}")


if __name__ == "__main__":
    main()
