from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DASHBOARD_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = WORKSPACE_ROOT / "output" / "bdc_tracker_centralized" / "bdc_tracker_holdings.sqlite"
OUTPUT_PATH = DASHBOARD_ROOT / "lib" / "dashboard-data.json"

FUNDS = ["ARCC", "BBDC", "BXSL", "FSK", "GBDC", "MAIN", "OBDC", "TSLX"]
FUND_NAMES = {
    "ARCC": "Ares Capital Corporation",
    "BBDC": "Barings BDC, Inc.",
    "BXSL": "Blackstone Secured Lending Fund",
    "FSK": "FS KKR Capital Corp.",
    "GBDC": "Golub Capital BDC, Inc.",
    "MAIN": "Main Street Capital Corporation",
    "OBDC": "Blue Owl Capital Corporation",
    "TSLX": "Sixth Street Specialty Lending, Inc.",
}
TIMELINE_ISSUER_LIMIT = 200

# The generic issuer normalizer intentionally strips acquisition-vehicle suffixes,
# but a handful of short names become false matches when the remaining token is
# too generic. Keep these evidence-reviewed exceptions close to the dashboard
# export so every derived Exposure and Timeline aggregate uses the corrected key.
ISSUER_MATCH_KEY_OVERRIDES = {
    "Continental Buyer, Inc.": "CONTINENTAL BUYER",
    "Continental Buyer Inc": "CONTINENTAL BUYER",
    "Continental Finance Company, LLC": "CONTINENTAL FINANCE",
    "Minerva Bidco, Ltd.": "MINERVA BIDCO",
    "Minerva Holdco, Inc.": "MINERVA HOLDCO",
}

CATEGORY_EXPR = """
case
    when fund = 'TSLX' then
        case
            when lower(coalesce(instrument_type, '')) like '%first-lien%'
              or lower(coalesce(instrument_type, '')) like '%first lien%'
              or lower(coalesce(instrument_type, '')) like '%filo%'
              or lower(coalesce(instrument_type, '')) like '%dip term loan%'
              then 'First Lien Debt'
            when lower(coalesce(instrument_type, '')) like '%second-lien%'
              or lower(coalesce(instrument_type, '')) like '%second lien%'
              then 'Second Lien Debt'
            when lower(coalesce(instrument_type, '')) like '%structured credit%'
              or lower(coalesce(instrument_type, '')) like 'class % units'
              or lower(coalesce(instrument_type, '')) like '%trust certificates%'
              then 'Structured Credit / ABS'
            when lower(coalesce(instrument_type, '')) like '%common%'
              or lower(coalesce(instrument_type, '')) like '%preferred%'
              or lower(coalesce(instrument_type, '')) like '%preference%'
              or lower(coalesce(instrument_type, '')) like '%partnership%'
              or lower(coalesce(instrument_type, '')) like '%membership%'
              or lower(coalesce(instrument_type, '')) like '%warrants%'
              or lower(coalesce(instrument_type, '')) like '%shares%'
              or lower(coalesce(instrument_type, '')) like '%units%'
              or lower(coalesce(instrument_type, '')) like '%interests%'
              then 'Equity / Other'
            when lower(coalesce(instrument_type, '')) like '%promissory note%'
              then 'Other Debt'
            else 'Other Investments'
        end
    when lower(coalesce(investment_category, '')) like '%first lien%' then 'First Lien Debt'
    when lower(coalesce(investment_category, '')) like '%second lien%' then 'Second Lien Debt'
    when lower(coalesce(investment_category, '')) like '%asset based%' then 'Asset Based Finance'
    when lower(coalesce(investment_category, '')) like '%subordinated%' then 'Subordinated Debt'
    when lower(coalesce(investment_category, '')) like '%unsecured%' then 'Unsecured Debt'
    when lower(coalesce(investment_category, '')) like '%equity%' then 'Equity / Other'
    when lower(coalesce(investment_category, '')) like '%credit opportunities partners jv%' then 'Joint Venture / Other'
    when trim(coalesce(investment_category, '')) <> '' then investment_category
    else 'Uncategorized'
end
"""


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    install_issuer_match_key_overrides(con)
    return con


