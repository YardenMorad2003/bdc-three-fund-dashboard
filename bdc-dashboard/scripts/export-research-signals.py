from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = PROJECT_ROOT / "lib" / "dashboard-data.json"
TRANCHE_PATH = PROJECT_ROOT / "lib" / "tranche-comparison.json"
ENRICHMENT_PATH = PROJECT_ROOT / "lib" / "company-enrichment.json"
OUTPUT_PATH = PROJECT_ROOT / "lib" / "research-signals.json"
MATERIAL_TIER_COST_FLOOR_MM = 1.0

CAPITAL_TIERS: dict[str, int] = {
    "Common equity / warrants": 0,
    "Preferred equity": 1,
    "Junior / unsecured debt": 2,
    "First-lien senior secured": 3,
}

SIGNAL_DEFINITIONS = {
    "deep_discount": {
        "label": "Deep discount",
        "description": "Aggregate fair value is below 90% of amortized cost.",
    },
    "below_cost": {
        "label": "Below cost",
        "description": "Aggregate fair value is between 90% and 97% of amortized cost.",
    },
    "rapid_deterioration": {
        "label": "Rapid deterioration",
        "description": "Aggregate FV/cost fell at least 5 percentage points from the prior observed quarter.",
    },
    "emerging_deterioration": {
        "label": "Emerging deterioration",
        "description": "Aggregate FV/cost fell 2-5 percentage points from the prior observed quarter.",
    },
    "audited_disagreement": {
        "label": "Audited disagreement",
        "description": "Matched first-lien facilities differ by at least 5 points of FV/principal across funds.",
    },
    "crowded": {
        "label": "Crowded exposure",
        "description": "At least four verified BDCs hold the normalized issuer.",
    },
    "senior_first": {
        "label": "Senior moved first",
        "description": "An explicit fund-pair test shows first-lien debt crossed below 95% before junior capital.",
    },
    "junior_first": {
        "label": "Junior moved first",
        "description": "An explicit fund-pair test shows junior capital crossed below 95% before first-lien debt.",
    },
    "stable_context": {
        "label": "Context",
        "description": "No primary triage threshold is currently breached.",
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def source_derived(profile: dict[str, Any]) -> bool:
    return str(profile.get("notes") or "").startswith("Source-derived schedule context")


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
    if any(term in text for term in ("first lien", "senior secured", "senior loan", "unitranche")):
        return "First-lien senior secured"
    return None


def first_breach(periods: list[str], marks: dict[str, float], threshold: float) -> str | None:
    return next((period for period in periods if marks.get(period, 999.0) < threshold), None)


def build_fund_pair_lead_lag(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in dashboard["loan_timeline_securities"]:
        issuer = row.get("issuer_match_key")
        period = row.get("filing_period_end")
        fund = row.get("fund")
        if not issuer or not period or not fund or row.get("exposure_type") != "funded":
            continue
        tier = classify_capital_tier(row)
        if not tier:
            continue
        key = (str(issuer), str(period), str(fund), tier)
        bucket = buckets.setdefault(
            key,
            {
                "issuer_match_key": issuer,
                "filing_period_end": period,
                "fund": fund,
                "tier": tier,
                "tier_rank": CAPITAL_TIERS[tier],
                "amortized_cost_mm": 0.0,
                "fair_value_mm": 0.0,
                "holding_rows": 0,
            },
        )
        bucket["amortized_cost_mm"] += float(row.get("amortized_cost_mm") or 0.0)
        bucket["fair_value_mm"] += float(row.get("fair_value_mm") or 0.0)
        bucket["holding_rows"] += 1

    histories: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for bucket in buckets.values():
        cost = float(bucket["amortized_cost_mm"])
        if cost < MATERIAL_TIER_COST_FLOOR_MM:
            continue
        bucket["amortized_cost_mm"] = round(cost, 6)
        bucket["fair_value_mm"] = round(float(bucket["fair_value_mm"]), 6)
        bucket["fv_to_cost_pct"] = round(float(bucket["fair_value_mm"]) / cost * 100.0, 6)
        histories[(str(bucket["issuer_match_key"]), str(bucket["fund"]), str(bucket["tier"]))].append(bucket)

    by_issuer: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for issuer, fund, tier in histories:
        by_issuer[issuer].append((fund, tier))

    output: list[dict[str, Any]] = []
    senior_tier = "First-lien senior secured"
    for issuer, fund_tiers in by_issuer.items():
        junior_keys = sorted(
            {(fund, tier) for fund, tier in fund_tiers if CAPITAL_TIERS[tier] < CAPITAL_TIERS[senior_tier]},
            key=lambda item: (CAPITAL_TIERS[item[1]], item[0]),
        )
        senior_keys = sorted({(fund, tier) for fund, tier in fund_tiers if tier == senior_tier})
        for (junior_fund, junior_tier), (senior_fund, _) in product(junior_keys, senior_keys):
            junior_rows = histories[(issuer, junior_fund, junior_tier)]
            senior_rows = histories[(issuer, senior_fund, senior_tier)]
            junior_marks = {str(row["filing_period_end"]): float(row["fv_to_cost_pct"]) for row in junior_rows}
            senior_marks = {str(row["filing_period_end"]): float(row["fv_to_cost_pct"]) for row in senior_rows}
            common_periods = sorted(set(junior_marks) & set(senior_marks))
            if len(common_periods) < 2:
                continue

            junior_95 = first_breach(common_periods, junior_marks, 95.0)
            senior_95 = first_breach(common_periods, senior_marks, 95.0)
            junior_90 = first_breach(common_periods, junior_marks, 90.0)
            senior_90 = first_breach(common_periods, senior_marks, 90.0)
            lead_quarters: int | None = None
            if junior_95 and senior_95:
                lead_quarters = common_periods.index(senior_95) - common_periods.index(junior_95)
                status = "junior_first" if lead_quarters > 0 else "senior_first" if lead_quarters < 0 else "simultaneous"
            elif junior_95:
                status = "junior_first"
            elif senior_95:
                status = "senior_first"
            else:
                status = "no_breach"

            latest_period = common_periods[-1]
            output.append(
                {
                    "issuer_match_key": issuer,
                    "comparison_scope": "within-fund" if junior_fund == senior_fund else "cross-fund",
                    "junior_fund": junior_fund,
                    "senior_fund": senior_fund,
                    "junior_tier": junior_tier,
                    "senior_tier": senior_tier,
                    "common_period_count": len(common_periods),
                    "first_common_period": common_periods[0],
                    "latest_common_period": latest_period,
                    "junior_first_below_95_period": junior_95,
                    "senior_first_below_95_period": senior_95,
                    "junior_first_below_90_period": junior_90,
                    "senior_first_below_90_period": senior_90,
                    "lead_lag_status": status,
                    "lead_quarters_at_95": lead_quarters,
                    "latest_junior_fv_to_cost_pct": round(junior_marks[latest_period], 6),
                    "latest_senior_fv_to_cost_pct": round(senior_marks[latest_period], 6),
                    "latest_senior_minus_junior_gap_pp": round(senior_marks[latest_period] - junior_marks[latest_period], 6),
                    "minimum_junior_fv_to_cost_pct": round(min(junior_marks[p] for p in common_periods), 6),
                    "minimum_senior_fv_to_cost_pct": round(min(senior_marks[p] for p in common_periods), 6),
                    "periods": common_periods,
                }
            )

    status_order = {"junior_first": 0, "senior_first": 1, "simultaneous": 2, "no_breach": 3}
    output.sort(
        key=lambda row: (
            status_order[str(row["lead_lag_status"])],
            0 if row["comparison_scope"] == "cross-fund" else 1,
            -abs(float(row["latest_senior_minus_junior_gap_pp"])),
            str(row["issuer_match_key"]),
            str(row["junior_fund"]),
            str(row["senior_fund"]),
        )
    )
    return output


def positive_percentile(value: float | None, population: list[float]) -> float:
    if value is None or value <= 0:
        return 0.0
    positives = sorted(item for item in population if item > 0)
    if not positives:
        return 0.0
    below_or_equal = sum(1 for item in positives if item <= value)
    return below_or_equal / len(positives)


def percentile(value: float, population: list[float]) -> float:
    ordered = sorted(population)
    if not ordered:
        return 0.0
    below_or_equal = sum(1 for item in ordered if item <= value)
    return below_or_equal / len(ordered)


def main() -> None:
    dashboard = load_json(DASHBOARD_PATH)
    tranche = load_json(TRANCHE_PATH)
    enrichment = load_json(ENRICHMENT_PATH)
    latest_period = str(dashboard["meta"]["latest_common_period"])

    profiles: dict[str, dict[str, Any]] = {}
    for profile in enrichment:
        key = str(profile.get("issuer_match_key") or "")
        if not key:
            continue
        if key not in profiles or (source_derived(profiles[key]) and not source_derived(profile)):
            profiles[key] = profile

    history_by_issuer_period: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    periods_by_issuer: dict[str, set[str]] = defaultdict(set)
    for row in dashboard["issuer_period_history"]:
        key = str(row.get("issuer_match_key") or "")
        period = str(row.get("filing_period_end") or "")
        if not key or not period:
            continue
        history_by_issuer_period[(key, period)].append(row)
        periods_by_issuer[key].add(period)

    company_gaps_by_issuer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in tranche["company_gaps"]:
        company_gaps_by_issuer[str(row["issuer_match_key"])].append(row)

    pairwise_lead_lag = build_fund_pair_lead_lag(dashboard)
    pairwise_by_issuer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pairwise_lead_lag:
        pairwise_by_issuer[str(row["issuer_match_key"])].append(row)

    signal_rows: list[dict[str, Any]] = []
    for issuer in dashboard["cross_fund_issuer_latest"]:
        key = str(issuer["issuer_match_key"])
        profile = profiles.get(key, {})
        cost = float(issuer.get("amortized_cost_mm") or 0.0)
        fair_value = float(issuer.get("fair_value_mm") or 0.0)
        latest_mark = fair_value / cost * 100.0 if cost else None

        prior_periods = sorted(period for period in periods_by_issuer.get(key, set()) if period < latest_period)
        prior_period = prior_periods[-1] if prior_periods else None
        prior_rows = history_by_issuer_period.get((key, prior_period), []) if prior_period else []
        prior_cost = sum(float(row.get("amortized_cost_mm") or 0.0) for row in prior_rows)
        prior_fair_value = sum(float(row.get("fair_value_mm") or 0.0) for row in prior_rows)
        prior_mark = prior_fair_value / prior_cost * 100.0 if prior_cost else None
        qoq_change = latest_mark - prior_mark if latest_mark is not None and prior_mark is not None else None

        fund_marks = [
            float(row["fair_value_mm"]) / float(row["amortized_cost_mm"]) * 100.0
            for row in issuer.get("fund_breakdown", [])
            if float(row.get("amortized_cost_mm") or 0.0) > 0
        ]
        portfolio_spread = max(fund_marks) - min(fund_marks) if len(fund_marks) >= 2 else None
        audited_rows = company_gaps_by_issuer.get(key, [])
        audited_row = max(audited_rows, key=lambda row: float(row.get("inter_fund_gap_pp") or 0.0), default=None)
        pair_rows = pairwise_by_issuer.get(key, [])
        senior_first_pairs = sum(1 for row in pair_rows if row["lead_lag_status"] == "senior_first")
        junior_first_pairs = sum(1 for row in pair_rows if row["lead_lag_status"] == "junior_first")

        signal_rows.append(
            {
                "issuer_match_key": key,
                "display_name": profile.get("display_name") or issuer.get("representative_issuer_name") or key.title(),
                "mapped_company": profile.get("mapped_company") or issuer.get("representative_issuer_name") or key,
                "funds": issuer.get("funds", []),
                "fund_count": int(issuer.get("fund_count") or 0),
                "fair_value_mm": round(fair_value, 6),
                "amortized_cost_mm": round(cost, 6),
                "latest_fv_to_cost_pct": round(latest_mark, 6) if latest_mark is not None else None,
                "prior_period": prior_period,
                "prior_fv_to_cost_pct": round(prior_mark, 6) if prior_mark is not None else None,
                "qoq_change_pp": round(qoq_change, 6) if qoq_change is not None else None,
                "portfolio_mark_spread_pp": round(portfolio_spread, 6) if portfolio_spread is not None else None,
                "audited_same_facility_gap_pp": round(float(audited_row["inter_fund_gap_pp"]), 6) if audited_row else None,
                "audited_fund_pair": audited_row.get("fund_pair") if audited_row else None,
                "audited_conservative_fund": audited_row.get("conservative_fund") if audited_row else None,
                "pairwise_lead_lag_tests": len(pair_rows),
                "senior_first_pair_count": senior_first_pairs,
                "junior_first_pair_count": junior_first_pairs,
            }
        )

    discount_population = [max(0.0, 100.0 - float(row["latest_fv_to_cost_pct"])) for row in signal_rows if row["latest_fv_to_cost_pct"] is not None]
    decline_population = [max(0.0, -float(row["qoq_change_pp"])) for row in signal_rows if row["qoq_change_pp"] is not None]
    gap_population = [float(row["audited_same_facility_gap_pp"]) for row in signal_rows if row["audited_same_facility_gap_pp"] is not None]
    exposure_population = [float(row["fair_value_mm"]) for row in signal_rows]
    breadth_population = [float(row["fund_count"]) for row in signal_rows]

    for row in signal_rows:
        mark = row["latest_fv_to_cost_pct"]
        change = row["qoq_change_pp"]
        gap = row["audited_same_facility_gap_pp"]
        discount = max(0.0, 100.0 - float(mark)) if mark is not None else 0.0
        decline = max(0.0, -float(change)) if change is not None else 0.0
        components = {
            "discount": positive_percentile(discount, discount_population) * min(1.0, discount / 20.0),
            "deterioration": positive_percentile(decline, decline_population) * min(1.0, decline / 10.0),
            "audited_disagreement": (
                positive_percentile(float(gap), gap_population) * min(1.0, float(gap) / 10.0)
                if gap is not None
                else 0.0
            ),
            "materiality": percentile(float(row["fair_value_mm"]), exposure_population),
            "breadth": percentile(float(row["fund_count"]), breadth_population),
        }
        score = (
            components["discount"] * 0.35
            + components["deterioration"] * 0.28
            + components["audited_disagreement"] * 0.18
            + components["materiality"] * 0.12
            + components["breadth"] * 0.07
        ) * 100.0
        if row["senior_first_pair_count"]:
            score = min(100.0, score + 5.0)

        tags: list[str] = []
        if mark is not None and float(mark) < 90:
            tags.append("deep_discount")
        elif mark is not None and float(mark) < 97:
            tags.append("below_cost")
        if change is not None and float(change) <= -5:
            tags.append("rapid_deterioration")
        elif change is not None and float(change) <= -2:
            tags.append("emerging_deterioration")
        if gap is not None and float(gap) >= 5:
            tags.append("audited_disagreement")
        if int(row["fund_count"]) >= 4:
            tags.append("crowded")
        if int(row["senior_first_pair_count"]) > 0:
            tags.append("senior_first")
        if int(row["junior_first_pair_count"]) > 0:
            tags.append("junior_first")
        if not tags:
            tags.append("stable_context")

        row["priority_score"] = round(score, 1)
        row["priority_band"] = "review" if score >= 70 else "watch" if score >= 50 else "monitor" if score >= 30 else "context"
        row["score_components"] = {key: round(value * 100.0, 1) for key, value in components.items()}
        row["signal_tags"] = tags

    signal_rows.sort(key=lambda row: (-float(row["priority_score"]), -float(row["fair_value_mm"]), str(row["issuer_match_key"])))
    for rank, row in enumerate(signal_rows, start=1):
        row["priority_rank"] = rank

    material_rows = [row for row in signal_rows if float(row["fair_value_mm"]) >= 20]
    with_change = [row for row in material_rows if row["qoq_change_pp"] is not None]
    with_mark = [row for row in material_rows if row["latest_fv_to_cost_pct"] is not None]
    with_gap = [row for row in signal_rows if row["audited_same_facility_gap_pp"] is not None]
    most_crowded = sorted(signal_rows, key=lambda row: (-int(row["fund_count"]), -float(row["fair_value_mm"])))[0]

    payload = {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "latest_period": latest_period,
            "methodology": "Priority score combines empirical rank with absolute severity: 35% aggregate discount, 28% quarter deterioration, 18% audited same-facility disagreement, 12% exposure materiality, and 7% cross-fund breadth. Discount, deterioration, and disagreement reach full intensity at 20, 10, and 10 percentage points, respectively. A verified senior-first fund-pair breach adds five points. It is a triage tool, not a credit rating.",
            "pairwise_lead_lag_methodology": "Fund-pair lead-lag tests aggregate only within issuer, fund, quarter, and explicit capital tier. Each junior-fund versus senior-fund pair requires at least $1mm of cost in each tier and two common quarters. First crossings below 95% and 90% of cost are reported without pooling lenders.",
            "signal_count": len(signal_rows),
            "review_count": sum(1 for row in signal_rows if row["priority_band"] == "review"),
            "watch_count": sum(1 for row in signal_rows if row["priority_band"] == "watch"),
            "monitor_count": sum(1 for row in signal_rows if row["priority_band"] == "monitor"),
            "deep_discount_count": sum(1 for row in signal_rows if "deep_discount" in row["signal_tags"]),
            "rapid_deterioration_count": sum(1 for row in signal_rows if "rapid_deterioration" in row["signal_tags"]),
            "audited_disagreement_count": sum(1 for row in signal_rows if "audited_disagreement" in row["signal_tags"]),
            "crowded_count": sum(1 for row in signal_rows if "crowded" in row["signal_tags"]),
            "pairwise_lead_lag_count": len(pairwise_lead_lag),
            "cross_fund_pairwise_count": sum(1 for row in pairwise_lead_lag if row["comparison_scope"] == "cross-fund"),
            "junior_first_pair_count": sum(1 for row in pairwise_lead_lag if row["lead_lag_status"] == "junior_first"),
            "senior_first_pair_count": sum(1 for row in pairwise_lead_lag if row["lead_lag_status"] == "senior_first"),
        },
        "signal_definitions": SIGNAL_DEFINITIONS,
        "issuer_signals": signal_rows,
        "fund_pair_lead_lag": pairwise_lead_lag,
        "headline_insights": {
            "largest_material_decline": min(with_change, key=lambda row: float(row["qoq_change_pp"]), default=None),
            "largest_material_discount": min(with_mark, key=lambda row: float(row["latest_fv_to_cost_pct"]), default=None),
            "widest_audited_gap": max(with_gap, key=lambda row: float(row["audited_same_facility_gap_pp"]), default=None),
            "most_crowded": most_crowded,
        },
    }

    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Issuer signals: {len(signal_rows)}")
    print(f"Fund-pair lead-lag tests: {len(pairwise_lead_lag)}")


if __name__ == "__main__":
    main()
