from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PEER_PATH = PROJECT_ROOT / "lib" / "business-peer-pricing.json"
FUNDING_PATH = PROJECT_ROOT / "lib" / "bdc-funding-market.json"
DASHBOARD_PATH = PROJECT_ROOT / "lib" / "dashboard-data.json"
OUTPUT_PATH = PROJECT_ROOT / "lib" / "bdc-market-valuation.json"
FREE_SOURCES_PATH = PROJECT_ROOT / "lib" / "free-source-intelligence.json"
MAX_LOAN_REMARK_PP = 25.0


# Quarter-end balance-sheet facts are kept as a small, auditable snapshot. The
# source links below are official issuer or SEC materials. ARCC is updated
# through June 30, 2026; the remaining funds are through March 31, 2026.
FUND_FINANCIALS: dict[str, dict[str, Any]] = {
    "ARCC": {"nav_per_share": 19.35, "net_assets_mm": 13891.0, "debt_mm": 15800.0, "debt_to_equity_x": 1.15,
             "nav_date": "2026-06-30", "unsecured_debt_pct": None, "source_url": "https://www.sec.gov/Archives/edgar/data/1287750/000162828026050303/arccq2-2026exhibit991.htm"},
    "BBDC": {"nav_per_share": 11.02, "net_assets_mm": 1153.45, "debt_mm": 1425.202, "debt_to_equity_x": 1.24,
             "unsecured_debt_pct": 78.7, "source_url": "https://ir.barings.com/news-events/press-releases/detail/473/barings-bdc-inc-reports-first-quarter-2026-results-and-announces-quarterly-cash-dividend-of-0-26-per-share"},
    "BXSL": {"nav_per_share": 26.26, "net_assets_mm": 6100.0, "debt_mm": 8076.0, "debt_to_equity_x": 1.32,
             "unsecured_debt_pct": 25.0, "source_url": "https://s29.q4cdn.com/231559957/files/doc_financials/2026/q1/Q1-2026-BXSL-Earnings-Presentation-vF.pdf"},
    "FSK": {"nav_per_share": 18.83, "net_assets_mm": 5274.0, "debt_mm": 7271.0, "debt_to_equity_x": 1.38,
            "unsecured_debt_pct": 51.0, "source_url": "https://www.sec.gov/Archives/edgar/data/1422183/000110465926058250/tm2614112d1_ex99-1.htm"},
    "GBDC": {"nav_per_share": 14.35, "net_assets_mm": 3748.12, "debt_mm": 4723.905, "debt_to_equity_x": 1.26,
             "unsecured_debt_pct": 50.9, "source_url": "https://www.sec.gov/Archives/edgar/data/1476765/000147676526000033/gbdc-20260331.htm"},
    "MAIN": {"nav_per_share": 33.46, "net_assets_mm": 3093.644, "debt_mm": 2536.0, "debt_to_equity_x": 0.82,
             "unsecured_debt_pct": 71.0, "source_url": "https://www.mainstcapital.com/investors/news-events/press-releases/detail/2763/main-street-announces-first-quarter-2026-results"},
    "OBDC": {"nav_per_share": 14.41, "net_assets_mm": 7154.0, "debt_mm": 8454.559, "debt_to_equity_x": 1.18,
             "unsecured_debt_pct": None, "source_url": "https://www.sec.gov/Archives/edgar/data/1655888/000165588826000034/exhibit991-obdcxpressrelea.htm"},
    "TSLX": {"nav_per_share": 16.24, "net_assets_mm": 1543.0, "debt_mm": 1827.4, "debt_to_equity_x": 1.18,
             "unsecured_debt_pct": 68.4, "source_url": "https://www.sec.gov/Archives/edgar/data/1508655/000119312526206354/tslx-ex99_1.htm"},
}


MARKET_CLOSES: dict[str, dict[str, Any]] = {
    "ARCC": {"price": 18.76, "price_date": "2026-07-31"},
    "BBDC": {"price": 8.50, "price_date": "2026-07-17"},
    "BXSL": {"price": 23.82, "price_date": "2026-07-17"},
    "FSK": {"price": 10.93, "price_date": "2026-07-17"},
    "GBDC": {"price": 13.33, "price_date": "2026-07-16"},
    "MAIN": {"price": 55.37, "price_date": "2026-07-17"},
    "OBDC": {"price": 10.99, "price_date": "2026-07-17"},
    "TSLX": {"price": 17.44, "price_date": "2026-07-17"},
}


