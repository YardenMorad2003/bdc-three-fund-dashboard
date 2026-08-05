from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
DATABASE_PATH = WORKSPACE_ROOT / "output" / "bdc_tracker_centralized" / "bdc_tracker_holdings.sqlite"
OUTPUT_PATH = PROJECT_ROOT / "lib" / "obdc-quarterly-update.json"
CURRENT_PERIOD = "2026-06-30"
PRIOR_PERIOD = "2026-03-31"


def period_totals(connection: sqlite3.Connection, period: str) -> dict:
    row = connection.execute(
        """
        select count(*) as holding_rows,
               round(sum(amortized_cost_mm), 6) as amortized_cost_mm,
               round(sum(fair_value_mm), 6) as fair_value_mm
        from holdings
        where fund = 'OBDC' and filing_period_end = ?
        """,
        (period,),
    ).fetchone()
    if row is None or not row["holding_rows"]:
        raise RuntimeError(f"Missing OBDC holdings for {period}")
    return dict(row)


def largest_deterioration(connection: sqlite3.Connection) -> list[dict]:
    rows = connection.execute(
        """
        with normalized as (
          select filing_period_end,
                 case
                   when issuer_match_key like 'LOPAREX MIDCO B V%' then 'LOPAREX MIDCO B V'
                   when issuer_match_key in ('CORNERSTONE ONDEMAND', 'SUNSHINE SOFTWARE') then 'CORNERSTONE ONDEMAND'
                   else issuer_match_key
                 end as issuer_match_key,
                 case
                   when issuer_match_key like 'LOPAREX MIDCO B V%' then 'Loparex Midco B.V.'
                   when issuer_match_key in ('CORNERSTONE ONDEMAND', 'SUNSHINE SOFTWARE') then 'Cornerstone OnDemand, Inc.'
                   else issuer_name
                 end as issuer_name,
                 amortized_cost_mm, fair_value_mm
          from holdings
          where fund = 'OBDC'
            and exposure_type = 'funded'
            and filing_period_end in (?, ?)
        ), issuer_period as (
          select filing_period_end, issuer_match_key, max(issuer_name) as issuer,
                 sum(amortized_cost_mm) as cost_mm, sum(fair_value_mm) as fair_value_mm
          from normalized
          group by filing_period_end, issuer_match_key
        ), prior as (
          select * from issuer_period where filing_period_end = ?
        ), current as (
          select * from issuer_period where filing_period_end = ?
        )
        select current.issuer_match_key, current.issuer,
               current.fair_value_mm,
               100.0 * current.fair_value_mm / nullif(current.cost_mm, 0) as fv_to_cost_pct,
               (current.fair_value_mm - current.cost_mm)
                 - (prior.fair_value_mm - prior.cost_mm) as mark_gap_change_mm
        from current join prior using (issuer_match_key)
        order by mark_gap_change_mm asc
        limit 6
        """,
        (PRIOR_PERIOD, CURRENT_PERIOD, PRIOR_PERIOD, CURRENT_PERIOD),
    ).fetchall()
    return [dict(row) for row in rows]


def main() -> None:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    current = period_totals(connection, CURRENT_PERIOD)
    prior = period_totals(connection, PRIOR_PERIOD)
    deterioration = largest_deterioration(connection)
    connection.close()

    current_gap = current["fair_value_mm"] - current["amortized_cost_mm"]
    prior_gap = prior["fair_value_mm"] - prior["amortized_cost_mm"]
    payload = {
        "meta": {
            "fund": "OBDC",
            "period_end": CURRENT_PERIOD,
            "prior_period_end": PRIOR_PERIOD,
            "filing_date": "2026-08-05",
            "fiscal_quarter": "Q2 2026",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
        "headline": {
            "stance": "Earnings covered the dividend, but NAV and several credit marks moved lower.",
            "summary": (
                "Adjusted NII improved and fair-value non-accruals declined, while NAV fell 1.0% and "
                "repayments substantially exceeded new commitments."
            ),
        },
        "reported": {
            "total_investment_income_mm": 401.342,
            "gaap_nii_mm": 176.173,
            "gaap_nii_per_share": 0.36,
            "adjusted_nii_mm": 170.557,
            "adjusted_nii_per_share": 0.34,
            "nav_per_share": 14.26,
            "prior_nav_per_share": 14.41,
            "base_distribution_per_share": 0.31,
            "supplemental_distribution_per_share": 0.02,
            "total_distribution_per_share": 0.33,
            "non_accrual_fv_pct": 0.8,
            "prior_non_accrual_fv_pct": 1.0,
            "non_accrual_cost_pct": 2.8,
            "prior_non_accrual_cost_pct": 2.0,
            "new_commitments_mm": 319.324,
            "repayments_and_sales_mm": 746.699,
            "portfolio_fair_value_mm": 14955.049,
            "net_debt_to_equity_x": 1.11,
            "portfolio_company_count": 229,
            "first_lien_pct": 73.2,
            "weighted_average_yield_pct": 9.9,
        },
        "schedule": {
            "current": current,
            "prior": prior,
            "reported_fair_value_mm": 14955.049,
            "fair_value_reconciliation_delta_mm": round(current["fair_value_mm"] - 14955.049, 6),
            "fair_value_change_mm": round(current["fair_value_mm"] - prior["fair_value_mm"], 6),
            "mark_gap_change_mm": round(current_gap - prior_gap, 6),
            "largest_mark_deterioration": deterioration,
            "excluded_disclosure": {
                "name": "Blue Owl Cross-Strategy Opportunities LLC (BOCSO)",
                "cost_mm": 1250.0,
                "fair_value_mm": 1240.0,
                "reason": "Footnote transaction disclosure; not a retained OBDC Schedule of Investments position.",
            },
        },
        "sources": [
            {
                "name": "OBDC Q2 2026 earnings release",
                "url": "https://www.blueowlcapitalcorporation.com/investors/news-events/press-releases/detail/94/blue-owl-capital-corporation-announces-june-30-2026",
            },
            {
                "name": "OBDC June 2026 Form 10-Q",
                "url": "https://www.sec.gov/Archives/edgar/data/1655888/000165588826000056/obdc-20260630.htm",
            },
        ],
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"OBDC {CURRENT_PERIOD}: {current['holding_rows']} rows, "
        f"cost ${current['amortized_cost_mm']:.3f}m, FV ${current['fair_value_mm']:.3f}m"
    )


if __name__ == "__main__":
    main()
