from __future__ import annotations

import html
import json
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "lib" / "bdc-funding-market.json"
CACHE_ROOT = PROJECT_ROOT / ".cache" / "funding-sec"
USER_AGENT = "BDC Tracker research contact yarde@example.com"
FINRA_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
FINRA_EOD_TEMPLATE_ID = "template-4be2bd56-523d-4623-a401-031dfeadde1e"
SEC_START_DATE = date(2018, 1, 1)
TRACE_START_DATE = date(2023, 1, 1)
TODAY = date.today()
OFFERING_FORMS = {"424B2", "424B3", "424B5", "FWP"}
# Pricing terms live near the front of prospectus supplements and FWPs.  Some
# inline-XBRL filings are tens of megabytes; parsing their exhibits in full adds
# minutes without improving the offering extraction.
MAX_DOCUMENT_BYTES = 1_500_000

FUNDS: dict[str, dict[str, Any]] = {
    "ARCC": {"cik": 1287750, "name": "Ares Capital Corporation"},
    "BBDC": {"cik": 1379785, "name": "Barings BDC, Inc."},
    "BXSL": {"cik": 1736035, "name": "Blackstone Secured Lending Fund"},
    "FSK": {"cik": 1422183, "name": "FS KKR Capital Corp."},
    "GBDC": {"cik": 1476765, "name": "Golub Capital BDC, Inc."},
    "MAIN": {"cik": 1396440, "name": "Main Street Capital Corporation"},
    "OBDC": {"cik": 1655888, "name": "Blue Owl Capital Corporation"},
    "TSLX": {"cik": 1508655, "name": "Sixth Street Specialty Lending, Inc."},
}

# Filings usually disclose the CUSIP in an FWP pricing term sheet. These
# overrides cover older series where the definitive prospectus omits it.
# Each key is (ticker, coupon percentage, maturity year).
CUSIP_OVERRIDES: dict[tuple[str, float, int], str] = {
    ("GBDC", 2.500, 2026): "38173MAB8",
    ("GBDC", 2.050, 2027): "38173MAC6",
    ("GBDC", 7.050, 2028): "38173MAD4",
    ("GBDC", 6.000, 2029): "38173MAE2",
    ("GBDC", 6.250, 2031): "38173MAF9",
}


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.hidden_depth += 1
        elif tag.lower() in {"p", "div", "br", "tr", "td", "th", "li", "h1", "h2", "h3"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)
        elif tag.lower() in {"p", "div", "tr", "li", "h1", "h2", "h3"}:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


def visible_text(document: str) -> str:
    parser = VisibleTextParser()
    parser.feed(document)
    text = html.unescape(" ".join(parser.parts))
    return re.sub(r"\s+", " ", text).strip()


def request_bytes(url: str, *, headers: dict[str, str] | None = None) -> bytes:
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "identity",
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    }
    if headers:
        request_headers.update(headers)
    with urlopen(Request(url, headers=request_headers), timeout=45) as response:
        return response.read()


def request_json(url: str) -> Any:
    return json.loads(request_bytes(url).decode("utf-8"))


def sec_filing_rows(cik: int) -> list[dict[str, Any]]:
    submission = request_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    rows: list[dict[str, Any]] = []

    def append_columnar(recent: dict[str, list[Any]]) -> None:
        accessions = recent.get("accessionNumber", [])
        for index, accession in enumerate(accessions):
            row = {key: values[index] if index < len(values) else None for key, values in recent.items()}
            rows.append(row)

    append_columnar(submission.get("filings", {}).get("recent", {}))
    for older in submission.get("filings", {}).get("files", []):
        file_name = older.get("name")
        filing_from = older.get("filingFrom")
        if not file_name or (filing_from and filing_from < SEC_START_DATE.isoformat()):
            continue
        append_columnar(request_json(f"https://data.sec.gov/submissions/{file_name}"))

    output = []
    for row in rows:
        filing_date = str(row.get("filingDate") or "")
        form = str(row.get("form") or "").upper()
        if not filing_date or filing_date < SEC_START_DATE.isoformat() or form not in OFFERING_FORMS:
            continue
        if not row.get("primaryDocument") or not row.get("accessionNumber"):
            continue
        output.append(row)
    output.sort(key=lambda row: (str(row.get("filingDate")), str(row.get("accessionNumber"))))
    return output


