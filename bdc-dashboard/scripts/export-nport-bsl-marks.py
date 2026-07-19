from __future__ import annotations

import csv
import json
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
THREAD_ID = "019f777f-0927-7cf0-96b3-6b2d730356c7"
OUTPUT_ROOT = WORKSPACE_ROOT / "outputs" / THREAD_ID / "nport-bsl"
CACHE_ROOT = PROJECT_ROOT / ".cache" / "nport-bsl"
USER_AGENT = "BDC Tracker N-PORT research yarde@example.com"

FUNDS: dict[str, dict[str, str]] = {
    "FTSL": {"cik": "1517936", "series_id": "S000034146", "class_id": "C000105232", "months": "Jan / Apr / Jul / Oct"},
    "BKLN": {"cik": "1378872", "series_id": "S000031053", "class_id": "C000096299", "months": "Feb / May / Aug / Nov"},
    "SRLN": {"cik": "1516212", "series_id": "S000033064", "class_id": "C000101921", "months": "Mar / Jun / Sep / Dec"},
}

FILING_FIELDS = [
    "fund", "series_id", "class_id", "report_date", "filing_date", "accession", "filing_type",
    "total_assets", "net_assets", "total_position_count", "reported_loan_count", "loaded_loan_rows",
    "total_reported_principal", "total_loan_fair_value", "weighted_implied_mark", "loan_fv_pct_total_assets",
    "filing_index_url", "primary_doc_url", "status", "error",
]

HOLDING_FIELDS = [
    "fund", "report_date", "borrower", "loan_title", "cusip", "isin", "match_key", "principal", "units",
    "currency", "fair_value_usd", "implied_mark", "pct_fund_value", "maturity", "coupon_kind",
    "annualized_rate", "fair_value_level", "country", "is_default", "interest_in_arrears", "is_pik",
    "match_quality", "filing_date", "accession", "sec_source_url",
]


def request_bytes(url: str, attempts: int = 3) -> bytes:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
            with urlopen(request, timeout=60) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.2 * (attempt + 1))
    assert last_error is not None
    raise last_error


def cached_bytes(url: str, path: Path) -> bytes:
    if path.exists():
        return path.read_bytes()
    data = request_bytes(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    time.sleep(0.12)
    return data


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def first_child_text(element: ET.Element | None, name: str) -> str:
    if element is None:
        return ""
    for child in element.iter():
        if local_name(child.tag) == name:
            return (child.text or "").strip()
    return ""


def first_descendant(element: ET.Element | None, name: str) -> ET.Element | None:
    if element is None:
        return None
    return next((child for child in element.iter() if local_name(child.tag) == name), None)


def descendants(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element.iter() if local_name(child.tag) == name]


def safe_decimal(raw: str) -> Decimal | None:
    if raw == "":
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def decimal_text(value: Decimal | None) -> str:
    return "" if value is None else format(value, "f")


def valid_cusip(value: str) -> bool:
    normalized = value.strip().upper()
    return bool(re.fullmatch(r"[0-9A-Z]{9}", normalized)) and normalized not in {"000000000", "999999999"}


def valid_isin(value: str) -> bool:
    normalized = value.strip().upper()
    return bool(re.fullmatch(r"[0-9A-Z]{12}", normalized)) and normalized != "0" * 12


def normalize_text(value: str, *, drop_suffixes: bool = False) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^A-Z0-9]+", " ", ascii_text.upper().replace("&", " AND "))
    tokens = normalized.split()
    if drop_suffixes:
        suffixes = {"INC", "INCORPORATED", "LLC", "LTD", "LIMITED", "LP", "CORP", "CORPORATION", "CO", "COMPANY", "HOLDINGS"}
        while tokens and tokens[-1] in suffixes:
            tokens.pop()
    return " ".join(tokens)


