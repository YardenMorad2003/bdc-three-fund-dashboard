from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from lxml import html


DASHBOARD_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = WORKSPACE_ROOT / "output" / "nmfc_holdings" / "source"
DEFAULT_OUTPUT_DB = WORKSPACE_ROOT / "output" / "nmfc_holdings" / "nmfc_all_filings_holdings.sqlite"
SEC_USER_AGENT = "BDC dashboard research contact yarde@example.com"
TOLERANCE_MM = 0.001


@dataclass(frozen=True)
class FilingSpec:
    period: str
    report_type: str
    accession: str
    filename: str

    @property
    def url(self) -> str:
        accession_compact = self.accession.replace("-", "")
        return (
            "https://www.sec.gov/Archives/edgar/data/1496099/"
            f"{accession_compact}/{self.filename}"
        )


FILINGS = (
    FilingSpec("2023-03-31", "10-Q", "0001496099-23-000009", "nmfc-20230331.htm"),
    FilingSpec("2023-06-30", "10-Q", "0001496099-23-000018", "nmfc-20230630.htm"),
    FilingSpec("2023-09-30", "10-Q", "0001496099-23-000028", "nmfc-20230930.htm"),
    FilingSpec("2023-12-31", "10-K", "0001496099-24-000012", "nmfc-20231231.htm"),
    FilingSpec("2024-03-31", "10-Q", "0001496099-24-000023", "nmfc-20240331.htm"),
    FilingSpec("2024-06-30", "10-Q", "0001496099-24-000034", "nmfc-20240630.htm"),
    FilingSpec("2024-09-30", "10-Q", "0001496099-24-000040", "nmfc-20240930.htm"),
    FilingSpec("2024-12-31", "10-K", "0001496099-25-000010", "nmfc-20241231.htm"),
    FilingSpec("2025-03-31", "10-Q", "0001496099-25-000018", "nmfc-20250331.htm"),
    FilingSpec("2025-06-30", "10-Q", "0001496099-25-000027", "nmfc-20250630.htm"),
    FilingSpec("2025-09-30", "10-Q", "0001496099-25-000035", "nmfc-20250930.htm"),
    FilingSpec("2025-12-31", "10-K", "0001496099-26-000008", "nmfc-20251231.htm"),
    FilingSpec("2026-03-31", "10-Q", "0001496099-26-000016", "nmfc-20260331.htm"),
)


SECTION_LABELS = (
    "Non-Controlled/",
    "Non-Controlled ",
    "Controlled Investments",
    "Funded Debt Investments",
    "Unfunded Debt Investments",
    "Equity and Other Investments",
    "Total ",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: str) -> str:
    return " ".join(value.split())


def display_number(element) -> float:
    text = clean_text(element.text_content()).replace(",", "")
    if text in {"", "-", "—"}:
        return 0.0
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return 0.0
    value = float(match.group(0))
    if element.get("sign") == "-" or "(" in text:
        value *= -1
    return value


def fact_element(row, suffix: str):
    for element in row.iterdescendants():
        if (element.get("name") or "").endswith(suffix):
            return element
    return None


def fact_value(row, suffix: str) -> float | None:
    element = fact_element(row, suffix)
    return None if element is None else display_number(element)


def cell_text(cells, index: int | None) -> str:
    if index is None or index >= len(cells):
        return ""
    return clean_text(cells[index].text_content())