def sec_document_url(cik: int, accession: str, primary_document: str) -> str:
    compact = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{compact}/{primary_document}"


def amount_to_mm(raw: str, unit: str | None) -> float:
    value = float(raw.replace(",", ""))
    normalized = (unit or "").lower()
    if normalized == "billion":
        return value * 1000.0
    if normalized == "million":
        return value
    return value / 1_000_000.0


def nearest_amount(text: str, position: int) -> float | None:
    window = text[max(0, position - 900): position + 400]
    candidates: list[tuple[int, float]] = []
    for match in re.finditer(r"\$\s*([\d,.]+)\s*(billion|million)?", window, flags=re.I):
        try:
            value = amount_to_mm(match.group(1), match.group(2))
        except ValueError:
            continue
        if 20 <= value <= 5_000:
            absolute_distance = abs((max(0, position - 900) + match.start()) - position)
            candidates.append((absolute_distance, value))
    return min(candidates)[1] if candidates else None


def first_float(patterns: list[str], text: str, *, limit: int = 80_000) -> float | None:
    section = text[:limit]
    for pattern in patterns:
        match = re.search(pattern, section, flags=re.I)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                pass
    return None


def first_date(patterns: list[str], text: str, *, limit: int = 100_000) -> str | None:
    section = text[:limit]
    for pattern in patterns:
        match = re.search(pattern, section, flags=re.I)
        if not match:
            continue
        raw = match.group(1).replace(" ", " ").strip()
        for date_format in ("%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(raw, date_format).date().isoformat()
            except ValueError:
                pass
    return None


def extract_cusip_matches(text: str) -> list[tuple[int, str]]:
    values: list[tuple[int, str]] = []
    patterns = [
        r"CUSIP(?:\s+(?:Number|No\.?))?\s*[:#]?\s*([0-9A-Z]{9})",
        r"CUSIP\s*/\s*ISIN\s*[:#]?\s*([0-9A-Z]{9})",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            value = match.group(1).upper()
            if not any(existing == value for _, existing in values):
                values.append((match.start(), value))
    return values


def extract_note_offerings(
    ticker: str,
    cik: int,
    filing: dict[str, Any],
    text: str,
    source_url: str,
) -> list[dict[str, Any]]:
    header = text[:90_000]
    # The securities being priced appear on the cover.  Looking deeper starts
    # to pick up legacy notes listed in capitalization and risk disclosures.
    title_header = text[:30_000]
    title_pattern = re.compile(
        r"(?P<coupon>\d{1,2}(?:\.\d{1,4})?)\s*%\s+"
        r"(?:(?:senior|unsecured|fixed-rate)\s+)*notes?\s+due\s+(?P<year>20\d{2})",
        flags=re.I,
    )
    title_matches = list(title_pattern.finditer(title_header))
    if not title_matches:
        return []
    # BDC public-note offerings in this tracker are single-series deals. Later
    # title matches on the same cover are usually capitalization-table history.
    title_matches = [title_matches[0]]

    cusip_matches = extract_cusip_matches(header)
    cusips = [value for _, value in cusip_matches]
    maturity_date = first_date(
        [
            r"(?:Notes|notes)\s+will\s+mature\s+on\s+([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
            r"Maturity\s+(?:Date\s+)?([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
        ],
        header,
    )
    settlement_date = first_date(
        [
            r"delivery\s+of\s+the\s+Notes.*?(?:on|about)\s+([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
            r"Settlement\s+(?:Date\s+)?([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
            r"Expected\s+settlement\s+date.*?([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
        ],
        header,
    )
    issue_price = first_float(
        [
            r"public\s+offering\s+price(?:\s+of)?\s+([\d.]+)%",
            r"Price\s+to\s+Public\s+([\d.]+)%",
            r"Purchase\s+Price.*?([\d.]+)%\s+of\s+par",
            r"Issue\s+Price\s+([\d.]+)%",
        ],
        header,
    )
    offering_yield = first_float(
        [
            r"yield\s+to\s+maturity(?:\s+of)?\s+([\d.]+)%",
            r"Re-offer\s+yield\s+([\d.]+)%",
        ],
        header,
    )
    treasury_spread_bps = first_float(
        [
            r"spread\s+to\s+(?:the\s+)?benchmark\s+treasury.*?(\d+(?:\.\d+)?)\s+basis\s+points",
            r"Re-offer\s+spread.*?\+\s*(\d+(?:\.\d+)?)\s+basis\s+points",
        ],
        header,
    )

    results: list[dict[str, Any]] = []
    seen_titles: set[tuple[float, int]] = set()
    for match in title_matches:
        coupon = round(float(match.group("coupon")), 4)
        if coupon > 15:
            continue
        maturity_year = int(match.group("year"))
        amount_mm = nearest_amount(header, match.start())
        signature = (coupon, maturity_year)
        if signature in seen_titles:
            continue
        seen_titles.add(signature)
        override = CUSIP_OVERRIDES.get((ticker, coupon, maturity_year))
        nearest_cusip = min(cusip_matches, key=lambda item: abs(item[0] - match.start()))[1] if cusip_matches else None
        cusip = override or nearest_cusip
        filed = str(filing.get("filingDate"))
        results.append(
            {
                "ticker": ticker,
                "cik": cik,
                "form": filing.get("form"),
                "filed_date": filed,
                "pricing_date": filed,
                "settlement_date": settlement_date,
                "accession_number": filing.get("accessionNumber"),
                "source_url": source_url,
                "coupon_pct": coupon,
                "maturity_year": maturity_year,
                "maturity_date": maturity_date if maturity_date and maturity_date.startswith(str(maturity_year)) else None,
                "offering_amount_mm": round(amount_mm, 3) if amount_mm is not None else None,
                "issue_price_pct": issue_price,
                "offering_yield_pct": offering_yield,
                "treasury_spread_bps": treasury_spread_bps,
                "cusip": cusip,
                "cusip_candidates": cusips,
                "is_reopening": bool(re.search(r"(?:further\s+issuance|re-opening|additional\s+notes)", header[:35_000], flags=re.I)),
                "security_title": f"{coupon:.3f}% Notes due {maturity_year}",
                "extraction_confidence": "high" if amount_mm is not None else "review",
            }
        )
    return results


def merge_duplicate_documents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = sorted(rows, key=lambda row: (row["ticker"], row["pricing_date"], row["coupon_pct"], row["maturity_year"], row.get("form") or ""))
    merged: list[dict[str, Any]] = []
    for row in rows:
        row_date = date.fromisoformat(row["pricing_date"])
        match = next(
            (
                item
                for item in reversed(merged)
                if item["ticker"] == row["ticker"]
                and item["coupon_pct"] == row["coupon_pct"]
                and item["maturity_year"] == row["maturity_year"]
                and (
                    abs((row_date - date.fromisoformat(item["pricing_date"])).days) <= 14
                    or (
                        row.get("offering_amount_mm") is not None
                        and row.get("offering_amount_mm") == item.get("offering_amount_mm")
                        and not row.get("is_reopening")
                        and not item.get("is_reopening")
                    )
                )
            ),
            None,
        )
        if not match:
            row["source_documents"] = [{"form": row["form"], "filed_date": row["filed_date"], "url": row["source_url"]}]
            merged.append(row)
            continue
        match["source_documents"].append({"form": row["form"], "filed_date": row["filed_date"], "url": row["source_url"]})
        for field in ("cusip", "settlement_date", "maturity_date", "issue_price_pct", "offering_yield_pct", "treasury_spread_bps"):
            if match.get(field) is None and row.get(field) is not None:
                match[field] = row[field]
        match["is_reopening"] = match["is_reopening"] or row["is_reopening"]
        match["extraction_confidence"] = "high" if match.get("offering_amount_mm") is not None else "review"

    for index, row in enumerate(merged, start=1):
        row["event_id"] = f"{row['ticker']}-{row['pricing_date']}-{row['coupon_pct']:.4f}-{row['maturity_year']}-{index}"
        row.pop("cusip_candidates", None)
        row.pop("source_url", None)
        row.pop("accession_number", None)
        row.pop("filed_date", None)
        row.pop("form", None)
    return merged


@dataclass
class FinraClient:
    xsrf_token: str
    cookie_header: str

    @classmethod
    def create(cls) -> "FinraClient":
        template_url = (
            "https://services-dynarep.ddwa.finra.org/public/reporting/v2/template/"
            f"{FINRA_EOD_TEMPLATE_ID}/composite"
        )
        request = Request(template_url, headers={"User-Agent": FINRA_USER_AGENT, "Accept": "application/json"})
        with urlopen(request, timeout=45) as response:
            response.read()
            set_cookie_headers = response.headers.get_all("Set-Cookie") or []
        cookie_pairs: list[str] = []
        token = ""
        for header in set_cookie_headers:
            cookie = SimpleCookie()
            cookie.load(header)
            for name, morsel in cookie.items():
                cookie_pairs.append(f"{name}={morsel.value}")
                if name == "XSRF-TOKEN":
                    token = morsel.value
        if not token:
            raise RuntimeError("FINRA did not issue an XSRF token")
        return cls(xsrf_token=token, cookie_header="; ".join(cookie_pairs))

    def eod_price_yield(self, cusip: str, start_date: date, end_date: date) -> list[dict[str, Any]]:
        url = (
            "https://services-dynarep.ddwa.finra.org/public/reporting/v2/data/group/"
            "FixedIncomeMarket/name/EndOfDayPriceYield"
        )
        payload = {
            "fields": ["cusip", "productType", "lastSalePrice", "lastSaleYield", "tradeDate", "numberOfAllocations"],
            "orFilters": [{"compareFilters": [{"fieldName": "cusip", "fieldValue": cusip, "compareType": "EQUAL"}]}],
            "dateRangeFilters": [{
                "startDate": f"{start_date.isoformat()} 00:00:00 ",
                "endDate": f"{end_date.isoformat()} 23:59:59 ",
                "fieldName": "tradeDate",
            }],
            "sortFields": ["-tradeDate"],
            "offset": 0,
            "limit": 5000,
        }
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            method="POST",
            headers={
                "User-Agent": FINRA_USER_AGENT,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-XSRF-TOKEN": self.xsrf_token,
                "Cookie": self.cookie_header,
            },
        )
        with urlopen(request, timeout=60) as response:
            envelope = json.loads(response.read().decode("utf-8"))
        return json.loads(envelope["returnBody"]["data"])


def compressed_trace_history(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    ordered = sorted(rows, key=lambda row: str(row["tradeDate"]))
    recent_cutoff = TODAY - timedelta(days=120)
    month_end: dict[str, dict[str, Any]] = {}
    recent: dict[str, dict[str, Any]] = {}
    for row in ordered:
        trade_date = date.fromisoformat(str(row["tradeDate"]))
        compact = {
            "date": trade_date.isoformat(),
            "price": row.get("lastSalePrice"),
            "yield_pct": row.get("lastSaleYield"),
        }
        month_end[trade_date.strftime("%Y-%m")] = compact
        if trade_date >= recent_cutoff:
            recent[trade_date.isoformat()] = compact
    combined = {item["date"]: item for item in month_end.values()}
    combined.update(recent)
    return [combined[key] for key in sorted(combined)]


def observation_on_or_before(rows: list[dict[str, Any]], target: date) -> dict[str, Any] | None:
    eligible = [row for row in rows if date.fromisoformat(str(row["tradeDate"])) <= target]
    return max(eligible, key=lambda row: str(row["tradeDate"]), default=None)


def trace_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: str(row["tradeDate"]))
    latest = ordered[-1] if ordered else None
    prior_30 = observation_on_or_before(ordered, TODAY - timedelta(days=30))
    prior_90 = observation_on_or_before(ordered, TODAY - timedelta(days=90))

    def change(field: str, prior: dict[str, Any] | None) -> float | None:
        if not latest or not prior or latest.get(field) is None or prior.get(field) is None:
            return None
        return round(float(latest[field]) - float(prior[field]), 4)

    return {
        "trace_status": "matched" if latest else "matched_no_trades",
        "last_trade_date": latest.get("tradeDate") if latest else None,
        "last_price": latest.get("lastSalePrice") if latest else None,
        "last_yield_pct": latest.get("lastSaleYield") if latest else None,
        "price_change_30d": change("lastSalePrice", prior_30),
        "yield_change_30d_pp": change("lastSaleYield", prior_30),
        "price_change_90d": change("lastSalePrice", prior_90),
        "yield_change_90d_pp": change("lastSaleYield", prior_90),
        "observation_count": len(ordered),
        "history": compressed_trace_history(ordered),
    }


def build_series(events: list[dict[str, Any]], finra: FinraClient | None) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, float, int], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        key = (event["ticker"], event["coupon_pct"], event["maturity_year"])
        grouped[key].append(event)

    series_rows: list[dict[str, Any]] = []
    for (ticker, coupon, maturity_year), series_events in sorted(grouped.items()):
        series_events.sort(key=lambda row: row["pricing_date"])
        cusip_values = list(dict.fromkeys(row["cusip"] for row in series_events if row.get("cusip")))
        cusip = cusip_values[0] if len(cusip_values) == 1 else None
        amounts = [float(row["offering_amount_mm"]) for row in series_events if row.get("offering_amount_mm") is not None]
        maturity_dates = [row["maturity_date"] for row in series_events if row.get("maturity_date")]
        maturity_date = maturity_dates[-1] if maturity_dates else f"{maturity_year}-12-31"
        trace = {
            "trace_status": "no_cusip",
            "last_trade_date": None,
            "last_price": None,
            "last_yield_pct": None,
            "price_change_30d": None,
            "yield_change_30d_pp": None,
            "price_change_90d": None,
            "yield_change_90d_pp": None,
            "observation_count": 0,
            "history": [],
        }
        if cusip and finra:
            try:
                first_event_date = date.fromisoformat(series_events[0]["pricing_date"])
                rows = finra.eod_price_yield(cusip, max(TRACE_START_DATE, first_event_date), TODAY)
                trace = trace_summary(rows)
            except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as exc:
                trace["trace_status"] = "query_error"
                trace["trace_error"] = type(exc).__name__
            time.sleep(0.18)

        series_rows.append(
            {
                "series_id": f"{ticker}-{coupon:.4f}-{maturity_year}-{cusip or 'UNMATCHED'}",
                "ticker": ticker,
                "company_name": FUNDS[ticker]["name"],
                "security_title": f"{coupon:.3f}% Notes due {maturity_year}",
                "coupon_pct": coupon,
                "maturity_year": maturity_year,
                "maturity_date": maturity_date,
                "cusip": cusip,
                "issuance_event_count": len(series_events),
                "gross_issued_mm": round(sum(amounts), 3) if amounts else None,
                "first_pricing_date": series_events[0]["pricing_date"],
                "latest_pricing_date": series_events[-1]["pricing_date"],
                "status": "matured" if date.fromisoformat(maturity_date) < TODAY else "outstanding_candidate",
                "finra_url": (
                    f"https://www.finra.org/finra-data/fixed-income/trade-history?cusip={cusip}&bondType=CA"
                    if cusip
                    else None
                ),
                **trace,
            }
        )
    return series_rows


