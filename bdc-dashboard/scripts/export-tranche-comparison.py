from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
AUDIT_DB = WORKSPACE_ROOT / "output" / "bdc_fv_par_audit" / "bdc_fv_par_same_facility_audit.sqlite"
OUTPUT_PATH = PROJECT_ROOT / "lib" / "tranche-comparison.json"
DASHBOARD_DATA_PATH = PROJECT_ROOT / "lib" / "dashboard-data.json"
MATERIAL_PRINCIPAL_FLOOR_MM = 5.0
SPREAD_TOLERANCE_PCT = 0.061
MATERIAL_TIER_COST_FLOOR_MM = 1.0


def records(connection: sqlite3.Connection, query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(query, parameters)]


def different_tranche_reasons(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if a["lien_tier"] != b["lien_tier"]:
        reasons.append(f"lien: {a['lien_tier']} vs {b['lien_tier']}")
    flexible_loan_types = {"loan", "loan_unspecified", "term_loan", "delayed_draw_term_loan"}
    facility_types_are_compatible = (
        a["facility_type"] == b["facility_type"]
        or (a["facility_type"] in flexible_loan_types and b["facility_type"] in flexible_loan_types)
    )
    if not facility_types_are_compatible:
        reasons.append(f"type: {a['facility_type']} vs {b['facility_type']}")
    if a["maturity_month"] != b["maturity_month"]:
        reasons.append(f"maturity: {a['maturity_month'] or 'n/a'} vs {b['maturity_month'] or 'n/a'}")
    if a["reference_base_rate"] != b["reference_base_rate"]:
        reasons.append(f"base rate: {a['reference_base_rate'] or 'fixed/n.a.'} vs {b['reference_base_rate'] or 'fixed/n.a.'}")

    fixed_a = a["fixed_coupon_pct"]
    fixed_b = b["fixed_coupon_pct"]
    spread_a = a["spread_pct"]
    spread_b = b["spread_pct"]
    if fixed_a is not None or fixed_b is not None:
        if fixed_a is None or fixed_b is None or abs(float(fixed_a) - float(fixed_b)) > SPREAD_TOLERANCE_PCT:
            reasons.append(f"coupon: {fixed_a if fixed_a is not None else 'floating'} vs {fixed_b if fixed_b is not None else 'floating'}")
    elif spread_a is None or spread_b is None or abs(float(spread_a) - float(spread_b)) > SPREAD_TOLERANCE_PCT:
        reasons.append(f"spread: {spread_a if spread_a is not None else 'n/a'} vs {spread_b if spread_b is not None else 'n/a'}")
    return reasons


def build_different_tranche_gaps(connection: sqlite3.Connection, latest_period: str) -> tuple[list[dict[str, Any]], int, int]:
    facility_rows = records(
        connection,
        """
        select group_id, issuer_match_key, period_end, fund, lien_tier, facility_type,
               maturity_month, reference_base_rate, spread_pct, fixed_coupon_pct,
               principal_mm, fair_value_mm, fv_to_principal_pct, row_count
        from facility_groups
        where period_end = ?
          and principal_quality_status = 'ok'
          and comparison_currency = 'USD'
          and lien_tier = 'first_lien'
          and facility_type not in ('unknown', 'other')
          and principal_mm >= ?
          and fair_value_mm is not null
          and fv_to_principal_pct is not null
          and fv_to_principal_pct between 25 and 125
          and (reference_base_rate = 'SOFR' or fixed_coupon_pct is not null)
          and maturity_month >= ?
        order by issuer_match_key, fund, group_id
        """,
        (latest_period, MATERIAL_PRINCIPAL_FLOOR_MM, latest_period[:7]),
    )
    by_issuer: dict[str, list[dict[str, Any]]] = {}
    for row in facility_rows:
        by_issuer.setdefault(str(row["issuer_match_key"]), []).append(row)

    gaps: list[dict[str, Any]] = []
    for issuer, issuer_rows in by_issuer.items():
        for a, b in combinations(issuer_rows, 2):
            reasons = different_tranche_reasons(a, b)
            if not reasons:
                continue
            mark_a = float(a["fv_to_principal_pct"])
            mark_b = float(b["fv_to_principal_pct"])
            lower_mark_fund = "Tie"
            if mark_a < mark_b:
                lower_mark_fund = str(a["fund"])
            elif mark_b < mark_a:
                lower_mark_fund = str(b["fund"])
            gaps.append(
                {
                    "issuer_match_key": issuer,
                    "period_end": latest_period,
                    "comparison_scope": "cross-fund" if a["fund"] != b["fund"] else "within-fund",
                    "fund_a": a["fund"],
                    "fund_b": b["fund"],
                    "fund_pair": f"{a['fund']} vs {b['fund']}",
                    "fund_a_group_id": a["group_id"],
                    "fund_b_group_id": b["group_id"],
                    "fund_a_lien_tier": a["lien_tier"],
                    "fund_b_lien_tier": b["lien_tier"],
                    "fund_a_facility_type": a["facility_type"],
                    "fund_b_facility_type": b["facility_type"],
                    "fund_a_maturity_month": a["maturity_month"],
                    "fund_b_maturity_month": b["maturity_month"],
                    "fund_a_reference_base_rate": a["reference_base_rate"],
                    "fund_b_reference_base_rate": b["reference_base_rate"],
                    "fund_a_spread_pct": a["spread_pct"],
                    "fund_b_spread_pct": b["spread_pct"],
                    "fund_a_fixed_coupon_pct": a["fixed_coupon_pct"],
                    "fund_b_fixed_coupon_pct": b["fixed_coupon_pct"],
                    "fund_a_principal_mm": a["principal_mm"],
                    "fund_b_principal_mm": b["principal_mm"],
                    "fund_a_fair_value_mm": a["fair_value_mm"],
                    "fund_b_fair_value_mm": b["fair_value_mm"],
                    "fund_a_fv_to_principal_pct": mark_a,
                    "fund_b_fv_to_principal_pct": mark_b,
                    "inter_tranche_gap_pp": abs(mark_a - mark_b),
                    "lower_mark_fund": lower_mark_fund,
                    "structural_differences": reasons,
                }
            )
    gaps.sort(key=lambda row: (-float(row["inter_tranche_gap_pp"]), row["issuer_match_key"], row["fund_pair"]))
    company_count = len({row["issuer_match_key"] for row in gaps})
    return gaps[:250], len(gaps), company_count


CAPITAL_TIERS: dict[str, int] = {
    "Common equity / warrants": 0,
    "Preferred equity": 1,
    "Junior / unsecured debt": 2,
    "First-lien senior secured": 3,
}


def classify_capital_tier(row: dict[str, Any]) -> str | None:
    text = " ".join(
        str(row.get(field) or "")
        for field in ("investment_category", "instrument_type", "investment_description")
    ).lower().replace("-", " ")
    if any(term in text for term in ("preferred equity", "preferred stock", "preferred shares", "preferred interest")):
        return "Preferred equity"
    if any(
        term in text
        for term in (
            "common equity",
            "common stock",
            "common shares",
            "equity interest",
            "membership interest",
            "member interest",
            "partnership interest",
            "warrant",
        )
    ):
        return "Common equity / warrants"
    if any(
        term in text
        for term in (
            "second lien",
            "subordinated",
            "mezzanine",
            "junior debt",
            "unsecured loan",
            "unsecured note",
        )
    ):
        return "Junior / unsecured debt"
    if any(
        term in text
        for term in (
            "first lien",
            "senior secured",
            "senior loan",
            "unitranche",
        )
    ):
        return "First-lien senior secured"
    return None


def build_capital_structure_pairs() -> tuple[list[dict[str, Any]], dict[str, int]]:
    dashboard = json.loads(DASHBOARD_DATA_PATH.read_text(encoding="utf-8"))
    cross_fund_keys = {row["issuer_match_key"] for row in dashboard["cross_fund_issuer_latest"]}
    buckets: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in dashboard["holdings_detail_latest"]:
        issuer = row.get("issuer_match_key")
        if not issuer or issuer not in cross_fund_keys or row.get("exposure_type") != "funded":
            continue
        tier = classify_capital_tier(row)
        if not tier:
            continue
        cost = float(row.get("amortized_cost_mm") or 0.0)
        fair_value = float(row.get("fair_value_mm") or 0.0)
        key = (issuer, str(row["fund"]), tier)
        bucket = buckets.setdefault(
            key,
            {
                "issuer_match_key": issuer,
                "fund": row["fund"],
                "tier": tier,
                "tier_rank": CAPITAL_TIERS[tier],
                "amortized_cost_mm": 0.0,
                "fair_value_mm": 0.0,
                "holding_rows": 0,
                "instrument_labels": set(),
            },
        )
        bucket["amortized_cost_mm"] += cost
        bucket["fair_value_mm"] += fair_value
        bucket["holding_rows"] += 1
        label = row.get("investment_description") or row.get("instrument_type") or row.get("investment_category")
        if label:
            bucket["instrument_labels"].add(str(label))

    by_issuer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for bucket in buckets.values():
        cost = float(bucket["amortized_cost_mm"])
        if cost < MATERIAL_TIER_COST_FLOOR_MM:
            continue
        bucket["amortized_cost_mm"] = round(cost, 6)
        bucket["fair_value_mm"] = round(float(bucket["fair_value_mm"]), 6)
        bucket["fv_to_cost_pct"] = round(float(bucket["fair_value_mm"]) / cost * 100.0, 6)
        bucket["instrument_labels"] = sorted(bucket["instrument_labels"])[:4]
        by_issuer[str(bucket["issuer_match_key"])].append(bucket)

    pairs: list[dict[str, Any]] = []
    for issuer, issuer_buckets in by_issuer.items():
        for a, b in combinations(issuer_buckets, 2):
            if a["tier_rank"] == b["tier_rank"]:
                continue
            junior, senior = (a, b) if a["tier_rank"] < b["tier_rank"] else (b, a)
            signed_gap = float(senior["fv_to_cost_pct"]) - float(junior["fv_to_cost_pct"])
            status = "flat"
            if signed_gap >= 5.0:
                status = "expected_waterfall"
            elif signed_gap <= -5.0:
                status = "inversion"
            pairs.append(
                {
                    "issuer_match_key": issuer,
                    "comparison_scope": "cross-fund" if junior["fund"] != senior["fund"] else "within-fund",
                    "junior_fund": junior["fund"],
                    "senior_fund": senior["fund"],
                    "junior_tier": junior["tier"],
                    "senior_tier": senior["tier"],
                    "junior_holding_rows": junior["holding_rows"],
                    "senior_holding_rows": senior["holding_rows"],
                    "junior_amortized_cost_mm": junior["amortized_cost_mm"],
                    "junior_fair_value_mm": junior["fair_value_mm"],
                    "junior_fv_to_cost_pct": junior["fv_to_cost_pct"],
                    "senior_amortized_cost_mm": senior["amortized_cost_mm"],
                    "senior_fair_value_mm": senior["fair_value_mm"],
                    "senior_fv_to_cost_pct": senior["fv_to_cost_pct"],
                    "senior_minus_junior_gap_pp": round(signed_gap, 6),
                    "absolute_gap_pp": round(abs(signed_gap), 6),
                    "waterfall_status": status,
                    "junior_instrument_labels": junior["instrument_labels"],
                    "senior_instrument_labels": senior["instrument_labels"],
                }
            )
    status_order = {"expected_waterfall": 0, "inversion": 1, "flat": 2}
    pairs.sort(
        key=lambda row: (
            status_order[row["waterfall_status"]],
            -float(row["absolute_gap_pp"]),
            row["issuer_match_key"],
        )
    )
    counts = Counter(row["waterfall_status"] for row in pairs)
    return pairs, {
        "pair_count": len(pairs),
        "company_count": len({row["issuer_match_key"] for row in pairs}),
        "expected_waterfall_count": counts["expected_waterfall"],
        "inversion_count": counts["inversion"],
        "flat_count": counts["flat"],
    }


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
    different_tranche_gaps, different_tranche_pair_count, different_tranche_company_count = build_different_tranche_gaps(
        connection, latest_period
    )
    capital_structure_pairs, capital_structure_counts = build_capital_structure_pairs()

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
            "different_tranche_pair_count": different_tranche_pair_count,
            "different_tranche_company_count": different_tranche_company_count,
            "material_principal_floor_mm": MATERIAL_PRINCIPAL_FLOOR_MM,
            "capital_structure_pair_count": capital_structure_counts["pair_count"],
            "capital_structure_company_count": capital_structure_counts["company_count"],
            "expected_waterfall_count": capital_structure_counts["expected_waterfall_count"],
            "capital_structure_inversion_count": capital_structure_counts["inversion_count"],
            "capital_structure_flat_count": capital_structure_counts["flat_count"],
            "material_tier_cost_floor_mm": MATERIAL_TIER_COST_FLOOR_MM,
            "spread_tolerance_bps": float(metrics["spread_tolerance_pct"]) * 100,
            "methodology": "Comparable facilities must be first-lien USD loans with complete principal, plausible FV/par, the same maturity month and reference rate, compatible facility types, and spread or fixed coupon within the stated tolerance.",
            "different_tranche_methodology": "Different-tranche pairs must be first-lien USD debt with at least $5mm of disclosed principal in each facility, a current or future maturity, a SOFR or stated fixed-rate structure, and FV/principal between 25% and 125%. At least one maturity, rate, coupon, lien, or non-equivalent facility-type field must differ.",
            "capital_structure_methodology": "Capital-structure pairs aggregate funded holdings by issuer, fund, and explicit seniority label, then compare FV/cost for common equity or warrants, preferred equity, junior or unsecured debt, and first-lien senior secured debt. Each tier must have at least $1mm of amortized cost. A 5 percentage-point separation defines either an expected junior-first waterfall or an inversion.",
        },
        "facility_gaps": facility_gaps,
        "company_gaps": company_gaps,
        "different_tranche_gaps": different_tranche_gaps,
        "capital_structure_pairs": capital_structure_pairs,
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
    print(f"Different-tranche gaps: {len(different_tranche_gaps)}")
    print(f"Capital-structure pairs: {len(capital_structure_pairs)}")


if __name__ == "__main__":
    main()
