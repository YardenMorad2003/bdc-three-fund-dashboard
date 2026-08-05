from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
DATABASE_PATH = WORKSPACE_ROOT / "output" / "bdc_tracker_centralized" / "bdc_tracker_holdings.sqlite"
OUTPUT_PATH = PROJECT_ROOT / "lib" / "ocsl-quarterly-update.json"
CURRENT_PERIOD = "2026-06-30"
PRIOR_PERIOD = "2026-03-31"


def period_totals(connection: sqlite3.Connection, period: str) -> dict:
    row = connection.execute(
        """
        select count(*) as holding_rows,
               round(sum(amortized_cost_mm), 6) as amortized_cost_mm,
               round(sum(fair_value_mm), 6) as fair_value_mm
        from holdings
        where fund = 'OCSL' and filing_period_end = ?
        """,
        (period,),
    ).fetchone()
    if row is None or not row["holding_rows"]:
        raise RuntimeError(f"Missing OCSL holdings for {period}")
    return dict(row)


def largest_deterioration(connection: sqlite3.Connection) -> list[dict]:
    rows = connection.execute(
        """
        with issuer_period as (
          select filing_period_end, issuer_match_key, max(issuer_name) as issuer,
                 sum(amortized_cost_mm) as cost_mm, sum(fair_value_mm) as fair_value_mm
          from holdings
          where fund = 'OCSL'
            and exposure_type = 'funded'
            and filing_period_end in (?, ?)
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
        limit 5
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
            "fund": "OCSL",
            "period_end": CURRENT_PERIOD,
            "prior_period_end": PRIOR_PERIOD,
            "filing_date": "2026-08-05",
            "fiscal_quarter": "Q3 2026",
            "calendar_quarter": "Q2 2026",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
        "headline": {
            "stance": "NAV held steady while the non-accrual burden fell materially.",
            "summary": (
                "OCSL's June quarter showed lower income and net portfolio runoff, but NAV per share edged up "
                "and non-accruals declined from ten investments to six."
            ),
        },
        "reported": {
            "total_investment_income_mm": 69.433,
            "gaap_nii_mm": 32.521,
            "gaap_nii_per_share": 0.37,
            "adjusted_nii_mm": 32.240,
            "adjusted_nii_per_share": 0.37,
            "nav_per_share": 15.70,
            "prior_nav_per_share": 15.69,
            "regular_distribution_per_share": 0.30,
            "supplemental_distribution_per_share": 0.03,
            "total_distribution_per_share": 0.33,
            "non_accrual_fv_pct": 1.8,
            "prior_non_accrual_fv_pct": 2.6,
            "non_accrual_cost_pct": 4.2,
            "prior_non_accrual_cost_pct": 5.9,
            "non_accrual_count": 6,
            "prior_non_accrual_count": 10,
            "new_commitments_mm": 206.4,
            "repayments_and_exits_mm": 262.8,
            "new_debt_yield_pct": 10.0,
        },
        "schedule": {
            "current": current,
            "prior": prior,
            "fair_value_change_mm": round(current["fair_value_mm"] - prior["fair_value_mm"], 6),
            "mark_gap_change_mm": round(current_gap - prior_gap, 6),
            "largest_mark_deterioration": deterioration,
        },
        "sources": [
            {
                "name": "OCSL fiscal Q3 2026 earnings release",
                "url": "https://www.sec.gov/Archives/edgar/data/1414932/000119312526333737/d158058dex991.htm",
            },
            {
                "name": "OCSL June 2026 Form 10-Q",
                "url": "https://www.sec.gov/Archives/edgar/data/1414932/000141493226000017/ocsl-20260630.htm",
            },
        ],
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"OCSL {CURRENT_PERIOD}: {current['holding_rows']} rows, "
        f"cost ${current['amortized_cost_mm']:.3f}m, FV ${current['fair_value_mm']:.3f}m"
    )


if __name__ == "__main__":
    main()
