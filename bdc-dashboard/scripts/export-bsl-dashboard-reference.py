from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
THREAD_ID = "019f777f-0927-7cf0-96b3-6b2d730356c7"
NPORT_PATH = WORKSPACE_ROOT / "outputs" / THREAD_ID / "nport-bsl" / "nport_bsl_summary.json"
DASHBOARD_PATH = PROJECT_ROOT / "lib" / "dashboard-data.json"
ENRICHMENT_PATH = PROJECT_ROOT / "lib" / "company-enrichment.json"
OUTPUT_PATH = PROJECT_ROOT / "lib" / "bsl-reference-marks.json"

LEGAL_SUFFIXES = {
    "INC", "INCORPORATED", "LLC", "LTD", "LIMITED", "LP", "CORP", "CORPORATION", "CO", "COMPANY",
    "HOLDING", "HOLDINGS",
}


def normalize(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Z0-9]+", " ", ascii_text.upper().replace("&", " AND "))
    tokens = text.split()
    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def aggregate_nport_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in history:
        grouped[row["report_date"]].append(row)
    output = []
    for report_date, rows in sorted(grouped.items()):
        eligible = [row for row in rows if row["principal"] > 0]
        principal = sum(row["principal"] for row in eligible)
        fair_value = sum(row["fair_value_usd"] for row in eligible)
        if not principal:
            continue
        output.append({
            "report_date": report_date,
            "implied_mark": round(fair_value / principal * 100, 4),
            "principal_mm": round(principal / 1_000_000, 3),
            "fair_value_mm": round(fair_value / 1_000_000, 3),
            "funds": sorted({row["fund"] for row in eligible}),
            "facility_count": len(eligible),
            "source_url": eligible[0]["sec_source_url"],
        })
    return output


def nearest_change(points: list[dict[str, Any]], days: int) -> float | None:
    if len(points) < 2:
        return None
    latest_date = date.fromisoformat(points[-1]["report_date"])
    target = latest_date - timedelta(days=days)
    candidates = [point for point in points[:-1] if date.fromisoformat(point["report_date"]) <= target + timedelta(days=45)]
    if not candidates:
        return None
    prior = min(candidates, key=lambda point: abs((date.fromisoformat(point["report_date"]) - target).days))
    if abs((date.fromisoformat(prior["report_date"]) - target).days) > 150:
        return None
    return round(points[-1]["implied_mark"] - prior["implied_mark"], 4)


def first_breach(points: list[dict[str, Any]], threshold: float) -> str | None:
    return next((point["report_date"] for point in points if point["implied_mark"] < threshold), None)


def is_debt_row(row: dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(field) or "")
        for field in ("investment_category", "instrument_type", "investment_description", "security_signature")
    ).lower()
    if any(term in text for term in ("equity", "stock", "llc interest", "warrant", "partnership interest")):
        return False
    return any(term in text for term in ("loan", "debt", "lien", "revolver", "note", "secured", "term"))