def atom_entries(fund: str, identity: dict[str, str]) -> list[dict[str, str]]:
    series_id = identity["series_id"]
    feed_url = (
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&"
        f"CIK={series_id}&type=NPORT-P&owner=exclude&count=100&output=atom"
    )
    feed = cached_bytes(feed_url, CACHE_ROOT / fund / "feed.atom")
    root = ET.fromstring(feed)
    rows: list[dict[str, str]] = []
    for entry in descendants(root, "entry"):
        accession = first_child_text(entry, "accession-number")
        filing_date = first_child_text(entry, "filing-date")
        filing_index_url = first_child_text(entry, "filing-href")
        filing_type = first_child_text(entry, "filing-type")
        if not accession or not filing_index_url:
            continue
        compact = accession.replace("-", "")
        archive_dir = filing_index_url.rsplit("/", 1)[0]
        rows.append({
            "fund": fund,
            "series_id": series_id,
            "class_id": identity["class_id"],
            "filing_date": filing_date,
            "accession": accession,
            "filing_type": filing_type,
            "filing_index_url": filing_index_url,
            "primary_doc_url": f"{archive_dir}/primary_doc.xml",
            "compact_accession": compact,
        })
    return rows


def parse_filing(source: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    fund = source["fund"]
    accession = source["accession"]
    xml_path = CACHE_ROOT / fund / f"{source['compact_accession']}-primary_doc.xml"
    data = cached_bytes(source["primary_doc_url"], xml_path)
    root = ET.fromstring(data)
    gen_info = first_descendant(root, "genInfo")
    fund_info = first_descendant(root, "fundInfo")
    report_date = first_child_text(gen_info, "repPdDate")
    total_assets = safe_decimal(first_child_text(fund_info, "totAssets"))
    net_assets = safe_decimal(first_child_text(fund_info, "netAssets"))
    all_positions = descendants(root, "invstOrSec")
    loan_positions = [position for position in all_positions if first_child_text(position, "assetCat") == "LON"]
    holdings: list[dict[str, Any]] = []
    for position in loan_positions:
        identifiers = first_descendant(position, "identifiers")
        isin_element = first_descendant(identifiers, "isin")
        isin = (isin_element.attrib.get("value", "") if isin_element is not None else "").strip().upper()
        debt = first_descendant(position, "debtSec")
        principal_raw = first_child_text(position, "balance")
        fair_value_raw = first_child_text(position, "valUSD")
        principal = safe_decimal(principal_raw)
        fair_value = safe_decimal(fair_value_raw)
        units = first_child_text(position, "units")
        currency = first_child_text(position, "curCd")
        implied_mark = (
            fair_value / principal * Decimal("100")
            if principal is not None and principal > 0 and fair_value is not None and units == "PA" and currency == "USD"
            else None
        )
        holdings.append({
            "fund": fund,
            "report_date": report_date,
            "borrower": first_child_text(position, "name"),
            "loan_title": first_child_text(position, "title"),
            "cusip": first_child_text(position, "cusip").upper(),
            "isin": isin,
            "principal": principal_raw,
            "units": units,
            "currency": currency,
            "fair_value_usd": fair_value_raw,
            "implied_mark": decimal_text(implied_mark),
            "pct_fund_value": first_child_text(position, "pctVal"),
            "maturity": first_child_text(debt, "maturityDt"),
            "coupon_kind": first_child_text(debt, "couponKind"),
            "annualized_rate": first_child_text(debt, "annualizedRt"),
            "fair_value_level": first_child_text(position, "fairValLevel"),
            "country": first_child_text(position, "invCountry"),
            "is_default": first_child_text(debt, "isDefault"),
            "interest_in_arrears": first_child_text(debt, "areIntrstPmntsInArrs"),
            "is_pik": first_child_text(debt, "isPaidKind"),
            "filing_date": source["filing_date"],
            "accession": accession,
            "sec_source_url": source["filing_index_url"],
            "normalized_borrower": normalize_text(first_child_text(position, "name"), drop_suffixes=True),
            "normalized_title": normalize_text(first_child_text(position, "title")),
        })
    total_principal = sum((safe_decimal(row["principal"]) or Decimal("0")) for row in holdings)
    total_fair_value = sum((safe_decimal(row["fair_value_usd"]) or Decimal("0")) for row in holdings)
    weighted_mark = total_fair_value / total_principal * Decimal("100") if total_principal else None
    filing_row = {
        **{key: source[key] for key in ("fund", "series_id", "class_id", "filing_date", "accession", "filing_type", "filing_index_url", "primary_doc_url")},
        "report_date": report_date,
        "total_assets": decimal_text(total_assets),
        "net_assets": decimal_text(net_assets),
        "total_position_count": len(all_positions),
        "reported_loan_count": len(loan_positions),
        "loaded_loan_rows": len(holdings),
        "total_reported_principal": decimal_text(total_principal),
        "total_loan_fair_value": decimal_text(total_fair_value),
        "weighted_implied_mark": decimal_text(weighted_mark),
        "loan_fv_pct_total_assets": decimal_text(total_fair_value / total_assets * Decimal("100")) if total_assets else "",
        "status": "parsed",
        "error": "",
    }
    return filing_row, holdings


def assign_match_keys(rows: list[dict[str, Any]]) -> None:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["normalized_borrower"], row["maturity"])].append(row)
    for (borrower, maturity), group in groups.items():
        cusips = sorted({row["cusip"] for row in group if valid_cusip(row["cusip"])})
        isins = sorted({row["isin"] for row in group if valid_isin(row["isin"])})
        ambiguous = len(cusips) > 1 or (not cusips and len(isins) > 1)
        for row in group:
            if valid_cusip(row["cusip"]):
                row["match_key"] = f"CUSIP:{row['cusip']}"
                row["match_quality"] = "CUSIP direct"
            elif len(cusips) == 1:
                row["match_key"] = f"CUSIP:{cusips[0]}"
                row["match_quality"] = "CUSIP propagated"
            elif valid_isin(row["isin"]):
                row["match_key"] = f"ISIN:{row['isin']}"
                row["match_quality"] = "ISIN direct"
            elif len(isins) == 1:
                row["match_key"] = f"ISIN:{isins[0]}"
                row["match_quality"] = "ISIN propagated"
            elif ambiguous:
                row["match_key"] = f"FALLBACK:{borrower}|{maturity}|{row['normalized_title']}"
                row["match_quality"] = "Ambiguous borrower/maturity"
            else:
                row["match_key"] = f"FALLBACK:{borrower}|{maturity}"
                row["match_quality"] = "Borrower/maturity fallback"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_dashboard_reference(rows: list[dict[str, Any]], filing_rows: list[dict[str, Any]]) -> dict[str, Any]:
    borrower_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        mark = safe_decimal(row["implied_mark"])
        if mark is None:
            continue
        borrower_history[row["normalized_borrower"]].append({
            "report_date": row["report_date"],
            "fund": row["fund"],
            "borrower": row["borrower"],
            "loan_title": row["loan_title"],
            "match_key": row["match_key"],
            "match_quality": row["match_quality"],
            "maturity": row["maturity"],
            "principal": float(safe_decimal(row["principal"]) or 0),
            "fair_value_usd": float(safe_decimal(row["fair_value_usd"]) or 0),
            "implied_mark": round(float(mark), 5),
            "annualized_rate": float(safe_decimal(row["annualized_rate"]) or 0) if row["annualized_rate"] else None,
            "sec_source_url": row["sec_source_url"],
        })
    compact_borrowers = []
    for normalized_borrower, history in borrower_history.items():
        history.sort(key=lambda item: (item["report_date"], item["fund"], item["match_key"]))
        latest_date = max(item["report_date"] for item in history)
        latest = [item for item in history if item["report_date"] == latest_date]
        latest_principal = sum(item["principal"] for item in latest)
        latest_mark = (
            sum(item["implied_mark"] * item["principal"] for item in latest) / latest_principal
            if latest_principal else None
        )
        min_item = min(history, key=lambda item: item["implied_mark"])
        compact_borrowers.append({
            "normalized_borrower": normalized_borrower,
            "display_borrower": latest[0]["borrower"],
            "latest_date": latest_date,
            "latest_mark": round(latest_mark, 4) if latest_mark is not None else None,
            "latest_funds": sorted({item["fund"] for item in latest}),
            "observation_count": len(history),
            "first_date": history[0]["report_date"],
            "minimum_mark": min_item["implied_mark"],
            "minimum_mark_date": min_item["report_date"],
            "history": history,
        })
    compact_borrowers.sort(key=lambda item: (item["latest_mark"] is None, item["latest_mark"] or 999, item["display_borrower"]))
    return {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "filing_count": len(filing_rows),
            "holding_count": len(rows),
            "valid_mark_count": sum(bool(row["implied_mark"]) for row in rows),
            "zero_principal_count": sum((safe_decimal(row["principal"]) or Decimal("0")) == 0 for row in rows),
            "ambiguous_identifier_count": sum(row["match_quality"] == "Ambiguous borrower/maturity" for row in rows),
            "earliest_report_date": min(row["report_date"] for row in filing_rows),
            "latest_report_date": max(row["report_date"] for row in filing_rows),
            "funds": list(FUNDS),
            "methodology": "Implied mark equals 100 times SEC-reported fair value divided by SEC-reported principal for USD positions reported in principal amount units. These are periodic fund valuation marks, not executable dealer bids.",
        },
        "monthly_summary": filing_rows,
        "borrowers": compact_borrowers,
        "sources": [
            {"name": "SEC Form N-PORT data sets", "url": "https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets"},
            {"name": "SEC EDGAR filing archive", "url": "https://www.sec.gov/edgar/search/"},
        ],
    }


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    raw_filings: list[dict[str, Any]] = []
    raw_holdings: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for fund, identity in FUNDS.items():
        entries = atom_entries(fund, identity)
        print(f"{fund}: {len(entries)} public N-PORT filings", flush=True)
        for index, entry in enumerate(entries, start=1):
            try:
                filing, holdings = parse_filing(entry)
                raw_filings.append(filing)
                raw_holdings.extend(holdings)
            except (HTTPError, URLError, TimeoutError, ET.ParseError, ValueError) as exc:
                failures.append({
                    **{key: entry.get(key, "") for key in ("fund", "series_id", "class_id", "filing_date", "accession", "filing_type", "filing_index_url", "primary_doc_url")},
                    "report_date": "", "status": "failed", "error": type(exc).__name__,
                })
            if index % 10 == 0 or index == len(entries):
                print(f"  parsed {index}/{len(entries)}", flush=True)

    # One filing per fund/report date; later valid amendments win.
    by_period: dict[tuple[str, str], tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    holdings_by_accession: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw_holdings:
        holdings_by_accession[row["accession"]].append(row)
    for filing in sorted(raw_filings, key=lambda row: (row["fund"], row["report_date"], row["filing_date"], row["accession"])):
        by_period[(filing["fund"], filing["report_date"])] = (filing, holdings_by_accession[filing["accession"]])
    filing_rows = [value[0] for value in by_period.values()]
    holdings = [row for value in by_period.values() for row in value[1]]
    filing_rows.sort(key=lambda row: (row["report_date"], row["fund"]))
    holdings.sort(key=lambda row: (row["report_date"], row["fund"], row["borrower"], row["loan_title"]))
    assign_match_keys(holdings)

    write_csv(OUTPUT_ROOT / "filings.csv", FILING_FIELDS, filing_rows + failures)
    write_csv(OUTPUT_ROOT / "loan_holdings.csv", HOLDING_FIELDS, holdings)
    write_csv(OUTPUT_ROOT / "failures.csv", ["fund", "filing_date", "accession", "filing_index_url", "status", "error"], failures)
    dashboard_reference = build_dashboard_reference(holdings, filing_rows)
    (OUTPUT_ROOT / "nport_bsl_summary.json").write_text(json.dumps(dashboard_reference, indent=2), encoding="utf-8")
    print(f"Filings: {len(filing_rows)}", flush=True)
    print(f"Loan holding rows: {len(holdings)}", flush=True)
    print(f"Valid implied marks: {dashboard_reference['meta']['valid_mark_count']}", flush=True)
    print(f"Zero-principal rows: {dashboard_reference['meta']['zero_principal_count']}", flush=True)
    print(f"Ambiguous identifier rows: {dashboard_reference['meta']['ambiguous_identifier_count']}", flush=True)
    print(f"Failed filings: {len(failures)}", flush=True)


if __name__ == "__main__":
    main()
