"""
Step 7: Richer breakdown of comparison results.

Reads `comparison/per_theorem.jsonl` and joins against the test split's
`aesop_collect_messages` to separate trivial proofs (no unsafe-rule decisions
in the original aesop run) from proofs that exercise the rule ordering.
"""
import argparse
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).parent
DEFAULT_PER_THEOREM = ROOT / "comparison" / "per_theorem.jsonl"
TEST = ROOT.parent / "aesop_data_split" / "test.jsonl"
DEFAULT_SUMMARY = ROOT / "comparison" / "summary_breakdown.json"


def has_decisions(record: dict) -> bool:
    return any(m != "aesop_collect: []" for m in record.get("aesop_collect_messages", []))


def stat(xs: list, fn) -> float | None:
    xs = [x for x in xs if x is not None]
    return fn(xs) if xs else None


def summarise(records: list, label: str) -> dict:
    n = len(records)
    if n == 0:
        return {"n": 0}
    both_ok = [r for r in records if r["default_success"] and r["custom_success"]]

    def get(side, field):
        return [r[side][field] for r in both_ok]

    def_wall = get("default", "wall_seconds")
    cus_wall = get("custom",  "wall_seconds")
    def_apps = get("default", "total_rule_applications")
    cus_apps = get("custom",  "total_rule_applications")
    def_fail = get("default", "failed_rule_applications")
    cus_fail = get("custom",  "failed_rule_applications")
    def_succ = get("default", "successful_rule_applications")
    cus_succ = get("custom",  "successful_rule_applications")
    def_app_ms = get("default", "rule_apps_ms")
    cus_app_ms = get("custom",  "rule_apps_ms")

    summary = {
        "label": label,
        "n_records": n,
        "default_success": sum(r["default_success"] for r in records),
        "custom_success":  sum(r["custom_success"]  for r in records),
        "both_succeed":    len(both_ok),
        "wall_seconds": {
            "default_mean":   stat(def_wall, statistics.mean),
            "custom_mean":    stat(cus_wall, statistics.mean),
            "default_median": stat(def_wall, statistics.median),
            "custom_median":  stat(cus_wall, statistics.median),
        },
        "rule_apps_ms (aesop search time on rules)": {
            "default_mean":   stat(def_app_ms, statistics.mean),
            "custom_mean":    stat(cus_app_ms, statistics.mean),
            "default_median": stat(def_app_ms, statistics.median),
            "custom_median":  stat(cus_app_ms, statistics.median),
        },
        "total_rule_applications": {
            "default_mean":   stat(def_apps, statistics.mean),
            "custom_mean":    stat(cus_apps, statistics.mean),
            "default_total":  sum(def_apps),
            "custom_total":   sum(cus_apps),
        },
        "failed_rule_applications": {
            "default_mean":   stat(def_fail, statistics.mean),
            "custom_mean":    stat(cus_fail, statistics.mean),
            "default_total":  sum(def_fail),
            "custom_total":   sum(cus_fail),
        },
        "successful_rule_applications": {
            "default_mean":   stat(def_succ, statistics.mean),
            "custom_mean":    stat(cus_succ, statistics.mean),
            "default_total":  sum(def_succ),
            "custom_total":   sum(cus_succ),
        },
        "paired": {
            "custom_faster_wall":      sum(1 for r in both_ok if r["custom"]["wall_seconds"]   < r["default"]["wall_seconds"]),
            "custom_slower_wall":      sum(1 for r in both_ok if r["custom"]["wall_seconds"]   > r["default"]["wall_seconds"]),
            "tie_wall":                sum(1 for r in both_ok if r["custom"]["wall_seconds"]  == r["default"]["wall_seconds"]),
            "custom_fewer_apps":       sum(1 for r in both_ok if r["custom"]["total_rule_applications"] < r["default"]["total_rule_applications"]),
            "custom_more_apps":        sum(1 for r in both_ok if r["custom"]["total_rule_applications"] > r["default"]["total_rule_applications"]),
            "tie_apps":                sum(1 for r in both_ok if r["custom"]["total_rule_applications"] == r["default"]["total_rule_applications"]),
            "custom_fewer_failed_apps":sum(1 for r in both_ok if r["custom"]["failed_rule_applications"] < r["default"]["failed_rule_applications"]),
            "custom_more_failed_apps": sum(1 for r in both_ok if r["custom"]["failed_rule_applications"] > r["default"]["failed_rule_applications"]),
        },
    }
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input",  default=str(DEFAULT_PER_THEOREM))
    ap.add_argument("--output", default=str(DEFAULT_SUMMARY))
    args = ap.parse_args()

    per_theorem = Path(args.input)
    summary_path = Path(args.output)

    # load test records to know which had decisions
    decisions = {}
    with TEST.open() as f:
        for line in f:
            r = json.loads(line)
            decisions[r["jsonl_id"]] = has_decisions(r)

    records = []
    with per_theorem.open() as f:
        for line in f:
            r = json.loads(line)
            r["had_decisions"] = decisions.get(r["jsonl_id"], False)
            records.append(r)

    all_summary  = summarise(records, "ALL records")
    decn_summary = summarise([r for r in records if r["had_decisions"]],
                             "records with branch decisions")
    plain_summary = summarise([r for r in records if not r["had_decisions"]],
                              "records without branch decisions")

    out = {
        "all": all_summary,
        "with_decisions": decn_summary,
        "without_decisions": plain_summary,
    }
    summary_path.write_text(json.dumps(out, indent=2))

    for s in (all_summary, decn_summary, plain_summary):
        print(f"\n=== {s['label']}  (n={s['n_records']}) ===")
        print(json.dumps(s, indent=2))

    print(f"\nWrote {summary_path}")


if __name__ == "__main__":
    main()
