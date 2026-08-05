from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from lxml import html


DASHBOARD_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = WORKSPACE_ROOT / "output" / "multi_bdc_holdings" / "source"
SEC_USER_AGENT = "BDC dashboard research contact yarde@example.com"
TOLERANCE_MM = 0.001


@dataclass(frozen=True)
class FilingSpec:
    fund: str
    company: str
    cik: int
    period: str
    report_type: str
    accession: str
    filename: str
    table_start: int
    table_end: int
    source_divisor: float
    reported_cost_mm: float
    reported_fair_value_mm: float

    @property
    def url(self) -> str:
        return (
            f"https://www.sec.gov/Archives/edgar/data/{self.cik}/"
            f"{self.accession.replace('-', '')}/{self.filename}"
        )

    @property
    def output_db(self) -> Path:
        stem = self.fund.lower()
        return WORKSPACE_ROOT / "output" / f"{stem}_holdings" / f"{stem}_all_filings_holdings.sqlite"


FILINGS = (
    FilingSpec("BCSF", "Bain Capital Specialty Finance, Inc.", 1655050, "2026-03-31", "10-Q", "0001193125-26-217068", "bcsf-20260331.htm", 12, 28, 1000.0, 2482.858, 2470.798),
    FilingSpec("CCAP", "Crescent Capital BDC, Inc.", 1633336, "2026-03-31", "10-Q", "0001193125-26-221936", "ccap-20260331.htm", 9, 44, 1000.0, 1618.654, 1562.470),
    FilingSpec("CSWC", "Capital Southwest Corporation", 17313, "2026-03-31", "10-K", "0000017313-26-000035", "cswc-20260331.htm", 35, 59, 1000.0, 2119.485, 2097.446),
    FilingSpec("HTGC", "Hercules Capital, Inc.", 1280784, "2026-03-31", "10-Q", "0001280784-26-000027", "htgc-20260331.htm", 12, 26, 1000.0, 4770.369, 4721.987),
    FilingSpec("HTGC", "Hercules Capital, Inc.", 1280784, "2026-06-30", "10-Q", "0001280784-26-000042", "htgc-20260630.htm", 12, 26, 1000.0, 4603.266, 4583.870),
    FilingSpec("OCSL", "Oaktree Specialty Lending Corporation", 1414932, "2026-03-31", "10-Q", "0001414932-26-000012", "ocsl-20260331.htm", 10, 19, 1000.0, 3067.902, 2766.367),
    FilingSpec("OCSL", "Oaktree Specialty Lending Corporation", 1414932, "2026-06-30", "10-Q", "0001414932-26-000017", "ocsl-20260630.htm", 10, 19, 1000.0, 2996.697, 2741.814),
    FilingSpec("PSEC", "Prospect Capital Corporation", 1287032, "2026-03-31", "10-Q", "0001287032-26-000164", "psec-20260331.htm", 17, 29, 1000.0, 6192.901, 6302.465),
    FilingSpec("TCPC", "BlackRock TCP Capital Corp.", 1370755, "2026-03-31", "10-Q", "0001193125-26-210632", "tcpc-20260331.htm", 11, 21, 1_000_000.0, 1535.496962, 1388.668517),
)


def clean_text(value: str) -> str:
    return " ".join(value.split())


def strip_footnotes(value: str) -> str:
    return clean_text(re.sub(r"(?:\s*\(\d+\))+$", "", value))


def number_from_text(value: str) -> float | None:
    text = "".join(value.split()).replace(",", "")
    if text in {"", "-", "—", "$", "%"}:
        return None
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    return -number if text.startswith("-") or "(" in text else number


def fact_element(row, suffix: str):
    for element in row.iterdescendants():
        if (element.get("name") or "").endswith(suffix):
            return element
    return None


def fact_value(row, suffix: str) -> float | None:
    element = fact_element(row, suffix)
    if element is None:
        return None
    value = number_from_text(clean_text(element.text_content())) or 0.0
    return -abs(value) if element.get("sign") == "-" else value


