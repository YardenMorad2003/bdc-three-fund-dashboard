from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
THREAD_ID = "019f777f-0927-7cf0-96b3-6b2d730356c7"
NPORT_PATH = WORKSPACE_ROOT / "outputs" / THREAD_ID / "nport-bsl" / "nport_bsl_summary.json"
DASHBOARD_PATH = PROJECT_ROOT / "lib" / "dashboard-data.json"
REFERENCE_PATH = PROJECT_ROOT / "lib" / "bsl-reference-marks.json"
RESEARCH_PATH = PROJECT_ROOT / "lib" / "company-credit-research.json"
OUTPUT_PATH = PROJECT_ROOT / "lib" / "etf-implied-bdc-marks.json"


def is_debt(row: dict[str, Any]) -> bool:
    text = " ".join(str(row.get(field) or "") for field in (
        "investment_category", "instrument_type", "investment_description"
    )).lower()
    if any(term in text for term in ("equity", "stock", "warrant", "llc interest", "partnership interest")):
        return False
    return any(term in text for term in ("loan", "debt", "lien", "secured", "revolver", "note", "term"))


def parse_date(value: str | None) -> tuple[date | None, str]:
    text = str(value or "").strip()
    for fmt, precision in (("%Y-%m-%d", "day"), ("%m/%d/%Y", "day"), ("%m/%Y", "month"), ("%Y", "year")):
        try:
            return datetime.strptime(text, fmt).date(), precision
        except ValueError:
            pass
    return None, "none"