def aggregate_bdc_history(rows: list[dict[str, Any]], issuer_key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["issuer_match_key"] == issuer_key and not row.get("is_unfunded_commitment") and is_debt_row(row):
            grouped[row["filing_period_end"]].append(row)
    output = []
    for period, period_rows in sorted(grouped.items()):
        cost = sum(float(row.get("amortized_cost_mm") or 0) for row in period_rows)
        fair_value = sum(float(row.get("fair_value_mm") or 0) for row in period_rows)
        if cost <= 0:
            continue
        output.append({
            "report_date": period,
            "mark_to_cost": round(fair_value / cost * 100, 4),
            "cost_mm": round(cost, 3),
            "fair_value_mm": round(fair_value, 3),
            "funds": sorted({row["fund"] for row in period_rows}),
        })
    return output


def month_lead(first_date: str | None, second_date: str | None) -> int | None:
    if not first_date or not second_date:
        return None
    first = date.fromisoformat(first_date)
    second = date.fromisoformat(second_date)
    return round((second - first).days / 30.4375)


def main() -> None:
    nport = json.loads(NPORT_PATH.read_text(encoding="utf-8"))
    dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
    enrichment = json.loads(ENRICHMENT_PATH.read_text(encoding="utf-8"))
    nport_by_name = {row["normalized_borrower"]: row for row in nport["borrowers"]}
    dataset_as_of = date.fromisoformat(nport["meta"]["latest_report_date"])
    enrichment_by_key = {row["issuer_match_key"]: row for row in enrichment}

    display_by_key: dict[str, str] = {}
    for row in dashboard["holdings_detail_latest"]:
        display_by_key.setdefault(row["issuer_match_key"], row["issuer_name"])
    for row in dashboard["loan_timeline_issuers"]:
        display_by_key[row["issuer_match_key"]] = row["display_name"]

    current_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in dashboard["holdings_detail_latest"]:
        if not row.get("is_unfunded_commitment") and is_debt_row(row) and float(row.get("amortized_cost_mm") or 0) > 0:
            current_by_key[row["issuer_match_key"]].append(row)

    matches = []
    for issuer_key, display_name in sorted(display_by_key.items()):
        enriched = enrichment_by_key.get(issuer_key, {})
        candidates = [
            ("issuer key", issuer_key, "high"),
            ("schedule display", display_name, "high"),
            ("enriched display", str(enriched.get("display_name") or ""), "medium"),
            ("mapped company", str(enriched.get("mapped_company") or ""), "medium"),
        ]
        matched_name = ""
        match_method = ""
        confidence = ""
        for method, candidate, candidate_confidence in candidates:
            normalized = normalize(candidate)
            if normalized and normalized in nport_by_name:
                matched_name = normalized
                match_method = method
                confidence = candidate_confidence
                break
        if not matched_name:
            continue
        reference = nport_by_name[matched_name]
        nport_points = aggregate_nport_history(reference["history"])
        if not nport_points:
            continue
        latest = nport_points[-1]
        reference_age_months = round((dataset_as_of - date.fromisoformat(latest["report_date"])).days / 30.4375)
        current_rows = current_by_key.get(issuer_key, [])
        current_cost = sum(float(row.get("amortized_cost_mm") or 0) for row in current_rows)
        current_fv = sum(float(row.get("fair_value_mm") or 0) for row in current_rows)
        bdc_latest_mark = current_fv / current_cost * 100 if current_cost else None
        bdc_points = aggregate_bdc_history(dashboard["loan_timeline_securities"], issuer_key)
        bdc_first_95 = next((point["report_date"] for point in bdc_points if point["mark_to_cost"] < 95), None)
        bdc_first_90 = next((point["report_date"] for point in bdc_points if point["mark_to_cost"] < 90), None)
        nport_first_95 = first_breach(nport_points, 95)
        nport_first_90 = first_breach(nport_points, 90)
        matches.append({
            "issuer_match_key": issuer_key,
            "dashboard_display_name": display_name,
            "nport_borrower": reference["display_borrower"],
            "match_method": match_method,
            "match_confidence": confidence,
            "latest_reference_date": latest["report_date"],
            "latest_reference_mark": latest["implied_mark"],
            "latest_reference_funds": latest["funds"],
            "reference_age_months": reference_age_months,
            "reference_status": "current" if reference_age_months <= 15 else "historical_only",
            "reference_observation_count": len(nport_points),
            "change_3m": nearest_change(nport_points, 91),
            "change_12m": nearest_change(nport_points, 365),
            "minimum_reference_mark": min(point["implied_mark"] for point in nport_points),
            "minimum_reference_date": min(nport_points, key=lambda point: point["implied_mark"])["report_date"],
            "bdc_latest_mark_to_cost": round(bdc_latest_mark, 4) if bdc_latest_mark is not None else None,
            "bdc_current_funds": sorted({row["fund"] for row in current_rows}),
            "bdc_current_cost_mm": round(current_cost, 3),
            "bdc_current_fair_value_mm": round(current_fv, 3),
            "bdc_minus_reference_pp": round(bdc_latest_mark - latest["implied_mark"], 4) if bdc_latest_mark is not None else None,
            "nport_first_below_95": nport_first_95,
            "bdc_first_below_95": bdc_first_95,
            "nport_lead_months_at_95": month_lead(nport_first_95, bdc_first_95),
            "nport_first_below_90": nport_first_90,
            "bdc_first_below_90": bdc_first_90,
            "nport_lead_months_at_90": month_lead(nport_first_90, bdc_first_90),
            "history": nport_points,
            "bdc_history": bdc_points,
        })

    matches.sort(key=lambda row: (row["latest_reference_mark"], -row["bdc_current_fair_value_mm"], row["issuer_match_key"]))
    current_matches = [row for row in matches if row["reference_status"] == "current"]
    current_discounted = [row for row in current_matches if row["latest_reference_mark"] < 98]
    payload = {
        "meta": {
            **nport["meta"],
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dashboard_match_count": len(matches),
            "high_confidence_match_count": sum(row["match_confidence"] == "high" for row in matches),
            "current_below_98_count": len(current_discounted),
            "current_match_count": len(current_matches),
            "current_below_95_count": sum(row["latest_reference_mark"] < 95 for row in current_matches),
            "current_below_90_count": sum(row["latest_reference_mark"] < 90 for row in current_matches),
            "scope_note": "Dashboard joins are borrower-level exact normalized-name or sourced-enrichment matches. N-PORT and BDC positions may be different facilities or tranches. Reference marks are not executable dealer bids.",
        },
        "matches": matches,
        "insights": {
            "largest_12m_declines": sorted(
                [row for row in current_matches if row["change_12m"] is not None], key=lambda row: row["change_12m"]
            )[:12],
            "largest_bdc_reference_gaps": sorted(
                [row for row in current_matches if row["bdc_minus_reference_pp"] is not None],
                key=lambda row: abs(row["bdc_minus_reference_pp"]), reverse=True,
            )[:12],
            "reference_led_bdc_below_95": sorted(
                [row for row in matches if row["nport_lead_months_at_95"] is not None and row["nport_lead_months_at_95"] > 0],
                key=lambda row: row["nport_lead_months_at_95"], reverse=True,
            ),
        },
        "sources": nport["sources"],
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Dashboard matches: {len(matches)}")
    print(f"High confidence: {payload['meta']['high_confidence_match_count']}")
    print(f"Current below 98: {payload['meta']['current_below_98_count']}")
    print(f"Current below 95: {payload['meta']['current_below_95_count']}")
    print(f"Current below 90: {payload['meta']['current_below_90_count']}")


if __name__ == "__main__":
    main()