def parse_percent(value: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    return float(match.group(0)) if match else None


def strip_footnotes(value: str) -> str:
    return clean_text(re.sub(r"\s*\(\d+\)(?=\s|$)", "", value))


def major_category_from_label(label: str, current: str | None) -> str | None:
    if label.startswith(("Funded Debt Investments", "Unfunded Debt Investments", "Equity and Other Investments")):
        return label
    return current


def is_section_label(label: str) -> bool:
    return not label or label.startswith(SECTION_LABELS)


def primary_schedule_tables(document) -> tuple[list, int, int]:
    tables = document.xpath("//table")
    header_indices = []
    for index, table in enumerate(tables):
        text = clean_text(table.text_content())
        if text.startswith("Portfolio Company, Location and Industry"):
            header_indices.append(index)
    if not header_indices:
        raise RuntimeError("Primary Schedule of Investments header was not found")

    start = header_indices[0]
    end = start
    while end + 1 in header_indices:
        end += 1
    block = tables[start : end + 1]
    if "Total Investments" not in clean_text(block[-1].text_content()):
        raise RuntimeError(f"Primary schedule block {start}-{end} has no Total Investments row")
    return block, start, end


def header_positions(table) -> dict[str, int]:
    for row in table.xpath(".//tr"):
        cells = row.xpath("./th|./td")
        labels = {clean_text(cell.text_content()): index for index, cell in enumerate(cells)}
        instrument = next((index for text, index in labels.items() if "Type of" in text and "Investment" in text), None)
        if instrument is None:
            continue
        return {
            "company": next(index for text, index in labels.items() if text.startswith("Portfolio Company")),
            "instrument": instrument,
            "reference": next(index for text, index in labels.items() if text.startswith("Reference")),
            "spread": next(index for text, index in labels.items() if text.startswith("Spread")),
            "coupon": next(
                index
                for text, index in labels.items()
                if text.startswith("Total Coupon") or text.startswith("Interest Rate")
            ),
            "acquisition": next(index for text, index in labels.items() if text.startswith("Acquisition")),
            "maturity": next(index for text, index in labels.items() if text.startswith("Maturity")),
        }
    raise RuntimeError("Schedule header positions were not found")


def amount_currency(row, amount_element, reference: str) -> str | None:
    row_text = clean_text(row.text_content())
    reference_upper = reference.upper()
    if "€" in row_text or reference_upper.startswith("EURIBOR"):
        return "EUR"
    if "£" in row_text or reference_upper.startswith(("SONIA", "GBP")):
        return "GBP"
    return "USD" if "$" in row_text or amount_element is not None else None


def parse_schedule(spec: FilingSpec, source_path: Path) -> tuple[list[dict], dict]:
    document = html.parse(str(source_path))
    tables, table_start, table_end = primary_schedule_tables(document)
    positions = header_positions(tables[0])
    current_issuer: str | None = None
    current_industry: str | None = None
    current_category: str | None = None
    holdings: list[dict] = []

    for table_index, table in enumerate(tables, start=table_start):
        positions = header_positions(table)
        for row_index, row in enumerate(table.xpath(".//tr"), start=1):
            cells = row.xpath("./th|./td")
            if not cells:
                continue
            label = cell_text(cells, positions["company"])
            instrument = cell_text(cells, positions["instrument"])

            if not instrument:
                current_category = major_category_from_label(label, current_category)
                if label and not is_section_label(label):
                    current_issuer = strip_footnotes(label)
                continue
            if "Type of" in instrument and "Investment" in instrument:
                continue
            if current_issuer is None:
                raise RuntimeError(f"Holding row without issuer at table {table_index}, row {row_index}")

            if label:
                current_industry = label
            amount = fact_element(row, "InvestmentOwnedBalancePrincipalAmount")
            amount_kind = "principal_amount"
            if amount is None:
                amount = fact_element(row, "InvestmentOwnedBalanceShares")
                amount_kind = "number_of_shares"
            amount_value = display_number(amount) if amount is not None else None
            cost_thousands = fact_value(row, "InvestmentOwnedAtCost")
            fair_value_thousands = fact_value(row, "InvestmentOwnedAtFairValue")
            pct_net_assets = fact_value(row, "InvestmentOwnedPercentOfNetAssets")
            if cost_thousands is None and fair_value_thousands is None:
                continue

            reference = cell_text(cells, positions["reference"])
            spread_raw = cell_text(cells, positions["spread"])
            coupon_raw = cell_text(cells, positions["coupon"])
            instrument_clean = strip_footnotes(instrument)
            is_fixed = reference.upper().startswith("FIXED")
            holdings.append(
                {
                    "filing_key": f"nmfc_{spec.period}",
                    "accession": spec.accession,
                    "report_type": spec.report_type,
                    "filing_period_end": spec.period,
                    "as_of_date": spec.period,
                    "primary_period": 1,
                    "company": current_issuer,
                    "company_raw": current_issuer,
                    "industry": current_industry,
                    "major_category": current_category,
                    "instrument_type": instrument_clean,
                    "investment_description": instrument,
                    "interest_rate": coupon_raw if coupon_raw not in {"", "—"} else None,
                    "reference_rate_and_spread": " ".join(part for part in (reference, spread_raw) if part and part != "—") or None,
                    "reference_base_rate": reference if reference not in {"", "—"} else None,
                    "spread_pct": parse_percent(spread_raw),
                    "fixed_coupon_pct": parse_percent(coupon_raw) if is_fixed else None,
                    "is_fixed": 1 if is_fixed else 0,
                    "pik_rate_pct": parse_percent(coupon_raw) if "PIK" in coupon_raw.upper() else None,
                    "acquisition_date": cell_text(cells, positions["acquisition"]),
                    "maturity": cell_text(cells, positions["maturity"]),
                    "amount_kind": amount_kind if amount is not None else None,
                    "amount_currency": amount_currency(row, amount, reference) if amount_kind == "principal_amount" else None,
                    "amount_value": amount_value,
                    "amortized_cost_mm": (cost_thousands or 0.0) / 1000.0,
                    "fair_value_mm": (fair_value_thousands or 0.0) / 1000.0,
                    "percentage_of_net_assets": pct_net_assets,
                    "is_unfunded_commitment": 1 if "undrawn" in instrument.lower() else 0,
                    "source_sheet": f"html_table_{table_index}",
                    "source_row_number": row_index,
                    "source_db_name": DEFAULT_OUTPUT_DB.name,
                    "raw_values_json": json.dumps(
                        {
                            "label": label,
                            "instrument": instrument,
                            "reference": reference,
                            "spread": spread_raw,
                            "coupon": coupon_raw,
                            "source_url": spec.url,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                }
            )

    schedule_text = clean_text(tables[-1].text_content())
    total_match = re.search(
        r"Total Investments.*?\$\s*([\d,()]+).*?\$\s*([\d,()]+)",
        schedule_text,
    )
    if not total_match:
        raise RuntimeError("Reported Total Investments values were not found")
    reported_cost_mm = display_text_number(total_match.group(1)) / 1000.0
    reported_fair_value_mm = display_text_number(total_match.group(2)) / 1000.0
    parsed_cost_mm = sum(row["amortized_cost_mm"] for row in holdings)
    parsed_fair_value_mm = sum(row["fair_value_mm"] for row in holdings)
    reconciliation = {
        "filing_key": f"nmfc_{spec.period}",
        "accession": spec.accession,
        "report_type": spec.report_type,
        "filing_period_end": spec.period,
        "as_of_date": spec.period,
        "check_name": "primary_schedule_detail_to_total_investments",
        "status": "ok" if abs(parsed_cost_mm - reported_cost_mm) <= TOLERANCE_MM and abs(parsed_fair_value_mm - reported_fair_value_mm) <= TOLERANCE_MM else "review",
        "reported_cost_mm": reported_cost_mm,
        "parsed_cost_mm": parsed_cost_mm,
        "cost_delta_mm": parsed_cost_mm - reported_cost_mm,
        "reported_fair_value_mm": reported_fair_value_mm,
        "parsed_fair_value_mm": parsed_fair_value_mm,
        "fair_value_delta_mm": parsed_fair_value_mm - reported_fair_value_mm,
        "holding_rows": len(holdings),
        "table_start": table_start,
        "table_end": table_end,
    }
    return holdings, reconciliation


def display_text_number(value: str) -> float:
    clean = value.replace(",", "").strip()
    number = float(re.sub(r"[^0-9.]", "", clean) or 0)
    return -number if clean.startswith("(") else number


def ensure_source(spec: FilingSpec, source_dir: Path, download: bool) -> Path:
    source_dir.mkdir(parents=True, exist_ok=True)
    path = source_dir / spec.filename
    if path.exists():
        return path
    temp_candidate = Path("C:/tmp") / spec.filename
    if temp_candidate.exists():
        return temp_candidate
    if not download:
        raise FileNotFoundError(f"Missing {path}; rerun with --download")
    request = urllib.request.Request(spec.url, headers={"User-Agent": SEC_USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    path.write_bytes(payload)
    time.sleep(0.15)
    return path


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        create table filings (
            id integer primary key,
            filing_key text not null unique,
            accession text not null unique,
            company text not null,
            ticker text not null,
            report_type text not null,
            filing_period_end text not null,
            source_filename text not null,
            source_path text not null,
            source_units text not null,
            normalized_units text not null,
            notes text
        );

        create table holdings (
            combined_detail_id integer primary key,
            source_filing_id integer not null,
            filing_key text not null,
            accession text not null,
            report_type text not null,
            filing_period_end text not null,
            as_of_date text not null,
            primary_period integer not null,
            company text not null,
            company_raw text not null,
            industry text,
            major_category text,
            instrument_type text,
            investment_description text,
            interest_rate text,
            reference_rate_and_spread text,
            reference_base_rate text,
            spread_pct real,
            fixed_coupon_pct real,
            is_fixed integer,
            pik_rate_pct real,
            acquisition_date text,
            maturity text,
            amount_kind text,
            amount_currency text,
            amount_value real,
            amortized_cost_mm real not null,
            fair_value_mm real not null,
            percentage_of_net_assets real,
            is_unfunded_commitment integer not null,
            source_sheet text not null,
            source_row_number integer not null,
            source_db_name text not null,
            raw_values_json text not null,
            foreign key (source_filing_id) references filings(id)
        );

        create table reconciliation_checks (
            id integer primary key,
            filing_key text not null,
            accession text not null,
            report_type text not null,
            filing_period_end text not null,
            as_of_date text not null,
            check_name text not null,
            status text not null,
            reported_cost_mm real not null,
            parsed_cost_mm real not null,
            cost_delta_mm real not null,
            reported_fair_value_mm real not null,
            parsed_fair_value_mm real not null,
            fair_value_delta_mm real not null,
            holding_rows integer not null,
            table_start integer not null,
            table_end integer not null,
            expected text,
            actual text,
            delta_mm real,
            tolerance_mm real not null,
            details_json text not null
        );

        create table qc_results (
            id integer primary key,
            check_name text not null,
            status text not null,
            expected text,
            actual text,
            details_json text not null
        );

        create view primary_holdings as
        select
            h.*,
            h.combined_detail_id as source_detail_id,
            h.combined_detail_id as combined_raw_row_id
        from holdings h;
        """
    )


def insert_dicts(connection: sqlite3.Connection, table: str, rows: Iterable[dict]) -> None:
    rows = list(rows)
    if not rows:
        return
    columns = list(rows[0])
    placeholders = ", ".join("?" for _ in columns)
    connection.executemany(
        f"insert into {table} ({', '.join(columns)}) values ({placeholders})",
        [[row[column] for column in columns] for row in rows],
    )


def build(source_dir: Path, output_db: Path, download: bool) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    if output_db.exists():
        output_db.unlink()
    connection = sqlite3.connect(output_db)
    try:
        create_schema(connection)
        all_reconciliations = []
        for spec in FILINGS:
            source_path = ensure_source(spec, source_dir, download)
            holdings, reconciliation = parse_schedule(spec, source_path)
            if reconciliation["status"] != "ok":
                raise RuntimeError(f"{spec.period} failed reconciliation: {reconciliation}")
            cursor = connection.execute(
                """
                insert into filings (
                    filing_key, accession, company, ticker, report_type, filing_period_end,
                    source_filename, source_path, source_units, normalized_units, notes
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"nmfc_{spec.period}", spec.accession, "New Mountain Finance Corporation", "NMFC",
                    spec.report_type, spec.period, spec.filename, str(source_path), "USD thousands",
                    "USD millions", "Dedicated primary Schedule of Investments HTML extraction; supplemental joint-venture schedules excluded.",
                ),
            )
            filing_id = cursor.lastrowid
            for holding in holdings:
                holding["source_filing_id"] = filing_id
            insert_dicts(connection, "holdings", holdings)
            details = json.dumps(reconciliation, sort_keys=True)
            insert_dicts(
                connection,
                "reconciliation_checks",
                [{
                    **reconciliation,
                    "expected": f"cost={reconciliation['reported_cost_mm']:.3f}; fair_value={reconciliation['reported_fair_value_mm']:.3f}",
                    "actual": f"cost={reconciliation['parsed_cost_mm']:.3f}; fair_value={reconciliation['parsed_fair_value_mm']:.3f}",
                    "delta_mm": reconciliation["fair_value_delta_mm"],
                    "tolerance_mm": TOLERANCE_MM,
                    "details_json": details,
                }],
            )
            all_reconciliations.append(reconciliation)

        integrity = connection.execute("pragma integrity_check").fetchone()[0]
        insert_dicts(
            connection,
            "qc_results",
            [
                {"check_name": "sqlite_integrity_check", "status": "ok" if integrity == "ok" else "review", "expected": "ok", "actual": integrity, "details_json": "{}"},
                {"check_name": "all_primary_schedules_reconcile", "status": "ok", "expected": str(len(FILINGS)), "actual": str(sum(item["status"] == "ok" for item in all_reconciliations)), "details_json": json.dumps(all_reconciliations, sort_keys=True)},
            ],
        )
        connection.commit()
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a reconciled NMFC holdings database from SEC filing HTML.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-db", type=Path, default=DEFAULT_OUTPUT_DB)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    build(args.source_dir, args.output_db, args.download)
    print(f"Built {args.output_db.name}")


if __name__ == "__main__":
    main()
