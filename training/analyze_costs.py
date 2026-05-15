"""Phase 0 viability analysis.

Consumes the JSONL produced by collect_branch_costs.py (with --sample-plan) and
reports the three viability numbers:

  (1) Percentage of multi-candidate decisions where at least one non-stock
      candidate solves with fewer splits than stock.
  (2) Median, mean, and p90 improvement (splits_saved) among those decisions.
  (3) Non-stock candidate failure / timeout rate.

Results are stratified by pool-size stratum.  A decision is included in the
analysis only when its stock candidate run succeeded — otherwise we have no
reliable baseline to compare against.

Example:
  python training/analyze_costs.py \\
    --in training/data/phase0_branch_costs.jsonl \\
    --out training/data/phase0_report.md
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IN = ROOT / "training" / "data" / "phase0_branch_costs.jsonl"
DEFAULT_OUT = ROOT / "training" / "data" / "phase0_report.md"


def load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def classify_forced_step(row: dict[str, Any]) -> str:
    """Return action:reason for the decision-log entry at the forced step.

    If `multiStepIndex` is set on the row, scans the decision log for the Nth
    entry with `numCandidates >= 2` (matches serve_forced_choice.py's
    multi-step targeting).  Otherwise falls back to the raw `forcedQueryIndex`
    1-based offset.

    Returns sentinel strings ("log_missing", "forced_beyond_log") on data
    problems.
    """
    log_path = row.get("decisionLog")
    if not log_path:
        return "no_forced_query"
    try:
        with open(log_path) as h:
            lines = [json.loads(l) for l in h if l.strip()]
    except FileNotFoundError:
        return "log_missing"
    except json.JSONDecodeError:
        return "log_unparseable"

    multi_step = row.get("multiStepIndex")
    if multi_step:
        multi = 0
        for entry in lines:
            if int(entry.get("numCandidates", 0)) >= 2:
                multi += 1
                if multi == int(multi_step):
                    return f"{entry.get('action')}:{entry.get('reason')}"
        return "forced_beyond_log"

    forced_idx = int(row.get("forcedQueryIndex", 0))
    if forced_idx <= 0:
        return "no_forced_query"
    if forced_idx > len(lines):
        return "forced_beyond_log"
    entry = lines[forced_idx - 1]
    return f"{entry.get('action')}:{entry.get('reason')}"


def forcing_effective(row: dict[str, Any]) -> bool:
    """Did the forced anchor actually drive the proof at the forced step?

    For stock rows (isGrindChoice=True), either action=model:stock_choice or
    action=model:override produces stock-anchor behaviour because both mean
    Lean validated and applied the requested anchor.

    For non-stock rows, only action=model:override is a true "alternative"
    test — :stock_choice means the requested anchor coincided with Lean's
    own stock pick, so the measurement is indistinguishable from stock.
    """
    cls = classify_forced_step(row)
    if row.get("isGrindChoice"):
        return cls in {"model:stock_choice", "model:override"}
    return cls == "model:override"


def pct(num: int, denom: int) -> str:
    if denom == 0:
        return "n/a"
    return f"{100.0 * num / denom:.1f}%"


def percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def _new_bucket() -> dict[str, Any]:
    return {
        "decisions_total": 0,
        "decisions_with_stock_success": 0,
        "decisions_with_alt_success": 0,
        "decisions_with_alt_better": 0,
        "decisions_with_alt_strictly_better": 0,
        "decisions_with_alt_tie": 0,
        "improvements": [],
        "non_stock_runs_total": 0,
        "non_stock_runs_success": 0,
        "non_stock_runs_timeout": 0,
        "non_stock_runs_failure": 0,
        "non_stock_runs_ineffective": 0,
        "stock_runs_total": 0,
        "stock_runs_success": 0,
        "stock_runs_ineffective": 0,
    }


def _analyze(rows: list[dict[str, Any]], *, effective_only: bool) -> dict[str, Any]:
    by_decision: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_decision[(r["case"], int(r["traceStep"]))].append(r)

    per_stratum: dict[str, dict[str, Any]] = defaultdict(_new_bucket)
    decision_records: list[dict[str, Any]] = []

    def _stratum_from_pool(ps: int | None) -> str:
        if ps is None:
            return "?"
        if ps <= 2:
            return "2"
        if ps == 3:
            return "3"
        if ps <= 5:
            return "4-5"
        if ps <= 10:
            return "6-10"
        return "11+"

    for (case, step), candidates in by_decision.items():
        pool_size = candidates[0].get("poolSize")
        # Always derive stratum from poolSize so the analyzer is agnostic to
        # how the sample plan tagged decisions.
        stratum = _stratum_from_pool(pool_size if isinstance(pool_size, int) else None)
        stock_candidates = [c for c in candidates if c.get("isGrindChoice")]
        non_stock = [c for c in candidates if not c.get("isGrindChoice")]
        bucket = per_stratum[stratum]
        bucket["decisions_total"] += 1

        for c in stock_candidates:
            bucket["stock_runs_total"] += 1
            if c.get("status") == "success":
                bucket["stock_runs_success"] += 1
            if not forcing_effective(c):
                bucket["stock_runs_ineffective"] += 1
        for c in non_stock:
            bucket["non_stock_runs_total"] += 1
            status = c.get("status")
            if status == "success":
                bucket["non_stock_runs_success"] += 1
            elif status == "timeout":
                bucket["non_stock_runs_timeout"] += 1
            else:
                bucket["non_stock_runs_failure"] += 1
            if not forcing_effective(c):
                bucket["non_stock_runs_ineffective"] += 1

        stock_pool = stock_candidates
        if effective_only:
            stock_pool = [c for c in stock_pool if forcing_effective(c)]
        successful_stock = [c for c in stock_pool if c.get("status") == "success"]
        if not successful_stock:
            continue
        bucket["decisions_with_stock_success"] += 1
        stock_splits = min(int(c["splitsToClose"]) for c in successful_stock)

        alt_pool = non_stock
        if effective_only:
            alt_pool = [c for c in alt_pool if forcing_effective(c)]
        successful_alts = [c for c in alt_pool if c.get("status") == "success"]
        if successful_alts:
            bucket["decisions_with_alt_success"] += 1
        alt_splits_list = [int(c["splitsToClose"]) for c in successful_alts]
        best_alt = min(alt_splits_list) if alt_splits_list else None

        decision_records.append(
            {
                "case": case,
                "step": step,
                "stratum": stratum,
                "poolSize": pool_size,
                "stockSplits": stock_splits,
                "altSplits": alt_splits_list,
                "bestAltSplits": best_alt,
                "improvement": (stock_splits - best_alt) if best_alt is not None else None,
            }
        )

        if best_alt is not None:
            if best_alt < stock_splits:
                bucket["decisions_with_alt_strictly_better"] += 1
                bucket["improvements"].append(stock_splits - best_alt)
            elif best_alt == stock_splits:
                bucket["decisions_with_alt_tie"] += 1
            if best_alt <= stock_splits:
                bucket["decisions_with_alt_better"] += 1

    return {"per_stratum": per_stratum, "decisions": decision_records}


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    raw = _analyze(rows, effective_only=False)
    effective = _analyze(rows, effective_only=True)
    return {
        "per_stratum": raw["per_stratum"],
        "decisions": raw["decisions"],
        "effective_per_stratum": effective["per_stratum"],
        "effective_decisions": effective["decisions"],
    }


STRATA_ORDER = ["2", "3", "4-5", "6-10", "11+", "?"]


def _overall_from_strata(per_stratum: dict[str, dict[str, Any]]) -> dict[str, Any]:
    overall = _new_bucket()
    for stratum_name in STRATA_ORDER:
        if stratum_name not in per_stratum:
            continue
        b = per_stratum[stratum_name]
        for key in overall:
            if key == "improvements":
                overall[key].extend(b[key])
            else:
                overall[key] += b[key]
    return overall


def _section_lines(name: str, b: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    lines.append(f"## Stratum {name}\n")
    lines.append(f"- decisions sampled: {b['decisions_total']}")
    lines.append(
        f"- stock reproduces (success rate): {b['stock_runs_success']}/{b['stock_runs_total']}"
        f" ({pct(b['stock_runs_success'], b['stock_runs_total'])})"
    )
    lines.append(
        f"- non-stock forcings ineffective (fell back to stock at forced step):"
        f" {b['non_stock_runs_ineffective']}/{b['non_stock_runs_total']}"
        f" ({pct(b['non_stock_runs_ineffective'], b['non_stock_runs_total'])})"
    )
    valid = b["decisions_with_stock_success"]
    lines.append(f"- decisions with valid stock baseline: {valid}")
    lines.append(
        f"- decisions with any successful non-stock candidate:"
        f" {b['decisions_with_alt_success']} ({pct(b['decisions_with_alt_success'], valid)})"
    )
    lines.append(
        f"- decisions where alt strictly beats stock on splits:"
        f" {b['decisions_with_alt_strictly_better']}"
        f" ({pct(b['decisions_with_alt_strictly_better'], valid)})"
    )
    lines.append(
        f"- decisions where alt ties stock on splits:"
        f" {b['decisions_with_alt_tie']} ({pct(b['decisions_with_alt_tie'], valid)})"
    )
    imps = b["improvements"]
    if imps:
        lines.append(
            f"- improvement (splits saved) over stock — median:"
            f" {statistics.median(imps):.1f}, mean: {statistics.mean(imps):.2f},"
            f" p90: {percentile([float(x) for x in imps], 0.9):.1f},"
            f" max: {max(imps)}"
        )
    else:
        lines.append("- improvement: no strictly-better alternatives observed")
    nst = b["non_stock_runs_total"]
    lines.append(
        f"- non-stock candidate runs: total={nst},"
        f" success={b['non_stock_runs_success']} ({pct(b['non_stock_runs_success'], nst)}),"
        f" failure={b['non_stock_runs_failure']} ({pct(b['non_stock_runs_failure'], nst)}),"
        f" timeout={b['non_stock_runs_timeout']} ({pct(b['non_stock_runs_timeout'], nst)})"
    )
    lines.append("")
    return lines


def _headline_lines(label: str, overall: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    lines.append(f"## Headline numbers — {label}\n")
    valid = overall["decisions_with_stock_success"]
    lines.append(
        f"- (1) decisions where an alt strictly beats stock:"
        f" **{pct(overall['decisions_with_alt_strictly_better'], valid)}** of"
        f" {valid} valid decisions"
    )
    imps = overall["improvements"]
    if imps:
        lines.append(
            f"- (2) improvement magnitude — median **{statistics.median(imps):.1f}** splits,"
            f" mean {statistics.mean(imps):.2f}, p90 {percentile([float(x) for x in imps], 0.9):.1f},"
            f" max {max(imps)}"
        )
    else:
        lines.append("- (2) improvement magnitude: no strictly-better alternatives observed")
    nst = overall["non_stock_runs_total"]
    lines.append(
        f"- (3) non-stock candidate failure/timeout rate:"
        f" **{pct(overall['non_stock_runs_failure'] + overall['non_stock_runs_timeout'], nst)}**"
        f" ({overall['non_stock_runs_failure']} failure + {overall['non_stock_runs_timeout']} timeout"
        f" of {nst} runs)"
    )
    lines.append(
        f"- (4) non-stock forcings that silently fell back to stock at forced step:"
        f" **{pct(overall['non_stock_runs_ineffective'], nst)}**"
        f" ({overall['non_stock_runs_ineffective']} of {nst} runs)"
    )
    lines.append("")
    return lines


def render(result: dict[str, Any]) -> str:
    lines: list[str] = ["# Phase 0 branch-cost viability report\n"]
    lines.append(
        "Two views below — the **raw** view counts every forced run; the"
        " **effective-only** view filters out non-stock runs where Lean could"
        " not actually use the requested anchor and fell back to stock, so"
        " those runs are not double-counted as alternatives.\n"
    )

    per_stratum = result["per_stratum"]
    eff_per_stratum = result["effective_per_stratum"]

    lines.append("# Raw view (all forced runs)\n")
    for name in STRATA_ORDER:
        if name in per_stratum:
            lines.extend(_section_lines(name, per_stratum[name]))
    overall = _overall_from_strata(per_stratum)
    lines.extend(_section_lines("ALL", overall))
    lines.extend(_headline_lines("raw", overall))

    lines.append("# Effective-only view (forcings that actually took effect)\n")
    for name in STRATA_ORDER:
        if name in eff_per_stratum:
            lines.extend(_section_lines(name, eff_per_stratum[name]))
    eff_overall = _overall_from_strata(eff_per_stratum)
    lines.extend(_section_lines("ALL", eff_overall))
    lines.extend(_headline_lines("effective-only", eff_overall))

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="inp", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--decisions-out",
        type=Path,
        default=None,
        help="Optional JSONL of per-decision summaries for follow-up analysis",
    )
    args = parser.parse_args()

    rows = load(args.inp)
    result = analyze(rows)
    report = render(result)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report)
    print(report)
    print(f"\nreport written to {args.out}")

    if args.decisions_out is not None:
        args.decisions_out.parent.mkdir(parents=True, exist_ok=True)
        with args.decisions_out.open("w") as h:
            for d in result["decisions"]:
                h.write(json.dumps(d, sort_keys=True) + "\n")
        print(f"per-decision summary written to {args.decisions_out}")


if __name__ == "__main__":
    main()