def install_issuer_match_key_overrides(con: sqlite3.Connection) -> None:
    """Shadow issuer-key views in TEMP with reviewed collision corrections."""

    def resolved_key(issuer_name: str | None, issuer_match_key: str | None) -> str | None:
        return ISSUER_MATCH_KEY_OVERRIDES.get(issuer_name or "", issuer_match_key)

    con.create_function("resolved_issuer_match_key", 2, resolved_key, deterministic=True)

    columns = [row[1] for row in con.execute("pragma main.table_info(security_level_holdings)")]
    select_columns = []
    for column in columns:
        quoted = f'"{column}"'
        if column == "issuer_match_key":
            select_columns.append(
                'resolved_issuer_match_key("issuer_name", "issuer_match_key") as "issuer_match_key"'
            )
        else:
            select_columns.append(quoted)
    projection = ", ".join(select_columns)

    con.execute(
        f"create temp table security_level_holdings as "
        f"select {projection} from main.security_level_holdings"
    )
    con.execute(
        "create temp table funded_security_level_holdings as "
        "select * from temp.security_level_holdings "
        "where coalesce(is_unfunded_commitment, 0) = 0"
    )
    con.executescript(
        """
        create temp view fund_issuer_match_period_exposure as
        select
            fund,
            filing_period_end,
            coalesce(issuer_match_key, 'UNKNOWN') as issuer_match_key,
            min(issuer_name) as representative_issuer_name,
            group_concat(distinct issuer_name) as issuer_name_variants,
            count(*) as holding_rows,
            round(sum(amortized_cost_mm), 6) as amortized_cost_mm,
            round(sum(fair_value_mm), 6) as fair_value_mm
        from temp.funded_security_level_holdings
        group by fund, filing_period_end, coalesce(issuer_match_key, 'UNKNOWN');

        create temp view cross_fund_issuer_period_exposure as
        select
            filing_period_end,
            issuer_match_key,
            min(representative_issuer_name) as representative_issuer_name,
            group_concat(distinct fund) as funds,
            count(distinct fund) as fund_count,
            sum(holding_rows) as holding_rows,
            round(sum(amortized_cost_mm), 6) as amortized_cost_mm,
            round(sum(fair_value_mm), 6) as fair_value_mm,
            group_concat(distinct issuer_name_variants) as issuer_name_variants
        from temp.fund_issuer_match_period_exposure
        where issuer_match_key <> 'UNKNOWN'
        group by filing_period_end, issuer_match_key
        having count(distinct fund) >= 2;
        """
    )


def rows(con: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in con.execute(sql, params)]


