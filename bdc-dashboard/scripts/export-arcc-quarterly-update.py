from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
DB_PATH = WORKSPACE_ROOT / "output" / "bdc_tracker_centralized" / "bdc_tracker_holdings.sqlite"
OUTPUT_PATH = PROJECT_ROOT / "lib" / "arcc-quarterly-update.json"
CURRENT_PERIOD = "2026-06-30"
PRIOR_PERIOD = "2026-03-31"
EARNINGS_RELEASE_URL = (
    "https://www.sec.gov/Archives/edgar/data/1287750/"
    "000162828026050303/arccq2-2026exhibit991.htm"
)
TEN_Q_URL = (
    "https://www.sec.gov/Archives/edgar/data/1287750/"
    "000162828026050307/arcc-20260630.htm"
)
MARKET_SOURCE_URL = "https://stockanalysis.com/stocks/arcc/history/"


REPORTED_FACTS: dict[str, dict[str, Any]] = {
    CURRENT_PERIOD: {
        "core_eps": 0.47,
        "gaap_nii_mm": 359.0,
        "gaap_nii_per_share": 0.50,
        "dividend_per_share": 0.48,
        "gaap_net_income_mm": 171.0,
        "gaap_net_income_per_share": 0.24,
        "net_realized_gain_loss_mm": -5.0,
        "net_unrealized_gain_loss_mm": -183.0,
        "nav_per_share": 19.35,
        "net_assets_mm": 13891.0,
        "portfolio_fair_value_mm": 29349.0,
        "debt_carrying_value_mm": 15800.0,
        "debt_to_equity_x": 1.15,
        "net_debt_to_equity_x": 1.12,
        "cash_mm": 383.0,
        "borrowing_availability_mm": 6700.0,
        "gross_commitments_mm": 2592.0,
        "exits_of_commitments_mm": 2915.0,
        "portfolio_company_count": 619,
        "first_lien_fv_pct": 59.0,
        "floating_rate_fv_pct": 71.0,
        "debt_income_security_yield_cost_pct": 10.3,
        "total_investment_yield_cost_pct": 9.3,
        "reported_non_accrual_cost_pct": 2.4,
        "reported_non_accrual_fv_pct": 1.4,
        "grade_1_fv_mm": 493.0,
        "grade_2_fv_mm": 1089.0,
        "grade_3_fv_mm": 22619.0,
        "grade_4_fv_mm": 5148.0,
    },
    PRIOR_PERIOD: {
        "core_eps": 0.47,
        "gaap_nii_mm": 398.0,
        "gaap_nii_per_share": 0.55,
        "dividend_per_share": 0.48,
        "gaap_net_income_mm": 92.0,
        "gaap_net_income_per_share": 0.13,
        "net_realized_gain_loss_mm": 106.0,
        "net_unrealized_gain_loss_mm": -412.0,
        "nav_per_share": 19.59,
        "net_assets_mm": 14065.0,
        "portfolio_fair_value_mm": 29499.0,
        "debt_carrying_value_mm": 15848.0,
        "debt_to_equity_x": 1.13,
        "net_debt_to_equity_x": 1.10,
        "cash_mm": 505.0,
        "borrowing_availability_mm": 5500.0,
        "gross_commitments_mm": 3246.0,
        "exits_of_commitments_mm": 3176.0,
        "portfolio_company_count": 607,
        "first_lien_fv_pct": 60.0,
        "floating_rate_fv_pct": 71.0,
        "debt_income_security_yield_cost_pct": 10.3,
        "total_investment_yield_cost_pct": 9.3,
        "reported_non_accrual_cost_pct": 2.1,
        "reported_non_accrual_fv_pct": 1.2,
        "grade_1_fv_mm": 436.0,
        "grade_2_fv_mm": 919.0,
        "grade_3_fv_mm": 22849.0,
        "grade_4_fv_mm": 5295.0,
    },
}