def fund_summaries(events: list[dict[str, Any]], series_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for ticker, identity in FUNDS.items():
        fund_events = [row for row in events if row["ticker"] == ticker]
        fund_series = [row for row in series_rows if row["ticker"] == ticker and row["status"] == "outstanding_candidate"]
        trace_series = [row for row in fund_series if row["trace_status"] == "matched"]
        recent_events = [row for row in fund_events if row["pricing_date"] >= "2024-01-01"]
        weighted_coupon_numerator = sum(
            float(row["coupon_pct"]) * float(row["gross_issued_mm"])
            for row in fund_series
            if row.get("gross_issued_mm") is not None
        )
        weighted_coupon_denominator = sum(float(row["gross_issued_mm"]) for row in fund_series if row.get("gross_issued_mm") is not None)
        output.append(
            {
                "ticker": ticker,
                "company_name": identity["name"],
                "cik": identity["cik"],
                "issuance_event_count": len(fund_events),
                "recent_issuance_event_count": len(recent_events),
                "recent_gross_issued_mm": round(sum(float(row.get("offering_amount_mm") or 0) for row in recent_events), 3),
                "outstanding_candidate_series_count": len(fund_series),
                "outstanding_candidate_gross_mm": round(sum(float(row.get("gross_issued_mm") or 0) for row in fund_series), 3),
                "weighted_coupon_pct": round(weighted_coupon_numerator / weighted_coupon_denominator, 4) if weighted_coupon_denominator else None,
                "trace_matched_series_count": len(trace_series),
                "trace_last_yield_pct": (
                    round(sum(float(row["last_yield_pct"]) for row in trace_series if row.get("last_yield_pct") is not None) / sum(1 for row in trace_series if row.get("last_yield_pct") is not None), 4)
                    if any(row.get("last_yield_pct") is not None for row in trace_series)
                    else None
                ),
            }
        )
    return output


def main() -> None:
    raw_events: list[dict[str, Any]] = []
    filing_audit: list[dict[str, Any]] = []
    for ticker, identity in FUNDS.items():
        cik = int(identity["cik"])
        candidates = sec_filing_rows(cik)
        print(f"{ticker}: {len(candidates)} candidate offering documents", flush=True)
        parsed_documents = 0
        extracted_rows = 0
        for document_index, filing in enumerate(candidates, start=1):
            source_url = sec_document_url(cik, str(filing["accessionNumber"]), str(filing["primaryDocument"]))
            try:
                cache_path = CACHE_ROOT / ticker / f"{str(filing['accessionNumber']).replace('-', '')}-{filing['primaryDocument']}"
                if cache_path.exists():
                    document_bytes = cache_path.read_bytes()[:MAX_DOCUMENT_BYTES]
                else:
                    document_bytes = request_bytes(source_url)[:MAX_DOCUMENT_BYTES]
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_bytes(document_bytes)
                    time.sleep(0.12)
                document = document_bytes.decode("utf-8", errors="replace")
                text = visible_text(document)
                offerings = extract_note_offerings(ticker, cik, filing, text, source_url)
            except (HTTPError, URLError, TimeoutError) as exc:
                filing_audit.append({
                    "ticker": ticker,
                    "source_url": source_url,
                    "status": "download_error",
                    "error": type(exc).__name__,
                })
                continue
            parsed_documents += 1
            extracted_rows += len(offerings)
            raw_events.extend(offerings)
            if document_index % 20 == 0 or document_index == len(candidates):
                print(
                    f"  parsed {document_index}/{len(candidates)} documents; "
                    f"{extracted_rows} candidate note rows",
                    flush=True,
                )
        filing_audit.append(
            {
                "ticker": ticker,
                "candidate_documents": len(candidates),
                "parsed_documents": parsed_documents,
                "extracted_rows_before_deduplication": extracted_rows,
                "status": "parsed",
            }
        )

    events = merge_duplicate_documents(raw_events)
    try:
        finra = FinraClient.create()
        finra_status = "connected"
    except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
        finra = None
        finra_status = f"unavailable:{type(exc).__name__}"
    series_rows = build_series(events, finra)
    fund_rows = fund_summaries(events, series_rows)

    payload = {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sec_start_date": SEC_START_DATE.isoformat(),
            "trace_start_date": TRACE_START_DATE.isoformat(),
            "as_of_date": TODAY.isoformat(),
            "fund_count": len(FUNDS),
            "issuance_event_count": len(events),
            "series_count": len(series_rows),
            "outstanding_candidate_series_count": sum(1 for row in series_rows if row["status"] == "outstanding_candidate"),
            "cusip_matched_series_count": sum(1 for row in series_rows if row.get("cusip")),
            "trace_matched_series_count": sum(1 for row in series_rows if row["trace_status"] == "matched"),
            "finra_status": finra_status,
            "methodology": "SEC 424B2, 424B3, 424B5, and FWP filings are parsed into note issuance events and deduplicated across pricing term sheets and prospectus supplements. Series are grouped by fund, coupon, and maturity year, then enriched with a verified CUSIP where the filing supplies one. Gross issuance is not adjusted for tenders or open-market repurchases unless a later source explicitly supplies the change; outstanding status is therefore labeled as a candidate. FINRA EndOfDayPriceYield observations are executed-trade closes, not dealer quotes.",
        },
        "funds": fund_rows,
        "series": sorted(series_rows, key=lambda row: (row["status"] != "outstanding_candidate", row["maturity_date"], row["ticker"])),
        "issuance_events": sorted(events, key=lambda row: (row["pricing_date"], row["ticker"]), reverse=True),
        "filing_audit": filing_audit,
        "sources": [
            {
                "name": "SEC EDGAR submissions and filing archives",
                "url": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
                "role": "Issuer filing history and offering documents",
            },
            {
                "name": "FINRA TRACE EndOfDayPriceYield",
                "url": "https://www.finra.org/finra-data/fixed-income/about-trade-activity",
                "role": "Executed-trade end-of-day price and yield history",
            },
        ],
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Issuance events: {len(events)}")
    print(f"Series: {len(series_rows)}")
    print(f"CUSIP matched: {payload['meta']['cusip_matched_series_count']}")
    print(f"TRACE matched: {payload['meta']['trace_matched_series_count']}")


if __name__ == "__main__":
    main()
