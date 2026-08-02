from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import time
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from free_sources import cached_bytes, discover_zip_links, number, request_json_post, safe_error


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = PROJECT_ROOT / ".cache" / "equity-positioning"
OUTPUT_PATH = PROJECT_ROOT / "lib" / "bdc-equity-positioning.json"
TICKERS = ("ARCC", "BBDC", "BXSL", "FSK", "GBDC", "MAIN", "OBDC", "TSLX")
BIZD_URL = "https://www.vaneck.com/us/en/etf/income/bizd/holdings/download/xlsx/"
BIZD_PAGE = "https://www.vaneck.com/us/en/investments/bdc-income-etf-bizd"
FINRA_SHORT_INTEREST_URL = "https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest"
FINRA_SHORT_INTEREST_PAGE = "https://www.finra.org/finra-data/browse-catalog/equity-short-interest"
FINRA_SHORT_VOLUME_URL = "https://api.finra.org/data/group/otcMarket/name/regShoDaily"
FINRA_SHORT_VOLUME_PAGE = "https://www.finra.org/finra-data/browse-catalog/short-sale-volume"
SEC_FTD_PAGE = "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_xlsx(data: bytes) -> list[list[str]]:
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall(f"{namespace}si"):
                shared.append("".join(node.text or "" for node in item.iter(f"{namespace}t")))
        sheet_name = next(name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"))
        root = ElementTree.fromstring(archive.read(sheet_name))
        output: list[list[str]] = []
        for row in root.iter(f"{namespace}row"):
            values: dict[int, str] = {}
            for cell in row.findall(f"{namespace}c"):
                ref = cell.attrib.get("r", "A1")
                letters = re.match(r"[A-Z]+", ref).group(0)
                column = 0
                for letter in letters:
                    column = column * 26 + ord(letter) - 64
                node = cell.find(f"{namespace}v")
                value = node.text if node is not None and node.text is not None else ""
                if cell.attrib.get("t") == "s" and value:
                    value = shared[int(value)]
                values[column - 1] = value
            if values:
                output.append([values.get(index, "") for index in range(max(values) + 1)])
        return output


def parse_bizd(data: bytes) -> dict[str, Any]:
    rows = parse_xlsx(data)
    header_index = next(index for index, row in enumerate(rows) if "Ticker" in row and "% of Net Assets" in row)
    headers = rows[header_index]
    index = {header: position for position, header in enumerate(headers)}
    title = rows[0][0] if rows and rows[0] else ""
    date_match = re.search(r"(\d{2}/\d{2}/\d{4})", title)
    as_of = datetime.strptime(date_match.group(1), "%m/%d/%Y").date().isoformat() if date_match else None
    holdings = []
    for row in rows[header_index + 1:]:
        ticker = row[index["Ticker"]].strip().upper() if len(row) > index["Ticker"] else ""
        if ticker not in TICKERS:
            continue
        get = lambda field: row[index[field]] if len(row) > index[field] else ""
        holdings.append({
            "ticker": ticker,
            "name": get("Holding Name"),
            "figi": get("Identifier (FIGI)"),
            "shares": number(get("Shares")),
            "market_value": number(get("Market Value (US$)")),
            "weight_pct": number(get("% of Net Assets")),
        })
    holdings.sort(key=lambda item: item["weight_pct"] or 0, reverse=True)
    return {"as_of": as_of, "holdings": holdings}


def cached_post(dataset: str, ticker: str, endpoint: str, field: str, max_age_hours: float = 12) -> list[dict[str, Any]]:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    path = CACHE_ROOT / f"{dataset}-{ticker}.json"
    if path.exists() and time.time() - path.stat().st_mtime <= max_age_hours * 3600:
        return json.loads(path.read_text(encoding="utf-8"))
    payload = {"limit": 5000, "compareFilters": [{"compareType": "equal", "fieldName": field, "fieldValue": ticker}]}
    result = request_json_post(endpoint, payload)
    if not isinstance(result, list):
        raise TypeError(f"FINRA {dataset} response was not a list")
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def short_interest() -> dict[str, Any]:
    funds = []
    for ticker in TICKERS:
        rows = cached_post("short-interest", ticker, FINRA_SHORT_INTEREST_URL, "symbolCode")
        by_date: dict[str, dict[str, Any]] = {}
        for row in rows:
            report_date = str(row.get("settlementDate") or "")
            if report_date:
                by_date[report_date] = row
        history = []
        for report_date, row in sorted(by_date.items())[-24:]:
            history.append({
                "settlement_date": report_date,
                "short_interest_shares": number(row.get("currentShortPositionQuantity")),
                "prior_short_interest_shares": number(row.get("previousShortPositionQuantity")),
                "change_pct": number(row.get("changePercent")),
                "average_daily_volume": number(row.get("averageDailyVolumeQuantity")),
                "days_to_cover": number(row.get("daysToCoverQuantity")),
                "revision_flag": row.get("revisionFlag"),
            })
        latest = history[-1] if history else None
        funds.append({"ticker": ticker, "latest": latest, "history": history})
    latest_dates = [item["latest"]["settlement_date"] for item in funds if item["latest"]]
    return {"as_of": max(latest_dates) if latest_dates else None, "funds": funds}


def short_volume() -> dict[str, Any]:
    funds = []
    for ticker in TICKERS:
        rows = cached_post(
            "short-volume", ticker, FINRA_SHORT_VOLUME_URL,
            "securitiesInformationProcessorSymbolIdentifier",
        )
        grouped: dict[str, dict[str, float]] = defaultdict(lambda: {"short": 0, "short_exempt": 0, "total": 0})
        for row in rows:
            report_date = str(row.get("tradeReportDate") or "")
            if report_date:
                grouped[report_date]["short"] += number(row.get("shortParQuantity")) or 0
                grouped[report_date]["short_exempt"] += number(row.get("shortExemptParQuantity")) or 0
                grouped[report_date]["total"] += number(row.get("totalParQuantity")) or 0
        history = []
        for report_date, values in sorted(grouped.items())[-65:]:
            total = values["total"]
            history.append({
                "trade_date": report_date,
                "short_volume": round(values["short"], 4),
                "short_exempt_volume": round(values["short_exempt"], 4),
                "total_volume": round(total, 4),
                "short_volume_ratio_pct": round(values["short"] / total * 100, 4) if total else None,
            })

        def window_ratio(count: int) -> float | None:
            recent = history[-count:]
            total = sum(item["total_volume"] for item in recent)
            return round(sum(item["short_volume"] for item in recent) / total * 100, 4) if total else None

        latest = history[-1] if history else None
        funds.append({
            "ticker": ticker,
            "latest": latest,
            "ratio_5d_pct": window_ratio(5),
            "ratio_20d_pct": window_ratio(20),
            "history": history,
        })
    latest_dates = [item["latest"]["trade_date"] for item in funds if item["latest"]]
    return {"as_of": max(latest_dates) if latest_dates else None, "funds": funds}


def ftd_sort_key(item: dict[str, str]) -> tuple[int, int, int]:
    text = f"{item.get('url', '')} {item.get('label', '')}".lower()
    compact = re.search(r"(20\d{2})(0[1-9]|1[0-2])([ab])", text)
    if compact:
        return int(compact.group(1)), int(compact.group(2)), 2 if compact.group(3) == "b" else 1
    year = re.search(r"20\d{2}", text)
    return int(year.group(0)) if year else 0, 0, 0


def fails_to_deliver(package_limit: int = 8) -> dict[str, Any]:
    links, _ = discover_zip_links(SEC_FTD_PAGE)
    selected = sorted(links, key=ftd_sort_key, reverse=True)[:package_limit]
    observations: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    packages = []
    for link in reversed(selected):
        response = cached_bytes(link["url"], suffix=".zip", max_age_hours=168)
        packages.append({"label": link["label"], "url": link["url"], "bytes": len(response.data)})
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            for name in archive.namelist():
                if name.endswith("/"):
                    continue
                raw = archive.read(name).decode("utf-8-sig", errors="replace")
                reader = csv.DictReader(io.StringIO(raw), delimiter="|")
                for row in reader:
                    ticker = str(row.get("SYMBOL") or "").strip().upper()
                    if ticker not in TICKERS:
                        continue
                    raw_date = str(row.get("SETTLEMENT DATE") or "").strip()
                    if len(raw_date) == 8 and raw_date.isdigit():
                        report_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
                    else:
                        report_date = raw_date
                    quantity = number(row.get("QUANTITY (FAILS)")) or 0
                    price = number(row.get("PRICE"))
                    current = observations[ticker].setdefault(report_date, {
                        "settlement_date": report_date,
                        "fails_shares": 0,
                        "price": price,
                        "fail_value": 0,
                    })
                    current["fails_shares"] += quantity
                    current["fail_value"] += quantity * (price or 0)
    funds = []
    for ticker in TICKERS:
        history = list(sorted(observations[ticker].values(), key=lambda item: item["settlement_date"]))[-90:]
        for item in history:
            item["fails_shares"] = round(item["fails_shares"], 4)
            item["fail_value"] = round(item["fail_value"], 2)
        recent = history[-20:]
        funds.append({
            "ticker": ticker,
            "latest": history[-1] if history else None,
            "average_fails_20obs": round(sum(item["fails_shares"] for item in recent) / len(recent), 2) if recent else None,
            "maximum_fails_20obs": max((item["fails_shares"] for item in recent), default=None),
            "history": history,
        })
    latest_dates = [item["latest"]["settlement_date"] for item in funds if item["latest"]]
    return {"as_of": max(latest_dates) if latest_dates else None, "packages": packages, "funds": funds}


def prior_bizd_history() -> list[dict[str, Any]]:
    if not OUTPUT_PATH.exists():
        return []


def powershell_bizd_download(target: Path) -> bytes:
    if os.name != "nt":
        raise RuntimeError("VanEck PowerShell fallback is available only on Windows")
    target.parent.mkdir(parents=True, exist_ok=True)
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    command = f"Invoke-WebRequest -UseBasicParsing -Uri '{BIZD_URL}' -OutFile '{target}'"
    subprocess.run(
        [str(powershell), "-NoProfile", "-NonInteractive", "-Command", command],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    data = target.read_bytes()
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise ValueError("VanEck fallback did not return a valid XLSX workbook")
    return data
    try:
        prior = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        return prior.get("bizd", {}).get("history", [])
    except (OSError, json.JSONDecodeError):
        return []


def main() -> None:
    statuses = []
    errors = []

    try:
        local_bizd = CACHE_ROOT / "bizd.xlsx"
        if local_bizd.exists() and time.time() - local_bizd.stat().st_mtime <= 12 * 3600:
            workbook_data = local_bizd.read_bytes()
            bizd_refresh_mode = "provider_file_cache"
        else:
            try:
                response = cached_bytes(BIZD_URL, suffix=".xlsx", max_age_hours=12)
                workbook_data = response.data
                CACHE_ROOT.mkdir(parents=True, exist_ok=True)
                local_bizd.write_bytes(workbook_data)
                bizd_refresh_mode = "provider_download"
            except Exception as provider_error:
                try:
                    workbook_data = powershell_bizd_download(local_bizd)
                    bizd_refresh_mode = "provider_download_powershell"
                except Exception:
                    if not local_bizd.exists():
                        raise provider_error
                    workbook_data = local_bizd.read_bytes()
                    bizd_refresh_mode = "provider_file_cache"
        bizd = parse_bizd(workbook_data)
        bizd["refresh_mode"] = bizd_refresh_mode
        snapshot = {"as_of": bizd["as_of"], "holdings": bizd["holdings"]}
        history = prior_bizd_history()
        history = [item for item in history if item.get("as_of") != snapshot["as_of"]]
        history.append(snapshot)
        bizd["history"] = sorted(history, key=lambda item: item.get("as_of") or "")[-365:]
        statuses.append({"id": "bizd", "status": "refreshed", "as_of": bizd["as_of"], "records": len(bizd["holdings"]), "refresh_mode": bizd_refresh_mode})
    except Exception as exc:
        bizd = {"as_of": None, "holdings": [], "history": prior_bizd_history()}
        errors.append(f"BIZD: {safe_error(exc)}")
        statuses.append({"id": "bizd", "status": "error", "as_of": None, "records": 0})

    try:
        interest = short_interest()
        statuses.append({"id": "finra_short_interest", "status": "refreshed", "as_of": interest["as_of"], "records": sum(len(item["history"]) for item in interest["funds"])})
    except Exception as exc:
        interest = {"as_of": None, "funds": []}
        errors.append(f"FINRA short interest: {safe_error(exc)}")
        statuses.append({"id": "finra_short_interest", "status": "error", "as_of": None, "records": 0})

    try:
        volume = short_volume()
        statuses.append({"id": "finra_short_volume", "status": "refreshed", "as_of": volume["as_of"], "records": sum(len(item["history"]) for item in volume["funds"])})
    except Exception as exc:
        volume = {"as_of": None, "funds": []}
        errors.append(f"FINRA short volume: {safe_error(exc)}")
        statuses.append({"id": "finra_short_volume", "status": "error", "as_of": None, "records": 0})

    try:
        ftd = fails_to_deliver()
        statuses.append({"id": "sec_ftd", "status": "refreshed", "as_of": ftd["as_of"], "records": sum(len(item["history"]) for item in ftd["funds"])})
    except Exception as exc:
        ftd = {"as_of": None, "packages": [], "funds": []}
        errors.append(f"SEC FTD: {safe_error(exc)}")
        statuses.append({"id": "sec_ftd", "status": "error", "as_of": None, "records": 0})

    payload = {
        "meta": {
            "generated_at_utc": utc_now(),
            "tickers": list(TICKERS),
            "source_status": statuses,
            "errors": errors,
            "methodology": "Source-direct equity positioning observations are joined only by listed ticker. No composite bearish/bullish score is calculated.",
            "promotion_rule": "Keep outside valuation scores until historical baselines, corporate-action adjustments, and signal usefulness are validated.",
        },
        "bizd": bizd,
        "short_interest": interest,
        "short_volume": volume,
        "fails_to_deliver": ftd,
        "sources": [
            {"name": "VanEck BIZD daily holdings", "url": BIZD_PAGE, "download_url": BIZD_URL, "role": "ETF ownership weight and locally accumulated snapshots"},
            {"name": "FINRA Equity Short Interest", "url": FINRA_SHORT_INTEREST_PAGE, "api_url": FINRA_SHORT_INTEREST_URL, "role": "Twice-monthly consolidated short positions"},
            {"name": "FINRA Short Sale Volume", "url": FINRA_SHORT_VOLUME_PAGE, "api_url": FINRA_SHORT_VOLUME_URL, "role": "Daily off-exchange short-sale volume"},
            {"name": "SEC Fails-to-Deliver Data", "url": SEC_FTD_PAGE, "role": "Half-monthly published settlement fails"},
        ],
        "limitations": [
            "FINRA daily short-sale volume is not short interest and covers only trades reported to specified off-exchange facilities.",
            "Fails-to-deliver can arise from operational or market-making activity and should not be interpreted as proof of naked short selling.",
            "BIZD weight changes become available only after multiple local refresh snapshots and can reflect price moves, creations/redemptions, or portfolio trades.",
            "Ticker joins do not adjust automatically for future symbol changes, mergers, splits, or other corporate actions.",
        ],
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    for status in statuses:
        print(f"{status['id']}: {status['status']} ({status['records']:,} observations; as of {status['as_of']})")
    if errors:
        print("Refresh errors: " + " | ".join(errors))


if __name__ == "__main__":
    main()