def period_totals(con: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    return {
        row["filing_period_end"]: dict(row)
        for row in con.execute(
            """
            select
                filing_period_end,
                holding_rows,
                round(amortized_cost_mm, 3) as amortized_cost_mm,
                round(fair_value_mm, 3) as fair_value_mm,
                round(mark_vs_cost_mm, 3) as mark_vs_cost_mm
            from fund_period_summary
            where fund = 'ARCC' and filing_period_end in (?, ?)
            """,
            (PRIOR_PERIOD, CURRENT_PERIOD),
        )
    }


def issuer_period_rows(con: sqlite3.Connection) -> dict[tuple[str, str], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for row in con.execute(
        """
        select
            filing_period_end,
            issuer_match_key,
            min(issuer_name) as issuer,
            round(sum(amortized_cost_mm), 3) as cost_mm,
            round(sum(fair_value_mm), 3) as fair_value_mm
        from funded_security_level_holdings
        where fund = 'ARCC'
          and filing_period_end in (?, ?)
          and coalesce(is_residual_row, 0) = 0
        group by filing_period_end, issuer_match_key
        """,
        (PRIOR_PERIOD, CURRENT_PERIOD),
    ):
        item = dict(row)
        rows[(item["filing_period_end"], item["issuer_match_key"])] = item
    return rows


def non_accrual_issuers(con: sqlite3.Connection, period: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for row in con.execute(
        """
        select issuer_match_key, issuer_name, amortized_cost_mm, fair_value_mm, raw_values_json
        from security_level_holdings
        where fund = 'ARCC' and filing_period_end = ?
        """,
        (period,),
    ):
        try:
            raw = json.loads(row["raw_values_json"] or "{}")
        except json.JSONDecodeError:
            raw = {}
        if "(8)" not in str(raw.get("footnotes") or ""):
            continue
        key = row["issuer_match_key"]
        item = groups.setdefault(
            key,
            {
                "issuer_match_key": key,
                "issuer": row["issuer_name"],
                "amortized_cost_mm": 0.0,
                "fair_value_mm": 0.0,
                "security_count": 0,
            },
        )
        item["amortized_cost_mm"] += float(row["amortized_cost_mm"] or 0)
        item["fair_value_mm"] += float(row["fair_value_mm"] or 0)
        item["security_count"] += 1
    for item in groups.values():
        item["amortized_cost_mm"] = round(item["amortized_cost_mm"], 3)
        item["fair_value_mm"] = round(item["fair_value_mm"], 3)
        item["fv_to_cost_pct"] = round(
            item["fair_value_mm"] / item["amortized_cost_mm"] * 100, 3
        ) if item["amortized_cost_mm"] else None
    return groups


def build_payload() -> dict[str, Any]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Central holdings database not found: {DB_PATH}")
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        totals = period_totals(con)
        if set(totals) != {PRIOR_PERIOD, CURRENT_PERIOD}:
            raise RuntimeError("ARCC Q1 and Q2 2026 holdings must both be present before export")
        issuer_rows = issuer_period_rows(con)
        current_non_accruals = non_accrual_issuers(con, CURRENT_PERIOD)
        prior_non_accruals = non_accrual_issuers(con, PRIOR_PERIOD)
    finally:
        con.close()

    deterioration = []
    for (period, key), current in issuer_rows.items():
        if period != CURRENT_PERIOD:
            continue
        prior = issuer_rows.get((PRIOR_PERIOD, key))
        if not prior or min(float(current["cost_mm"] or 0), float(prior["cost_mm"] or 0)) < 5:
            continue
        current_mark = current["fair_value_mm"] / current["cost_mm"] * 100 if current["cost_mm"] else None
        prior_mark = prior["fair_value_mm"] / prior["cost_mm"] * 100 if prior["cost_mm"] else None
        gap_change = (
            (current["fair_value_mm"] - current["cost_mm"])
            - (prior["fair_value_mm"] - prior["cost_mm"])
        )
        deterioration.append(
            {
                "issuer_match_key": key,
                "issuer": current["issuer"],
                "q2_cost_mm": current["cost_mm"],
                "q2_fair_value_mm": current["fair_value_mm"],
                "q2_fv_to_cost_pct": round(current_mark, 3) if current_mark is not None else None,
                "q1_fv_to_cost_pct": round(prior_mark, 3) if prior_mark is not None else None,
                "qoq_fv_to_cost_change_pp": round(current_mark - prior_mark, 3)
                if current_mark is not None and prior_mark is not None else None,
                "qoq_mark_gap_change_mm": round(gap_change, 3),
                "non_accrual_q2": key in current_non_accruals,
                "new_non_accrual_q2": key in current_non_accruals and key not in prior_non_accruals,
            }
        )
    deterioration.sort(key=lambda item: (item["qoq_mark_gap_change_mm"], item["issuer"]))

    current = REPORTED_FACTS[CURRENT_PERIOD]
    prior = REPORTED_FACTS[PRIOR_PERIOD]
    current_total = totals[CURRENT_PERIOD]
    prior_total = totals[PRIOR_PERIOD]
    new_non_accruals = sorted(
        (item for key, item in current_non_accruals.items() if key not in prior_non_accruals),
        key=lambda item: (-item["amortized_cost_mm"], item["issuer"]),
    )
    return {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fund": "ARCC",
            "period_end": CURRENT_PERIOD,
            "prior_period_end": PRIOR_PERIOD,
            "filing_date": "2026-07-29",
            "scope": "ARCC Q2 2026 earnings, balance sheet, risk grades, non-accruals, and reconciled Schedule of Investments.",
        },
        "headline": {
            "stance": "incremental credit softening; earnings and liquidity remain intact",
            "summary": (
                "NII still covered the regular dividend, but NAV fell, Core EPS sat just below the payout, "
                "and both non-accrual and lower-grade exposure increased. The Schedule of Investments shows "
                "the deterioration is concentrated in a finite group of credits rather than a portfolio-wide collapse."
            ),
        },
        "reported": {
            "current": current,
            "prior": prior,
            "changes": {
                "gaap_nii_per_share": round(current["gaap_nii_per_share"] - prior["gaap_nii_per_share"], 3),
                "nav_per_share": round(current["nav_per_share"] - prior["nav_per_share"], 3),
                "nav_per_share_pct": round((current["nav_per_share"] / prior["nav_per_share"] - 1) * 100, 3),
                "debt_to_equity_x": round(current["debt_to_equity_x"] - prior["debt_to_equity_x"], 3),
                "reported_non_accrual_cost_pp": round(current["reported_non_accrual_cost_pct"] - prior["reported_non_accrual_cost_pct"], 3),
                "reported_non_accrual_fv_pp": round(current["reported_non_accrual_fv_pct"] - prior["reported_non_accrual_fv_pct"], 3),
                "grade_1_2_fv_mm": round(
                    current["grade_1_fv_mm"] + current["grade_2_fv_mm"]
                    - prior["grade_1_fv_mm"] - prior["grade_2_fv_mm"],
                    3,
                ),
            },
            "dividend_coverage_pct": round(current["gaap_nii_per_share"] / current["dividend_per_share"] * 100, 3),
            "core_eps_dividend_coverage_pct": round(current["core_eps"] / current["dividend_per_share"] * 100, 3),
        },
        "schedule": {
            "current": current_total,
            "prior": prior_total,
            "mark_gap_change_mm": round(current_total["mark_vs_cost_mm"] - prior_total["mark_vs_cost_mm"], 3),
            "non_accrual_issuers": sorted(
                current_non_accruals.values(),
                key=lambda item: (-item["amortized_cost_mm"], item["issuer"]),
            ),
            "new_non_accrual_issuers": new_non_accruals,
            "largest_mark_deterioration": deterioration[:10],
        },
        "market_reaction": {
            "pre_report_date": "2026-07-28",
            "pre_report_close": 19.04,
            "report_date": "2026-07-29",
            "report_date_close": 18.71,
            "report_day_change_pct": -1.73,
            "latest_date": "2026-07-31",
            "latest_close": 18.76,
            "change_since_pre_report_pct": round((18.76 / 19.04 - 1) * 100, 3),
        },
        "sources": [
            {"name": "ARCC Q2 2026 earnings release", "url": EARNINGS_RELEASE_URL},
            {"name": "ARCC Q2 2026 Form 10-Q", "url": TEN_Q_URL},
            {"name": "ARCC historical closes", "url": MARKET_SOURCE_URL},
        ],
        "limitations": [
            "Core EPS is an issuer-defined non-GAAP measure; GAAP NII and GAAP net income remain separately displayed.",
            "Issuer mark changes mix company performance, market spreads, capital-structure changes, exits, and new funding.",
            "Footnote (8) identifies non-accrual loan rows; related equity positions are not automatically treated as non-accrual debt.",
            "The latest stock close is after the report, while NAV is measured at quarter-end.",
        ],
    }


def main() -> None:
    payload = build_payload()
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(
        "ARCC Q2: NAV {nav:.2f}, NII/share {nii:.2f}, non-accrual FV {na:.1f}%, "
        "new non-accrual issuers {count}".format(
            nav=payload["reported"]["current"]["nav_per_share"],
            nii=payload["reported"]["current"]["gaap_nii_per_share"],
            na=payload["reported"]["current"]["reported_non_accrual_fv_pct"],
            count=len(payload["schedule"]["new_non_accrual_issuers"]),
        )
    )


if __name__ == "__main__":
    main()
