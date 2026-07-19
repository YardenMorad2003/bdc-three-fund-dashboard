from __future__ import annotations

import json
import math
import re
import statistics
from collections import Counter, defaultdict
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
OUTPUT_PATH = PROJECT_ROOT / "lib" / "business-peer-pricing.json"


PEER_PATTERNS: dict[str, tuple[str, ...]] = {
    "Enterprise software & SaaS": (
        "MCAFEE", "GOTO GROUP", "IVANTI", "QUEST SOFTWARE", "PERFORCE", "CORNERSTONE ONDEMAND",
        "FLASH CHARM", "IDERA", "PLANVIEW", "KASEYA", "SOLARWINDS", "SOLERA", "APTTUS", "CONGA",
        "KNOWBE4", "CLOUDERA", "CLOUD SOFTWARE", "GENESYS CLOUD", "CONNECTWISE", "FINASTRA", "DAYFORCE",
        "ULTIMATE SOFTWARE", "REALPAGE", "ROCKET SOFTWARE", "INSTRUCTURE", "UKG INC", "CVENT", "PROOFPOINT",
        "FLEXERA", "SYNCSORT", "NEWFOLD DIGITAL", "ENDURE DIGITAL", "VISION SOLUTIONS", "MICRO HOLDING",
        "VERIFONE", "DCERT BUYER", "DIGICERT", "XPLOR", "PROJECT LEOPARD", "BOXER PARENT",
    ),
    "Healthcare technology & services": (
        "ATHENAHEALTH", "COTIVITI", "VERSCEND", "R1 RCM", "ENSEMBLE HEALTH", "SYNEOS", "AGILITI",
        "RADIOLOGY PARTNERS", "SOUTHERN VETERINARY", "MIDWEST PHYSICIAN", "GAINWELL", "R1 RCM",
        "PADAGIS", "AHP HEALTH", "HEARTLAND DENTAL", "PAREXEL", "HOLOGIC", "HOPPER MERGER",
    ),
    "Insurance & wealth services": (
        "TRUCORDIA", "HYPERION INSURANCE", "HOWDEN GROUP", "CFC BIDCO", "FOCUS FINANCIAL", "ADVISOR GROUP",
        "OSAIC", "APEX GROUP TREASURY", "EDELMAN FINANCIAL", "ONEDIGITAL", "TRUIST INSURANCE", "ACRISURE",
        "BALDWIN INSURANCE", "ARDONAGH", "GENUINE FINANCIAL", "CLOVER HOLDINGS", "ALERA GROUP",
    ),
    "Media, telecom & information": (
        "CSC HOLDINGS", "NUMERICABLE", "RADIATE HOLDCO", "NIELSEN", "NEPTUNE BIDCO", "DISCOVERY",
        "COGECO", "GRAY TELEVISION", "NEXSTAR", "CHARTER COMMUNICATIONS", "LEVEL 3 FINANCING",
        "MITCHELL INTERNATIONAL", "MH SUB I", "IRIDIUM SATELLITE", "SINCLAIR TELEVISION",
    ),
    "Consumer, retail & leisure": (
        "STAPLES", "MICHAELS", "WHATABRANDS", "RAISING CANE", "BALLY", "JETBLUE", "TRIPADVISOR",
        "SHEARER", "FIESTA PURCHASER", "BOOTS GROUP", "PRIMO BRANDS", "CELSIUS HOLDINGS", "MAVIS TIRE",
        "POLARIS NEWCO", "VIKING OCEAN", "SURF HOLDINGS", "TEMPO ACQUISITION",
    ),
    "Industrial, building & distribution": (
        "FIRST BRANDS", "LABL", "CORNERSTONE BUILDING", "ACPRODUCTS", "LBM ACQUISITION", "WHITE CAP",
        "PROAMPAC", "BERLIN PACKAGING", "AMERICAN BATH", "QXO BUILDING", "QUIKRETE", "SMYRNA READY MIX",
        "TAMKO", "MI WINDOWS", "FILTRATION GROUP", "CLARIOS", "ACTION ENVIRONMENTAL", "BELRON",
        "HIGHLINE AFTERMARKET", "CHARTER NEXT GENERATION", "Glatfelter".upper(), "MORTON", "SCI H SALT",
    ),
    "Aerospace, defense & government services": (
        "PERATON", "AMENTUM", "TRANSDIGM", "GARDA WORLD", "JANE STREET", "ALLIED UNIVERSAL",
    ),
    "Professional & outsourced services": (
        "CAST AND CREW", "CONSILIO", "GRANT THORNTON", "ANKURA", "Clydesdale".upper(), "VESTIS",
        "SKOPIMA", "EAB GLOBAL", "CREATIVE PLANNING", "SEDGWICK", "PYE BARKER", "CENTURI GROUP",
    ),
    "Energy & infrastructure services": (
        "AGGREKO", "ALPHA GENERATION", "QTS THUNDER", "OLYMPUS WATER", "IRB HOLDING",
    ),
}


