from __future__ import annotations

import csv
import json
import math
import re
import statistics
import unicodedata
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.request import Request, urlopen

from free_sources import DEFAULT_USER_AGENT, newest_zip_links, number


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = PROJECT_ROOT / ".cache" / "nport-consensus"
DASHBOARD_PATH = PROJECT_ROOT / "lib" / "dashboard-data.json"
ENRICHMENT_PATH = PROJECT_ROOT / "lib" / "company-enrichment.json"
REFERENCE_PATH = PROJECT_ROOT / "lib" / "bsl-reference-marks.json"
OUTPUT_PATH = PROJECT_ROOT / "lib" / "nport-consensus-marks.json"
NPORT_PAGE = "https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets"
LEGAL_SUFFIXES = {
    "INC", "INCORPORATED", "LLC", "LTD", "LIMITED", "LP", "CORP", "CORPORATION",
    "CO", "COMPANY", "HOLDING", "HOLDINGS", "GROUP", "PLC", "SA", "AG",
}
csv.field_size_limit(2_147_483_647)


def normalize(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Z0-9]+", " ", ascii_text.upper().replace("&", " AND "))
    tokens = text.split()
    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def iso_date(value: str) -> str:
    value = (value or "").strip()
    for pattern in ("%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    return value


def member_name(archive: zipfile.ZipFile, wanted: str) -> str:
    for name in archive.namelist():
        if Path(name).name.upper() == wanted.upper():
            return name
    raise FileNotFoundError(f"{wanted} is missing from the N-PORT archive")


def rows(archive: zipfile.ZipFile, wanted: str) -> Iterator[dict[str, str]]:
    with archive.open(member_name(archive, wanted)) as binary:
        import io

        with io.TextIOWrapper(binary, encoding="utf-8-sig", errors="replace", newline="") as text:
            for row in csv.DictReader(text, delimiter="\t"):
                yield {str(key or "").strip(): str(value or "").strip() for key, value in row.items()}


def download_archive(url: str) -> Path:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    filename = Path(url.split("?", 1)[0]).name or "nport.zip"
    target = CACHE_ROOT / filename
    if target.exists() and zipfile.is_zipfile(target):
        return target
    partial = target.with_suffix(target.suffix + ".part")
    request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT, "Accept-Encoding": "identity"})
    with urlopen(request, timeout=180) as response, partial.open("wb") as output:
        while chunk := response.read(4 * 1024 * 1024):
            output.write(chunk)
    if not zipfile.is_zipfile(partial):
        raise ValueError("SEC N-PORT download did not produce a valid ZIP archive")
    partial.replace(target)
    return target


def find_archive() -> tuple[Path, str]:
    cached = sorted(CACHE_ROOT.glob("*_nport.zip"), reverse=True)
    if cached:
        path = cached[0]
        return path, f"https://www.sec.gov/files/dera/data/form-n-port-data-sets/{path.name}"
    links, _ = newest_zip_links(NPORT_PAGE, limit=1)
    if not links:
        raise RuntimeError("No SEC N-PORT ZIP link was found")
    return download_archive(links[0]["url"]), links[0]["url"]


def alias_index(dashboard: dict[str, Any], enrichment: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, str], int]:
    names: dict[str, set[str]] = defaultdict(set)
    display: dict[str, str] = {}

    def add(key: str | None, value: str | None) -> None:
        if not key or not value:
            return
        normalized = normalize(value)
        if len(normalized) >= 4:
            names[normalized].add(key)

    for item in dashboard.get("cross_fund_issuer_latest", []):
        key = item.get("issuer_match_key")
        display[key] = item.get("representative_issuer_name") or key
        add(key, key)
        add(key, item.get("representative_issuer_name"))
        for value in item.get("issuer_name_variants", []):
            add(key, value)
    for item in dashboard.get("loan_timeline_issuers", []):
        key = item.get("issuer_match_key")
        display[key] = item.get("display_name") or display.get(key, key)
        add(key, item.get("display_name"))
    for item in enrichment:
        key = item.get("issuer_match_key")
        add(key, item.get("display_name"))
        add(key, item.get("mapped_company"))
    if REFERENCE_PATH.exists():
        reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
        for item in reference.get("matches", []):
            add(item.get("issuer_match_key"), item.get("nport_borrower"))

    unambiguous = {alias: next(iter(keys)) for alias, keys in names.items() if len(keys) == 1}
    return unambiguous, display, sum(len(keys) > 1 for keys in names.values())


