"""
Step 5: Convert `rule_scores.json` to an `AESOP_OVERRIDES_JSON` file.

Only **unsafe** rules can be overridden via `successProbability`; safe/norm
rules use integer penalties that the override mechanism does not touch.
We strip rules whose feature prefix is `safe|...` or `norm|...`, and pull the
declaration name out of the trailing pipe segment.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent
INPUT = ROOT / "rule_scores.json"
OUTPUT = ROOT / "aesop_overrides.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", default=str(INPUT),
                    help="Path to rule_scores JSON (default: rule_scores.json)")
    ap.add_argument("--out", default=str(OUTPUT),
                    help="Output overrides JSON path (default: aesop_overrides.json)")
    args = ap.parse_args()

    scores = json.loads(Path(args.scores).read_text())
    overrides: dict = {}
    skipped = []
    for rule, score in scores.items():
        # Format: <safe|unsafe|norm>|<builder>|<scope>|<decl_name>
        parts = rule.split("|")
        category = parts[0]
        decl_name = parts[-1]
        if category != "unsafe":
            skipped.append((rule, score))
            continue
        # Some safety: clamp to (0, 1) — Aesop.Percent.ofFloat may reject 0.0 or 1.0.
        prob = max(0.001, min(0.999, score))
        overrides[decl_name] = prob

    out_path = Path(args.out)
    out_path.write_text(json.dumps(overrides, indent=2, ensure_ascii=False))

    print(f"Total scored rules:  {len(scores)}")
    print(f"Unsafe rules kept:   {len(overrides)}")
    print(f"Safe/norm skipped:   {len(skipped)}")
    print()
    print("Skipped (cannot override):")
    for r, s in skipped:
        print(f"  {s:.4f}  {r}")
    print()
    print("Overrides written:")
    for name, prob in sorted(overrides.items(), key=lambda kv: -kv[1]):
        print(f"  {prob:.4f}  {name}")
    print()
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