def one(con: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    row = con.execute(sql, params).fetchone()
    return dict(row) if row else None


def money(value: Any) -> float:
    return round(float(value or 0), 6)


def pct_change(current: float | None, prior: float | None) -> float | None:
    if current is None or prior in (None, 0):
        return None
    return round((current - prior) / prior * 100, 2)


def latest_common_period(con: sqlite3.Connection) -> str:
    result = one(
        con,
        """
        select filing_period_end
        from period_coverage
        group by filing_period_end
        having count(distinct fund) = ?
        order by filing_period_end desc
        limit 1
        """,
        (len(FUNDS),),
    )
    if not result:
        raise RuntimeError(f"No common period found across {', '.join(FUNDS)}")
    return str(result["filing_period_end"])


def parse_maturity_year(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"n/a", "na", "none", "perpetual"}:
        return None

    iso = re.search(r"\b(20\d{2}|19\d{2})(?:[-/]\d{1,2})?(?:[-/]\d{1,2})?\b", text)
    if iso:
        return int(iso.group(1))

    slash = re.search(r"\b\d{1,2}/\d{1,2}/(\d{2}|\d{4})\b", text)
    if slash:
        year = int(slash.group(1))
        if year < 100:
            year += 2000 if year < 50 else 1900
        return year

    return None


def maturity_bucket(value: Any) -> str:
    year = parse_maturity_year(value)
    if year is None:
        return "No stated maturity"
    if year <= 2026:
        return "2026 and earlier"
    if year in {2027, 2028, 2029}:
        return str(year)
    return "2030+"


def rate_bucket(row: dict[str, Any]) -> str:
    if row.get("is_fixed") == 1 or row.get("fixed_coupon_pct") is not None:
        return "Fixed-rate"
    if row.get("reference_base_rate"):
        return "Floating-rate"
    if not row.get("rate_raw"):
        return "Rate not stated"
    return "Other rate text"


def group_sum(items: list[dict[str, Any]], keys: list[str], value_key: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in items:
        key = tuple(item.get(k) for k in keys)
        if key not in grouped:
            grouped[key] = {k: item.get(k) for k in keys}
            grouped[key]["fair_value_mm"] = 0.0
            grouped[key]["rows"] = 0
        grouped[key]["fair_value_mm"] += float(item.get(value_key) or 0)
        grouped[key]["rows"] += 1
    output = list(grouped.values())
    for item in output:
        item["fair_value_mm"] = money(item["fair_value_mm"])
    return output


def unique_sorted(values: list[Any]) -> list[str]:
    return sorted({str(value) for value in values if value is not None and str(value).strip()})


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def comparable_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", compact_text(value).lower()).strip()


def security_signature(row: dict[str, Any]) -> str:
    issuer_norm = comparable_text(row.get("issuer_name"))
    key_norm = comparable_text(row.get("issuer_match_key"))
    parts: list[str] = []

    for field in ("instrument_type", "investment_description"):
        text = compact_text(row.get(field))
        text_norm = comparable_text(text)
        if not text or text_norm in {issuer_norm, key_norm}:
            continue
        if text not in parts:
            parts.append(text)

    if not parts and row.get("investment_category"):
        parts.append(compact_text(row.get("investment_category")))

    details = []
    if row.get("exposure_type") == "unfunded_commitment" or row.get("is_unfunded_commitment") == 1:
        details.append("unfunded commitment")
    if row.get("rate_raw"):
        details.append(compact_text(row.get("rate_raw")))
    if row.get("maturity_date"):
        details.append(f"due {compact_text(row.get('maturity_date'))}")
    if row.get("principal_mm") is not None:
        details.append(f"principal {money(row.get('principal_mm'))}mm")
    elif row.get("amount_value") is not None and row.get("amount_kind"):
        currency = compact_text(row.get("amount_currency")) or "units"
        details.append(f"{compact_text(row.get('amount_kind'))} {compact_text(row.get('amount_value'))} {currency}")

    if details:
        parts.append(" / ".join(details))

    return " | ".join(parts[:3]) or compact_text(row.get("issuer_name")) or "Security row"


def build_data() -> dict[str, Any]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Central database not found: {DB_PATH}")

    con = connect()
    try:
        latest_period = latest_common_period(con)
        built_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        integrity = con.execute("pragma integrity_check").fetchone()[0]

        period_summary = rows(
            con,
            """
            select
                fund,
                filing_period_end,
                report_type,
                holding_rows,
                round(amortized_cost_mm, 6) as amortized_cost_mm,
                round(fair_value_mm, 6) as fair_value_mm,
                round(mark_vs_cost_mm, 6) as mark_vs_cost_mm
            from fund_period_summary
            order by fund, filing_period_end
            """,
        )

        fund_totals = rows(
            con,
            """
            select
                fund,
                count(*) as holding_rows,
                count(distinct filing_period_end) as periods,
                round(sum(amortized_cost_mm), 6) as amortized_cost_mm,
                round(sum(fair_value_mm), 6) as fair_value_mm,
                round(sum(fair_value_mm) - sum(amortized_cost_mm), 6) as mark_vs_cost_mm
            from holdings
            group by fund
            order by fund
            """,
        )

        latest_by_fund = rows(
            con,
            """
            select
                fund,
                filing_period_end,
                report_type,
                holding_rows,
                round(amortized_cost_mm, 6) as amortized_cost_mm,
                round(fair_value_mm, 6) as fair_value_mm,
                round(mark_vs_cost_mm, 6) as mark_vs_cost_mm
            from fund_period_summary
            where filing_period_end = ?
            order by fund
            """,
            (latest_period,),
        )

        latest_available_by_fund = rows(
            con,
            """
            with latest_periods as (
                select fund, max(filing_period_end) as filing_period_end
                from fund_period_summary
                group by fund
            )
            select
                summary.fund,
                summary.filing_period_end,
                summary.report_type,
                summary.holding_rows,
                round(summary.amortized_cost_mm, 6) as amortized_cost_mm,
                round(summary.fair_value_mm, 6) as fair_value_mm,
                round(summary.mark_vs_cost_mm, 6) as mark_vs_cost_mm
            from fund_period_summary summary
            join latest_periods latest
              on latest.fund = summary.fund
             and latest.filing_period_end = summary.filing_period_end
            order by summary.fund
            """,
        )

        raw_cross_fund_issuer_count = one(
            con,
            """
            select count(*) as issuer_groups
            from (
                select issuer_name
                from funded_security_level_holdings
                where filing_period_end = ?
                group by issuer_name
                having count(distinct fund) >= 2
            )
            """,
            (latest_period,),
        )["issuer_groups"]

        cross_fund_issuer_rows = rows(
            con,
            """
            select
                issuer_match_key,
                representative_issuer_name,
                funds,
                fund_count,
                holding_rows,
                round(amortized_cost_mm, 6) as amortized_cost_mm,
                round(fair_value_mm, 6) as fair_value_mm
            from cross_fund_issuer_period_exposure
            where filing_period_end = ?
            order by fair_value_mm desc
            """,
            (latest_period,),
        )
        timeline_issuer_rows = rows(
            con,
            """
            select
                issuer_match_key,
                max(issuer_name) as representative_issuer_name,
                group_concat(distinct fund) as funds,
                count(distinct fund) as fund_count,
                count(*) as holding_rows,
                round(sum(amortized_cost_mm), 6) as amortized_cost_mm,
                round(sum(fair_value_mm), 6) as fair_value_mm
            from funded_security_level_holdings
            where filing_period_end = ?
              and issuer_match_key is not null
              and trim(issuer_match_key) <> ''
            group by issuer_match_key
            order by fund_count desc, fair_value_mm desc
            limit ?
            """,
            (latest_period, TIMELINE_ISSUER_LIMIT),
        )
        cross_keys = [row["issuer_match_key"] for row in cross_fund_issuer_rows]
        timeline_keys = unique_sorted([*cross_keys, *[row["issuer_match_key"] for row in timeline_issuer_rows]])
        timeline_issuer_rank = {row["issuer_match_key"]: index for index, row in enumerate(timeline_issuer_rows)}
        timeline_issuer_lookup = {row["issuer_match_key"]: row for row in timeline_issuer_rows}
        cross_fund_issuer_latest: list[dict[str, Any]] = []
        loan_timeline_issuers: list[dict[str, Any]] = []
        loan_timeline_periods: list[dict[str, Any]] = []
        loan_timeline_securities: list[dict[str, Any]] = []
        if timeline_keys:
            placeholders = ",".join("?" for _ in timeline_keys)
            detail_rows = rows(
                con,
                f"""
                select
                    fund,
                    issuer_match_key,
                    issuer_name,
                    count(*) as holding_rows,
                    round(sum(amortized_cost_mm), 6) as amortized_cost_mm,
                    round(sum(fair_value_mm), 6) as fair_value_mm
                from funded_security_level_holdings
                where filing_period_end = ?
                  and issuer_match_key in ({placeholders})
                group by fund, issuer_match_key, issuer_name
                order by fund, fair_value_mm desc
                """,
                (latest_period, *timeline_keys),
            )
            for row in cross_fund_issuer_rows:
                key = row["issuer_match_key"]
                details = [item for item in detail_rows if item["issuer_match_key"] == key]
                fund_breakdown = []
                for fund in FUNDS:
                    fund_details = [item for item in details if item["fund"] == fund]
                    if not fund_details:
                        continue
                    fund_breakdown.append(
                        {
                            "fund": fund,
                            "holding_rows": sum(int(item["holding_rows"] or 0) for item in fund_details),
                            "amortized_cost_mm": money(sum(float(item["amortized_cost_mm"] or 0) for item in fund_details)),
                            "fair_value_mm": money(sum(float(item["fair_value_mm"] or 0) for item in fund_details)),
                            "issuer_names": unique_sorted([item["issuer_name"] for item in fund_details]),
                        }
                    )
                cross_fund_issuer_latest.append(
                    {
                        **row,
                        "funds": [item["fund"] for item in fund_breakdown],
                        "issuer_name_variants": unique_sorted([item["issuer_name"] for item in details]),
                        "fund_breakdown": fund_breakdown,
                    }
                )

            loan_timeline_periods = rows(
                con,
                f"""
                select
                    issuer_match_key,
                    fund,
                    filing_period_end,
                    count(*) as holding_rows,
                    round(sum(amortized_cost_mm), 6) as amortized_cost_mm,
                    round(sum(fair_value_mm), 6) as fair_value_mm,
                    round(sum(fair_value_mm) - sum(amortized_cost_mm), 6) as mark_vs_cost_mm,
                    case
                        when sum(case when principal_mm is not null then 1 else 0 end) > 0
                        then round(sum(coalesce(principal_mm, 0)), 6)
                        else null
                    end as principal_mm
                from funded_security_level_holdings
                where issuer_match_key in ({placeholders})
                group by issuer_match_key, fund, filing_period_end
                order by issuer_match_key, filing_period_end, fund
                """,
                tuple(timeline_keys),
            )

            loan_timeline_securities = rows(
                con,
                f"""
                select
                    issuer_match_key,
                    fund,
                    filing_period_end,
                    exposure_type,
                    is_unfunded_commitment,
                    issuer_name,
                    industry,
                    investment_category,
                    instrument_type,
                    investment_description,
                    maturity_date,
                    rate_raw,
                    amount_kind,
                    amount_currency,
                    amount_value,
                    principal_mm,
                    round(amortized_cost_mm, 6) as amortized_cost_mm,
                    round(fair_value_mm, 6) as fair_value_mm,
                    round(fair_value_mm - amortized_cost_mm, 6) as mark_vs_cost_mm
                from security_level_holdings
                where issuer_match_key in ({placeholders})
                order by issuer_match_key, filing_period_end desc, fund, fair_value_mm desc
                """,
                tuple(timeline_keys),
            )

            for item in loan_timeline_periods:
                item["amortized_cost_mm"] = money(item["amortized_cost_mm"])
                item["fair_value_mm"] = money(item["fair_value_mm"])
                item["mark_vs_cost_mm"] = money(item["mark_vs_cost_mm"])
                item["principal_mm"] = money(item["principal_mm"]) if item.get("principal_mm") is not None else None

            for item in loan_timeline_securities:
                item["amortized_cost_mm"] = money(item["amortized_cost_mm"])
                item["fair_value_mm"] = money(item["fair_value_mm"])
                item["mark_vs_cost_mm"] = money(item["mark_vs_cost_mm"])
                item["principal_mm"] = money(item["principal_mm"]) if item.get("principal_mm") is not None else None
                item["security_signature"] = security_signature(item)

            timeline_rows_by_key = {row["issuer_match_key"]: row for row in cross_fund_issuer_latest}
            for key in timeline_keys:
                row = timeline_rows_by_key.get(key) or timeline_issuer_lookup.get(key, {})
                issuer_periods = [item for item in loan_timeline_periods if item["issuer_match_key"] == key]
                period_totals: dict[str, float] = defaultdict(float)
                for item in issuer_periods:
                    period_totals[item["filing_period_end"]] += float(item["fair_value_mm"] or 0)
                period_values = sorted(period_totals)
                latest_key_period = period_values[-1] if period_values else None
                latest_key_total = period_totals.get(latest_key_period or "", 0.0)
                loan_timeline_issuers.append(
                    {
                        "issuer_match_key": key,
                        "display_name": row.get("representative_issuer_name") or key.title(),
                        "funds": unique_sorted([item["fund"] for item in issuer_periods]),
                        "first_period": period_values[0] if period_values else None,
                        "latest_period": latest_key_period,
                        "period_count": len(period_values),
                        "security_rows": sum(int(item["holding_rows"] or 0) for item in issuer_periods),
                        "latest_fair_value_mm": money(latest_key_total),
                        "max_fair_value_mm": money(max(period_totals.values()) if period_totals else 0),
                        "is_cross_fund": key in set(cross_keys),
                        "latest_rank": timeline_issuer_rank.get(key),
                    }
                )
            loan_timeline_issuers.sort(
                key=lambda item: (
                    0 if item["is_cross_fund"] else 1,
                    item["latest_rank"] if item["latest_rank"] is not None else TIMELINE_ISSUER_LIMIT + 1,
                    item["issuer_match_key"],
                )
            )

        issuer_period_history = rows(
            con,
            """
            select
                fund,
                filing_period_end,
                issuer_match_key,
                representative_issuer_name,
                holding_rows,
                round(amortized_cost_mm, 6) as amortized_cost_mm,
                round(fair_value_mm, 6) as fair_value_mm,
                case
                    when amortized_cost_mm != 0
                    then round(fair_value_mm / amortized_cost_mm * 100, 6)
                    else null
                end as fv_to_cost_pct
            from fund_issuer_match_period_exposure
            order by fund, issuer_match_key, filing_period_end
            """,
        )
        for item in issuer_period_history:
            item["amortized_cost_mm"] = money(item["amortized_cost_mm"])
            item["fair_value_mm"] = money(item["fair_value_mm"])

        change_by_fund = []
        for fund in FUNDS:
            current = one(
                con,
                """
                select filing_period_end, fair_value_mm, amortized_cost_mm, holding_rows
                from fund_period_summary
                where fund = ?
                order by filing_period_end desc
                limit 1
                """,
                (fund,),
            )
            prior = one(
                con,
                """
                select filing_period_end, fair_value_mm, amortized_cost_mm, holding_rows
                from fund_period_summary
                where fund = ? and filing_period_end < ?
                order by filing_period_end desc
                limit 1
                """,
                (fund, current["filing_period_end"] if current else latest_period),
            )
            if current:
                change_by_fund.append(
                    {
                        "fund": fund,
                        "current_period": current["filing_period_end"],
                        "prior_period": prior["filing_period_end"] if prior else None,
                        "current_fair_value_mm": money(current["fair_value_mm"]),
                        "prior_fair_value_mm": money(prior["fair_value_mm"]) if prior else None,
                        "change_mm": money(float(current["fair_value_mm"]) - float(prior["fair_value_mm"])) if prior else None,
                        "change_pct": pct_change(float(current["fair_value_mm"]), float(prior["fair_value_mm"])) if prior else None,
                        "holding_rows": current["holding_rows"],
                    }
                )

        periods = sorted({item["filing_period_end"] for item in period_summary})
        series = []
        for period in periods:
            point: dict[str, Any] = {"filing_period_end": period, "coverage_count": 0, "total_fair_value_mm": 0.0}
            for fund in FUNDS:
                match = next((item for item in period_summary if item["fund"] == fund and item["filing_period_end"] == period), None)
                point[fund] = money(match["fair_value_mm"]) if match else None
                if match:
                    point["coverage_count"] += 1
                    point["total_fair_value_mm"] += float(match["fair_value_mm"] or 0)
            point["total_fair_value_mm"] = money(point["total_fair_value_mm"])
            series.append(point)

        category_latest = rows(
            con,
            f"""
            select
                fund,
                investment_category,
                count(*) as holding_rows,
                round(sum(amortized_cost_mm), 6) as amortized_cost_mm,
                round(sum(fair_value_mm), 6) as fair_value_mm
                from (
                    select
                        fund,
                        {CATEGORY_EXPR} as investment_category,
                        amortized_cost_mm,
                        fair_value_mm
                    from funded_security_level_holdings
                    where filing_period_end = ?
                )
            group by fund, investment_category
            order by fund, fair_value_mm desc
            """,
            (latest_period,),
        )

        category_totals_latest = rows(
            con,
            f"""
            select
                investment_category,
                count(*) as holding_rows,
                round(sum(amortized_cost_mm), 6) as amortized_cost_mm,
                round(sum(fair_value_mm), 6) as fair_value_mm
            from (
                select
                    {CATEGORY_EXPR} as investment_category,
                    amortized_cost_mm,
                    fair_value_mm
                from funded_security_level_holdings
                where filing_period_end = ?
            )
            group by investment_category
            order by fair_value_mm desc
            limit 20
            """,
            (latest_period,),
        )

        top_issuers_latest = rows(
            con,
            """
            select
                fund,
                representative_issuer_name as issuer_name,
                holding_rows,
                round(amortized_cost_mm, 6) as amortized_cost_mm,
                round(fair_value_mm, 6) as fair_value_mm
            from (
                select
                    fund,
                    representative_issuer_name,
                    holding_rows,
                    amortized_cost_mm,
                    fair_value_mm,
                    row_number() over (
                        partition by fund
                        order by fair_value_mm desc
                    ) as fund_rank
                from fund_issuer_match_period_exposure
                where filing_period_end = ?
            )
            where fund_rank <= 20
            order by fair_value_mm desc
            """,
            (latest_period,),
        )

        holdings_latest = rows(
            con,
            """
            select
                fund,
                issuer_name,
                issuer_match_key,
                industry,
                investment_category,
                instrument_type,
                investment_description,
                rate_raw,
                reference_base_rate,
                spread_pct,
                fixed_coupon_pct,
                pik_rate_pct,
                maturity_date,
                amount_kind,
                amount_currency,
                amount_value,
                principal_mm,
                shares_units,
                exposure_type,
                is_unfunded_commitment,
                round(amortized_cost_mm, 6) as amortized_cost_mm,
                round(fair_value_mm, 6) as fair_value_mm,
                round(fair_value_mm - amortized_cost_mm, 6) as mark_vs_cost_mm,
                pct_net_assets,
                source_lineage_json
            from security_level_holdings
            where filing_period_end = ?
            order by fair_value_mm desc
            limit 250
            """,
            (latest_period,),
        )

        holdings_detail_latest = rows(
            con,
            """
            select
                fund,
                issuer_name,
                issuer_match_key,
                industry,
                investment_category,
                instrument_type,
                investment_description,
                rate_raw,
                reference_base_rate,
                spread_pct,
                fixed_coupon_pct,
                pik_rate_pct,
                maturity_date,
                amount_kind,
                amount_currency,
                amount_value,
                principal_mm,
                shares_units,
                exposure_type,
                is_unfunded_commitment,
                round(amortized_cost_mm, 6) as amortized_cost_mm,
                round(fair_value_mm, 6) as fair_value_mm,
                round(fair_value_mm - amortized_cost_mm, 6) as mark_vs_cost_mm,
                pct_net_assets,
                source_lineage_json
            from security_level_holdings
            where filing_period_end = ?
            order by fund, issuer_match_key, fair_value_mm desc
            """,
            (latest_period,),
        )

        holdings_detail_latest_by_fund = rows(
            con,
            """
            with latest_periods as (
                select fund, max(filing_period_end) as filing_period_end
                from fund_period_summary
                group by fund
            )
            select
                holding.fund,
                holding.filing_period_end,
                holding.issuer_name,
                holding.issuer_match_key,
                holding.industry,
                holding.investment_category,
                holding.instrument_type,
                holding.investment_description,
                holding.rate_raw,
                holding.reference_base_rate,
                holding.spread_pct,
                holding.fixed_coupon_pct,
                holding.pik_rate_pct,
                holding.maturity_date,
                holding.amount_kind,
                holding.amount_currency,
                holding.amount_value,
                holding.principal_mm,
                holding.shares_units,
                holding.exposure_type,
                holding.is_unfunded_commitment,
                round(holding.amortized_cost_mm, 6) as amortized_cost_mm,
                round(holding.fair_value_mm, 6) as fair_value_mm,
                round(holding.fair_value_mm - holding.amortized_cost_mm, 6) as mark_vs_cost_mm,
                holding.pct_net_assets,
                holding.source_lineage_json
            from security_level_holdings holding
            join latest_periods latest
              on latest.fund = holding.fund
             and latest.filing_period_end = holding.filing_period_end
            order by holding.fund, holding.issuer_match_key, holding.fair_value_mm desc
            """,
        )

        all_latest = rows(
            con,
            """
            select
                fund,
                fair_value_mm,
                maturity_date,
                is_fixed,
                fixed_coupon_pct,
                reference_base_rate,
                rate_raw,
                amount_kind,
                amount_currency
            from funded_security_level_holdings
            where filing_period_end = ?
            """,
            (latest_period,),
        )

        for item in holdings_latest:
            item["rate_type"] = rate_bucket(item)
            item["maturity_bucket"] = maturity_bucket(item.get("maturity_date"))

        for item in holdings_detail_latest:
            item["rate_type"] = rate_bucket(item)
            item["maturity_bucket"] = maturity_bucket(item.get("maturity_date"))

        for item in holdings_detail_latest_by_fund:
            item["rate_type"] = rate_bucket(item)
            item["maturity_bucket"] = maturity_bucket(item.get("maturity_date"))

        rate_items = []
        maturity_items = []
        amount_items = []
        for item in all_latest:
            value = float(item.get("fair_value_mm") or 0)
            rate_items.append({"fund": item["fund"], "rate_type": rate_bucket(item), "fair_value_mm": value})
            maturity_items.append({"fund": item["fund"], "maturity_bucket": maturity_bucket(item.get("maturity_date")), "fair_value_mm": value})
            amount_items.append(
                {
                    "fund": item["fund"],
                    "amount_kind": item.get("amount_kind") or "Not stated",
                    "amount_currency": item.get("amount_currency") or "Not stated",
                    "fair_value_mm": value,
                }
            )

        base_rate_latest = rows(
            con,
            """
            select
                fund,
                coalesce(reference_base_rate, 'Not stated') as reference_base_rate,
                count(*) as holding_rows,
                round(sum(fair_value_mm), 6) as fair_value_mm
            from funded_security_level_holdings
            where filing_period_end = ?
            group by fund, coalesce(reference_base_rate, 'Not stated')
            order by fund, fair_value_mm desc
            """,
            (latest_period,),
        )

        spread_time_series = rows(
            con,
            """
            select
                fund,
                filing_period_end,
                count(*) as holding_rows,
                sum(case when spread_pct is not null then 1 else 0 end) as spread_rows,
                round(sum(fair_value_mm), 6) as fair_value_mm,
                round(sum(case when spread_pct is not null then fair_value_mm else 0 end), 6) as spread_fair_value_mm,
                round(
                    sum(case when spread_pct is not null then coalesce(fair_value_mm, 0) * spread_pct * 100 else 0 end)
                    / nullif(sum(case when spread_pct is not null then coalesce(fair_value_mm, 0) else 0 end), 0),
                    6
                ) as weighted_avg_spread_bps
            from funded_security_level_holdings
            group by fund, filing_period_end
            order by fund, filing_period_end
            """,
        )

        for item in spread_time_series:
            item["fair_value_mm"] = money(item["fair_value_mm"])
            item["spread_fair_value_mm"] = money(item["spread_fair_value_mm"])
            item["weighted_avg_spread_bps"] = (
                round(float(item["weighted_avg_spread_bps"]), 2) if item.get("weighted_avg_spread_bps") is not None else None
            )

        source_databases = rows(
            con,
            """
            select fund, source_db_path, source_view, expected_rows, actual_rows, integrity_check, notes
            from source_databases
            order by fund
            """,
        )

        validation_results = rows(
            con,
            """
            select check_name, fund, status, expected, actual, details_json
            from validation_results
            order by id
            """,
        )

        validation_counts = rows(
            con,
            """
            select status, count(*) as rows
            from validation_results
            group by status
            order by status
            """,
        )

        source_qc_status = rows(
            con,
            """
            select fund, source_object, source_status, check_rows
            from source_qc_status
            order by fund, source_object, source_status
            """,
        )

        concentration = []
        for fund in FUNDS:
            fund_latest = [item for item in top_issuers_latest if item["fund"] == fund]
            total = next((item["fair_value_mm"] for item in latest_by_fund if item["fund"] == fund), 0) or 0
            top_5 = sum(float(item["fair_value_mm"] or 0) for item in fund_latest[:5])
            top_10 = sum(float(item["fair_value_mm"] or 0) for item in fund_latest[:10])
            concentration.append(
                {
                    "fund": fund,
                    "top_5_fair_value_mm": money(top_5),
                    "top_5_pct": round(top_5 / total * 100, 2) if total else None,
                    "top_10_fair_value_mm": money(top_10),
                    "top_10_pct": round(top_10 / total * 100, 2) if total else None,
                }
            )

        limitations = [
            {
                "title": "Eight verified holdings funds",
                "body": "Holdings analytics cover ARCC, BBDC, BXSL, FSK, GBDC, MAIN, OBDC, and TSLX after source-level reconciliation. The broader EdgarTools universe is shown separately and is not mixed into verified rankings until each fund passes equivalent detail and aggregate checks.",
            },
            {
                "title": "Current-period holdings only",
                "body": "The central table uses the canonical current-period holdings views. Comparative schedules and audit context are preserved in source databases, but they are not mixed into the main dashboard totals.",
            },
            {
                "title": "FSK category nuance",
                "body": "FSK footnote (x) rows are unfunded commitments. They are retained in the central holdings table for source reconciliation, but funded issuer, security, timeline, category, rate, and maturity views exclude them.",
            },
            {
                "title": "Issuer match keys are join aids",
                "body": "The dashboard now uses issuer_match_key for cross-fund overlap, while keeping each source issuer_name as the display label. The key strips punctuation and common legal or structural suffixes, but it is not a fully researched legal-entity master.",
            },
            {
                "title": "Dashboard categories are normalized",
                "body": "Combined category views map each source's investment labels into dashboard categories. ARCC and TSLX instrument descriptions are used where the source category is an industry or broad debt label; original fields remain preserved in the central database.",
            },
            {
                "title": "Amount fields are not all the same thing",
                "body": "Cost and fair value are in USD millions. Source par, share, unit, and non-USD amount fields are preserved separately and should not be summed without more context.",
            },
            {
                "title": "Maturity and rate fields come from source text",
                "body": "The maturity and rate views are useful for scanning, but a handful of source formats are irregular. Treat those charts as analytical triage, not final legal terms.",
            },
        ]

        return {
            "meta": {
                "generated_at_utc": built_at,
                "source_database": str(DB_PATH.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
                "sqlite_integrity": integrity,
                "funds": FUNDS,
                "fund_names": FUND_NAMES,
                "latest_common_period": latest_period,
                "latest_period_label": "March 31, 2026",
            },
            "narrative": {
                "overview": "The eight-fund verified view compares scale, direction, and portfolio composition across ARCC, BBDC, BXSL, FSK, GBDC, MAIN, OBDC, and TSLX without blending unreconciled bulk rows into the rankings.",
                "trend": "All eight verified funds have a common latest period at March 31, 2026. The EdgarTools cohort additions currently contribute their latest annual and quarterly observations, while the original five retain deeper histories.",
                "exposure": "Category, issuer, rate, maturity, and match-key views use funded security-level rows to make concentration visible quickly. As-filed schedule rows remain available in the holdings and timeline detail tables, with FSK footnote (x) rows tagged as unfunded commitments.",
                "quality": "The dashboard is built from the centralized SQLite database, and it carries the source integrity checks, source row counts, and central reconciliation checks into the interface.",
            },
            "raw_cross_fund_issuer_count_latest": raw_cross_fund_issuer_count,
            "cross_fund_issuer_latest": cross_fund_issuer_latest,
            "loan_timeline_issuers": loan_timeline_issuers,
            "loan_timeline_periods": loan_timeline_periods,
            "loan_timeline_securities": loan_timeline_securities,
            "issuer_period_history": issuer_period_history,
            "fund_totals": fund_totals,
            "latest_by_fund": latest_by_fund,
            "latest_available_by_fund": latest_available_by_fund,
            "change_by_fund": change_by_fund,
            "period_summary": period_summary,
            "time_series": series,
            "category_latest": category_latest,
            "category_totals_latest": category_totals_latest,
            "top_issuers_latest": top_issuers_latest,
            "issuer_concentration": concentration,
            "holdings_latest": holdings_latest,
            "holdings_detail_latest": holdings_detail_latest,
            "holdings_detail_latest_by_fund": holdings_detail_latest_by_fund,
            "rate_mix_latest": group_sum(rate_items, ["fund", "rate_type"], "fair_value_mm"),
            "maturity_buckets_latest": group_sum(maturity_items, ["fund", "maturity_bucket"], "fair_value_mm"),
            "amount_field_summary_latest": group_sum(amount_items, ["fund", "amount_kind", "amount_currency"], "fair_value_mm"),
            "base_rate_latest": base_rate_latest,
            "spread_time_series": spread_time_series,
            "source_databases": source_databases,
            "validation_counts": validation_counts,
            "validation_results": validation_results,
            "source_qc_status": source_qc_status,
            "limitations": limitations,
        }
    finally:
        con.close()


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = build_data()
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(DASHBOARD_ROOT)}")


if __name__ == "__main__":
    main()