def clamp(value: float, lower: float = 0, upper: float = 100) -> float:
    return max(lower, min(upper, value))


def weighted_average(rows: list[dict[str, Any]], field: str, weight: str) -> float | None:
    denominator = sum(float(row.get(weight) or 0) for row in rows)
    if not denominator:
        return None
    return sum(float(row.get(field) or 0) * float(row.get(weight) or 0) for row in rows) / denominator


def main() -> None:
    peer_data = json.loads(PEER_PATH.read_text(encoding="utf-8"))
    funding_data = json.loads(FUNDING_PATH.read_text(encoding="utf-8"))
    dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
    free_sources = json.loads(FREE_SOURCES_PATH.read_text(encoding="utf-8")) if FREE_SOURCES_PATH.exists() else {}
    refreshed_quotes = {
        row["ticker"]: row
        for row in free_sources.get("market", {}).get("quotes", [])
        if row.get("ticker") in FUND_FINANCIALS and row.get("price") is not None and row.get("price_date")
    }
    funding_by_fund = {row["ticker"]: row for row in funding_data["funds"]}
    latest_fund_rows = dashboard.get("latest_available_by_fund", dashboard["latest_by_fund"])
    total_fv_by_fund = {row["fund"]: float(row["fair_value_mm"]) for row in latest_fund_rows}
    as_of = date.fromisoformat(funding_data["meta"]["as_of_date"])
    rows = []

    for fund, financials in FUND_FINANCIALS.items():
        estimates = [row for row in peer_data["estimates"] if row["bdc_fund"] == fund]
        funding = funding_by_fund[fund]
        comparable_principal = sum(float(row["bdc_principal_mm"]) for row in estimates)
        comparable_fv = sum(float(row["bdc_fair_value_mm"]) for row in estimates)
        modeled_gaps = [
            clamp(
                float(row["peer_implied_mark"]) - float(row["bdc_mark_on_principal"]),
                -MAX_LOAN_REMARK_PP,
                MAX_LOAN_REMARK_PP,
            )
            for row in estimates
        ]
        asset_adjustment = sum(
            float(row["bdc_principal_mm"]) * modeled_gap / 100
            for row, modeled_gap in zip(estimates, modeled_gaps)
        )
        weighted_bdc_mark = weighted_average(estimates, "bdc_mark_on_principal", "bdc_principal_mm")
        weighted_peer_mark = weighted_average(estimates, "peer_implied_mark", "bdc_principal_mm")
        coverage_pct = comparable_fv / total_fv_by_fund[fund] * 100 if total_fv_by_fund.get(fund) else 0
        nav_impact_pct = asset_adjustment / financials["net_assets_mm"] * 100
        adjusted_nav = financials["nav_per_share"] * (1 + nav_impact_pct / 100)
        market = dict(MARKET_CLOSES[fund])
        refreshed_quote = refreshed_quotes.get(fund)
        if refreshed_quote and refreshed_quote["price_date"] >= market["price_date"]:
            market = {
                "price": float(refreshed_quote["price"]),
                "price_date": refreshed_quote["price_date"],
                "source_url": refreshed_quote.get("source_url"),
                "provider": "Massive",
            }
        price_to_nav = market["price"] / financials["nav_per_share"] * 100
        price_to_adjusted_nav = market["price"] / adjusted_nav * 100

        candidate_series = [
            row for row in funding_data["series"]
            if row["ticker"] == fund and row["status"] == "outstanding_candidate" and row.get("maturity_date")
            and date.fromisoformat(row["maturity_date"]) >= as_of
        ]
        candidate_total = sum(float(row.get("gross_issued_mm") or 0) for row in candidate_series)
        near_term = sum(
            float(row.get("gross_issued_mm") or 0) for row in candidate_series
            if date.fromisoformat(row["maturity_date"]) <= date(2028, 12, 31)
        )
        near_term_pct = near_term / candidate_total * 100 if candidate_total else 0
        next_maturity = min((row["maturity_date"] for row in candidate_series), default=None)

        leverage_score = clamp(100 - (financials["debt_to_equity_x"] - .70) / .80 * 100)
        maturity_score = clamp(100 - near_term_pct * 1.25)
        trace_yield = funding.get("trace_last_yield_pct")
        bond_market_score = clamp(100 - (float(trace_yield) - 4.5) * 20) if trace_yield is not None else 50
        funding_resilience = .55 * leverage_score + .25 * maturity_score + .20 * bond_market_score
        adjusted_discount = price_to_adjusted_nav - 100
        valuation_score = clamp(50 - adjusted_discount * 1.5)
        evidence_score = clamp(coverage_pct / 50 * 100)
        aggregate_score = .70 * valuation_score + .20 * funding_resilience + .10 * evidence_score
        if coverage_pct < 5:
            interpretation = "market discount / BSL pending" if adjusted_discount < -10 else "market premium / BSL pending" if adjusted_discount > 10 else "BSL coverage pending"
        else:
            interpretation = "screened undervalued" if aggregate_score >= 70 else "screened overvalued" if aggregate_score <= 35 else "balanced / inconclusive"

        rows.append({
            "fund": fund,
            "company_name": funding["company_name"],
            "price": market["price"],
            "price_date": market["price_date"],
            "nav_per_share": financials["nav_per_share"],
            "nav_date": financials.get("nav_date", "2026-03-31"),
            "reported_price_to_nav_pct": round(price_to_nav, 4),
            "reported_premium_discount_pct": round(price_to_nav - 100, 4),
            "comparable_loan_count": len(estimates),
            "comparable_principal_mm": round(comparable_principal, 3),
            "comparable_fair_value_mm": round(comparable_fv, 3),
            "comparable_portfolio_coverage_pct": round(coverage_pct, 4),
            "weighted_bdc_mark": round(weighted_bdc_mark, 4) if weighted_bdc_mark is not None else None,
            "weighted_bsl_peer_mark": round(weighted_peer_mark, 4) if weighted_peer_mark is not None else None,
            "bsl_minus_bdc_mark_pp": round((weighted_peer_mark or 0) - (weighted_bdc_mark or 0), 4),
            "modeled_bsl_minus_bdc_mark_pp": round(asset_adjustment / comparable_principal * 100, 4) if comparable_principal else None,
            "bsl_asset_adjustment_mm": round(asset_adjustment, 3),
            "bsl_asset_nav_impact_pct": round(nav_impact_pct, 4),
            "bsl_adjusted_nav_per_share": round(adjusted_nav, 4),
            "price_to_bsl_adjusted_nav_pct": round(price_to_adjusted_nav, 4),
            "market_gap_vs_bsl_adjusted_nav_pct": round(adjusted_discount, 4),
            "net_assets_mm": financials["net_assets_mm"],
            "total_debt_mm": financials["debt_mm"],
            "debt_to_equity_x": financials["debt_to_equity_x"],
            "unsecured_debt_pct": financials["unsecured_debt_pct"],
            "observed_note_coupon_pct": funding["weighted_coupon_pct"],
            "trace_last_yield_pct": trace_yield,
            "trace_matched_series_count": funding["trace_matched_series_count"],
            "next_observed_note_maturity": next_maturity,
            "near_term_observed_note_pct": round(near_term_pct, 4),
            "valuation_score": round(valuation_score, 2),
            "funding_resilience_score": round(funding_resilience, 2),
            "evidence_score": round(evidence_score, 2),
            "aggregate_value_score": round(aggregate_score, 2),
            "screen_confidence": "higher" if coverage_pct >= 40 and funding["trace_matched_series_count"] else "medium" if coverage_pct >= 20 else "limited",
            "interpretation": interpretation,
            "financial_source_url": financials["source_url"],
            "market_source_url": market.get("source_url") or f"https://stockanalysis.com/stocks/{fund.lower()}/history/",
            "market_data_provider": market.get("provider") or "audited static close",
        })

    rows.sort(key=lambda row: (-row["aggregate_value_score"], row["fund"]))
    loan_rows = sorted(
        [{
            "issuer_match_key": row["issuer_match_key"],
            "issuer": row["issuer"],
            "fund": row["bdc_fund"],
            "business_model": row["business_model"],
            "bdc_fair_value_mm": row["bdc_fair_value_mm"],
            "bdc_mark": row["bdc_mark_on_principal"],
            "bsl_peer_mark": row["peer_implied_mark"],
            "bsl_minus_bdc_pp": round(row["peer_implied_mark"] - row["bdc_mark_on_principal"], 4),
            "modeled_gap_pp": round(clamp(row["peer_implied_mark"] - row["bdc_mark_on_principal"], -MAX_LOAN_REMARK_PP, MAX_LOAN_REMARK_PP), 4),
            "modeled_adjustment_mm": round(row["bdc_principal_mm"] * clamp(row["peer_implied_mark"] - row["bdc_mark_on_principal"], -MAX_LOAN_REMARK_PP, MAX_LOAN_REMARK_PP) / 100, 4),
            "remark_capped": abs(row["peer_implied_mark"] - row["bdc_mark_on_principal"]) > MAX_LOAN_REMARK_PP,
            "peer_low": row["peer_low"],
            "peer_high": row["peer_high"],
            "confidence": row["confidence"],
        } for row in peer_data["estimates"]],
        key=lambda row: (-abs(row["bsl_minus_bdc_pp"]), -row["bdc_fair_value_mm"]),
    )
    payload = {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "market_price_through": max(row["price_date"] for row in rows),
            "nav_date": max(row["nav_date"] for row in rows),
            "fund_count": len(rows),
            "free_source_market_quotes_used": sum(1 for row in rows if row["market_data_provider"] == "Massive"),
            "methodology": "Each fund's covered senior loans are re-marked from the BDC schedule mark toward the selected BSL operating-model peer median. Individual gaps are winsorized at plus or minus 25 price points so one impaired or imperfectly matched loan cannot dominate the fund. The dollar adjustment is applied to reported net assets while uncovered assets and all liabilities remain at reported value. The public share price is then compared with this BSL-adjusted NAV.",
            "score_methodology": "The 0-100 aggregate value score weights market price versus BSL-adjusted NAV at 70%, funding resilience at 20%, and comparable-loan coverage at 10%. Funding resilience combines gross debt-to-equity, observed near-term note maturities, and TRACE yield where available; a neutral bond-market input is used where TRACE coverage is absent.",
            "caveats": [
                "This is a relative screening model, not a target price or investment recommendation.",
                "Uncovered loans, equity investments, joint ventures, cash, taxes, fees, and other assets remain at the BDC's reported carrying value.",
                "Operating-model BSL peers are not identical facilities; leverage, covenants, collateral, sponsor support, and liquidity can justify different marks.",
                "The debt maturity screen uses SEC issuance series labeled as outstanding candidates and can overstate debt that was tendered, repurchased, or otherwise retired.",
                "TRACE coverage is incomplete and executed bond trades are not dealer quotes. Funds without a matched TRACE series receive a neutral bond-market input rather than an inferred yield.",
                "Market prices are recent closes while NAV and debt structure are quarter-end observations, so timing is deliberately shown rather than hidden.",
                "A plus or minus 25-point cap is applied to each modeled loan re-mark; the uncapped comparison remains in the audit table.",
            ],
        },
        "funds": rows,
        "loan_screen": loan_rows,
        "sources": [
            {"name": "Recent BDC closing prices", "url": "https://stockanalysis.com/stocks/arcc/history/", "role": "Public closing-price snapshot; each row retains its ticker-specific URL."},
            {"name": "SEC and issuer Q1/Q2 2026 materials", "url": "https://www.sec.gov/edgar/search/", "role": "NAV, net assets, debt, and leverage; each row retains its fund-specific source URL and observation date."},
            {"name": "SEC Form N-PORT data sets", "url": "https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets", "role": "Public senior-loan ETF marks."},
            {"name": "FINRA TRACE", "url": "https://www.finra.org/finra-data/fixed-income", "role": "Observed BDC bond trades and yields where matched."},
        ],
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    for row in rows:
        print(f"{row['fund']}: score {row['aggregate_value_score']:.1f}, market gap {row['market_gap_vs_bsl_adjusted_nav_pct']:+.1f}%, coverage {row['comparable_portfolio_coverage_pct']:.1f}%")


if __name__ == "__main__":
    main()