def fact_text(row, *suffixes: str) -> str | None:
    for suffix in suffixes:
        element = fact_element(row, suffix)
        if element is not None:
            text = clean_text(element.text_content())
            if text and text != "—":
                return text
    return None


def fallback_cell_number(texts: list[str], indices: tuple[int, ...]) -> float:
    for index in indices:
        if index < len(texts):
            value = number_from_text(texts[index])
            if value is not None:
                return value
    return 0.0


def layout_indices(fund: str, table_index: int) -> tuple[int, int | None]:
    if fund == "CSWC" and table_index >= 52:
        return 5, 6
    if fund in {"BCSF", "CSWC", "OCSL", "PSEC", "TCPC"}:
        return 2, None
    return 1, None


def detail_identity(
    fund: str,
    table_index: int,
    texts: list[str],
) -> tuple[str, str, str | None]:
    company = texts[0] if texts else ""
    instrument_index, fallback_index = layout_indices(fund, table_index)
    instrument = texts[instrument_index] if instrument_index < len(texts) else ""
    if fallback_index is not None and not instrument and fallback_index < len(texts):
        instrument = texts[fallback_index]
    industry = None
    if fund in {"OCSL", "PSEC"} and len(texts) > 1:
        industry = texts[1] or None
    if fund == "PSEC" and (not instrument or re.match(r"^\d", instrument)) and company:
        instrument = company
        company = ""
    return company, instrument, industry


def reference_rate(row_text: str) -> str | None:
    upper = row_text.upper()
    for label, normalized in (
        ("EURIBOR", "EURIBOR"),
        ("SONIA", "SONIA"),
        ("SOFR", "SOFR"),
        ("PRIME", "Prime"),
        ("FIXED", "Fixed"),
    ):
        if label in upper:
            return normalized
    return None


def amount_currency(row_text: str, reference: str | None) -> str | None:
    if "€" in row_text or reference == "EURIBOR":
        return "EUR"
    if "£" in row_text or reference == "SONIA":
        return "GBP"
    if "AUD" in row_text:
        return "AUD"
    if "CAD" in row_text:
        return "CAD"
    return "USD"


def section_label(label: str) -> str | None:
    lower = label.lower()
    if "debt investments" in lower:
        return "Debt Investments"
    if "equity" in lower and "investments" in lower:
        return "Equity Investments"
    if "other financial instruments" in lower:
        return "Other Financial Instruments"
    if "controlled affiliate investments" in lower:
        return "Controlled Affiliate Investments"
    if "non-control" in lower and "investments" in lower:
        return "Non-Controlled Investments"
    return None