def normalized(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).strip()


def is_senior_debt(row: dict[str, Any]) -> bool:
    text = " ".join(str(row.get(field) or "") for field in (
        "investment_category", "instrument_type", "investment_description"
    )).lower()
    if row.get("is_unfunded_commitment") or any(term in text for term in (
        "equity", "stock", "warrant", "llc interest", "partnership interest", "second lien", "subordinated", "mezzanine"
    )):
        return False
    return any(term in text for term in ("first lien", "senior secured", "loan", "term loan", "senior debt"))


def parse_maturity(value: str | None) -> date | None:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%Y", "%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def classify_peer(name: str) -> str | None:
    value = normalized(name)
    for model, patterns in PEER_PATTERNS.items():
        if any(pattern in value for pattern in patterns):
            return model
    return None


def classify_target(rows: list[dict[str, Any]]) -> tuple[str | None, str]:
    issuer = normalized(rows[0].get("issuer_name") or rows[0].get("issuer_match_key") or "")
    if any(term in issuer for term in ("PERATON", "AMENTUM", "CUBIC", "WEST STAR AVIATION", "SUNVAIR AEROSPACE")):
        return "Aerospace, defense & government services", "name override"
    if any(term in issuer for term in ("CUSTOMINK", "SPECIALTY RETAIL")):
        return "Consumer, retail & leisure", "name override"
    # Expanded EdgarTools schedules do not always expose an industry concept.
    # Reuse exact curated company-pattern matches before falling back to the
    # reported industry so those funds can still contribute auditable peers.
    name_model = classify_peer(issuer)
    if name_model:
        return name_model, "curated company match"
    industry = " ".join(str(row.get("industry") or "") for row in rows).lower()
    if any(term in industry for term in ("software", "technology", "it services", "internet")):
        return "Enterprise software & SaaS", "reported industry"
    if any(term in industry for term in ("health care", "healthcare", "pharmaceutical", "biotechnology", "life sciences")):
        return "Healthcare technology & services", "reported industry"
    if any(term in industry for term in ("insurance", "financial", "capital markets", "bank", "diversified finance")):
        return "Insurance & wealth services", "reported industry"
    if any(term in industry for term in ("media", "telecommunication", "broadcast", "cable")):
        return "Media, telecom & information", "reported industry"
    if any(term in industry for term in ("retail", "consumer", "food", "restaurant", "leisure", "hotel")):
        return "Consumer, retail & leisure", "reported industry"
    if any(term in industry for term in ("aerospace", "defense")):
        return "Aerospace, defense & government services", "reported industry"
    if any(term in industry for term in ("energy", "utility", "power", "renewable")):
        return "Energy & infrastructure services", "reported industry"
    if any(term in industry for term in ("professional services", "commercial services", "business services")):
        return "Professional & outsourced services", "reported industry"
    if any(term in industry for term in ("capital goods", "materials", "manufacturing", "construction", "distribution")):
        return "Industrial, building & distribution", "broad reported industry"
    return None, "unclassified"


def weighted_quantile(values: list[float], weights: list[float], quantile: float) -> float:
    ordered = sorted(zip(values, weights), key=lambda pair: pair[0])
    total = sum(weight for _, weight in ordered)
    threshold = total * quantile
    running = 0.0
    for value, weight in ordered:
        running += weight
        if running >= threshold:
            return value
    return ordered[-1][0]