def parse_rate(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        number = float(text)
        return number * 100 if abs(number) <= 1 else number
    except ValueError:
        pass
    percentages = re.findall(r"(-?\d+(?:\.\d+)?)\s*%", text)
    if len(percentages) == 1 and not re.search(r"SOFR|LIBOR|PRIME|EURIBOR|CORRA|SONIA", text, re.I):
        return float(percentages[0])
    return None


def maturity_distance(bdc_value: str | None, nport_value: str | None) -> tuple[int | None, str]:
    bdc_date, precision = parse_date(bdc_value)
    nport_date, _ = parse_date(nport_value)
    if not bdc_date or not nport_date:
        return None, precision
    if precision == "month":
        months = abs((bdc_date.year - nport_date.year) * 12 + bdc_date.month - nport_date.month)
        return months * 30, precision
    if precision == "year":
        return abs(bdc_date.year - nport_date.year) * 365, precision
    return abs((bdc_date - nport_date).days), precision


def tier_label(row: dict[str, Any]) -> str:
    text = " ".join(str(row.get(field) or "") for field in (
        "investment_category", "instrument_type", "investment_description", "loan_title"
    )).lower()
    if "second lien" in text or "2nd lien" in text:
        return "Second lien"
    if "first lien" in text or "1st lien" in text or "senior secured" in text:
        return "First lien / senior secured"
    return "Debt — tier not explicit"


def compatible_tier(bdc: dict[str, Any], nport: dict[str, Any]) -> bool:
    bdc_tier = tier_label(bdc)
    nport_tier = tier_label(nport)
    if bdc_tier == "Second lien":
        return nport_tier == "Second lien"
    if bdc_tier == "First lien / senior secured":
        return nport_tier != "Second lien"
    return True


def round_or_none(value: float | None, digits: int = 4) -> float | None:
    return round(value, digits) if value is not None else None


def main() -> None:
    dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
    nport = json.loads(NPORT_PATH.read_text(encoding="utf-8"))
    references = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    research = json.loads(RESEARCH_PATH.read_text(encoding="utf-8"))
    research_by_key = {row["issuer_match_key"]: row for row in research["rows"]}
    match_by_key = {row["issuer_match_key"]: row for row in references["matches"]}
    borrower_by_normalized = {row["normalized_borrower"]: row for row in nport["borrowers"]}
    borrower_by_display = {row["display_borrower"]: row for row in nport["borrowers"]}
    dataset_as_of = date.fromisoformat(nport["meta"]["latest_report_date"])
    recent_cutoff = dataset_as_of - timedelta(days=460)

    raw_matches: list[dict[str, Any]] = []
    directional: dict[tuple[str, str], dict[str, Any]] = {}
    for bdc in dashboard["holdings_detail_latest"]:
        issuer_key = bdc["issuer_match_key"]
        if issuer_key not in match_by_key or bdc.get("is_unfunded_commitment") or not is_debt(bdc):
            continue
        principal = float(bdc.get("principal_mm") or 0)
        if principal <= 0:
            continue
        reference = match_by_key[issuer_key]
        borrower = borrower_by_normalized.get(issuer_key) or borrower_by_display.get(reference["nport_borrower"])
        if not borrower:
            continue

        directional[(issuer_key, bdc["fund"])] = {
            "issuer_match_key": issuer_key,
            "issuer": reference["dashboard_display_name"],
            "bdc_fund": bdc["fund"],
            "reference_mark": reference["latest_reference_mark"],
            "reference_date": reference["latest_reference_date"],
            "reference_status": reference["reference_status"],
            "bdc_issuer_mark_to_cost": reference["bdc_latest_mark_to_cost"],
            "classification": "borrower-only directional reference",
            "confidence": "low",
            "reason": "The borrower matches, but the available schedule fields do not identify the same maturity, rate, and tier.",
        }

        bdc_rate = parse_rate(bdc.get("rate_raw"))
        best_by_etf: dict[str, dict[str, Any]] = {}
        for etf in borrower["history"]:
            if date.fromisoformat(etf["report_date"]) < recent_cutoff:
                continue
            distance, maturity_precision = maturity_distance(bdc.get("maturity_date"), etf.get("maturity"))
            if distance is None or distance > 31 or not compatible_tier(bdc, etf):
                continue
            etf_rate = float(etf["annualized_rate"]) if etf.get("annualized_rate") is not None else None
            rate_gap = abs(bdc_rate - etf_rate) if bdc_rate is not None and etf_rate is not None else None
            if rate_gap is not None and rate_gap > 1.50:
                continue
            score = 60 if distance == 0 else 48
            if rate_gap is not None:
                score += 24 if rate_gap <= 0.35 else 16 if rate_gap <= 0.75 else 8
            score += 10
            score -= min(abs((date.fromisoformat(etf["report_date"]) - dataset_as_of).days) // 120, 4)
            candidate = {
                "etf": etf["fund"],
                "report_date": etf["report_date"],
                "loan_title": etf["loan_title"],
                "maturity": etf.get("maturity"),
                "rate": etf_rate,
                "rate_gap_pp": round_or_none(rate_gap),
                "implied_mark": etf["implied_mark"],
                "principal_mm": round(float(etf["principal"]) / 1_000_000, 3),
                "identifier_key": etf.get("match_key"),
                "match_quality": etf.get("match_quality"),
                "source_url": etf.get("sec_source_url"),
                "score": score,
                "maturity_precision": maturity_precision,
            }
            prior = best_by_etf.get(etf["fund"])
            if prior is None or (score, etf["report_date"]) > (prior["score"], prior["report_date"]):
                best_by_etf[etf["fund"]] = candidate

        if best_by_etf:
            raw_matches.append({
                "issuer_match_key": issuer_key,
                "issuer": reference["dashboard_display_name"],
                "bdc_fund": bdc["fund"],
                "bdc_category": bdc.get("investment_category"),
                "bdc_tier": tier_label(bdc),
                "bdc_maturity": bdc.get("maturity_date"),
                "bdc_rate": round_or_none(bdc_rate),
                "bdc_principal_mm": principal,
                "bdc_cost_mm": float(bdc.get("amortized_cost_mm") or 0),
                "bdc_fair_value_mm": float(bdc.get("fair_value_mm") or 0),
                "etf_observations": sorted(best_by_etf.values(), key=lambda row: row["report_date"]),
            })

    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in raw_matches:
        key = (
            row["issuer_match_key"], row["bdc_fund"], row["bdc_category"],
            row["bdc_maturity"], row["bdc_rate"],
        )
        grouped[key].append(row)

    facility_rows = []
    for grouped_rows in grouped.values():
        first = grouped_rows[0]
        principal = sum(row["bdc_principal_mm"] for row in grouped_rows)
        cost = sum(row["bdc_cost_mm"] for row in grouped_rows)
        fair_value = sum(row["bdc_fair_value_mm"] for row in grouped_rows)
        observations_by_etf: dict[str, dict[str, Any]] = {}
        for row in grouped_rows:
            for obs in row["etf_observations"]:
                prior = observations_by_etf.get(obs["etf"])
                if prior is None or (obs["score"], obs["report_date"]) > (prior["score"], prior["report_date"]):
                    observations_by_etf[obs["etf"]] = obs
        observations = sorted(observations_by_etf.values(), key=lambda row: row["etf"])
        marks = [float(row["implied_mark"]) for row in observations]
        inferred = statistics.median(marks)
        tight_rate_matches = sum(row["rate_gap_pp"] is not None and row["rate_gap_pp"] <= 0.35 for row in observations)
        confidence = "high" if tight_rate_matches and all(row["score"] >= 75 for row in observations) else "medium"
        buffer = max(1.0 if len(marks) > 1 else 1.5, (max(marks) - min(marks)) / 2 if len(marks) > 1 else 0)
        bdc_mark_on_principal = fair_value / principal * 100 if principal else None
        facility_rows.append({
            "issuer_match_key": first["issuer_match_key"],
            "issuer": first["issuer"],
            "bdc_fund": first["bdc_fund"],
            "bdc_category": first["bdc_category"],
            "bdc_tier": first["bdc_tier"],
            "bdc_maturity": first["bdc_maturity"],
            "bdc_rate": first["bdc_rate"],
            "bdc_principal_mm": round(principal, 3),
            "bdc_cost_mm": round(cost, 3),
            "bdc_fair_value_mm": round(fair_value, 3),
            "bdc_mark_on_principal": round_or_none(bdc_mark_on_principal),
            "bdc_mark_to_cost": round_or_none(fair_value / cost * 100 if cost else None),
            "etf_implied_mark": round(inferred, 4),
            "etf_implied_low": round(max(0, inferred - buffer), 4),
            "etf_implied_high": round(inferred + buffer, 4),
            "etf_funds": sorted(observations_by_etf),
            "etf_observations": observations,
            "bdc_minus_etf_pp": round_or_none(bdc_mark_on_principal - inferred if bdc_mark_on_principal is not None else None),
            "classification": "probable same facility",
            "confidence": confidence,
            "rounding_warning": principal <= 1.0 or fair_value <= 1.0,
            "evidence": [
                "Borrower match",
                "Same maturity" if all(row["score"] >= 60 for row in observations) else "Near maturity",
                "Compatible capital tier",
                "All-in rate within 35 bp" if tight_rate_matches else "Rate evidence incomplete or time-shifted",
            ],
            "research": research_by_key.get(first["issuer_match_key"]),
        })

    facility_rows.sort(key=lambda row: (
        0 if row["confidence"] == "high" else 1,
        -abs(row["bdc_minus_etf_pp"] or 0),
        row["issuer"],
    ))
    facility_keys = {(row["issuer_match_key"], row["bdc_fund"]) for row in facility_rows}
    directional_rows = [row for key, row in directional.items() if key not in facility_keys]
    directional_rows.sort(key=lambda row: (row["reference_mark"], row["issuer"], row["bdc_fund"]))
    payload = {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "as_of_date": nport["meta"]["latest_report_date"],
            "facility_match_count": len(facility_rows),
            "facility_issuer_count": len({row["issuer_match_key"] for row in facility_rows}),
            "high_confidence_count": sum(row["confidence"] == "high" for row in facility_rows),
            "directional_borrower_fund_count": len(directional_rows),
            "methodology": "ETF-implied marks use the median of the most recent matching FTSL, BKLN, and SRLN facility observations. A facility match requires the same borrower, maturity within 31 days, compatible tier, and—when both are available—an all-in rate within 150 bp. The range is a confidence band, not a bid/ask spread.",
            "critical_limitation": "BDC schedules generally omit CUSIPs. Even high-confidence rows remain probable rather than legally confirmed instrument matches. Small BDC positions can be materially distorted by schedule rounding.",
        },
        "facility_matches": facility_rows,
        "directional_matches": directional_rows,
        "company_research": research["rows"],
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Facility rows: {len(facility_rows)} across {payload['meta']['facility_issuer_count']} issuers")
    print(f"High confidence: {payload['meta']['high_confidence_count']}")
    print(f"Directional borrower/fund rows: {len(directional_rows)}")


if __name__ == "__main__":
    main()
