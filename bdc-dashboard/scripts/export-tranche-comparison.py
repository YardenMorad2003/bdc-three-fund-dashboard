from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
AUDIT_DB = WORKSPACE_ROOT / "output" / "bdc_fv_par_audit" / "bdc_fv_par_same_facility_audit.sqlite"
OUTPUT_PATH = PROJECT_ROOT / "lib" / "tranche-comparison.json"


def records(connection: sqlite3.Connection, query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(query, parameters)]


def main() -> None:
    if not AUDIT_DB.exists():
        raise FileNotFoundError(f"Audit database not found: {AUDIT_DB}")

    connection = sqlite3.connect(AUDIT_DB)
    connection.row_factory = sqlite3.Row
    metrics = {row["metric"]: row["value"] for row in connection.execute("select metric, value from audit_summary")}
    latest_period = metrics["latest_period"]

    facility_gaps = records(
        connection,
        """
        select issuer_match_key, period_end, fund_pair, fund_a, fund_b,
               facility_match_confidence, fund_a_principal_mm, fund_a_fair_value_mm,
               fund_a_fv_to_principal_pct, fund_b_principal_mm, fund_b_fair_value_mm,
               fund_b_fv_to_principal_pct, fund_a_minus_fund_b_gap_pp,
               inter_fund_gap_pp, conservative_fund, maturity_month,
               reference_base_rate, spread_pct_a, spread_pct_b,
               fixed_coupon_pct_a, fixed_coupon_pct_b, currency
        from comparable_fv_par_gaps
        where period_end = ?
        order by inter_fund_gap_pp desc, issuer_match_key, fund_pair
        """,
        (latest_period,),
    )
    company_gaps = records(
        connection,
        """
        select issuer_match_key, period_end, fund_pair, funds,
               comparable_facility_pair_count, abstention_count, fund_a, fund_b,
               fund_a_matched_principal_mm, fund_a_matched_fair_value_mm,
               fund_a_fv_to_principal_pct, fund_b_matched_principal_mm,
               fund_b_matched_fair_value_mm, fund_b_fv_to_principal_pct,
               fund_a_minus_fund_b_gap_pp, inter_fund_gap_pp, conservative_fund,
               non_comparable_reasons
        from candidate_period_summary
        where period_end = ? and candidate_status = 'comparable'
        order by inter_fund_gap_pp desc, issuer_match_key, fund_pair
        """,
        (latest_period,),
    )
    persistence = records(
        connection,
        """
        select issuer_match_key, fund_pair, comparable_period_count,
               latest_period_status, latest_inter_fund_gap_pp,
               latest_conservative_fund, avg_abs_gap_pp, max_abs_gap_pp,
               persistent_conservative_fund, conservative_fund_sequence
        from five_quarter_persistence
        where latest_period_status = 'comparable'
        order by avg_abs_gap_pp desc, issuer_match_key, fund_pair
        """,
    )

    reason_counts: Counter[str] = Counter()
    for row in connection.execute(
        """
        select non_comparable_reason
        from same_facility_comparability
        where period_end = ? and facility_match_status <> 'comparable'
        """,
        (latest_period,),
    ):
        for reason in str(row["non_comparable_reason"] or "").split(";"):
            if reason:
                reason_counts[reason] += 1

    payload = {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "latest_period": latest_period,
            "candidate_count": int(metrics["latest_candidate_count"]),
            "par_covered_candidate_count": int(metrics["latest_par_covered_candidate_count"]),
            "comparable_candidate_count": int(metrics["latest_comparable_candidate_count"]),
            "abstained_candidate_count": int(metrics["latest_abstained_candidate_count"]),
            "comparable_facility_pair_count": int(metrics["latest_comparable_facility_pair_count"]),
            "spread_tolerance_bps": float(metrics["spread_tolerance_pct"]) * 100,
            "methodology": "Comparable facilities must be first-lien USD loans with complete principal, plausible FV/par, the same maturity month and reference rate, compatible facility types, and spread or fixed coupon within the stated tolerance.",
        },
        "facility_gaps": facility_gaps,
        "company_gaps": company_gaps,
        "persistence": persistence,
        "abstention_reasons": [
            {"reason": reason, "count": count}
            for reason, count in reason_counts.most_common()
        ],
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(WORKSPACE_ROOT)}")
    print(f"Facility gaps: {len(facility_gaps)}")
    print(f"Company gaps: {len(company_gaps)}")


if __name__ == "__main__":
    main()