def main() -> None:
    nport = json.loads(NPORT_PATH.read_text(encoding="utf-8"))
    dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
    references = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    research = json.loads(RESEARCH_PATH.read_text(encoding="utf-8"))
    dataset_as_of = date.fromisoformat(nport["meta"]["latest_report_date"])
    current_cutoff = dataset_as_of - timedelta(days=460)
    nport_name_by_dashboard_key = {
        row["issuer_match_key"]: normalized(row["nport_borrower"]) for row in references["matches"]
    }
    research_rows = research["rows"]

    peers_by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for borrower in nport["borrowers"]:
        model = classify_peer(borrower["display_borrower"])
        if not model or not borrower.get("latest_mark"):
            continue
        latest_date = date.fromisoformat(borrower["latest_date"])
        if latest_date < current_cutoff:
            continue
        latest_rows = [row for row in borrower["history"] if row["report_date"] == borrower["latest_date"]]
        maturities = [parse_maturity(row.get("maturity")) for row in latest_rows]
        maturity_ordinals = sorted(item.toordinal() for item in maturities if item)
        median_maturity = date.fromordinal(round(statistics.median(maturity_ordinals))) if maturity_ordinals else None
        principal_mm = sum(float(row.get("principal") or 0) for row in latest_rows) / 1_000_000
        peers_by_model[model].append({
            "normalized_borrower": borrower["normalized_borrower"],
            "borrower": borrower["display_borrower"],
            "business_model": model,
            "latest_mark": borrower["latest_mark"],
            "latest_date": borrower["latest_date"],
            "latest_funds": borrower["latest_funds"],
            "maturity": median_maturity.isoformat() if median_maturity else None,
            "principal_mm": round(principal_mm, 3),
            "source_url": latest_rows[0]["sec_source_url"] if latest_rows else None,
        })

    grouped_targets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in dashboard["holdings_detail_latest"]:
        if is_senior_debt(row) and float(row.get("principal_mm") or 0) > 0:
            grouped_targets[(row["issuer_match_key"], row["fund"])].append(row)

    # Carry a classification across funds when the normalized issuer is the
    # same and one filing supplies an industry while another does not.
    issuer_model_candidates: dict[str, set[str]] = defaultdict(set)
    for (issuer_key, _fund), rows in grouped_targets.items():
        model, _basis = classify_target(rows)
        if model:
            issuer_model_candidates[issuer_key].add(model)
    cross_fund_models = {
        issuer_key: next(iter(models))
        for issuer_key, models in issuer_model_candidates.items()
        if len(models) == 1
    }

    estimates = []
    for (issuer_key, fund), rows in grouped_targets.items():
        total_principal = sum(float(row.get("principal_mm") or 0) for row in rows)
        if total_principal < 5:
            continue
        fair_value = sum(float(row.get("fair_value_mm") or 0) for row in rows)
        cost = sum(float(row.get("amortized_cost_mm") or 0) for row in rows)
        if fair_value <= 0:
            continue
        bdc_mark_on_principal = fair_value / total_principal * 100
        # Values materially above par usually reflect a currency/unit mismatch or a
        # principal field that is not a clean remaining-par balance. They are useful
        # in the source schedule but not as a comparable loan-price anchor.
        if bdc_mark_on_principal > 115:
            continue
        business_model, taxonomy_basis = classify_target(rows)
        if not business_model and issuer_key in cross_fund_models:
            business_model = cross_fund_models[issuer_key]
            taxonomy_basis = "cross-fund issuer classification"
        if not business_model:
            continue
        maturities = [parse_maturity(row.get("maturity_date")) for row in rows]
        maturity_ordinals = sorted(item.toordinal() for item in maturities if item)
        target_maturity = date.fromordinal(round(statistics.median(maturity_ordinals))) if maturity_ordinals else None
        excluded_borrower = nport_name_by_dashboard_key.get(issuer_key)
        candidate_rows = []
        for peer in peers_by_model.get(business_model, []):
            if excluded_borrower and normalized(peer["borrower"]) == excluded_borrower:
                continue
            peer_date = date.fromisoformat(peer["latest_date"])
            freshness_days = (dataset_as_of - peer_date).days
            peer_maturity = date.fromisoformat(peer["maturity"]) if peer["maturity"] else None
            maturity_gap_years = abs((target_maturity - peer_maturity).days) / 365.25 if target_maturity and peer_maturity else None
            maturity_score = 20 if maturity_gap_years is not None and maturity_gap_years <= 1 else 14 if maturity_gap_years is not None and maturity_gap_years <= 2 else 7 if maturity_gap_years is not None and maturity_gap_years <= 3 else 2
            freshness_score = 10 if freshness_days <= 120 else 7 if freshness_days <= 270 else 4
            similarity = 65 + maturity_score + freshness_score
            weight = (0.65 + maturity_score / 20) * (1 if freshness_days <= 120 else .85 if freshness_days <= 270 else .7)
            candidate_rows.append({
                **peer,
                "maturity_gap_years": round(maturity_gap_years, 2) if maturity_gap_years is not None else None,
                "similarity_score": similarity,
                "weight": weight,
            })
        # Use ETF position size only as a neutral tie-breaker. Sorting tied peers by
        # their marks would systematically bias the inferred value up or down.
        selected = sorted(
            candidate_rows,
            key=lambda row: (-row["similarity_score"], -row["principal_mm"], row["borrower"]),
        )[:8]
        if len(selected) < 3:
            continue
        values = [float(row["latest_mark"]) for row in selected]
        weights = [float(row["weight"]) for row in selected]
        implied = weighted_quantile(values, weights, .5)
        lower = weighted_quantile(values, weights, .25)
        upper = weighted_quantile(values, weights, .75)
        if upper - lower < 5:
            midpoint = (upper + lower) / 2
            lower, upper = midpoint - 2.5, midpoint + 2.5
        research_match = next((item for item in research_rows if item["issuer_match_key"] in issuer_key or issuer_key in item["issuer_match_key"]), None)
        broad_taxonomy = taxonomy_basis == "broad reported industry"
        confidence = "medium" if len(selected) >= 6 and not broad_taxonomy and (upper - lower) <= 18 else "low"
        estimates.append({
            "issuer_match_key": issuer_key,
            "issuer": rows[0]["issuer_name"],
            "bdc_fund": fund,
            "business_model": business_model,
            "taxonomy_basis": taxonomy_basis,
            "reported_industry": Counter(str(row.get("industry") or "Unspecified") for row in rows).most_common(1)[0][0],
            "bdc_principal_mm": round(total_principal, 3),
            "bdc_fair_value_mm": round(fair_value, 3),
            "bdc_cost_mm": round(cost, 3),
            "bdc_mark_on_principal": round(bdc_mark_on_principal, 4),
            "bdc_mark_to_cost": round(fair_value / cost * 100, 4) if cost else None,
            "target_maturity": target_maturity.isoformat() if target_maturity else None,
            "peer_implied_mark": round(implied, 4),
            "peer_low": round(max(0, lower), 4),
            "peer_high": round(min(125, upper), 4),
            "bdc_minus_peer_pp": round(bdc_mark_on_principal - implied, 4),
            "peer_count": len(selected),
            "confidence": confidence,
            "research_signal": research_match["signal"] if research_match else "unresearched",
            "research_headline": research_match["headline"] if research_match else None,
            "peer_keys": [peer["normalized_borrower"] for peer in selected],
        })

    estimates.sort(key=lambda row: (-abs(row["bdc_minus_peer_pp"]), -row["bdc_fair_value_mm"], row["issuer"]))
    model_summary = []
    for model, peers in sorted(peers_by_model.items()):
        marks = [float(row["latest_mark"]) for row in peers]
        model_summary.append({
            "business_model": model,
            "peer_company_count": len(peers),
            "median_mark": round(statistics.median(marks), 4),
            "minimum_mark": round(min(marks), 4),
            "maximum_mark": round(max(marks), 4),
            "below_90_count": sum(mark < 90 for mark in marks),
        })
    payload = {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "as_of_date": nport["meta"]["latest_report_date"],
            "estimate_count": len(estimates),
            "covered_issuer_count": len({row["issuer_match_key"] for row in estimates}),
            "business_model_count": len(model_summary),
            "methodology": "For each material BDC senior-debt borrower with at least $5 million of reported principal and a usable par-based mark, the model selects up to eight distinct ETF borrowers in the same curated business-model group. It favors closer maturities and fresher N-PORT observations, excludes the same borrower, and reports the weighted peer median with a weighted interquartile range widened to at least five points.",
            "included_factors": [
                "Curated operating-model taxonomy",
                "Senior-debt-only BDC targets",
                "Maturity proximity",
                "N-PORT valuation freshness",
                "Distinct-borrower peer selection",
            ],
            "displayed_not_scored": [
                "Public credit and media research signals where available",
            ],
            "not_yet_standardized": [
                "Revenue, EBITDA, and enterprise value",
                "Leverage and interest coverage",
                "Covenant and collateral quality",
                "Sponsor reputation and support",
                "Geography and customer concentration",
            ],
            "caveats": [
                "A business-model peer is not a capital-structure comparable. Leverage, covenants, collateral, liquidity, sponsor support, size, geography, and customer concentration can dominate sector similarity.",
                "N-PORT marks are periodic fund valuations, not executable dealer bids. BDC schedule values may be rounded and use different valuation dates.",
                "BDC rows with missing fair value or a mark above 115 are omitted because the reported principal is unlikely to be a comparable remaining-par balance.",
                "The taxonomy is curated from public company descriptions and reported BDC industries. Opaque acquisition vehicles and broad industry labels lower confidence.",
                "Research signals are displayed as overlays and do not mechanically shift the peer estimate.",
            ],
        },
        "business_models": model_summary,
        "peer_universe": sorted(
            [peer for peers in peers_by_model.values() for peer in peers],
            key=lambda row: (row["business_model"], row["borrower"]),
        ),
        "estimates": estimates,
        "sources": [
            {"name": "SEC Form N-PORT data sets", "url": "https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets"},
            {"name": "FTSL official holdings and industry exposure", "url": "https://www.ftportfolios.com/retail/etf/etfsummary.aspx?Ticker=FTSL"},
            {"name": "BKLN official fund and holdings page", "url": "https://www.invesco.com/us/en/financial-products/etfs/invesco-senior-loan-etf.html"},
            {"name": "SRLN official holdings and sector allocation", "url": "https://www.ssga.com/us/en/intermediary/etfs/state-street-blackstone-senior-loan-etf-srln"},
        ],
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Peer estimates: {len(estimates)}")
    print(f"Covered issuers: {payload['meta']['covered_issuer_count']}")
    print(f"Business models: {len(model_summary)}")


if __name__ == "__main__":
    main()