def parse_filing(spec: FilingSpec, source_path: Path) -> tuple[list[dict], dict]:
    document = html.parse(str(source_path))
    tables = document.xpath("//table")
    rows: list[dict] = []
    current_issuer: str | None = None
    current_industry: str | None = None
    current_category: str | None = None

    for table_index in range(spec.table_start, spec.table_end + 1):
        table = tables[table_index]
        for row_index, row in enumerate(table.xpath(".//tr"), start=1):
            cells = row.xpath("./th|./td")
            texts = [clean_text(cell.text_content()) for cell in cells]
            meaningful = [text for text in texts if text]
            company, instrument, row_industry = detail_identity(spec.fund, table_index, texts)
            cost_source = fact_value(row, "InvestmentOwnedAtCost")
            fair_value_source = fact_value(row, "InvestmentOwnedAtFairValue")

            # OCSL's June 2026 filing leaves this investment-type cell blank;
            # the prior-quarter schedule identifies the same security.
            if (
                spec.fund == "OCSL"
                and spec.period == "2026-06-30"
                and company == "Fairbridge Strategic Capital Funding LLC"
                and not instrument
                and cost_source is not None
            ):
                instrument = "First Lien Term Loan"

            if cost_source is None and fair_value_source is None:
                if len(meaningful) == 1:
                    label = meaningful[0]
                    category = section_label(label)
                    if category:
                        current_category = category
                    elif not any(token in label.lower() for token in ("schedule of investments", "portfolio company", "total", "investments")):
                        current_industry = strip_footnotes(label)
                continue

            lowered_instrument = instrument.lower()
            if (
                not instrument
                or lowered_instrument.startswith(("type of", "investment type", "total", "subtotal"))
                or "cash equivalent" in lowered_instrument
            ):
                continue

            if company and not company.lower().startswith(("total", "subtotal")):
                current_issuer = strip_footnotes(company)
            if current_issuer is None:
                raise RuntimeError(
                    f"{spec.fund} {spec.period}: holding without issuer at table {table_index}, row {row_index}"
                )
            if row_industry:
                current_industry = strip_footnotes(row_industry)

            if spec.fund == "BCSF" and fair_value_source is None:
                fair_value_source = fallback_cell_number(texts, (24, 23))
            if spec.fund == "CCAP" and fair_value_source is None:
                fair_value_source = fallback_cell_number(texts, (18,))

            principal = fact_element(row, "InvestmentOwnedBalancePrincipalAmount")
            shares = fact_element(row, "InvestmentOwnedBalanceShares")
            amount = principal if principal is not None else shares
            amount_kind = "principal_amount" if principal is not None else "number_of_shares" if shares is not None else None
            amount_value = (
                number_from_text(clean_text(amount.text_content())) if amount is not None else None
            )
            row_text = clean_text(row.text_content())
            reference = reference_rate(row_text)
            spread = fact_value(row, "InvestmentBasisSpreadVariableRate")
            if spread is not None and spread > 50:
                spread /= 100.0
            coupon = fact_value(row, "InvestmentInterestRate")
            pik = fact_value(row, "InvestmentInterestRatePaidInKind")
            pct_net_assets = fact_value(row, "InvestmentOwnedPercentOfNetAssets")
            is_unfunded = bool(
                amount_kind == "principal_amount"
                and (amount_value is None or amount_value == 0)
                and (cost_source or 0) <= 0
                and any(term in lowered_instrument for term in ("revolver", "delayed draw"))
            )
            rows.append(
                {
                    "source_filing_id": None,
                    "filing_key": f"{spec.fund.lower()}_{spec.period}",
                    "accession": spec.accession,
                    "report_type": spec.report_type,
                    "filing_period_end": spec.period,
                    "as_of_date": spec.period,
                    "primary_period": 1,
                    "company": current_issuer,
                    "company_raw": current_issuer,
                    "industry": current_industry,
                    "major_category": current_category,
                    "instrument_type": strip_footnotes(instrument),
                    "investment_description": instrument,
                    "interest_rate": f"{coupon:g}%" if coupon is not None else None,
                    "reference_rate_and_spread": (
                        f"{reference} + {spread:g}%" if reference and spread is not None else reference
                    ),
                    "reference_base_rate": reference,
                    "spread_pct": spread,
                    "fixed_coupon_pct": coupon if reference == "Fixed" else None,
                    "is_fixed": 1 if reference == "Fixed" else 0,
                    "pik_rate_pct": pik,
                    "maturity": fact_text(row, "InvestmentMaturityDate", "InvestmentsMaturityMonthAndYear"),
                    "amount_kind": amount_kind,
                    "amount_currency": amount_currency(row_text, reference) if amount_kind == "principal_amount" else None,
                    "amount_value": amount_value,
                    "amortized_cost_mm": (cost_source or 0.0) / spec.source_divisor,
                    "fair_value_mm": (fair_value_source or 0.0) / spec.source_divisor,
                    "percentage_of_net_assets": pct_net_assets,
                    "is_unfunded_commitment": 1 if is_unfunded else 0,
                    "source_sheet": f"html_table_{table_index}",
                    "source_row_number": row_index,
                    "source_db_name": spec.output_db.name,
                    "raw_values_json": json.dumps(
                        {
                            "cells": meaningful,
                            "source_url": spec.url,
                            "table_index": table_index,
                            "row_index": row_index,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                }
            )

    parsed_cost_mm = sum(row["amortized_cost_mm"] for row in rows)
    parsed_fair_value_mm = sum(row["fair_value_mm"] for row in rows)
    reconciliation = {
        "filing_key": f"{spec.fund.lower()}_{spec.period}",
        "accession": spec.accession,
        "report_type": spec.report_type,
        "filing_period_end": spec.period,
        "as_of_date": spec.period,
        "check_name": "primary_schedule_detail_to_total_investments",
        "status": "ok" if abs(parsed_cost_mm - spec.reported_cost_mm) <= TOLERANCE_MM and abs(parsed_fair_value_mm - spec.reported_fair_value_mm) <= TOLERANCE_MM else "review",
        "reported_cost_mm": spec.reported_cost_mm,
        "parsed_cost_mm": parsed_cost_mm,
        "cost_delta_mm": parsed_cost_mm - spec.reported_cost_mm,
        "reported_fair_value_mm": spec.reported_fair_value_mm,
        "parsed_fair_value_mm": parsed_fair_value_mm,
        "fair_value_delta_mm": parsed_fair_value_mm - spec.reported_fair_value_mm,
        "holding_rows": len(rows),
        "table_start": spec.table_start,
        "table_end": spec.table_end,
    }
    return rows, reconciliation


def ensure_source(spec: FilingSpec, source_dir: Path, download: bool) -> Path:
    source_dir.mkdir(parents=True, exist_ok=True)
    path = source_dir / spec.filename
    if path.exists():
        return path
    if not download:
        raise FileNotFoundError(f"Missing {path}; rerun with --download")
    request = urllib.request.Request(spec.url, headers={"User-Agent": SEC_USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        path.write_bytes(response.read())
    time.sleep(0.15)
    return path


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        create table filings (
            id integer primary key, filing_key text not null unique, accession text not null unique,
            company text not null, ticker text not null, report_type text not null,
            filing_period_end text not null, source_filename text not null, source_path text not null,
            source_units text not null, normalized_units text not null, notes text
        );
        create table holdings (
            combined_detail_id integer primary key, source_filing_id integer not null,
            filing_key text not null, accession text not null, report_type text not null,
            filing_period_end text not null, as_of_date text not null, primary_period integer not null,
            company text not null, company_raw text not null, industry text, major_category text,
            instrument_type text, investment_description text, interest_rate text,
            reference_rate_and_spread text, reference_base_rate text, spread_pct real,
            fixed_coupon_pct real, is_fixed integer, pik_rate_pct real, maturity text,
            amount_kind text, amount_currency text, amount_value real,
            amortized_cost_mm real not null, fair_value_mm real not null,
            percentage_of_net_assets real, is_unfunded_commitment integer not null,
            source_sheet text not null, source_row_number integer not null,
            source_db_name text not null, raw_values_json text not null,
            foreign key (source_filing_id) references filings(id)
        );
        create table reconciliation_checks (
            id integer primary key, filing_key text not null, accession text not null,
            report_type text not null, filing_period_end text not null, as_of_date text not null,
            check_name text not null, status text not null, reported_cost_mm real not null,
            parsed_cost_mm real not null, cost_delta_mm real not null,
            reported_fair_value_mm real not null, parsed_fair_value_mm real not null,
            fair_value_delta_mm real not null, holding_rows integer not null,
            table_start integer not null, table_end integer not null, expected text,
            actual text, delta_mm real, tolerance_mm real not null, details_json text not null
        );
        create table qc_results (
            id integer primary key, check_name text not null, status text not null,
            expected text, actual text, details_json text not null
        );
        create view primary_holdings as
        select h.*, h.combined_detail_id as source_detail_id,
               h.combined_detail_id as combined_raw_row_id
        from holdings h;
        """
    )


def insert_dicts(connection: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    columns = list(rows[0])
    placeholders = ", ".join("?" for _ in columns)
    connection.executemany(
        f"insert into {table} ({', '.join(columns)}) values ({placeholders})",
        [[row[column] for column in columns] for row in rows],
    )


def build_fund(fund: str, specs: list[FilingSpec], source_dir: Path, download: bool) -> tuple[int, list[dict]]:
    output_db = specs[0].output_db
    output_db.parent.mkdir(parents=True, exist_ok=True)
    resolved_output = output_db.resolve()
    expected_parent = (WORKSPACE_ROOT / "output").resolve()
    if expected_parent not in resolved_output.parents:
        raise RuntimeError(f"Refusing to replace database outside output: {resolved_output}")
    if output_db.exists():
        output_db.unlink()
    connection = sqlite3.connect(output_db)
    reconciliations: list[dict] = []
    total_rows = 0
    try:
        create_schema(connection)
        for spec in specs:
            source_path = ensure_source(spec, source_dir, download)
            holdings, reconciliation = parse_filing(spec, source_path)
            if reconciliation["status"] != "ok":
                raise RuntimeError(f"{fund} {spec.period} failed reconciliation: {reconciliation}")
            cursor = connection.execute(
                """insert into filings (
                    filing_key, accession, company, ticker, report_type, filing_period_end,
                    source_filename, source_path, source_units, normalized_units, notes
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"{fund.lower()}_{spec.period}", spec.accession, spec.company, fund,
                    spec.report_type, spec.period, spec.filename, str(source_path),
                    "USD thousands" if spec.source_divisor == 1000 else "USD",
                    "USD millions", "Dedicated primary Schedule of Investments HTML extraction.",
                ),
            )
            for holding in holdings:
                holding["source_filing_id"] = cursor.lastrowid
            insert_dicts(connection, "holdings", holdings)
            details = json.dumps(reconciliation, sort_keys=True)
            insert_dicts(
                connection,
                "reconciliation_checks",
                [{
                    **reconciliation,
                    "expected": f"cost={reconciliation['reported_cost_mm']:.6f}; fair_value={reconciliation['reported_fair_value_mm']:.6f}",
                    "actual": f"cost={reconciliation['parsed_cost_mm']:.6f}; fair_value={reconciliation['parsed_fair_value_mm']:.6f}",
                    "delta_mm": reconciliation["fair_value_delta_mm"],
                    "tolerance_mm": TOLERANCE_MM,
                    "details_json": details,
                }],
            )
            reconciliations.append(reconciliation)
            total_rows += len(holdings)
        integrity = connection.execute("pragma integrity_check").fetchone()[0]
        insert_dicts(connection, "qc_results", [
            {"check_name": "sqlite_integrity_check", "status": "ok" if integrity == "ok" else "review", "expected": "ok", "actual": integrity, "details_json": "{}"},
            {"check_name": "all_primary_schedules_reconcile", "status": "ok", "expected": str(len(specs)), "actual": str(len(reconciliations)), "details_json": json.dumps(reconciliations, sort_keys=True)},
        ])
        connection.commit()
    finally:
        connection.close()
    return total_rows, reconciliations


def main() -> None:
    parser = argparse.ArgumentParser(description="Build reconciled current holdings databases for tracked BDCs.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    funds = sorted({spec.fund for spec in FILINGS})
    for fund in funds:
        specs = [spec for spec in FILINGS if spec.fund == fund]
        rows, reconciliations = build_fund(fund, specs, args.source_dir, args.download)
        periods = ", ".join(item["filing_period_end"] for item in reconciliations)
        print(f"{fund}: {rows} rows across {periods}; all schedules reconciled")


if __name__ == "__main__":
    main()