def bdc_marks(dashboard: dict[str, Any]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in dashboard.get("holdings_detail_latest", []):
        key = row.get("issuer_match_key")
        cost = number(row.get("amortized_cost_mm")) or 0
        if key and cost > 0 and not row.get("is_unfunded_commitment"):
            text = " ".join(str(row.get(field) or "") for field in ("investment_category", "instrument_type", "investment_description")).lower()
            equity_terms = ("equity", "stock", "llc interest", "warrant", "partnership interest")
            debt_terms = ("loan", "debt", "lien", "revolver", "note", "secured", "term")
            if not any(word in text for word in equity_terms) and any(word in text for word in debt_terms):
                grouped[key].append(row)
    output: dict[str, dict[str, Any]] = {}
    for key, items in grouped.items():
        cost = sum(number(row.get("amortized_cost_mm")) or 0 for row in items)
        fair_value = sum(number(row.get("fair_value_mm")) or 0 for row in items)
        output[key] = {
            "mark_to_cost": round(fair_value / cost * 100, 4) if cost else None,
            "cost_mm": round(cost, 3),
            "fair_value_mm": round(fair_value, 3),
            "funds": sorted({row.get("fund") for row in items if row.get("fund")}),
        }
    return output


def sec_filing_url(cik: str, accession: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession.replace('-', '')}/"


def summarize_snapshot(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_fund: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_fund[item["series_key"]].append(item)
    fund_marks = []
    observations = []
    for series_key, fund_items in sorted(by_fund.items()):
        balance = sum(item["balance"] for item in fund_items)
        value = sum(item["currency_value"] for item in fund_items)
        mark = value / balance * 100
        first = fund_items[0]
        identifiers = sorted({identifier for item in fund_items for identifier in item.get("identifiers", []) if identifier})
        maturities = sorted({item.get("maturity_date") for item in fund_items if item.get("maturity_date")})
        observations.append({
            "fund": first["series_name"],
            "registrant": first["registrant_name"],
            "report_date": first["report_date"],
            "filing_date": first["filing_date"],
            "accession_number": first["accession_number"],
            "source_url": first["source_url"],
            "mark": round(mark, 4),
            "balance_mm": round(balance / 1_000_000, 3),
            "fair_value_mm": round(value / 1_000_000, 3),
            "holding_count": len(fund_items),
            "identifiers": identifiers[:12],
            "maturities": maturities,
            "annualized_rates": sorted({item.get("annualized_rate") for item in fund_items if item.get("annualized_rate") is not None}),
            "has_default_flag": any(item.get("is_default") == "Y" for item in fund_items),
            "issuer_names": sorted({item["issuer_name"] for item in fund_items}),
            "issuer_titles": sorted({item["issuer_title"] for item in fund_items if item["issuer_title"]})[:12],
        })
        fund_marks.append(mark)
    total_balance = sum(item["balance"] for item in items)
    total_value = sum(item["currency_value"] for item in items)
    return {
        "report_date": items[0]["report_date"],
        "fund_count": len(fund_marks),
        "holding_count": len(items),
        "consensus_status": "independent_consensus" if len(fund_marks) >= 2 else "single_fund_observation",
        "median_fund_mark": round(statistics.median(fund_marks), 4),
        "mean_fund_mark": round(statistics.mean(fund_marks), 4),
        "balance_weighted_mark": round(total_value / total_balance * 100, 4),
        "low_fund_mark": round(min(fund_marks), 4),
        "high_fund_mark": round(max(fund_marks), 4),
        "range_pp": round(max(fund_marks) - min(fund_marks), 4),
        "stddev_pp": round(statistics.pstdev(fund_marks), 4) if len(fund_marks) > 1 else None,
        "balance_mm": round(total_balance / 1_000_000, 3),
        "fair_value_mm": round(total_value / 1_000_000, 3),
        "observations": observations,
    }


def main() -> None:
    archive_path, archive_url = find_archive()
    dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
    enrichment = json.loads(ENRICHMENT_PATH.read_text(encoding="utf-8")) if ENRICHMENT_PATH.exists() else []
    aliases, display, ambiguous_alias_count = alias_index(dashboard, enrichment)
    current_bdc = bdc_marks(dashboard)

    with zipfile.ZipFile(archive_path) as archive:
        submissions = {}
        for row in rows(archive, "SUBMISSION.tsv"):
            row["REPORT_DATE"] = iso_date(row.get("REPORT_DATE", ""))
            row["REPORT_ENDING_PERIOD"] = iso_date(row.get("REPORT_ENDING_PERIOD", ""))
            row["FILING_DATE"] = iso_date(row.get("FILING_DATE", ""))
            submissions[row["ACCESSION_NUMBER"]] = row
        registrants = {row["ACCESSION_NUMBER"]: row for row in rows(archive, "REGISTRANT.tsv")}
        fund_info = list(rows(archive, "FUND_REPORTED_INFO.tsv"))

        # Amendments and duplicate submissions can describe the same series/report date. Keep the latest filing.
        selected: dict[tuple[str, str], dict[str, str]] = {}
        for row in fund_info:
            accession = row["ACCESSION_NUMBER"]
            submission = submissions.get(accession, {})
            key = (row.get("SERIES_ID") or row.get("SERIES_NAME") or accession, submission.get("REPORT_DATE", ""))
            candidate = {**row, **submission}
            current = selected.get(key)
            if current is None or (candidate.get("FILING_DATE", ""), accession) > (current.get("FILING_DATE", ""), current.get("ACCESSION_NUMBER", "")):
                selected[key] = candidate
        selected_accessions = {row["ACCESSION_NUMBER"]: row for row in selected.values()}

        matched: list[dict[str, Any]] = []
        scanned = 0
        eligible = 0
        for row in rows(archive, "FUND_REPORTED_HOLDING.tsv"):
            scanned += 1
            accession = row.get("ACCESSION_NUMBER", "")
            fund = selected_accessions.get(accession)
            if not fund or row.get("ASSET_CAT") != "DBT" or row.get("CURRENCY_CODE") != "USD" or row.get("UNIT") != "PA":
                continue
            balance = number(row.get("BALANCE"))
            value = number(row.get("CURRENCY_VALUE"))
            if not balance or balance <= 0 or value is None or value <= 0:
                continue
            mark = value / balance * 100
            if not math.isfinite(mark) or not 0 < mark < 250:
                continue
            eligible += 1
            issuer_name = row.get("ISSUER_NAME", "")
            alias = normalize(issuer_name)
            issuer_key = aliases.get(alias)
            if not issuer_key:
                continue
            submission = submissions[accession]
            registrant = registrants.get(accession, {})
            matched.append({
                "issuer_match_key": issuer_key,
                "matched_alias": alias,
                "issuer_name": issuer_name,
                "issuer_title": row.get("ISSUER_TITLE", ""),
                "holding_id": row.get("HOLDING_ID", ""),
                "accession_number": accession,
                "series_key": fund.get("SERIES_ID") or fund.get("SERIES_NAME") or accession,
                "series_name": fund.get("SERIES_NAME") or registrant.get("REGISTRANT_NAME") or accession,
                "registrant_name": registrant.get("REGISTRANT_NAME", ""),
                "report_date": submission.get("REPORT_DATE", ""),
                "filing_date": submission.get("FILING_DATE", ""),
                "balance": balance,
                "currency_value": value,
                "source_url": sec_filing_url(registrant.get("CIK", ""), accession),
            })

        holding_ids = {item["holding_id"] for item in matched if item["holding_id"]}
        identifiers: dict[str, set[str]] = defaultdict(set)
        for row in rows(archive, "IDENTIFIERS.tsv"):
            holding_id = row.get("HOLDING_ID", "")
            if holding_id in holding_ids:
                for field, prefix in (("IDENTIFIER_ISIN", "ISIN"), ("IDENTIFIER_TICKER", "Ticker"), ("OTHER_IDENTIFIER", "Other")):
                    if row.get(field):
                        identifiers[holding_id].add(f"{prefix}: {row[field]}")
        debt: dict[str, dict[str, Any]] = {}
        for row in rows(archive, "DEBT_SECURITY.tsv"):
            holding_id = row.get("HOLDING_ID", "")
            if holding_id in holding_ids:
                debt[holding_id] = {
                    "maturity_date": row.get("MATURITY_DATE") or None,
                    "annualized_rate": number(row.get("ANNUALIZED_RATE")),
                    "is_default": row.get("IS_DEFAULT") or None,
                }
        for item in matched:
            item["identifiers"] = sorted(identifiers.get(item["holding_id"], set()))
            item.update(debt.get(item["holding_id"], {}))

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in matched:
        grouped[(item["issuer_match_key"], item["report_date"])].append(item)
    snapshots_by_issuer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (issuer_key, _), items in grouped.items():
        snapshots_by_issuer[issuer_key].append(summarize_snapshot(items))

    issuer_rows = []
    for issuer_key, history in snapshots_by_issuer.items():
        history.sort(key=lambda item: item["report_date"])
        consensus = [item for item in history if item["fund_count"] >= 2]
        latest = history[-1]
        latest_consensus = consensus[-1] if consensus else None
        bdc = current_bdc.get(issuer_key)
        comparison = latest_consensus or latest
        issuer_rows.append({
            "issuer_match_key": issuer_key,
            "dashboard_display_name": display.get(issuer_key, issuer_key.title()),
            "match_method": "exact_normalized_name",
            "latest_observation": latest,
            "latest_independent_consensus": latest_consensus,
            "consensus_observation_count": len(consensus),
            "bdc_latest": bdc,
            "bdc_minus_nport_pp": round(bdc["mark_to_cost"] - comparison["median_fund_mark"], 4) if bdc and bdc.get("mark_to_cost") is not None else None,
            "history": history[-8:],
        })
    issuer_rows.sort(key=lambda item: (
        (item["latest_independent_consensus"] or item["latest_observation"])["median_fund_mark"],
        item["issuer_match_key"],
    ))

    report_dates = sorted({item["report_date"] for item in matched if item["report_date"]})
    payload = {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "archive_file": archive_path.name,
            "archive_url": archive_url,
            "archive_bytes": archive_path.stat().st_size,
            "report_date_min": report_dates[0] if report_dates else None,
            "report_date_max": report_dates[-1] if report_dates else None,
            "holding_rows_scanned": scanned,
            "eligible_usd_debt_rows": eligible,
            "matched_holding_rows": len(matched),
            "matched_issuer_count": len(issuer_rows),
            "independent_consensus_issuer_count": sum(item["latest_independent_consensus"] is not None for item in issuer_rows),
            "rejected_ambiguous_alias_count": ambiguous_alias_count,
            "methodology": "Exact normalized borrower-name matches only. USD debt positions reported in principal-amount units use currency value divided by balance. Each fund is first aggregated to one borrower mark; consensus statistics then weight each independent fund equally. A consensus requires at least two funds on the same report date.",
            "promotion_rule": "Review-only evidence. Do not feed valuation scores until match coverage, amendment handling, and mark stability are audited over multiple quarters.",
        },
        "issuers": issuer_rows,
        "sources": [
            {"name": "SEC Form N-PORT Data Sets", "url": NPORT_PAGE, "role": "Official quarterly bulk filing data"},
            {"name": archive_path.name, "url": archive_url, "role": "Parsed archive"},
        ],
        "limitations": [
            "Borrower-level name matches do not prove that N-PORT and BDC holdings are the same facility, lien, or tranche.",
            "N-PORT values are fund-reported fair values, not executable dealer bids, and filing publication lags the report date.",
            "Single-fund observations are retained but are not labeled consensus; very small positions can still be valuation outliers.",
        ],
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Scanned {scanned:,} holdings; matched {len(matched):,} rows across {len(issuer_rows):,} dashboard issuers")
    print(f"Issuers with independent consensus: {payload['meta']['independent_consensus_issuer_count']:,}")


if __name__ == "__main__":
    main()
