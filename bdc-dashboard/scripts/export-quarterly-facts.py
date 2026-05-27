from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import time
from csv import DictReader
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


DASHBOARD_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
CENTRAL_DB_PATH = WORKSPACE_ROOT / "output" / "bdc_5_fund_centralized" / "bdc_5_fund_holdings.sqlite"
MODEL_DIR = WORKSPACE_ROOT / "output" / "three_fund_institutional_model"
MODEL_DB_PATH = MODEL_DIR / "three_fund_institutional_model.sqlite"
MODEL_README_PATH = MODEL_DIR / "README_THREE_FUND_INSTITUTIONAL_MODEL.md"
JSON_OUTPUT_PATH = DASHBOARD_ROOT / "lib" / "quarterly-bdc-facts.json"
MARKET_CLOSE_CSV_PATH = Path.home() / "Downloads" / "bdc_close_raw.csv"
MARKET_CLOSE_SOURCE_LABEL = "source-docs/bdc_close_raw.csv"

FUNDS = ["BXSL", "FSK", "TSLX"]
FUND_NAMES = {
    "BXSL": "Blackstone Secured Lending Fund",
    "FSK": "FS KKR Capital Corp.",
    "TSLX": "Sixth Street Specialty Lending, Inc.",
}


Q1_2026_PRESENTATION_SEED: dict[str, dict[str, Any]] = {
    "BXSL": {
        "source_title": "Q1 2026 BXSL Earnings Presentation",
        "source_file": "source-docs/Q1-2026-BXSL-Earnings-Presentation-vF (2).pdf",
        "nav_per_share": 26.26,
        "nii_mm": 179.0,
        "nii_per_share": 0.77,
        "base_dividend_per_share": 0.77,
        "reported_total_investments_fv_mm": 13942.0,
        "total_debt_principal_mm": 8076.0,
        "net_assets_mm": 6100.0,
        "debt_to_equity_x": 1.32,
        "avg_debt_to_equity_x": 1.31,
        "liquidity_mm": 2300.0,
        "debt_cost_pct": 4.90,
        "weighted_avg_yield_pct": None,
        "first_lien_pct": 97.6,
        "floating_rate_debt_investments_pct": 95.8,
        "non_accrual_fv_pct": 3.1,
        "pik_income_mm": 22.0,
        "new_commitments_mm": 303.0,
        "fundings_mm": 325.0,
        "repayments_sales_mm": 451.0,
        "new_investment_yield_pct": 7.7,
        "repayment_yield_pct": 9.1,
        "source_notes": [
            "Presentation seed reviewed from the local Q1 2026 earnings deck.",
            "Deck metrics are kept separate from holdings-derived schedule totals when labels or scope differ.",
        ],
    },
    "FSK": {
        "source_title": "Q1 2026 FSK Earnings Supplement",
        "source_file": "source-docs/FSK Q1 2026 Earnings Supplement_Final (1).pdf",
        "nav_per_share": 18.83,
        "nii_mm": 117.0,
        "nii_per_share": 0.42,
        "adjusted_nii_mm": 116.0,
        "adjusted_nii_per_share": 0.41,
        "base_dividend_per_share": 0.45,
        "total_dividend_per_share": 0.48,
        "base_dividend_coverage_pct": 93.3333,
        "total_dividend_coverage_pct": 87.5,
        "reported_total_investments_fv_mm": 12269.0,
        "total_debt_principal_mm": 7290.0,
        "net_debt_to_equity_x": 1.31,
        "liquidity_mm": 2300.0,
        "debt_cost_pct": 5.27,
        "weighted_avg_yield_pct": 9.7,
        "first_lien_pct": 59.6,
        "floating_rate_debt_investments_pct": 88.6,
        "non_accrual_fv_pct": 4.2,
        "pik_income_mm": 38.0,
        "fee_income_mm": 2.0,
        "new_commitments_mm": 499.0,
        "repayments_sales_mm": 710.0,
        "net_investment_activity_mm": -211.0,
        "source_notes": [
            "Presentation seed reviewed from the local Q1 2026 earnings supplement.",
            "Reported total investments at fair value is presentation-defined and differs from the gross holdings schedule aggregation.",
        ],
    },
    "TSLX": {
        "source_title": "Q1 2026 Sixth Street Specialty Lending Earnings Presentation",
        "source_file": "source-docs/SLX 1Q'26 Earnings Presentation_vFF.pdf",
        "nav_per_share": 16.24,
        "nii_mm": 39.842,
        "nii_per_share": 0.42,
        "reported_total_investments_fv_mm": 3313.0,
        "total_debt_principal_mm": 1827.0,
        "net_assets_mm": 1543.0,
        "debt_to_equity_x": 1.18,
        "liquidity_mm": 926.0,
        "debt_cost_pct": 5.5,
        "weighted_avg_yield_pct": 11.2,
        "weighted_avg_spread_over_base_rate_pct": 7.1,
        "first_lien_pct": 89.0,
        "floating_rate_debt_investments_pct": 96.3,
        "non_accrual_fv_pct": 1.4,
        "new_commitments_mm": 338.1,
        "fundings_mm": 134.8,
        "repayments_sales_mm": 113.0,
        "net_investment_activity_mm": 21.8,
        "source_notes": [
            "Presentation seed reviewed from the local Q1 2026 earnings deck.",
            "PIK income needs the 10-Q or schedule tagging before it should be displayed as a sourced quarterly fact.",
        ],
    },
}


INVESTMENT_ACTIVITY_FACTS: list[dict[str, Any]] = [
    {
        "fund": "BXSL",
        "period_end": "2025-03-31",
        "source_title": "Q1 2025 BXSL Earnings Presentation - Investment Activity",
        "source_file": "source-docs/Q1-2025-BXSL-Earnings-Presentation_vF-2.pdf",
        "source_page": 12,
        "new_commitments_mm": 756.0,
        "fundings_mm": 689.0,
        "repayments_sales_mm": 978.0,
        "net_investment_activity_mm": -289.0,
        "new_investment_yield_pct": 9.5,
        "repayment_yield_pct": 10.3,
        "source_notes": [
            "BXSL labels this table as investment commitments at par, investment fundings, investments sold, investments repaid, and net funded investment activity.",
            "Repaid / sold is the sum of investments sold and investments repaid.",
        ],
    },
    {
        "fund": "BXSL",
        "period_end": "2025-06-30",
        "source_title": "Q2 2025 BXSL Earnings Presentation - Investment Activity",
        "source_file": "source-docs/Q2-2025-BXSL-Earnings-Presentation_vF.pdf",
        "source_page": 12,
        "new_commitments_mm": 631.0,
        "fundings_mm": 530.0,
        "repayments_sales_mm": 185.0,
        "net_investment_activity_mm": 345.0,
        "new_investment_yield_pct": 9.8,
        "repayment_yield_pct": 10.3,
        "source_notes": [
            "BXSL labels this table as investment commitments at par, investment fundings, investments sold, investments repaid, and net funded investment activity.",
            "Repaid / sold is the sum of investments sold and investments repaid.",
        ],
    },
    {
        "fund": "BXSL",
        "period_end": "2025-09-30",
        "source_title": "Q3 2025 BXSL Earnings Presentation - Investment Activity",
        "source_file": "source-docs/Q3-2025-BXSL-Earnings-Presentation_vF.pdf",
        "source_page": 12,
        "new_commitments_mm": 1289.0,
        "fundings_mm": 1007.0,
        "repayments_sales_mm": 437.0,
        "net_investment_activity_mm": 571.0,
        "new_investment_yield_pct": 9.3,
        "repayment_yield_pct": 9.9,
        "source_notes": [
            "BXSL labels this table as investment commitments at par, investment fundings, investments sold, investments repaid, and net funded investment activity.",
            "Repaid / sold is the sum of investments sold and investments repaid.",
        ],
    },
    {
        "fund": "BXSL",
        "period_end": "2025-12-31",
        "source_title": "Q4 2025 BXSL Earnings Presentation - Investment Activity",
        "source_file": "source-docs/Q4-2025-BXSL-Earnings-Presentation_vF.pdf",
        "source_page": 12,
        "new_commitments_mm": 907.0,
        "fundings_mm": 1042.0,
        "repayments_sales_mm": 629.0,
        "net_investment_activity_mm": 413.0,
        "new_investment_yield_pct": 8.9,
        "repayment_yield_pct": 9.9,
        "source_notes": [
            "BXSL labels this table as investment commitments at par, investment fundings, investments sold, investments repaid, and net funded investment activity.",
            "Repaid / sold is the sum of investments sold and investments repaid.",
        ],
    },
    {
        "fund": "BXSL",
        "period_end": "2026-03-31",
        "source_title": "Q1 2026 BXSL Earnings Presentation - Investment Activity",
        "source_file": "source-docs/Q1-2026-BXSL-Earnings-Presentation-vF (2).pdf",
        "source_page": 12,
        "new_commitments_mm": 303.0,
        "fundings_mm": 325.0,
        "repayments_sales_mm": 451.0,
        "net_investment_activity_mm": -126.0,
        "new_investment_yield_pct": 7.7,
        "repayment_yield_pct": 9.1,
        "source_notes": [
            "BXSL labels this table as investment commitments at par, investment fundings, investments sold, investments repaid, and net funded investment activity.",
            "Repaid / sold is the sum of investments sold and investments repaid.",
        ],
    },
    {
        "fund": "FSK",
        "period_end": "2025-03-31",
        "source_title": "Q1 2025 FSK Earnings Supplement - Quarterly Investment Activity",
        "source_file": "source-docs/FSK Q1 2025 Earnings Supplement_Final.pdf",
        "source_page": 6,
        "new_commitments_mm": 1998.0,
        "fundings_mm": None,
        "repayments_sales_mm": 1407.0,
        "net_investment_activity_mm": 591.0,
        "new_investment_yield_pct": None,
        "repayment_yield_pct": None,
        "source_notes": [
            "FSK labels the New column source as Investment Purchases, not new commitments.",
            "FSK's adjusted net investment activity adds back net sales to COPJV; the dashboard Net column uses the reported Net Investment Activity row.",
        ],
    },
    {
        "fund": "FSK",
        "period_end": "2025-06-30",
        "source_title": "Q2 2025 FSK Earnings Supplement - Quarterly Investment Activity",
        "source_file": "source-docs/FSK Q2 2025 Earnings Supplement_Final.pdf",
        "source_page": 6,
        "new_commitments_mm": 1400.0,
        "fundings_mm": None,
        "repayments_sales_mm": 1650.0,
        "net_investment_activity_mm": -250.0,
        "new_investment_yield_pct": None,
        "repayment_yield_pct": None,
        "source_notes": [
            "FSK labels the New column source as Investment Purchases, not new commitments.",
            "FSK's adjusted net investment activity adds back net sales to COPJV; the dashboard Net column uses the reported Net Investment Activity row.",
        ],
    },
    {
        "fund": "FSK",
        "period_end": "2025-09-30",
        "source_title": "Q3 2025 FSK Earnings Supplement - Quarterly Investment Activity",
        "source_file": "source-docs/FSK Q3 2025 Earnings Supplement_Final (1).pdf",
        "source_page": 6,
        "new_commitments_mm": 1142.0,
        "fundings_mm": None,
        "repayments_sales_mm": 1483.0,
        "net_investment_activity_mm": -341.0,
        "new_investment_yield_pct": None,
        "repayment_yield_pct": None,
        "source_notes": [
            "FSK labels the New column source as Investment Purchases, not new commitments.",
            "FSK's adjusted net investment activity adds back net sales to COPJV; the dashboard Net column uses the reported Net Investment Activity row.",
        ],
    },
    {
        "fund": "FSK",
        "period_end": "2025-12-31",
        "source_title": "Q4 2025 FSK Earnings Supplement - Quarterly Investment Activity",
        "source_file": "source-docs/FSK Q4 2025 Earnings Supplement_Final.pdf",
        "source_page": 6,
        "new_commitments_mm": 1098.0,
        "fundings_mm": None,
        "repayments_sales_mm": 1334.0,
        "net_investment_activity_mm": -236.0,
        "new_investment_yield_pct": None,
        "repayment_yield_pct": None,
        "source_notes": [
            "FSK labels the New column source as Investment Purchases, not new commitments.",
            "FSK's adjusted net investment activity adds back net sales to COPJV; the dashboard Net column uses the reported Net Investment Activity row.",
        ],
    },
    {
        "fund": "FSK",
        "period_end": "2026-03-31",
        "source_title": "Q1 2026 FSK Earnings Supplement - Quarterly Investment Activity",
        "source_file": "source-docs/FSK Q1 2026 Earnings Supplement_Final (1).pdf",
        "source_page": 7,
        "new_commitments_mm": 499.0,
        "fundings_mm": None,
        "repayments_sales_mm": 710.0,
        "net_investment_activity_mm": -211.0,
        "new_investment_yield_pct": None,
        "repayment_yield_pct": None,
        "source_notes": [
            "FSK labels the New column source as Investment Purchases, not new commitments.",
            "FSK's adjusted net investment activity adds back net sales to COPJV; the dashboard Net column uses the reported Net Investment Activity row.",
        ],
    },
    {
        "fund": "TSLX",
        "period_end": "2025-03-31",
        "source_title": "Q1 2025 Sixth Street Specialty Lending Earnings Presentation - Funding Activity",
        "source_file": "source-docs/SLX 1Q'25 Earnings Presentation_vFF.pdf",
        "source_page": 10,
        "new_commitments_mm": 154.4,
        "fundings_mm": 136.8,
        "repayments_sales_mm": 269.6,
        "net_investment_activity_mm": -132.9,
        "new_investment_yield_pct": None,
        "repayment_yield_pct": None,
        "source_notes": [
            "TSLX labels this table as new investment commitments, fundings, paydowns and sales, and net funding or repayment activity.",
            "Amounts are shown in millions by fair value.",
        ],
    },
    {
        "fund": "TSLX",
        "period_end": "2025-06-30",
        "source_title": "Q2 2025 Sixth Street Specialty Lending Earnings Presentation - Funding Activity",
        "source_file": "source-docs/SLX 2Q'25 Earnings Presentation_vFF.pdf",
        "source_page": 10,
        "new_commitments_mm": 297.7,
        "fundings_mm": 208.6,
        "repayments_sales_mm": 388.7,
        "net_investment_activity_mm": -180.0,
        "new_investment_yield_pct": None,
        "repayment_yield_pct": None,
        "source_notes": [
            "TSLX labels this table as new investment commitments, fundings, paydowns and sales, and net funding or repayment activity.",
            "Amounts are shown in millions by fair value.",
        ],
    },
    {
        "fund": "TSLX",
        "period_end": "2025-09-30",
        "source_title": "Q3 2025 Sixth Street Specialty Lending Earnings Presentation - Funding Activity",
        "source_file": "source-docs/SLX 3Q'25 Earnings Presentation_vF.pdf",
        "source_page": 10,
        "new_commitments_mm": 387.7,
        "fundings_mm": 351.8,
        "repayments_sales_mm": 302.8,
        "net_investment_activity_mm": 49.0,
        "new_investment_yield_pct": None,
        "repayment_yield_pct": None,
        "source_notes": [
            "TSLX labels this table as new investment commitments, fundings, paydowns and sales, and net funding or repayment activity.",
            "Amounts are shown in millions by fair value.",
        ],
    },
    {
        "fund": "TSLX",
        "period_end": "2025-12-31",
        "source_title": "Q4 2025 Sixth Street Specialty Lending Earnings Presentation - Funding Activity",
        "source_file": "source-docs/SLX 4Q'25 Earnings Presentation_vF.pdf",
        "source_page": 13,
        "new_commitments_mm": 242.4,
        "fundings_mm": 196.7,
        "repayments_sales_mm": 234.9,
        "net_investment_activity_mm": -38.2,
        "new_investment_yield_pct": None,
        "repayment_yield_pct": None,
        "source_notes": [
            "TSLX labels this table as new investment commitments, fundings, paydowns and sales, and net funding or repayment activity.",
            "Amounts are shown in millions by fair value.",
        ],
    },
    {
        "fund": "TSLX",
        "period_end": "2026-03-31",
        "source_title": "Q1 2026 Sixth Street Specialty Lending Earnings Presentation - Funding Activity",
        "source_file": "source-docs/SLX 1Q'26 Earnings Presentation_vFF (1).pdf",
        "source_page": 10,
        "new_commitments_mm": 338.1,
        "fundings_mm": 134.8,
        "repayments_sales_mm": 113.0,
        "net_investment_activity_mm": 21.8,
        "new_investment_yield_pct": None,
        "repayment_yield_pct": None,
        "source_notes": [
            "TSLX labels this table as new investment commitments, fundings, paydowns and sales, and net funding or repayment activity.",
            "Amounts are shown in millions by fair value.",
        ],
    },
]


FACT_COLUMNS = [
    "fund",
    "period_end",
    "company_name",
    "report_type",
    "source_status",
    "source_title",
    "source_file",
    "holding_rows",
    "holdings_amortized_cost_mm",
    "holdings_fair_value_mm",
    "holdings_mark_vs_cost_mm",
    "holdings_mark_to_cost_pct",
    "holdings_first_lien_pct",
    "holdings_floating_rate_pct",
    "holdings_pik_fair_value_mm",
    "holdings_pik_fair_value_pct",
    "holdings_below_90_fair_value_mm",
    "holdings_below_80_fair_value_mm",
    "holdings_weighted_avg_spread_bps",
    "nav_per_share",
    "nii_mm",
    "nii_per_share",
    "adjusted_nii_mm",
    "adjusted_nii_per_share",
    "base_dividend_per_share",
    "total_dividend_per_share",
    "base_dividend_coverage_pct",
    "total_dividend_coverage_pct",
    "reported_total_investments_fv_mm",
    "total_debt_principal_mm",
    "net_assets_mm",
    "debt_to_equity_x",
    "avg_debt_to_equity_x",
    "net_debt_to_equity_x",
    "liquidity_mm",
    "debt_cost_pct",
    "weighted_avg_yield_pct",
    "weighted_avg_spread_over_base_rate_pct",
    "first_lien_pct",
    "floating_rate_debt_investments_pct",
    "non_accrual_fv_pct",
    "non_accrual_cost_pct",
    "pik_income_mm",
    "fee_income_mm",
    "new_commitments_mm",
    "fundings_mm",
    "repayments_sales_mm",
    "net_investment_activity_mm",
    "new_investment_yield_pct",
    "repayment_yield_pct",
    "source_notes_json",
    "created_at_utc",
]

MARKET_PRICE_NAV_COLUMNS = [
    "fund",
    "price_date",
    "close_price",
    "nav_per_share",
    "nav_period_end",
    "nav_mark_age_days",
    "price_to_nav_pct",
    "premium_discount_to_nav_pct",
    "close_price_source_file",
    "nav_source_title",
    "nav_source_file",
    "nav_source_page",
    "created_at_utc",
]

QUARTERLY_MARKET_FACT_COLUMNS = [
    "fund",
    "period_end",
    "quarter_start",
    "quarter_end",
    "trading_days",
    "quarter_end_price_date",
    "quarter_end_close_price",
    "avg_daily_close_price",
    "min_daily_close_price",
    "max_daily_close_price",
    "nav_per_share",
    "nav_period_end",
    "price_date_to_nav_date_days",
    "quarter_end_price_to_nav_pct",
    "quarter_end_premium_discount_to_nav_pct",
    "avg_price_to_nav_pct",
    "avg_premium_discount_to_nav_pct",
    "close_price_source_file",
    "nav_source_title",
    "nav_source_file",
    "nav_source_page",
    "source_notes_json",
    "created_at_utc",
]

NAV_MARK_COLUMNS = [
    "fund",
    "period_end",
    "nav_per_share",
    "source_title",
    "source_file",
    "source_page",
    "source_excerpt",
    "created_at_utc",
]

EXPENSE_FACT_COLUMNS = [
    "fund",
    "period_end",
    "source_title",
    "source_file",
    "source_pages_json",
    "total_investment_income_mm",
    "interest_income_mm",
    "pik_interest_income_mm",
    "fee_income_mm",
    "dividend_income_mm",
    "other_income_mm",
    "interest_expense_mm",
    "base_management_fee_mm",
    "income_incentive_fee_mm",
    "capital_gains_incentive_fee_mm",
    "total_incentive_fee_mm",
    "professional_fees_mm",
    "directors_or_board_fees_mm",
    "administrative_service_expense_mm",
    "accounting_administrative_fees_mm",
    "other_g_and_a_mm",
    "total_g_and_a_mm",
    "fee_waivers_mm",
    "total_operating_expenses_mm",
    "net_expenses_mm",
    "tax_expense_mm",
    "nii_mm",
    "source_notes_json",
    "created_at_utc",
]

INCOME_QUALITY_COLUMNS = [
    "fund",
    "period_end",
    "source_title",
    "source_file",
    "source_pages_json",
    "total_investment_income_mm",
    "reported_nii_mm",
    "reported_nii_per_share",
    "adjusted_nii_mm",
    "adjusted_nii_per_share",
    "weighted_average_shares",
    "pik_interest_income_mm",
    "pik_income_tii_pct",
    "pik_income_nii_pct",
    "interest_from_investments_other_fees_mm",
    "other_fees_tii_pct",
    "other_income_mm",
    "other_income_tii_pct",
    "fee_waivers_mm",
    "capital_gains_incentive_fee_not_payable_mm",
    "capital_gains_incentive_fee_not_payable_per_share",
    "cash_nii_ex_pik_mm",
    "cash_nii_ex_pik_per_share",
    "cash_like_recurring_nii_mm",
    "cash_like_recurring_nii_per_share",
    "base_dividend_per_share",
    "record_date_distributions_per_share",
    "quarter_related_supplemental_dividend_per_share",
    "quarter_related_total_dividend_per_share",
    "reported_base_dividend_coverage_pct",
    "reported_record_date_distribution_coverage_pct",
    "reported_quarter_related_distribution_coverage_pct",
    "adjusted_base_dividend_coverage_pct",
    "adjusted_record_date_distribution_coverage_pct",
    "cash_like_base_dividend_coverage_pct",
    "cash_like_record_date_distribution_coverage_pct",
    "one_time_items_json",
    "source_notes_json",
    "created_at_utc",
]

DIVIDEND_DECLARATION_COLUMNS = [
    "fund",
    "declared_date",
    "record_date",
    "payment_date",
    "amount_per_share",
    "dividend_type",
    "related_period_end",
    "source_title",
    "source_file",
    "source_page",
    "source_notes_json",
    "created_at_utc",
]

NON_ACCRUAL_ISSUER_COLUMNS = [
    "fund",
    "period_end",
    "issuer_name",
    "security_count",
    "amortized_cost_mm",
    "fair_value_mm",
    "source_title",
    "source_file",
    "source_pages_json",
    "source_method",
    "source_notes_json",
    "created_at_utc",
]

NON_ACCRUAL_SUMMARY_COLUMNS = [
    "fund",
    "period_end",
    "issuer_count",
    "security_count",
    "amortized_cost_mm",
    "fair_value_mm",
    "reported_non_accrual_cost_pct",
    "reported_non_accrual_fv_pct",
    "reported_non_accrual_cost_mm",
    "reported_non_accrual_fv_mm",
    "source_title",
    "source_file",
    "source_pages_json",
    "source_notes_json",
    "created_at_utc",
]

ISSUER_WATCHLIST_COLUMNS = [
    "fund",
    "period_end",
    "issuer_match_key",
    "issuer_name",
    "issuer_industries",
    "instrument_context",
    "instrument_context_detail",
    "security_count",
    "principal_mm",
    "principal_fair_value_mm",
    "amortized_cost_mm",
    "fair_value_mm",
    "mark_vs_cost_mm",
    "fv_to_cost_pct",
    "fv_to_principal_pct",
    "prior_period_end",
    "prior_fv_to_cost_pct",
    "prior_fv_to_principal_pct",
    "qoq_fv_to_cost_change_pct",
    "qoq_fv_to_principal_change_pct",
    "qoq_fair_value_change_mm",
    "qoq_mark_vs_cost_change_mm",
    "below_97_fv_to_cost",
    "below_90_fv_to_cost",
    "below_80_fv_to_cost",
    "below_97_fv_to_principal",
    "below_90_fv_to_principal",
    "below_80_fv_to_principal",
    "is_non_accrual",
    "shadow_non_accrual",
    "material_qoq_deterioration",
    "watchlist_bucket",
    "watchlist_severity",
    "source_title",
    "source_file",
    "source_method",
    "source_notes_json",
    "created_at_utc",
]

PRESENTATION_NAV_MARKS: list[dict[str, Any]] = [
    {
        "fund": "BXSL",
        "period_end": period_end,
        "nav_per_share": nav_per_share,
        "source_title": "Q1 2026 BXSL Earnings Presentation - Selected Financial Highlights",
        "source_file": "source-docs/Q1-2026-BXSL-Earnings-Presentation-vF (2).pdf",
        "source_page": 17,
        "source_excerpt": "Net asset value per share row in selected financial highlights.",
    }
    for period_end, nav_per_share in [
        ("2025-03-31", 27.39),
        ("2025-06-30", 27.33),
        ("2025-09-30", 27.15),
        ("2025-12-31", 26.92),
        ("2026-03-31", 26.26),
    ]
] + [
    {
        "fund": "FSK",
        "period_end": period_end,
        "nav_per_share": nav_per_share,
        "source_title": "Q1 2026 FSK Earnings Supplement - Financial Results",
        "source_file": "source-docs/FSK Q1 2026 Earnings Supplement_Final (1).pdf",
        "source_page": 4,
        "source_excerpt": "Net asset value per share at period end row in financial results.",
    }
    for period_end, nav_per_share in [
        ("2025-03-31", 23.37),
        ("2025-06-30", 21.93),
        ("2025-09-30", 21.99),
        ("2025-12-31", 20.89),
        ("2026-03-31", 18.83),
    ]
] + [
    {
        "fund": "TSLX",
        "period_end": period_end,
        "nav_per_share": nav_per_share,
        "source_title": "Q1 2026 Sixth Street Specialty Lending Earnings Presentation - Financial Highlights",
        "source_file": "source-docs/SLX 1Q'26 Earnings Presentation_vFF.pdf",
        "source_page": 5,
        "source_excerpt": "Net Asset Value Per Share (Ending Shares) row in financial highlights.",
    }
    for period_end, nav_per_share in [
        ("2025-03-31", 17.04),
        ("2025-06-30", 17.17),
        ("2025-09-30", 17.14),
        ("2025-12-31", 16.98),
        ("2026-03-31", 16.24),
    ]
]

BXSL_INCOME_QUALITY_SOURCE_NOTES = [
    "Presentation summary operating results supply reported NII, NII/share, total investment income, PIK interest income, residual fee or other income, regular dividends, and weighted average shares.",
    "BXSL did not disclose adjusted NII in the reviewed decks; adjusted NII fields are left null rather than equated to reported NII.",
    "Management fee waivers are carried from the filing-sourced income/expense layer; BXSL Q1 2025 through Q1 2026 rows are zero.",
    "Cash-like recurring NII is a conservative derived estimate: reported NII less PIK interest, fee income or other income, and the management fee waiver benefit.",
    "No BXSL taxable-income, spillover-income, undistributed taxable-income, or current supplemental dividend table was found in the supplied Q1 2025 through Q1 2026 earnings presentations.",
]

BXSL_INCOME_QUALITY_FACTS: list[dict[str, Any]] = [
    {
        "fund": "BXSL",
        "period_end": "2025-03-31",
        "source_title": "Q1 2025 BXSL Earnings Presentation",
        "source_file": "source-docs/Q1-2025-BXSL-Earnings-Presentation_vF-2.pdf",
        "source_pages": [5, 9, 10, 17],
        "total_investment_income_mm": 358.0,
        "reported_nii_mm": 189.0,
        "reported_nii_per_share": 0.83,
        "adjusted_nii_mm": None,
        "adjusted_nii_per_share": None,
        "weighted_average_shares": 226577167,
        "pik_interest_income_mm": 21.0,
        "interest_from_investments_other_fees_mm": 1.0,
        "other_income_mm": 0.0,
        "capital_gains_incentive_fee_not_payable_mm": None,
        "capital_gains_incentive_fee_not_payable_per_share": None,
        "base_dividend_per_share": 0.77,
        "record_date_distributions_per_share": 0.77,
        "quarter_related_supplemental_dividend_per_share": 0.0,
        "source_notes": BXSL_INCOME_QUALITY_SOURCE_NOTES,
    },
    {
        "fund": "BXSL",
        "period_end": "2025-06-30",
        "source_title": "Q2 2025 BXSL Earnings Presentation",
        "source_file": "source-docs/Q2-2025-BXSL-Earnings-Presentation_vF.pdf",
        "source_pages": [5, 9, 10, 17],
        "total_investment_income_mm": 345.0,
        "reported_nii_mm": 176.0,
        "reported_nii_per_share": 0.77,
        "adjusted_nii_mm": None,
        "adjusted_nii_per_share": None,
        "weighted_average_shares": 228192335,
        "pik_interest_income_mm": 22.0,
        "interest_from_investments_other_fees_mm": 1.0,
        "other_income_mm": 0.0,
        "capital_gains_incentive_fee_not_payable_mm": None,
        "capital_gains_incentive_fee_not_payable_per_share": None,
        "base_dividend_per_share": 0.77,
        "record_date_distributions_per_share": 0.77,
        "quarter_related_supplemental_dividend_per_share": 0.0,
        "source_notes": BXSL_INCOME_QUALITY_SOURCE_NOTES,
    },
    {
        "fund": "BXSL",
        "period_end": "2025-09-30",
        "source_title": "Q3 2025 BXSL Earnings Presentation",
        "source_file": "source-docs/Q3-2025-BXSL-Earnings-Presentation_vF.pdf",
        "source_pages": [5, 9, 10, 17],
        "total_investment_income_mm": 359.0,
        "reported_nii_mm": 189.0,
        "reported_nii_per_share": 0.82,
        "adjusted_nii_mm": None,
        "adjusted_nii_per_share": None,
        "weighted_average_shares": 230462792,
        "pik_interest_income_mm": 30.0,
        "interest_from_investments_other_fees_mm": 0.0,
        "other_income_mm": 0.0,
        "capital_gains_incentive_fee_not_payable_mm": None,
        "capital_gains_incentive_fee_not_payable_per_share": None,
        "base_dividend_per_share": 0.77,
        "record_date_distributions_per_share": 0.77,
        "quarter_related_supplemental_dividend_per_share": 0.0,
        "source_notes": BXSL_INCOME_QUALITY_SOURCE_NOTES,
    },
    {
        "fund": "BXSL",
        "period_end": "2025-12-31",
        "source_title": "Q4 2025 BXSL Earnings Presentation",
        "source_file": "source-docs/Q4-2025-BXSL-Earnings-Presentation_vF.pdf",
        "source_pages": [5, 9, 10, 17],
        "total_investment_income_mm": 358.0,
        "reported_nii_mm": 186.0,
        "reported_nii_per_share": 0.80,
        "adjusted_nii_mm": None,
        "adjusted_nii_per_share": None,
        "weighted_average_shares": 231349087,
        "pik_interest_income_mm": 30.0,
        "interest_from_investments_other_fees_mm": 0.0,
        "other_income_mm": 0.0,
        "capital_gains_incentive_fee_not_payable_mm": None,
        "capital_gains_incentive_fee_not_payable_per_share": None,
        "base_dividend_per_share": 0.77,
        "record_date_distributions_per_share": 0.77,
        "quarter_related_supplemental_dividend_per_share": 0.0,
        "source_notes": BXSL_INCOME_QUALITY_SOURCE_NOTES,
    },
    {
        "fund": "BXSL",
        "period_end": "2026-03-31",
        "source_title": "Q1 2026 BXSL Earnings Presentation",
        "source_file": "source-docs/Q1-2026-BXSL-Earnings-Presentation-vF (2).pdf",
        "source_pages": [5, 9, 10, 17],
        "total_investment_income_mm": 325.0,
        "reported_nii_mm": 179.0,
        "reported_nii_per_share": 0.77,
        "adjusted_nii_mm": None,
        "adjusted_nii_per_share": None,
        "weighted_average_shares": 232203849,
        "pik_interest_income_mm": 22.0,
        "interest_from_investments_other_fees_mm": 0.0,
        "other_income_mm": 2.0,
        "capital_gains_incentive_fee_not_payable_mm": None,
        "capital_gains_incentive_fee_not_payable_per_share": None,
        "base_dividend_per_share": 0.77,
        "record_date_distributions_per_share": 0.77,
        "quarter_related_supplemental_dividend_per_share": 0.0,
        "source_notes": BXSL_INCOME_QUALITY_SOURCE_NOTES,
    },
]

FSK_INCOME_QUALITY_SOURCE_NOTES = [
    "FSK supplements supply reported NII, adjusted NII, per-share NII metrics, total investment income, PIK interest income, fee income, distribution amounts, and weighted average shares.",
    "Adjusted NII is disclosed by FSK and excludes capital gains incentive fee accruals, excise taxes, merger accounting accretion, and one-time expenses as described in the appendix.",
    "FSK reports a combined total dividend and other income line; because the supplements do not split recurring dividend income from miscellaneous other income, no separate other-income deduction is recorded in the bridge.",
    "FSK distribution timing can differ by table: the Financial Results rows show distributions declared, while coverage should use the distribution paid for or tied to the earnings quarter when that language is disclosed.",
    "Fee waivers are carried from the filing-sourced income/expense layer and are zero for Q1 2025 through Q1 2026; the Q1 2026 supplement describes an incentive fee waiver beginning with Q2 2026.",
    "No FSK taxable-income, spillover-income, or undistributed taxable-income table was found in the supplied Q1 2025 through Q1 2026 earnings supplements.",
]

FSK_INCOME_QUALITY_FACTS: list[dict[str, Any]] = [
    {
        "fund": "FSK",
        "period_end": "2025-03-31",
        "source_title": "Q1 2025 FSK Earnings Supplement",
        "source_file": "source-docs/FSK Q1 2025 Earnings Supplement_Final.pdf",
        "source_pages": [2, 3, 12, 13],
        "total_investment_income_mm": 400.0,
        "reported_nii_mm": 187.0,
        "reported_nii_per_share": 0.67,
        "adjusted_nii_mm": 182.0,
        "adjusted_nii_per_share": 0.65,
        "weighted_average_shares": 280100000,
        "pik_interest_income_mm": 62.0,
        "interest_from_investments_other_fees_mm": 17.0,
        "other_income_mm": 0.0,
        "fee_waivers_mm": 0.0,
        "capital_gains_incentive_fee_not_payable_mm": None,
        "capital_gains_incentive_fee_not_payable_per_share": None,
        "base_dividend_per_share": 0.64,
        "record_date_distributions_per_share": 0.70,
        "quarter_related_supplemental_dividend_per_share": 0.06,
        "one_time_items": [
            "Adjusted NII reconciliation includes net merger accretion and one-time expenses of $(5)mm.",
            "No excise-tax addback is recorded for the Q1 2025 adjusted NII reconciliation.",
        ],
        "source_notes": FSK_INCOME_QUALITY_SOURCE_NOTES,
    },
    {
        "fund": "FSK",
        "period_end": "2025-06-30",
        "source_title": "Q2 2025 FSK Earnings Supplement",
        "source_file": "source-docs/FSK Q2 2025 Earnings Supplement_Final.pdf",
        "source_pages": [2, 3, 12, 13],
        "total_investment_income_mm": 398.0,
        "reported_nii_mm": 173.0,
        "reported_nii_per_share": 0.62,
        "adjusted_nii_mm": 168.0,
        "adjusted_nii_per_share": 0.60,
        "weighted_average_shares": 280100000,
        "pik_interest_income_mm": 53.0,
        "interest_from_investments_other_fees_mm": 9.0,
        "other_income_mm": 0.0,
        "fee_waivers_mm": 0.0,
        "capital_gains_incentive_fee_not_payable_mm": None,
        "capital_gains_incentive_fee_not_payable_per_share": None,
        "base_dividend_per_share": 0.64,
        "record_date_distributions_per_share": 0.70,
        "quarter_related_supplemental_dividend_per_share": 0.06,
        "one_time_items": [
            "Adjusted NII reconciliation includes net merger accretion and one-time expenses of $(5)mm.",
            "No excise-tax addback is recorded for the Q2 2025 adjusted NII reconciliation.",
        ],
        "source_notes": FSK_INCOME_QUALITY_SOURCE_NOTES,
    },
    {
        "fund": "FSK",
        "period_end": "2025-09-30",
        "source_title": "Q3 2025 FSK Earnings Supplement",
        "source_file": "source-docs/FSK Q3 2025 Earnings Supplement_Final (1).pdf",
        "source_pages": [2, 3, 12, 13],
        "total_investment_income_mm": 373.0,
        "reported_nii_mm": 159.0,
        "reported_nii_per_share": 0.57,
        "adjusted_nii_mm": 159.0,
        "adjusted_nii_per_share": 0.57,
        "weighted_average_shares": 280100000,
        "pik_interest_income_mm": 54.0,
        "interest_from_investments_other_fees_mm": 4.0,
        "other_income_mm": 0.0,
        "fee_waivers_mm": 0.0,
        "capital_gains_incentive_fee_not_payable_mm": None,
        "capital_gains_incentive_fee_not_payable_per_share": None,
        "base_dividend_per_share": 0.64,
        "record_date_distributions_per_share": 0.70,
        "quarter_related_supplemental_dividend_per_share": 0.06,
        "one_time_items": [
            "Adjusted NII reconciliation includes a $4mm excise-tax addback.",
            "Adjusted NII reconciliation includes net merger accretion and one-time expenses of $(4)mm.",
        ],
        "source_notes": FSK_INCOME_QUALITY_SOURCE_NOTES,
    },
    {
        "fund": "FSK",
        "period_end": "2025-12-31",
        "source_title": "Q4 2025 FSK Earnings Supplement",
        "source_file": "source-docs/FSK Q4 2025 Earnings Supplement_Final.pdf",
        "source_pages": [2, 3, 12, 13],
        "total_investment_income_mm": 348.0,
        "reported_nii_mm": 135.0,
        "reported_nii_per_share": 0.48,
        "adjusted_nii_mm": 147.0,
        "adjusted_nii_per_share": 0.52,
        "weighted_average_shares": 280100000,
        "pik_interest_income_mm": 55.0,
        "interest_from_investments_other_fees_mm": 6.0,
        "other_income_mm": 0.0,
        "fee_waivers_mm": 0.0,
        "capital_gains_incentive_fee_not_payable_mm": None,
        "capital_gains_incentive_fee_not_payable_per_share": None,
        "base_dividend_per_share": 0.45,
        "record_date_distributions_per_share": 0.48,
        "quarter_related_supplemental_dividend_per_share": 0.03,
        "one_time_items": [
            "Adjusted NII reconciliation includes a $15mm excise-tax addback.",
            "Adjusted NII reconciliation includes net merger accretion and one-time expenses of $(3)mm.",
        ],
        "source_notes": FSK_INCOME_QUALITY_SOURCE_NOTES,
    },
    {
        "fund": "FSK",
        "period_end": "2026-03-31",
        "source_title": "Q1 2026 FSK Earnings Supplement",
        "source_file": "source-docs/FSK Q1 2026 Earnings Supplement_Final (1).pdf",
        "source_pages": [2, 3, 4, 13, 14],
        "total_investment_income_mm": 304.0,
        "reported_nii_mm": 117.0,
        "reported_nii_per_share": 0.42,
        "adjusted_nii_mm": 116.0,
        "adjusted_nii_per_share": 0.41,
        "weighted_average_shares": 280100000,
        "pik_interest_income_mm": 38.0,
        "interest_from_investments_other_fees_mm": 2.0,
        "other_income_mm": 0.0,
        "fee_waivers_mm": 0.0,
        "capital_gains_incentive_fee_not_payable_mm": None,
        "capital_gains_incentive_fee_not_payable_per_share": None,
        "base_dividend_per_share": 0.45,
        "record_date_distributions_per_share": 0.48,
        "quarter_related_supplemental_dividend_per_share": 0.03,
        "one_time_items": [
            "Adjusted NII reconciliation includes net merger accretion and one-time expenses of $(1)mm.",
            "FSK's 3/31/26 Financial Results row shows a $0.42 base distribution declared per share, but the supplement separately states that first-quarter 2026 distributions paid were $0.45 base plus $0.03 supplemental. The bridge uses the $0.48 quarter-related total for Q1 coverage.",
            "The Q1 2026 supplement describes an incentive fee waiver beginning with Q2 2026, outside this reviewed period.",
        ],
        "source_notes": FSK_INCOME_QUALITY_SOURCE_NOTES,
    },
]

TSLX_INCOME_QUALITY_FACTS: list[dict[str, Any]] = [
    {
        "fund": "TSLX",
        "period_end": "2025-03-31",
        "source_title": "Q1 2025 Sixth Street Specialty Lending Earnings Presentation",
        "source_file": "source-docs/SLX 1Q'25 Earnings Presentation_vFF.pdf",
        "source_pages": [5, 8, 9, 16, 17],
        "reported_nii_mm": 57.978,
        "reported_nii_per_share": 0.62,
        "adjusted_nii_mm": 54.292,
        "adjusted_nii_per_share": 0.58,
        "weighted_average_shares": 93669671,
        "interest_from_investments_other_fees_mm": 14.035,
        "other_income_mm": 3.460,
        "capital_gains_incentive_fee_not_payable_mm": -3.686,
        "capital_gains_incentive_fee_not_payable_per_share": -0.04,
        "base_dividend_per_share": 0.46,
        "record_date_distributions_per_share": 0.53,
        "quarter_related_supplemental_dividend_per_share": 0.06,
        "one_time_items": [
            "Adjusted NII excludes the accrued-but-not-payable capital gains incentive fee.",
            "NAV bridge shows a $0.13 per share reversal of net unrealized gains from paydowns and sales.",
        ],
    },
    {
        "fund": "TSLX",
        "period_end": "2025-06-30",
        "source_title": "Q2 2025 Sixth Street Specialty Lending Earnings Presentation",
        "source_file": "source-docs/SLX 2Q'25 Earnings Presentation_vFF.pdf",
        "source_pages": [5, 8, 9, 16, 17],
        "reported_nii_mm": 50.840,
        "reported_nii_per_share": 0.54,
        "adjusted_nii_mm": 52.278,
        "adjusted_nii_per_share": 0.56,
        "weighted_average_shares": 93971164,
        "interest_from_investments_other_fees_mm": 10.243,
        "other_income_mm": 7.612,
        "capital_gains_incentive_fee_not_payable_mm": 1.438,
        "capital_gains_incentive_fee_not_payable_per_share": 0.02,
        "base_dividend_per_share": 0.46,
        "record_date_distributions_per_share": 0.52,
        "quarter_related_supplemental_dividend_per_share": 0.05,
        "one_time_items": [
            "Adjusted NII excludes the accrued-but-not-payable capital gains incentive fee.",
            "NAV bridge notes the Lithium Technologies restructuring impact is shown net between unrealized-loss reversal and realized loss.",
        ],
    },
    {
        "fund": "TSLX",
        "period_end": "2025-09-30",
        "source_title": "Q3 2025 Sixth Street Specialty Lending Earnings Presentation",
        "source_file": "source-docs/SLX 3Q'25 Earnings Presentation_vF.pdf",
        "source_pages": [5, 8, 9, 16, 17],
        "reported_nii_mm": 50.680,
        "reported_nii_per_share": 0.54,
        "adjusted_nii_mm": 49.626,
        "adjusted_nii_per_share": 0.53,
        "weighted_average_shares": 94245993,
        "interest_from_investments_other_fees_mm": 6.817,
        "other_income_mm": 7.400,
        "capital_gains_incentive_fee_not_payable_mm": -1.054,
        "capital_gains_incentive_fee_not_payable_per_share": -0.01,
        "base_dividend_per_share": 0.46,
        "record_date_distributions_per_share": 0.51,
        "quarter_related_supplemental_dividend_per_share": 0.03,
        "one_time_items": [
            "Adjusted NII excludes the accrued-but-not-payable capital gains incentive fee.",
        ],
    },
    {
        "fund": "TSLX",
        "period_end": "2025-12-31",
        "source_title": "Q4 2025 Sixth Street Specialty Lending Earnings Presentation",
        "source_file": "source-docs/SLX 4Q'25 Earnings Presentation_vF.pdf",
        "source_pages": [7, 10, 12, 19, 20, 21],
        "reported_nii_mm": 50.497,
        "reported_nii_per_share": 0.53,
        "adjusted_nii_mm": 48.729,
        "adjusted_nii_per_share": 0.52,
        "weighted_average_shares": 94497933,
        "interest_from_investments_other_fees_mm": 10.881,
        "other_income_mm": 1.877,
        "capital_gains_incentive_fee_not_payable_mm": -1.768,
        "capital_gains_incentive_fee_not_payable_per_share": -0.02,
        "base_dividend_per_share": 0.46,
        "record_date_distributions_per_share": 0.49,
        "quarter_related_supplemental_dividend_per_share": 0.01,
        "one_time_items": [
            "Adjusted NII excludes the accrued-but-not-payable capital gains incentive fee.",
            "NAV bridge notes the IRGSE Holding Corp restructuring impact is shown net between unrealized-loss reversal and realized loss.",
        ],
    },
    {
        "fund": "TSLX",
        "period_end": "2026-03-31",
        "source_title": "Q1 2026 Sixth Street Specialty Lending Earnings Presentation",
        "source_file": "source-docs/SLX 1Q'26 Earnings Presentation_vFF (1).pdf",
        "source_pages": [5, 8, 9, 16, 17],
        "reported_nii_mm": 39.842,
        "reported_nii_per_share": 0.42,
        "adjusted_nii_mm": 39.842,
        "adjusted_nii_per_share": 0.42,
        "weighted_average_shares": 94709407,
        "interest_from_investments_other_fees_mm": 3.362,
        "other_income_mm": 2.190,
        "capital_gains_incentive_fee_not_payable_mm": 0.0,
        "capital_gains_incentive_fee_not_payable_per_share": 0.0,
        "base_dividend_per_share": 0.46,
        "record_date_distributions_per_share": 0.47,
        "quarter_related_supplemental_dividend_per_share": 0.0,
        "one_time_items": [
            "NAV bridge notes the Astra Acquisition Corp realization impact is shown net between unrealized-loss reversal and realized loss.",
            "The May 5, 2026 distribution table row declares a $0.42 base dividend with a June 15, 2026 record date; this row is outside the Q1 2026 record-date distribution total.",
        ],
    },
]

INCOME_QUALITY_FACTS: list[dict[str, Any]] = (
    BXSL_INCOME_QUALITY_FACTS + FSK_INCOME_QUALITY_FACTS + TSLX_INCOME_QUALITY_FACTS
)

BXSL_DIVIDEND_DECLARATION_SOURCE_NOTES = [
    "Extracted from the BXSL earnings-presentation press-release dividend declaration text.",
    "BXSL rows are regular base dividend declarations; no current supplemental dividend declaration table was found in the reviewed decks.",
]

BXSL_DIVIDEND_DECLARATION_FACTS: list[dict[str, Any]] = [
    {
        "fund": "BXSL",
        "declared_date": "2025-05-07",
        "record_date": "2025-06-30",
        "payment_date": "2025-07-25",
        "amount_per_share": 0.77,
        "dividend_type": "base",
        "related_period_end": "2025-06-30",
        "source_title": "Q1 2025 BXSL Earnings Presentation - Dividend Declaration",
        "source_file": "source-docs/Q1-2025-BXSL-Earnings-Presentation_vF-2.pdf",
        "source_page": 1,
        "source_notes": BXSL_DIVIDEND_DECLARATION_SOURCE_NOTES,
    },
    {
        "fund": "BXSL",
        "declared_date": "2025-08-06",
        "record_date": "2025-09-30",
        "payment_date": "2025-10-24",
        "amount_per_share": 0.77,
        "dividend_type": "base",
        "related_period_end": "2025-09-30",
        "source_title": "Q2 2025 BXSL Earnings Presentation - Dividend Declaration",
        "source_file": "source-docs/Q2-2025-BXSL-Earnings-Presentation_vF.pdf",
        "source_page": 1,
        "source_notes": BXSL_DIVIDEND_DECLARATION_SOURCE_NOTES,
    },
    {
        "fund": "BXSL",
        "declared_date": "2025-11-10",
        "record_date": "2025-12-31",
        "payment_date": "2026-01-23",
        "amount_per_share": 0.77,
        "dividend_type": "base",
        "related_period_end": "2025-12-31",
        "source_title": "Q3 2025 BXSL Earnings Presentation - Dividend Declaration",
        "source_file": "source-docs/Q3-2025-BXSL-Earnings-Presentation_vF.pdf",
        "source_page": 1,
        "source_notes": BXSL_DIVIDEND_DECLARATION_SOURCE_NOTES,
    },
    {
        "fund": "BXSL",
        "declared_date": "2026-02-25",
        "record_date": "2026-03-31",
        "payment_date": "2026-04-24",
        "amount_per_share": 0.77,
        "dividend_type": "base",
        "related_period_end": "2026-03-31",
        "source_title": "Q4 2025 BXSL Earnings Presentation - Dividend Declaration",
        "source_file": "source-docs/Q4-2025-BXSL-Earnings-Presentation_vF.pdf",
        "source_page": 1,
        "source_notes": BXSL_DIVIDEND_DECLARATION_SOURCE_NOTES,
    },
    {
        "fund": "BXSL",
        "declared_date": "2026-05-07",
        "record_date": "2026-06-30",
        "payment_date": "2026-07-24",
        "amount_per_share": 0.77,
        "dividend_type": "base",
        "related_period_end": "2026-06-30",
        "source_title": "Q1 2026 BXSL Earnings Presentation - Dividend Declaration",
        "source_file": "source-docs/Q1-2026-BXSL-Earnings-Presentation-vF (2).pdf",
        "source_page": 1,
        "source_notes": BXSL_DIVIDEND_DECLARATION_SOURCE_NOTES,
    },
]

FSK_DIVIDEND_DECLARATION_SOURCE_NOTES = [
    "FSK supplements disclose base and supplemental distribution amounts but do not provide declaration, record, or payment dates in a table comparable to BXSL or TSLX.",
]

FSK_DIVIDEND_DECLARATION_FACTS: list[dict[str, Any]] = []

TSLX_DIVIDEND_DECLARATION_FACTS: list[dict[str, Any]] = [
    {
        "fund": "TSLX",
        "declared_date": "2025-02-13",
        "record_date": "2025-02-28",
        "payment_date": "2025-03-20",
        "amount_per_share": 0.07,
        "dividend_type": "supplemental",
        "related_period_end": "2024-12-31",
        "source_title": "Q1 2025 Sixth Street Specialty Lending Earnings Presentation - Last 3 Years Distribution Information",
        "source_file": "source-docs/SLX 1Q'25 Earnings Presentation_vFF.pdf",
        "source_page": 16,
    },
    {
        "fund": "TSLX",
        "declared_date": "2025-02-13",
        "record_date": "2025-03-14",
        "payment_date": "2025-03-31",
        "amount_per_share": 0.46,
        "dividend_type": "base",
        "related_period_end": "2025-03-31",
        "source_title": "Q1 2025 Sixth Street Specialty Lending Earnings Presentation - Last 3 Years Distribution Information",
        "source_file": "source-docs/SLX 1Q'25 Earnings Presentation_vFF.pdf",
        "source_page": 16,
    },
    {
        "fund": "TSLX",
        "declared_date": "2025-04-30",
        "record_date": "2025-05-30",
        "payment_date": "2025-06-20",
        "amount_per_share": 0.06,
        "dividend_type": "supplemental",
        "related_period_end": "2025-03-31",
        "source_title": "Q1 2025 Sixth Street Specialty Lending Earnings Presentation - Last 3 Years Distribution Information",
        "source_file": "source-docs/SLX 1Q'25 Earnings Presentation_vFF.pdf",
        "source_page": 16,
    },
    {
        "fund": "TSLX",
        "declared_date": "2025-04-30",
        "record_date": "2025-06-16",
        "payment_date": "2025-06-30",
        "amount_per_share": 0.46,
        "dividend_type": "base",
        "related_period_end": "2025-06-30",
        "source_title": "Q1 2025 Sixth Street Specialty Lending Earnings Presentation - Last 3 Years Distribution Information",
        "source_file": "source-docs/SLX 1Q'25 Earnings Presentation_vFF.pdf",
        "source_page": 16,
    },
    {
        "fund": "TSLX",
        "declared_date": "2025-07-30",
        "record_date": "2025-08-29",
        "payment_date": "2025-09-19",
        "amount_per_share": 0.05,
        "dividend_type": "supplemental",
        "related_period_end": "2025-06-30",
        "source_title": "Q2 2025 Sixth Street Specialty Lending Earnings Presentation - Last 3 Years Distribution Information",
        "source_file": "source-docs/SLX 2Q'25 Earnings Presentation_vFF.pdf",
        "source_page": 16,
    },
    {
        "fund": "TSLX",
        "declared_date": "2025-07-30",
        "record_date": "2025-09-15",
        "payment_date": "2025-09-30",
        "amount_per_share": 0.46,
        "dividend_type": "base",
        "related_period_end": "2025-09-30",
        "source_title": "Q2 2025 Sixth Street Specialty Lending Earnings Presentation - Last 3 Years Distribution Information",
        "source_file": "source-docs/SLX 2Q'25 Earnings Presentation_vFF.pdf",
        "source_page": 16,
    },
    {
        "fund": "TSLX",
        "declared_date": "2025-11-04",
        "record_date": "2025-11-28",
        "payment_date": "2025-12-19",
        "amount_per_share": 0.03,
        "dividend_type": "supplemental",
        "related_period_end": "2025-09-30",
        "source_title": "Q3 2025 Sixth Street Specialty Lending Earnings Presentation - Last 3 Years Distribution Information",
        "source_file": "source-docs/SLX 3Q'25 Earnings Presentation_vF.pdf",
        "source_page": 16,
    },
    {
        "fund": "TSLX",
        "declared_date": "2025-11-04",
        "record_date": "2025-12-15",
        "payment_date": "2025-12-31",
        "amount_per_share": 0.46,
        "dividend_type": "base",
        "related_period_end": "2025-12-31",
        "source_title": "Q3 2025 Sixth Street Specialty Lending Earnings Presentation - Last 3 Years Distribution Information",
        "source_file": "source-docs/SLX 3Q'25 Earnings Presentation_vF.pdf",
        "source_page": 16,
    },
    {
        "fund": "TSLX",
        "declared_date": "2026-02-12",
        "record_date": "2026-02-27",
        "payment_date": "2026-03-20",
        "amount_per_share": 0.01,
        "dividend_type": "supplemental",
        "related_period_end": "2025-12-31",
        "source_title": "Q4 2025 Sixth Street Specialty Lending Earnings Presentation - Last 3 Years Distribution Information",
        "source_file": "source-docs/SLX 4Q'25 Earnings Presentation_vF.pdf",
        "source_page": 19,
    },
    {
        "fund": "TSLX",
        "declared_date": "2026-02-12",
        "record_date": "2026-03-16",
        "payment_date": "2026-03-31",
        "amount_per_share": 0.46,
        "dividend_type": "base",
        "related_period_end": "2026-03-31",
        "source_title": "Q4 2025 Sixth Street Specialty Lending Earnings Presentation - Last 3 Years Distribution Information",
        "source_file": "source-docs/SLX 4Q'25 Earnings Presentation_vF.pdf",
        "source_page": 19,
    },
    {
        "fund": "TSLX",
        "declared_date": "2026-05-05",
        "record_date": "2026-06-15",
        "payment_date": "2026-06-30",
        "amount_per_share": 0.42,
        "dividend_type": "base",
        "related_period_end": "2026-06-30",
        "source_title": "TSLX Q1 2026 Form 8-K press release - Dividend Declaration",
        "source_file": "source-docs/0001193125-26-206354.pdf",
        "source_page": 4,
        "source_notes": [
            "Extracted from the May 5, 2026 Form 8-K press-release dividend declaration text.",
            "This Q2 2026 base dividend row sits outside the Q1 2026 record-date distribution total.",
        ],
    },
]

DIVIDEND_DECLARATION_FACTS: list[dict[str, Any]] = (
    BXSL_DIVIDEND_DECLARATION_FACTS + FSK_DIVIDEND_DECLARATION_FACTS + TSLX_DIVIDEND_DECLARATION_FACTS
)

FILING_INCOME_EXPENSE_FACTS: list[dict[str, Any]] = [
    {
        "fund": "BXSL",
        "period_end": "2026-03-31",
        "source_title": "BXSL Q1 2026 Form 10-Q",
        "source_file": "source-docs/f0cb87a2-e0bd-4243-85e1-5816094738a1 (2).pdf",
        "source_pages": [6, 140, 141],
        "total_investment_income_mm": 325.471,
        "interest_income_mm": 302.216,
        "pik_interest_income_mm": 21.536,
        "fee_income_mm": None,
        "dividend_income_mm": 0.020,
        "other_income_mm": 1.699,
        "interest_expense_mm": 100.169,
        "base_management_fee_mm": 36.366,
        "income_incentive_fee_mm": 2.294,
        "capital_gains_incentive_fee_mm": 0.0,
        "professional_fees_mm": 1.217,
        "directors_or_board_fees_mm": 0.290,
        "administrative_service_expense_mm": 1.125,
        "accounting_administrative_fees_mm": None,
        "other_g_and_a_mm": 1.006,
        "total_g_and_a_mm": 3.638,
        "fee_waivers_mm": 0.0,
        "total_operating_expenses_mm": 142.467,
        "net_expenses_mm": 142.467,
        "tax_expense_mm": 4.090,
        "nii_mm": 178.914,
        "source_notes": [
            "Dollar amounts are converted from the 10-Q statement of operations shown in thousands.",
            "Other income is kept separate because the 10-Q does not label it solely as fee income.",
        ],
    },
    {
        "fund": "BXSL",
        "period_end": "2025-03-31",
        "source_title": "BXSL Q1 2025 Form 10-Q",
        "source_file": "source-docs/c136ea54-8c10-4475-8cc8-978e61d94be0 (1).pdf",
        "source_pages": [6],
        "total_investment_income_mm": 357.764,
        "interest_income_mm": 335.686,
        "pik_interest_income_mm": 21.353,
        "fee_income_mm": 0.725,
        "dividend_income_mm": 0.0,
        "other_income_mm": None,
        "interest_expense_mm": 92.976,
        "base_management_fee_mm": 34.301,
        "income_incentive_fee_mm": 34.301,
        "capital_gains_incentive_fee_mm": 0.0,
        "professional_fees_mm": 0.886,
        "directors_or_board_fees_mm": 0.306,
        "administrative_service_expense_mm": 0.966,
        "accounting_administrative_fees_mm": None,
        "other_g_and_a_mm": 1.063,
        "total_g_and_a_mm": 2.255,
        "fee_waivers_mm": 0.0,
        "total_operating_expenses_mm": 164.799,
        "net_expenses_mm": 164.799,
        "tax_expense_mm": 4.169,
        "nii_mm": 188.796,
        "source_notes": [
            "Dollar amounts are converted from the 10-Q statement of operations shown in thousands.",
            "Interest income and PIK income each aggregate controlled, affiliated, and non-affiliated investment categories.",
        ],
    },
    {
        "fund": "BXSL",
        "period_end": "2025-06-30",
        "source_title": "BXSL Q2 2025 Form 10-Q",
        "source_file": "source-docs/6eef3db0-e474-4c9e-bc7a-d720f6bca8ad (1).pdf",
        "source_pages": [6],
        "total_investment_income_mm": 344.803,
        "interest_income_mm": 321.083,
        "pik_interest_income_mm": 22.173,
        "fee_income_mm": 1.498,
        "dividend_income_mm": 0.049,
        "other_income_mm": None,
        "interest_expense_mm": 92.285,
        "base_management_fee_mm": 34.600,
        "income_incentive_fee_mm": 34.718,
        "capital_gains_incentive_fee_mm": 0.0,
        "professional_fees_mm": 1.243,
        "directors_or_board_fees_mm": 0.293,
        "administrative_service_expense_mm": 0.744,
        "accounting_administrative_fees_mm": None,
        "other_g_and_a_mm": 1.220,
        "total_g_and_a_mm": 3.500,
        "fee_waivers_mm": 0.0,
        "total_operating_expenses_mm": 165.103,
        "net_expenses_mm": 165.103,
        "tax_expense_mm": 3.798,
        "nii_mm": 175.902,
        "source_notes": [
            "Dollar amounts are converted from the 10-Q statement of operations shown in thousands.",
            "Interest income and PIK income each aggregate controlled, affiliated, and non-affiliated investment categories.",
        ],
    },
    {
        "fund": "BXSL",
        "period_end": "2025-09-30",
        "source_title": "BXSL Q3 2025 Form 10-Q",
        "source_file": "source-docs/3a21d3e0-48cb-40e5-b3b4-9854c5bb2937 (2).pdf",
        "source_pages": [6],
        "total_investment_income_mm": 358.557,
        "interest_income_mm": 327.952,
        "pik_interest_income_mm": 29.519,
        "fee_income_mm": 0.285,
        "dividend_income_mm": 0.801,
        "other_income_mm": None,
        "interest_expense_mm": 94.691,
        "base_management_fee_mm": 34.959,
        "income_incentive_fee_mm": 31.254,
        "capital_gains_incentive_fee_mm": 0.0,
        "professional_fees_mm": 1.402,
        "directors_or_board_fees_mm": 0.282,
        "administrative_service_expense_mm": 0.766,
        "accounting_administrative_fees_mm": None,
        "other_g_and_a_mm": 1.497,
        "total_g_and_a_mm": 3.947,
        "fee_waivers_mm": 0.0,
        "total_operating_expenses_mm": 164.851,
        "net_expenses_mm": 164.851,
        "tax_expense_mm": 4.232,
        "nii_mm": 189.474,
        "source_notes": [
            "Dollar amounts are converted from the 10-Q statement of operations shown in thousands.",
            "Interest income and PIK income each aggregate controlled, affiliated, and non-affiliated investment categories.",
        ],
    },
    {
        "fund": "BXSL",
        "period_end": "2025-12-31",
        "source_title": "BXSL 2025 Form 10-K annual-derived Q4 2025",
        "source_file": "source-docs/bxsl10k25.pdf",
        "source_pages": [151, 152],
        "total_investment_income_mm": 357.829,
        "interest_income_mm": 326.982,
        "pik_interest_income_mm": 30.135,
        "fee_income_mm": None,
        "dividend_income_mm": 0.218,
        "other_income_mm": 0.494,
        "interest_expense_mm": 101.687,
        "base_management_fee_mm": 36.141,
        "income_incentive_fee_mm": 26.400,
        "capital_gains_incentive_fee_mm": 0.0,
        "professional_fees_mm": 1.381,
        "directors_or_board_fees_mm": 0.289,
        "administrative_service_expense_mm": 1.018,
        "accounting_administrative_fees_mm": None,
        "other_g_and_a_mm": 1.238,
        "total_g_and_a_mm": 3.926,
        "fee_waivers_mm": 0.0,
        "total_operating_expenses_mm": 168.154,
        "net_expenses_mm": 168.154,
        "tax_expense_mm": 3.905,
        "nii_mm": 185.770,
        "source_notes": [
            "Q4 2025 is derived as full-year 2025 Form 10-K amounts less the Q3 2025 year-to-date 10-Q amounts.",
            "Dollar amounts are converted from filing statement amounts shown in thousands.",
            "The annual statement labels the residual non-interest and non-PIK line as other income; Q1 through Q3 2025 10-Qs labeled the comparable line as fee income.",
        ],
    },
    {
        "fund": "FSK",
        "period_end": "2026-03-31",
        "source_title": "FSK Q1 2026 Form 10-Q",
        "source_file": "source-docs/0001628280-26-033118.pdf",
        "source_pages": [4, 58, 59, 92, 93, 99],
        "total_investment_income_mm": 304.0,
        "interest_income_mm": 186.0,
        "pik_interest_income_mm": 38.0,
        "fee_income_mm": 2.0,
        "dividend_income_mm": 78.0,
        "other_income_mm": None,
        "interest_expense_mm": 105.0,
        "base_management_fee_mm": 48.0,
        "income_incentive_fee_mm": 25.0,
        "capital_gains_incentive_fee_mm": 0.0,
        "professional_fees_mm": None,
        "directors_or_board_fees_mm": None,
        "administrative_service_expense_mm": 2.0,
        "accounting_administrative_fees_mm": 1.0,
        "other_g_and_a_mm": 6.0,
        "total_g_and_a_mm": 9.0,
        "fee_waivers_mm": 0.0,
        "total_operating_expenses_mm": 187.0,
        "net_expenses_mm": 187.0,
        "tax_expense_mm": None,
        "nii_mm": 117.0,
        "source_notes": [
            "Dollar amounts are stated in millions in the 10-Q.",
            "The disclosed KKR Credit subordinated income incentive fee waiver begins with the quarter ending June 30, 2026, so no Q1 2026 waiver amount is recorded here.",
        ],
    },
    {
        "fund": "FSK",
        "period_end": "2025-03-31",
        "source_title": "FSK Q1 2025 Form 10-Q",
        "source_file": "source-docs/0001628280-25-023202.pdf",
        "source_pages": [4],
        "total_investment_income_mm": 400.0,
        "interest_income_mm": 240.0,
        "pik_interest_income_mm": 62.0,
        "fee_income_mm": 17.0,
        "dividend_income_mm": 81.0,
        "other_income_mm": None,
        "interest_expense_mm": 113.0,
        "base_management_fee_mm": 52.0,
        "income_incentive_fee_mm": 39.0,
        "capital_gains_incentive_fee_mm": 0.0,
        "professional_fees_mm": None,
        "directors_or_board_fees_mm": None,
        "administrative_service_expense_mm": 3.0,
        "accounting_administrative_fees_mm": 1.0,
        "other_g_and_a_mm": 5.0,
        "total_g_and_a_mm": 9.0,
        "fee_waivers_mm": 0.0,
        "total_operating_expenses_mm": 213.0,
        "net_expenses_mm": 213.0,
        "tax_expense_mm": None,
        "nii_mm": 187.0,
        "source_notes": [
            "Dollar amounts are stated in millions in the 10-Q statement of operations.",
            "Income line items aggregate non-controlled/unaffiliated, non-controlled/affiliated, and controlled/affiliated investment income categories.",
        ],
    },
    {
        "fund": "FSK",
        "period_end": "2025-06-30",
        "source_title": "FSK Q2 2025 Form 10-Q",
        "source_file": "source-docs/0001628280-25-038368.pdf",
        "source_pages": [4],
        "total_investment_income_mm": 398.0,
        "interest_income_mm": 245.0,
        "pik_interest_income_mm": 53.0,
        "fee_income_mm": 9.0,
        "dividend_income_mm": 91.0,
        "other_income_mm": None,
        "interest_expense_mm": 125.0,
        "base_management_fee_mm": 53.0,
        "income_incentive_fee_mm": 36.0,
        "capital_gains_incentive_fee_mm": 0.0,
        "professional_fees_mm": None,
        "directors_or_board_fees_mm": None,
        "administrative_service_expense_mm": 2.0,
        "accounting_administrative_fees_mm": 1.0,
        "other_g_and_a_mm": 8.0,
        "total_g_and_a_mm": 11.0,
        "fee_waivers_mm": 0.0,
        "total_operating_expenses_mm": 225.0,
        "net_expenses_mm": 225.0,
        "tax_expense_mm": 11.0,
        "nii_mm": 173.0,
        "source_notes": [
            "Dollar amounts are stated in millions in the 10-Q statement of operations.",
            "Provision for taxes on investments is stored as tax expense; NII is taken directly from the filing's net investment income row.",
        ],
    },
    {
        "fund": "FSK",
        "period_end": "2025-09-30",
        "source_title": "FSK Q3 2025 Form 10-Q",
        "source_file": "source-docs/0001628280-25-049617.pdf",
        "source_pages": [4],
        "total_investment_income_mm": 373.0,
        "interest_income_mm": 231.0,
        "pik_interest_income_mm": 54.0,
        "fee_income_mm": 4.0,
        "dividend_income_mm": 84.0,
        "other_income_mm": None,
        "interest_expense_mm": 116.0,
        "base_management_fee_mm": 51.0,
        "income_incentive_fee_mm": 33.0,
        "capital_gains_incentive_fee_mm": 0.0,
        "professional_fees_mm": None,
        "directors_or_board_fees_mm": None,
        "administrative_service_expense_mm": 3.0,
        "accounting_administrative_fees_mm": 1.0,
        "other_g_and_a_mm": 6.0,
        "total_g_and_a_mm": 10.0,
        "fee_waivers_mm": 0.0,
        "total_operating_expenses_mm": 210.0,
        "net_expenses_mm": 210.0,
        "tax_expense_mm": 4.0,
        "nii_mm": 159.0,
        "source_notes": [
            "Dollar amounts are stated in millions in the 10-Q statement of operations.",
            "Excise taxes are stored as tax expense; NII is taken directly from the filing's net investment income row.",
        ],
    },
    {
        "fund": "FSK",
        "period_end": "2025-12-31",
        "source_title": "FSK 2025 Form 10-K annual-derived Q4 2025",
        "source_file": "source-docs/0001628280-26-011734.pdf",
        "source_pages": [193, 196],
        "total_investment_income_mm": 348.0,
        "interest_income_mm": 201.0,
        "pik_interest_income_mm": 55.0,
        "fee_income_mm": 6.0,
        "dividend_income_mm": 86.0,
        "other_income_mm": None,
        "interest_expense_mm": 110.0,
        "base_management_fee_mm": 50.0,
        "income_incentive_fee_mm": 28.0,
        "capital_gains_incentive_fee_mm": 0.0,
        "professional_fees_mm": None,
        "directors_or_board_fees_mm": None,
        "administrative_service_expense_mm": 2.0,
        "accounting_administrative_fees_mm": 1.0,
        "other_g_and_a_mm": 4.0,
        "total_g_and_a_mm": 7.0,
        "fee_waivers_mm": 0.0,
        "total_operating_expenses_mm": 195.0,
        "net_expenses_mm": 195.0,
        "tax_expense_mm": 18.0,
        "nii_mm": 135.0,
        "source_notes": [
            "Q4 2025 is derived as full-year 2025 Form 10-K amounts less the Q3 2025 year-to-date 10-Q amounts.",
            "Dollar amounts are stated in millions; rounding follows the filing table precision.",
        ],
    },
    {
        "fund": "TSLX",
        "period_end": "2025-03-31",
        "source_title": "TSLX Q1 2025 Form 10-Q",
        "source_file": "source-docs/0000950170-25-061008.pdf",
        "source_pages": [5, 32, 57, 59],
        "total_investment_income_mm": 116.349,
        "interest_income_mm": 106.621,
        "pik_interest_income_mm": 5.360,
        "fee_income_mm": None,
        "dividend_income_mm": 0.908,
        "other_income_mm": 3.460,
        "interest_expense_mm": 32.971,
        "base_management_fee_mm": 13.083,
        "income_incentive_fee_mm": 11.516,
        "capital_gains_incentive_fee_mm": -3.686,
        "professional_fees_mm": 1.961,
        "directors_or_board_fees_mm": 0.248,
        "administrative_service_expense_mm": 1.000,
        "accounting_administrative_fees_mm": None,
        "other_g_and_a_mm": 1.337,
        "total_g_and_a_mm": 3.546,
        "fee_waivers_mm": 0.409,
        "total_operating_expenses_mm": 57.430,
        "net_expenses_mm": 57.021,
        "tax_expense_mm": 1.350,
        "nii_mm": 57.978,
        "source_notes": [
            "Dollar amounts are converted from the 10-Q statement of operations shown in thousands.",
            "Interest income and other income each aggregate non-controlled/non-affiliated and controlled/affiliated investment categories.",
            "Administrative service expense is disclosed in Note 3 and is included in other general and administrative expense, not added again to total G&A.",
        ],
    },
    {
        "fund": "TSLX",
        "period_end": "2025-06-30",
        "source_title": "TSLX Q2 2025 Form 10-Q",
        "source_file": "source-docs/0000950170-25-100204.pdf",
        "source_pages": [5, 33, 59, 61],
        "total_investment_income_mm": 115.015,
        "interest_income_mm": 101.233,
        "pik_interest_income_mm": 5.783,
        "fee_income_mm": None,
        "dividend_income_mm": 0.387,
        "other_income_mm": 7.612,
        "interest_expense_mm": 33.647,
        "base_management_fee_mm": 12.918,
        "income_incentive_fee_mm": 11.089,
        "capital_gains_incentive_fee_mm": 1.438,
        "professional_fees_mm": 2.561,
        "directors_or_board_fees_mm": 0.248,
        "administrative_service_expense_mm": 0.800,
        "accounting_administrative_fees_mm": None,
        "other_g_and_a_mm": 1.280,
        "total_g_and_a_mm": 4.089,
        "fee_waivers_mm": 0.297,
        "total_operating_expenses_mm": 63.181,
        "net_expenses_mm": 62.884,
        "tax_expense_mm": 1.291,
        "nii_mm": 50.840,
        "source_notes": [
            "Dollar amounts are converted from the 10-Q statement of operations shown in thousands.",
            "Interest income and other income each aggregate non-controlled/non-affiliated and controlled/affiliated investment categories.",
            "Administrative service expense is disclosed in Note 3 and is included in other general and administrative expense, not added again to total G&A.",
        ],
    },
    {
        "fund": "TSLX",
        "period_end": "2025-09-30",
        "source_title": "TSLX Q3 2025 Form 10-Q",
        "source_file": "source-docs/0001193125-25-264618.pdf",
        "source_pages": [5, 34, 60, 62, 63],
        "total_investment_income_mm": 109.444,
        "interest_income_mm": 94.893,
        "pik_interest_income_mm": 6.883,
        "fee_income_mm": None,
        "dividend_income_mm": 0.268,
        "other_income_mm": 7.400,
        "interest_expense_mm": 31.385,
        "base_management_fee_mm": 13.081,
        "income_incentive_fee_mm": 10.527,
        "capital_gains_incentive_fee_mm": -1.054,
        "professional_fees_mm": 2.022,
        "directors_or_board_fees_mm": 0.206,
        "administrative_service_expense_mm": 1.000,
        "accounting_administrative_fees_mm": None,
        "other_g_and_a_mm": 1.507,
        "total_g_and_a_mm": 3.735,
        "fee_waivers_mm": 0.284,
        "total_operating_expenses_mm": 57.674,
        "net_expenses_mm": 57.390,
        "tax_expense_mm": 1.374,
        "nii_mm": 50.680,
        "source_notes": [
            "Dollar amounts are converted from the 10-Q statement of operations shown in thousands.",
            "Interest income and other income each aggregate non-controlled/non-affiliated and controlled/affiliated investment categories.",
            "Administrative service expense is disclosed in Note 3 and is included in other general and administrative expense, not added again to total G&A.",
        ],
    },
    {
        "fund": "TSLX",
        "period_end": "2025-12-31",
        "source_title": "TSLX 2025 Form 10-K annual-derived Q4 2025",
        "source_file": "source-docs/TSLX10K25.pdf",
        "source_pages": [94, 122, 143],
        "total_investment_income_mm": 108.247,
        "interest_income_mm": 98.028,
        "pik_interest_income_mm": 7.560,
        "fee_income_mm": None,
        "dividend_income_mm": 0.782,
        "other_income_mm": 1.877,
        "interest_expense_mm": 31.554,
        "base_management_fee_mm": 13.094,
        "income_incentive_fee_mm": 10.337,
        "capital_gains_incentive_fee_mm": -1.768,
        "professional_fees_mm": 1.764,
        "directors_or_board_fees_mm": 0.260,
        "administrative_service_expense_mm": 1.100,
        "accounting_administrative_fees_mm": None,
        "other_g_and_a_mm": 1.507,
        "total_g_and_a_mm": 3.531,
        "fee_waivers_mm": 0.301,
        "total_operating_expenses_mm": 56.748,
        "net_expenses_mm": 56.447,
        "tax_expense_mm": 1.303,
        "nii_mm": 50.497,
        "source_notes": [
            "Q4 2025 is derived as full-year 2025 Form 10-K amounts less the Q3 2025 year-to-date 10-Q amounts.",
            "Dollar amounts are converted from filing statement amounts shown in thousands.",
            "Administrative service expense is disclosed annually in Note 3; Q4 is derived as full-year 2025 less Q3 2025 year-to-date disclosure.",
        ],
    },
    {
        "fund": "TSLX",
        "period_end": "2026-03-31",
        "source_title": "TSLX Q1 2026 Form 10-Q",
        "source_file": "source-docs/0001193125-26-206313.pdf",
        "source_pages": [5, 34, 35, 52, 62, 63],
        "total_investment_income_mm": 93.397,
        "interest_income_mm": 83.778,
        "pik_interest_income_mm": 6.969,
        "fee_income_mm": None,
        "dividend_income_mm": 0.460,
        "other_income_mm": 2.190,
        "interest_expense_mm": 28.258,
        "base_management_fee_mm": 12.593,
        "income_incentive_fee_mm": 8.451,
        "capital_gains_incentive_fee_mm": 0.0,
        "professional_fees_mm": 1.743,
        "directors_or_board_fees_mm": 0.254,
        "administrative_service_expense_mm": 0.900,
        "accounting_administrative_fees_mm": None,
        "other_g_and_a_mm": 1.369,
        "total_g_and_a_mm": 3.366,
        "fee_waivers_mm": 0.317,
        "total_operating_expenses_mm": 52.668,
        "net_expenses_mm": 52.351,
        "tax_expense_mm": 1.204,
        "nii_mm": 39.842,
        "source_notes": [
            "Dollar amounts are converted from the 10-Q statement of operations shown in thousands.",
            "The statement labels the residual non-interest and non-dividend line as other income; it is not forced into fee income.",
            "Administrative service expense is disclosed in Note 3 and is included in other general and administrative expense, not added again to total G&A.",
        ],
    },
]

BXSL_NON_ACCRUAL_PERIOD_SOURCES: list[dict[str, Any]] = [
    {
        "period_end": "2025-03-31",
        "source_title": "BXSL Q1 2025 Form 10-Q schedule footnote (17)",
        "source_file": "source-docs/c136ea54-8c10-4475-8cc8-978e61d94be0 (1).pdf",
        "metric_pages": [124, 125],
        "reported_non_accrual_cost_pct": 0.3,
        "reported_non_accrual_fv_pct": 0.1,
    },
    {
        "period_end": "2025-06-30",
        "source_title": "BXSL Q2 2025 Form 10-Q schedule footnote (17)",
        "source_file": "source-docs/6eef3db0-e474-4c9e-bc7a-d720f6bca8ad (1).pdf",
        "metric_pages": [130, 131],
        "reported_non_accrual_cost_pct": 0.3,
        "reported_non_accrual_fv_pct": 0.1,
    },
    {
        "period_end": "2025-09-30",
        "source_title": "BXSL Q3 2025 Form 10-Q schedule footnote (17)",
        "source_file": "source-docs/3a21d3e0-48cb-40e5-b3b4-9854c5bb2937 (2).pdf",
        "metric_pages": [135, 136],
        "reported_non_accrual_cost_pct": 0.1,
        "reported_non_accrual_fv_pct": 0.1,
    },
    {
        "period_end": "2025-12-31",
        "source_title": "BXSL 2025 Form 10-K schedule footnote (17)",
        "source_file": "source-docs/bxsl10k25.pdf",
        "metric_pages": [134, 135],
        "reported_non_accrual_cost_pct": 0.6,
        "reported_non_accrual_fv_pct": 0.5,
    },
    {
        "period_end": "2026-03-31",
        "source_title": "BXSL Q1 2026 Form 10-Q schedule footnote (17)",
        "source_file": "source-docs/f0cb87a2-e0bd-4243-85e1-5816094738a1 (2).pdf",
        "metric_pages": [138],
        "reported_non_accrual_cost_pct": 4.7,
        "reported_non_accrual_fv_pct": 3.1,
    },
]

BXSL_NON_ACCRUAL_ISSUER_FACTS: list[dict[str, Any]] = [
    {"period_end": "2025-03-31", "issuer_name": "Maverick Acquisition, Inc.", "security_count": 1, "amortized_cost_mm": 18.305, "fair_value_mm": 10.151, "source_pages": [10]},
    {"period_end": "2025-03-31", "issuer_name": "WHCG Purchaser III, Inc.", "security_count": 1, "amortized_cost_mm": 6.354, "fair_value_mm": 6.458, "source_pages": [17]},
    {"period_end": "2025-03-31", "issuer_name": "Benefytt Technologies, Inc.", "security_count": 2, "amortized_cost_mm": 6.956, "fair_value_mm": 1.453, "source_pages": [19]},
    {"period_end": "2025-03-31", "issuer_name": "Material Holdings, LLC", "security_count": 1, "amortized_cost_mm": 5.291, "fair_value_mm": 0.943, "source_pages": [32]},
    {"period_end": "2025-06-30", "issuer_name": "Maverick Acquisition, Inc.", "security_count": 1, "amortized_cost_mm": 18.305, "fair_value_mm": 10.151, "source_pages": [11]},
    {"period_end": "2025-06-30", "issuer_name": "WHCG Purchaser III, Inc.", "security_count": 1, "amortized_cost_mm": 6.354, "fair_value_mm": 7.121, "source_pages": [19]},
    {"period_end": "2025-06-30", "issuer_name": "Benefytt Technologies, Inc.", "security_count": 2, "amortized_cost_mm": 6.956, "fair_value_mm": 0.854, "source_pages": [20]},
    {"period_end": "2025-06-30", "issuer_name": "Material Holdings, LLC", "security_count": 1, "amortized_cost_mm": 5.270, "fair_value_mm": 0.393, "source_pages": [34]},
    {"period_end": "2025-09-30", "issuer_name": "WHCG Purchaser III, Inc.", "security_count": 1, "amortized_cost_mm": 6.354, "fair_value_mm": 6.605, "source_pages": [20]},
    {"period_end": "2025-09-30", "issuer_name": "Benefytt Technologies, Inc.", "security_count": 2, "amortized_cost_mm": 6.956, "fair_value_mm": 0.898, "source_pages": [22]},
    {"period_end": "2025-09-30", "issuer_name": "Material Holdings, LLC", "security_count": 1, "amortized_cost_mm": 5.263, "fair_value_mm": 0.102, "source_pages": [38]},
    {"period_end": "2025-12-31", "issuer_name": "DCA Investment Holdings, LLC", "security_count": 3, "amortized_cost_mm": 32.945, "fair_value_mm": 27.954, "source_pages": [163]},
    {"period_end": "2025-12-31", "issuer_name": "WHCG Purchaser III, Inc.", "security_count": 1, "amortized_cost_mm": 6.354, "fair_value_mm": 7.484, "source_pages": [164]},
    {"period_end": "2025-12-31", "issuer_name": "Benefytt Technologies, Inc.", "security_count": 2, "amortized_cost_mm": 6.956, "fair_value_mm": 0.921, "source_pages": [166]},
    {"period_end": "2025-12-31", "issuer_name": "Titan Investment Company, Inc.", "security_count": 1, "amortized_cost_mm": 40.453, "fair_value_mm": 31.242, "source_pages": [173]},
    {"period_end": "2025-12-31", "issuer_name": "Material Holdings, LLC", "security_count": 1, "amortized_cost_mm": 5.263, "fair_value_mm": 0.0, "source_pages": [180]},
    {"period_end": "2026-03-31", "issuer_name": "ACI Group Holdings, Inc.", "security_count": 2, "amortized_cost_mm": 143.533, "fair_value_mm": 101.546, "source_pages": [18]},
    {"period_end": "2026-03-31", "issuer_name": "DCA Investment Holdings, LLC", "security_count": 3, "amortized_cost_mm": 32.992, "fair_value_mm": 27.330, "source_pages": [18]},
    {"period_end": "2026-03-31", "issuer_name": "WHCG Purchaser III, Inc.", "security_count": 1, "amortized_cost_mm": 6.354, "fair_value_mm": 8.399, "source_pages": [20]},
    {"period_end": "2026-03-31", "issuer_name": "Benefytt Technologies, Inc.", "security_count": 2, "amortized_cost_mm": 6.956, "fair_value_mm": 0.921, "source_pages": [22]},
    {"period_end": "2026-03-31", "issuer_name": "Titan Investment Company, Inc.", "security_count": 1, "amortized_cost_mm": 40.345, "fair_value_mm": 14.052, "source_pages": [29]},
    {"period_end": "2026-03-31", "issuer_name": "Medallia, Inc.", "security_count": 2, "amortized_cost_mm": 383.239, "fair_value_mm": 238.110, "source_pages": [33]},
    {"period_end": "2026-03-31", "issuer_name": "Paramount Global Surfaces, Inc.", "security_count": 1, "amortized_cost_mm": 55.101, "fair_value_mm": 36.174, "source_pages": [35]},
    {"period_end": "2026-03-31", "issuer_name": "Material Holdings, LLC", "security_count": 1, "amortized_cost_mm": 5.263, "fair_value_mm": 0.0, "source_pages": [37]},
]

FSK_NON_ACCRUAL_PERIOD_SOURCES: list[dict[str, Any]] = [
    {
        "period_end": "2025-03-31",
        "source_title": "FSK Q1 2025 Form 10-Q schedule footnote (z)",
        "source_file": "source-docs/0001628280-25-023202.pdf",
        "source_pages": [25],
        "metric_pages": [82],
        "reported_non_accrual_fv_pct": 2.1,
    },
    {
        "period_end": "2025-06-30",
        "source_title": "FSK Q2 2025 Form 10-Q schedule footnote (z)",
        "source_file": "source-docs/0001628280-25-038368.pdf",
        "source_pages": [26],
        "metric_pages": [86],
        "reported_non_accrual_fv_pct": 3.0,
    },
    {
        "period_end": "2025-09-30",
        "source_title": "FSK Q3 2025 Form 10-Q schedule footnote (z)",
        "source_file": "source-docs/0001628280-25-049617.pdf",
        "source_pages": [26],
        "metric_pages": [86],
        "reported_non_accrual_fv_pct": 2.9,
    },
    {
        "period_end": "2025-12-31",
        "source_title": "FSK 2025 Form 10-K schedule footnote (z)",
        "source_file": "source-docs/0001628280-26-011734.pdf",
        "source_pages": [257],
        "metric_pages": [154, 177],
        "reported_non_accrual_fv_pct": 3.4,
    },
    {
        "period_end": "2026-03-31",
        "source_title": "FSK Q1 2026 Form 10-Q schedule footnote (z)",
        "source_file": "source-docs/0001628280-26-033118.pdf",
        "source_pages": [26],
        "metric_pages": [102],
        "reported_non_accrual_fv_pct": 4.2,
    },
]

TSLX_NON_ACCRUAL_PERIOD_SOURCES: list[dict[str, Any]] = [
    {
        "period_end": "2025-03-31",
        "footnote_token": "(14)",
        "source_title": "TSLX Q1 2025 Form 10-Q schedule footnote (14)",
        "source_file": "source-docs/0000950170-25-061008.pdf",
        "source_pages": [8, 9, 10, 14],
        "metric_pages": [57],
        "reported_non_accrual_cost_pct": 3.7,
        "reported_non_accrual_fv_pct": 1.2,
        "reported_non_accrual_cost_mm": 129.1,
        "reported_non_accrual_fv_mm": 42.0,
        "use_central_holdings": True,
    },
    {
        "period_end": "2025-06-30",
        "footnote_token": "(14)",
        "source_title": "TSLX Q2 2025 Form 10-Q schedule footnote (14)",
        "source_file": "source-docs/0000950170-25-100204.pdf",
        "source_pages": [7, 10, 14],
        "metric_pages": [59],
        "reported_non_accrual_cost_pct": 2.1,
        "reported_non_accrual_fv_pct": 0.6,
        "reported_non_accrual_cost_mm": 67.5,
        "reported_non_accrual_fv_mm": 21.4,
        "use_central_holdings": False,
        "source_notes": [
            "The filing discloses non-accrual cost/fair-value dollars and percentages.",
            "Issuer rows are manually extracted from Q2 2025 schedule rows tagged with footnote (14) because the centralized holdings database does not yet include TSLX 2025-06-30 holdings.",
        ],
    },
    {
        "period_end": "2025-09-30",
        "footnote_token": "(14)",
        "source_title": "TSLX Q3 2025 Form 10-Q schedule footnote (14)",
        "source_file": "source-docs/0001193125-25-264618.pdf",
        "source_pages": [7, 10, 15],
        "metric_pages": [60],
        "reported_non_accrual_cost_pct": 2.0,
        "reported_non_accrual_fv_pct": 0.6,
        "reported_non_accrual_cost_mm": 67.3,
        "reported_non_accrual_fv_mm": 20.3,
        "use_central_holdings": True,
    },
    {
        "period_end": "2025-12-31",
        "footnote_token": "(14)",
        "source_title": "TSLX 2025 Form 10-K schedule footnote (14)",
        "source_file": "source-docs/TSLX10K25.pdf",
        "source_pages": [97, 99, 104],
        "metric_pages": [70],
        "reported_non_accrual_cost_pct": 2.1,
        "reported_non_accrual_fv_pct": 0.6,
        "reported_non_accrual_cost_mm": 68.8,
        "reported_non_accrual_fv_mm": 20.0,
        "use_central_holdings": True,
    },
    {
        "period_end": "2026-03-31",
        "footnote_token": "(12)",
        "source_title": "TSLX Q1 2026 Form 10-Q schedule footnote (12)",
        "source_file": "source-docs/0001193125-26-206313.pdf",
        "source_pages": [15],
        "metric_pages": [60],
        "reported_non_accrual_cost_pct": 1.9,
        "reported_non_accrual_fv_pct": 1.4,
        "reported_non_accrual_cost_mm": 63.9,
        "reported_non_accrual_fv_mm": 47.4,
        "use_central_holdings": True,
    },
]

TSLX_NON_ACCRUAL_ISSUER_FACTS: list[dict[str, Any]] = [
    {"period_end": "2025-06-30", "issuer_name": "Astra Acquisition Corp.", "security_count": 1, "amortized_cost_mm": 39.703, "fair_value_mm": 1.511, "source_pages": [7]},
    {"period_end": "2025-06-30", "issuer_name": "American Achievement, Corp.", "security_count": 3, "amortized_cost_mm": 27.827, "fair_value_mm": 19.900, "source_pages": [10]},
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def pct(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round((numerator / denominator) * 100, 4)


def parse_close_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%m/%d/%Y").date()


def quarter_start_for(period_end: date) -> date:
    month = ((period_end.month - 1) // 3) * 3 + 1
    return date(period_end.year, month, 1)


def copy2_with_retries(source: Path, destination: Path, attempts: int = 8) -> None:
    last_error: PermissionError | None = None
    for attempt in range(attempts):
        try:
            shutil.copy2(source, destination)
            return
        except PermissionError as exc:
            last_error = exc
            try:
                destination.write_bytes(source.read_bytes())
                return
            except PermissionError:
                pass
            time.sleep(0.5 * (attempt + 1))
    if last_error is not None:
        raise last_error


def connect_central() -> sqlite3.Connection:
    con = sqlite3.connect(CENTRAL_DB_PATH.resolve().as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def build_holdings_rows(con: sqlite3.Connection, created_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in con.execute(
        """
        select
            fund,
            filing_period_end as period_end,
            max(report_type) as report_type,
            count(*) as holding_rows,
            sum(amortized_cost_mm) as holdings_amortized_cost_mm,
            sum(fair_value_mm) as holdings_fair_value_mm,
            sum(fair_value_mm) - sum(amortized_cost_mm) as holdings_mark_vs_cost_mm,
            sum(
                case
                    when lower(coalesce(investment_category, '') || ' ' || coalesce(instrument_type, '')) like '%first%lien%'
                    then fair_value_mm
                    else 0
                end
            ) as first_lien_fv_mm,
            sum(
                case
                    when reference_base_rate is not null and coalesce(is_fixed, 0) = 0
                    then fair_value_mm
                    else 0
                end
            ) as floating_fv_mm,
            sum(case when coalesce(pik_rate_pct, 0) > 0 then fair_value_mm else 0 end) as pik_fv_mm,
            sum(
                case
                    when amortized_cost_mm > 0 and fair_value_mm / amortized_cost_mm < 0.90
                    then fair_value_mm
                    else 0
                end
            ) as below_90_fv_mm,
            sum(
                case
                    when amortized_cost_mm > 0 and fair_value_mm / amortized_cost_mm < 0.80
                    then fair_value_mm
                    else 0
                end
            ) as below_80_fv_mm,
            sum(case when spread_pct is not null then fair_value_mm * spread_pct else 0 end) as spread_weighted_sum,
            sum(case when spread_pct is not null then fair_value_mm else 0 end) as spread_fv_mm
        from funded_security_level_holdings
        where fund in ('BXSL', 'FSK', 'TSLX')
        group by fund, filing_period_end
        order by fund, filing_period_end
        """
    ):
        item = {column: None for column in FACT_COLUMNS}
        item.update(
            {
                "fund": row["fund"],
                "period_end": row["period_end"],
                "company_name": FUND_NAMES[row["fund"]],
                "report_type": row["report_type"],
                "source_status": "holdings-derived",
                "source_title": "Centralized holdings database",
                "source_file": str(CENTRAL_DB_PATH.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
                "holding_rows": int(row["holding_rows"]),
                "holdings_amortized_cost_mm": as_float(row["holdings_amortized_cost_mm"]),
                "holdings_fair_value_mm": as_float(row["holdings_fair_value_mm"]),
                "holdings_mark_vs_cost_mm": as_float(row["holdings_mark_vs_cost_mm"]),
                "holdings_pik_fair_value_mm": as_float(row["pik_fv_mm"]),
                "holdings_below_90_fair_value_mm": as_float(row["below_90_fv_mm"]),
                "holdings_below_80_fair_value_mm": as_float(row["below_80_fv_mm"]),
                "created_at_utc": created_at,
            }
        )
        item["holdings_mark_to_cost_pct"] = pct(item["holdings_fair_value_mm"], item["holdings_amortized_cost_mm"])
        item["holdings_first_lien_pct"] = pct(as_float(row["first_lien_fv_mm"]), item["holdings_fair_value_mm"])
        item["holdings_floating_rate_pct"] = pct(as_float(row["floating_fv_mm"]), item["holdings_fair_value_mm"])
        item["holdings_pik_fair_value_pct"] = pct(item["holdings_pik_fair_value_mm"], item["holdings_fair_value_mm"])
        if row["spread_fv_mm"]:
            item["holdings_weighted_avg_spread_bps"] = round(float(row["spread_weighted_sum"]) / float(row["spread_fv_mm"]) * 100, 2)
        item["source_notes_json"] = json.dumps(
            [
                "Holdings-derived fields come from the centralized funded security-level database.",
                "FSK footnote (x) unfunded-commitment rows are excluded from funded holdings screeners and retained separately in the central database.",
                "First-lien, floating-rate, PIK, below-90, and below-80 metrics are first-pass screeners from normalized schedule fields.",
            ],
            ensure_ascii=False,
        )
        rows.append(item)
    return rows


def overlay_q1_presentation_seed(rows: list[dict[str, Any]], created_at: str) -> None:
    row_map = {(row["fund"], row["period_end"]): row for row in rows}
    for fund, seed in Q1_2026_PRESENTATION_SEED.items():
        row = row_map.get((fund, "2026-03-31"))
        if row is None:
            row = {column: None for column in FACT_COLUMNS}
            row.update(
                {
                    "fund": fund,
                    "period_end": "2026-03-31",
                    "company_name": FUND_NAMES[fund],
                    "report_type": "10-Q",
                    "created_at_utc": created_at,
                }
            )
            rows.append(row)

        row["source_status"] = "presentation seed + holdings-derived"
        row["source_title"] = seed["source_title"]
        row["source_file"] = seed["source_file"]
        for key, value in seed.items():
            if key in {"source_title", "source_file", "source_notes"}:
                continue
            row[key] = value

        if row.get("base_dividend_coverage_pct") is None and row.get("base_dividend_per_share") not in (None, 0):
            row["base_dividend_coverage_pct"] = round(row["nii_per_share"] / row["base_dividend_per_share"] * 100, 4)
        if row.get("total_dividend_coverage_pct") is None and row.get("total_dividend_per_share") not in (None, 0):
            row["total_dividend_coverage_pct"] = round(row["nii_per_share"] / row["total_dividend_per_share"] * 100, 4)

        existing_notes = json.loads(row["source_notes_json"] or "[]") if row.get("source_notes_json") else []
        row["source_notes_json"] = json.dumps(existing_notes + seed["source_notes"], ensure_ascii=False)


def overlay_investment_activity_facts(rows: list[dict[str, Any]], created_at: str) -> None:
    row_map = {(row["fund"], row["period_end"]): row for row in rows}
    for fact in INVESTMENT_ACTIVITY_FACTS:
        fund = fact["fund"]
        period_end = fact["period_end"]
        row = row_map.get((fund, period_end))
        if row is None:
            row = {column: None for column in FACT_COLUMNS}
            row.update(
                {
                    "fund": fund,
                    "period_end": period_end,
                    "company_name": FUND_NAMES[fund],
                    "report_type": "presentation",
                    "source_status": "presentation investment activity",
                    "source_title": fact["source_title"],
                    "source_file": fact["source_file"],
                    "source_notes_json": "[]",
                    "created_at_utc": created_at,
                }
            )
            rows.append(row)
            row_map[(fund, period_end)] = row

        for key in [
            "new_commitments_mm",
            "fundings_mm",
            "repayments_sales_mm",
            "net_investment_activity_mm",
            "new_investment_yield_pct",
            "repayment_yield_pct",
        ]:
            row[key] = fact[key]

        if row.get("source_status"):
            if "investment activity" not in row["source_status"]:
                row["source_status"] = f"{row['source_status']} + investment activity"
        else:
            row["source_status"] = "presentation investment activity"

        existing_notes = json.loads(row["source_notes_json"] or "[]") if row.get("source_notes_json") else []
        activity_note = (
            f"Investment activity fields for {period_end} are sourced from "
            f"{fact['source_title']}, page {fact['source_page']}."
        )
        if activity_note not in existing_notes:
            existing_notes.append(activity_note)
        for source_note in fact.get("source_notes", []):
            if source_note not in existing_notes:
                existing_notes.append(source_note)
        row["source_notes_json"] = json.dumps(existing_notes, ensure_ascii=False)


def overlay_presentation_nav_marks(rows: list[dict[str, Any]], created_at: str) -> None:
    row_map = {(row["fund"], row["period_end"]): row for row in rows}
    for mark in PRESENTATION_NAV_MARKS:
        fund = mark["fund"]
        period_end = mark["period_end"]
        row = row_map.get((fund, period_end))
        if row is None:
            row = {column: None for column in FACT_COLUMNS}
            row.update(
                {
                    "fund": fund,
                    "period_end": period_end,
                    "company_name": FUND_NAMES[fund],
                    "report_type": "presentation",
                    "source_status": "presentation NAV",
                    "source_title": mark["source_title"],
                    "source_file": mark["source_file"],
                    "source_notes_json": "[]",
                    "created_at_utc": created_at,
                }
            )
            rows.append(row)
            row_map[(fund, period_end)] = row

        row["nav_per_share"] = mark["nav_per_share"]
        if row.get("source_status") == "holdings-derived":
            row["source_status"] = "presentation NAV + holdings-derived"

        existing_notes = json.loads(row["source_notes_json"] or "[]") if row.get("source_notes_json") else []
        nav_note = (
            f"NAV/share for {period_end} is sourced from {mark['source_title']}, "
            f"page {mark['source_page']}."
        )
        if nav_note not in existing_notes:
            existing_notes.append(nav_note)
        row["source_notes_json"] = json.dumps(existing_notes, ensure_ascii=False)


def build_filing_income_expense_rows(created_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fact in FILING_INCOME_EXPENSE_FACTS:
        row = {column: fact.get(column) for column in EXPENSE_FACT_COLUMNS}
        row["source_pages_json"] = json.dumps(fact["source_pages"])
        row["total_incentive_fee_mm"] = round(
            float(fact.get("income_incentive_fee_mm") or 0) + float(fact.get("capital_gains_incentive_fee_mm") or 0),
            6,
        )
        row["source_notes_json"] = json.dumps(fact.get("source_notes", []), ensure_ascii=False)
        row["created_at_utc"] = created_at
        rows.append(row)
    return rows


def build_income_quality_rows(expense_rows: list[dict[str, Any]], created_at: str) -> list[dict[str, Any]]:
    expense_map = {(row["fund"], row["period_end"]): row for row in expense_rows}
    rows: list[dict[str, Any]] = []
    default_source_notes = [
        "Presentation operating-results detail supplies NII/share, adjusted NII/share, other-fee income, other income, distributions, and weighted average shares.",
        "PIK interest income and management fee waivers are carried from the filing-sourced income/expense layer.",
        "Cash-like recurring NII is a conservative derived estimate: reported NII less PIK interest, investment other fees, other income, and the management fee waiver benefit.",
        "TSLX presentation footnotes describe other fees as prepayment fees and accelerated amortization from unscheduled paydowns; other income includes amendment, syndication, cash, and miscellaneous fees.",
        "No TSLX taxable-income table was found in the supplied Q1 2025 through Q1 2026 earnings presentations.",
    ]
    for fact in INCOME_QUALITY_FACTS:
        expense = expense_map.get((fact["fund"], fact["period_end"]), {})
        total_investment_income_mm = fact.get("total_investment_income_mm", expense.get("total_investment_income_mm"))
        pik_interest_income_mm = fact.get("pik_interest_income_mm", expense.get("pik_interest_income_mm"))
        fee_waivers_mm = fact.get("fee_waivers_mm", expense.get("fee_waivers_mm"))
        other_fees_mm = fact.get("interest_from_investments_other_fees_mm")
        other_income_mm = fact.get("other_income_mm")
        reported_nii_mm = fact["reported_nii_mm"]
        shares_m = float(fact["weighted_average_shares"]) / 1_000_000
        base_dividend = fact["base_dividend_per_share"]
        record_date_distributions = fact["record_date_distributions_per_share"]
        quarter_related_supplement = fact.get("quarter_related_supplemental_dividend_per_share")
        quarter_related_total = None
        if base_dividend is not None and quarter_related_supplement is not None:
            quarter_related_total = round(base_dividend + quarter_related_supplement, 6)

        cash_nii_ex_pik_mm = None
        cash_nii_ex_pik_per_share = None
        if pik_interest_income_mm is not None:
            cash_nii_ex_pik_mm = round(reported_nii_mm - pik_interest_income_mm, 6)
            cash_nii_ex_pik_per_share = round(cash_nii_ex_pik_mm / shares_m, 6)

        recurring_deductions = [
            pik_interest_income_mm,
            other_fees_mm,
            other_income_mm,
            fee_waivers_mm,
        ]
        cash_like_recurring_nii_mm = None
        cash_like_recurring_nii_per_share = None
        if all(value is not None for value in recurring_deductions):
            cash_like_recurring_nii_mm = round(reported_nii_mm - sum(float(value) for value in recurring_deductions), 6)
            cash_like_recurring_nii_per_share = round(cash_like_recurring_nii_mm / shares_m, 6)

        row = {column: fact.get(column) for column in INCOME_QUALITY_COLUMNS}
        row.update(
            {
                "total_investment_income_mm": total_investment_income_mm,
                "pik_interest_income_mm": pik_interest_income_mm,
                "pik_income_tii_pct": pct(pik_interest_income_mm, total_investment_income_mm),
                "pik_income_nii_pct": pct(pik_interest_income_mm, reported_nii_mm),
                "other_fees_tii_pct": pct(other_fees_mm, total_investment_income_mm),
                "other_income_tii_pct": pct(other_income_mm, total_investment_income_mm),
                "fee_waivers_mm": fee_waivers_mm,
                "cash_nii_ex_pik_mm": cash_nii_ex_pik_mm,
                "cash_nii_ex_pik_per_share": cash_nii_ex_pik_per_share,
                "cash_like_recurring_nii_mm": cash_like_recurring_nii_mm,
                "cash_like_recurring_nii_per_share": cash_like_recurring_nii_per_share,
                "quarter_related_total_dividend_per_share": quarter_related_total,
                "reported_base_dividend_coverage_pct": pct(fact.get("reported_nii_per_share"), base_dividend),
                "reported_record_date_distribution_coverage_pct": pct(
                    fact.get("reported_nii_per_share"), record_date_distributions
                ),
                "reported_quarter_related_distribution_coverage_pct": pct(
                    fact.get("reported_nii_per_share"), quarter_related_total
                ),
                "adjusted_base_dividend_coverage_pct": pct(fact.get("adjusted_nii_per_share"), base_dividend),
                "adjusted_record_date_distribution_coverage_pct": pct(
                    fact.get("adjusted_nii_per_share"), record_date_distributions
                ),
                "cash_like_base_dividend_coverage_pct": pct(cash_like_recurring_nii_per_share, base_dividend),
                "cash_like_record_date_distribution_coverage_pct": pct(
                    cash_like_recurring_nii_per_share, record_date_distributions
                ),
                "source_pages_json": json.dumps(fact["source_pages"]),
                "one_time_items_json": json.dumps(fact.get("one_time_items", []), ensure_ascii=False),
                "source_notes_json": json.dumps(fact.get("source_notes", default_source_notes), ensure_ascii=False),
                "created_at_utc": created_at,
            }
        )
        rows.append(row)
    return rows


def build_dividend_declaration_rows(created_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    default_source_notes = [
        "Extracted from the TSLX earnings-presentation distribution information table.",
        "Supplemental rows are mapped to the earnings period named in the table when available; base rows are mapped to the quarter containing the record date.",
    ]
    for fact in DIVIDEND_DECLARATION_FACTS:
        row = {column: fact.get(column) for column in DIVIDEND_DECLARATION_COLUMNS}
        row["source_notes_json"] = json.dumps(fact.get("source_notes", default_source_notes), ensure_ascii=False)
        row["created_at_utc"] = created_at
        rows.append(row)
    return rows


def overlay_income_quality_facts(rows: list[dict[str, Any]], income_quality_rows: list[dict[str, Any]]) -> None:
    row_map = {(row["fund"], row["period_end"]): row for row in rows}
    for quality in income_quality_rows:
        row = row_map.get((quality["fund"], quality["period_end"]))
        if row is None:
            row = {column: None for column in FACT_COLUMNS}
            row.update(
                {
                    "fund": quality["fund"],
                    "period_end": quality["period_end"],
                    "company_name": FUND_NAMES[quality["fund"]],
                    "report_type": "presentation",
                    "source_status": "presentation income quality",
                    "source_title": quality["source_title"],
                    "source_file": quality["source_file"],
                    "source_notes_json": "[]",
                    "created_at_utc": quality["created_at_utc"],
                }
            )
            rows.append(row)
            row_map[(quality["fund"], quality["period_end"])] = row

        for source_key, target_key in [
            ("reported_nii_mm", "nii_mm"),
            ("reported_nii_per_share", "nii_per_share"),
            ("adjusted_nii_mm", "adjusted_nii_mm"),
            ("adjusted_nii_per_share", "adjusted_nii_per_share"),
            ("base_dividend_per_share", "base_dividend_per_share"),
            ("record_date_distributions_per_share", "total_dividend_per_share"),
            ("reported_base_dividend_coverage_pct", "base_dividend_coverage_pct"),
            ("reported_record_date_distribution_coverage_pct", "total_dividend_coverage_pct"),
            ("interest_from_investments_other_fees_mm", "fee_income_mm"),
        ]:
            row[target_key] = quality[source_key]

        if row.get("source_status"):
            if "income quality" not in row["source_status"]:
                row["source_status"] = f"{row['source_status']} + income quality"
        else:
            row["source_status"] = "presentation income quality"

        existing_notes = json.loads(row["source_notes_json"] or "[]") if row.get("source_notes_json") else []
        quality_note = (
            f"Income quality fields for {quality['period_end']} are sourced from "
            f"{quality['source_title']}, pages {', '.join(str(page) for page in json.loads(quality['source_pages_json']))}."
        )
        if quality_note not in existing_notes:
            existing_notes.append(quality_note)
        row["source_notes_json"] = json.dumps(existing_notes, ensure_ascii=False)


def overlay_10q_expense_facts(rows: list[dict[str, Any]], expense_rows: list[dict[str, Any]]) -> None:
    row_map = {(row["fund"], row["period_end"]): row for row in rows}
    for expense in expense_rows:
        row = row_map.get((expense["fund"], expense["period_end"]))
        if row is None:
            continue

        if expense.get("nii_mm") is not None:
            row["nii_mm"] = expense["nii_mm"]
        if expense.get("pik_interest_income_mm") is not None:
            row["pik_income_mm"] = expense["pik_interest_income_mm"]
        if expense.get("fee_income_mm") is not None:
            row["fee_income_mm"] = expense["fee_income_mm"]

        if "filing income/expense facts" not in row["source_status"]:
            row["source_status"] = f"{row['source_status']} + filing income/expense facts"
        existing_notes = json.loads(row["source_notes_json"] or "[]") if row.get("source_notes_json") else []
        note = (
            f"NII, PIK income, fee income where separately disclosed, and expense facts are sourced from "
            f"{expense['source_title']}."
        )
        if note not in existing_notes:
            existing_notes.append(note)
        row["source_notes_json"] = json.dumps(existing_notes, ensure_ascii=False)


def overlay_non_accrual_summary_facts(
    rows: list[dict[str, Any]],
    non_accrual_summary_rows: list[dict[str, Any]],
) -> None:
    row_map = {(row["fund"], row["period_end"]): row for row in rows}
    for summary in non_accrual_summary_rows:
        row = row_map.get((summary["fund"], summary["period_end"]))
        if row is None:
            continue

        if summary.get("reported_non_accrual_fv_pct") is not None:
            row["non_accrual_fv_pct"] = summary["reported_non_accrual_fv_pct"]
        if summary.get("reported_non_accrual_cost_pct") is not None:
            row["non_accrual_cost_pct"] = summary["reported_non_accrual_cost_pct"]

        if "non-accrual facts" not in row["source_status"]:
            row["source_status"] = f"{row['source_status']} + non-accrual facts"
        existing_notes = json.loads(row["source_notes_json"] or "[]") if row.get("source_notes_json") else []
        note = (
            f"Non-accrual fair-value percentage and issuer facts are sourced from "
            f"{summary['source_title']}."
        )
        if note not in existing_notes:
            existing_notes.append(note)
        row["source_notes_json"] = json.dumps(existing_notes, ensure_ascii=False)


def normalize_non_accrual_issuer(fund: str, issuer_name: str) -> str:
    if fund == "FSK":
        replacements = {
            "801 5th Ave, Seattle, Structured Mezzanine": "801 5th Ave, Seattle",
            "AVE Holdings I Corp (fka Amerivet Partners Management Inc), Preferred Stock": "AVE Holdings I Corp (fka Amerivet Partners Management Inc)",
            "Affordable Care Inc, Preferred Stock": "Affordable Care Inc",
            "Alacrity Solutions Group LLC, Preferred Equity": "Alacrity Solutions Group LLC",
            "Builders Capital Loan Acquisition Trust 2022-RTL1, Structured Mezzanine": "Builders Capital Loan Acquisition Trust 2022-RTL1",
            "Cubic Corp, Preferred Stock": "Cubic Corp",
            "Cubic Corp, Preferred Equity": "Cubic Corp",
            "Global Jet Capital LLC, Preferred Stock": "Global Jet Capital LLC",
            "JW Aluminum Co, Preferred Stock": "JW Aluminum Co",
            "KKR Central Park Leasing Aggregator L.P., Partnership Interest": "KKR Central Park Leasing Aggregator L.P.",
            "One Call Care Management Inc, Preferred Stock B": "One Call Care Management Inc",
            "Prime ST LLC, Structured Mezzanine": "Prime ST LLC",
        }
        return replacements.get(issuer_name, issuer_name)
    return issuer_name


def build_non_accrual_issuer_rows(con: sqlite3.Connection, created_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    bxsl_period_sources = {item["period_end"]: item for item in BXSL_NON_ACCRUAL_PERIOD_SOURCES}
    for item in BXSL_NON_ACCRUAL_ISSUER_FACTS:
        source = bxsl_period_sources[item["period_end"]]
        row = {column: None for column in NON_ACCRUAL_ISSUER_COLUMNS}
        row.update(
            {
                "fund": "BXSL",
                "period_end": item["period_end"],
                "issuer_name": item["issuer_name"],
                "security_count": item["security_count"],
                "amortized_cost_mm": item["amortized_cost_mm"],
                "fair_value_mm": item["fair_value_mm"],
                "source_title": source["source_title"],
                "source_file": source["source_file"],
                "source_pages_json": json.dumps(item["source_pages"]),
                "source_method": "Extracted from BXSL filing schedule rows tagged with footnote (17): loan was on non-accrual status as of the period end.",
                "source_notes_json": json.dumps(
                    [
                        "Amounts are converted from thousands in the filing schedule to millions.",
                        "BXSL footnote (17) rows are maintained manually because the centralized holdings database does not retain that footnote token.",
                    ],
                    ensure_ascii=False,
                ),
                "created_at_utc": created_at,
            }
        )
        rows.append(row)

    tslx_period_sources = {item["period_end"]: item for item in TSLX_NON_ACCRUAL_PERIOD_SOURCES}
    for item in TSLX_NON_ACCRUAL_ISSUER_FACTS:
        source = tslx_period_sources[item["period_end"]]
        row = {column: None for column in NON_ACCRUAL_ISSUER_COLUMNS}
        row.update(
            {
                "fund": "TSLX",
                "period_end": item["period_end"],
                "issuer_name": item["issuer_name"],
                "security_count": item["security_count"],
                "amortized_cost_mm": item["amortized_cost_mm"],
                "fair_value_mm": item["fair_value_mm"],
                "source_title": source["source_title"],
                "source_file": source["source_file"],
                "source_pages_json": json.dumps(item["source_pages"]),
                "source_method": "Manually extracted from TSLX Q2 2025 filing schedule rows tagged with footnote (14): investment is on non-accrual status.",
                "source_notes_json": json.dumps(
                    [
                        "Amounts are converted from thousands in the filing schedule to millions.",
                        "TSLX Q2 2025 issuer rows are manual because the centralized holdings database does not yet include TSLX 2025-06-30 holdings.",
                    ],
                    ensure_ascii=False,
                ),
                "created_at_utc": created_at,
            }
        )
        rows.append(row)

    source_specs = [
        *[
            {
                "fund": "FSK",
                "period_end": item["period_end"],
                "footnote_token": "(z)",
                "source_title": item["source_title"],
                "source_file": item["source_file"],
                "source_pages": item["source_pages"],
                "source_method": f"Grouped centralized holdings rows from the {item['period_end']} schedule tagged with footnote (z): asset is on non-accrual status.",
            }
            for item in FSK_NON_ACCRUAL_PERIOD_SOURCES
        ],
        *[
            {
                "fund": "TSLX",
                "period_end": item["period_end"],
                "footnote_token": item["footnote_token"],
                "source_title": item["source_title"],
                "source_file": item["source_file"],
                "source_pages": item["source_pages"],
                "source_method": f"Grouped centralized holdings rows from the {item['period_end']} schedule tagged with footnote {item['footnote_token']}: investment is on non-accrual status.",
            }
            for item in TSLX_NON_ACCRUAL_PERIOD_SOURCES
            if item.get("use_central_holdings", True)
        ],
    ]
    for spec in source_specs:
        grouped: dict[str, dict[str, Any]] = {}
        for holding in con.execute(
            """
            select
                issuer_name,
                amortized_cost_mm,
                fair_value_mm
            from holdings
            where fund = ?
              and filing_period_end = ?
              and (
                coalesce(issuer_name_raw, '') like ?
                or coalesce(investment_description, '') like ?
                or coalesce(raw_values_json, '') like ?
              )
            """,
            (
                spec["fund"],
                spec["period_end"],
                f"%{spec['footnote_token']}%",
                f"%{spec['footnote_token']}%",
                f"%{spec['footnote_token']}%",
            ),
        ):
            issuer_name = normalize_non_accrual_issuer(spec["fund"], holding["issuer_name"])
            item = grouped.setdefault(
                issuer_name,
                {"security_count": 0, "amortized_cost_mm": 0.0, "fair_value_mm": 0.0},
            )
            item["security_count"] += 1
            item["amortized_cost_mm"] += float(holding["amortized_cost_mm"] or 0)
            item["fair_value_mm"] += float(holding["fair_value_mm"] or 0)

        for issuer_name, item in sorted(grouped.items()):
            row = {column: None for column in NON_ACCRUAL_ISSUER_COLUMNS}
            row.update(
                {
                    "fund": spec["fund"],
                    "period_end": spec["period_end"],
                    "issuer_name": issuer_name,
                    "security_count": item["security_count"],
                    "amortized_cost_mm": round(item["amortized_cost_mm"], 6),
                    "fair_value_mm": round(item["fair_value_mm"], 6),
                    "source_title": spec["source_title"],
                    "source_file": spec["source_file"],
                    "source_pages_json": json.dumps(spec["source_pages"]),
                    "source_method": spec["source_method"],
                    "source_notes_json": json.dumps(
                        ["Rows are sourced from the normalized holdings database, which was built from the same filing schedule."],
                        ensure_ascii=False,
                    ),
                    "created_at_utc": created_at,
                }
            )
            rows.append(row)
    return rows


def build_non_accrual_summary_rows(
    non_accrual_issuer_rows: list[dict[str, Any]],
    created_at: str,
) -> list[dict[str, Any]]:
    disclosure_by_fund_period: dict[tuple[str, str], dict[str, Any]] = {
        **{
            ("BXSL", item["period_end"]): {
                "reported_non_accrual_cost_pct": item["reported_non_accrual_cost_pct"],
                "reported_non_accrual_fv_pct": item["reported_non_accrual_fv_pct"],
                "reported_non_accrual_cost_mm": None,
                "reported_non_accrual_fv_mm": None,
                "source_title": item["source_title"].replace("schedule footnote (17)", "non-accrual portfolio metrics"),
                "source_file": item["source_file"],
                "source_pages": item["metric_pages"],
                "source_notes": [
                    "The filing discloses non-accrual percentages; issuer dollar amounts come from schedule rows tagged with footnote (17).",
                    "BXSL issuer-level rows are manually grouped because the centralized holdings database does not retain footnote (17).",
                ],
            }
            for item in BXSL_NON_ACCRUAL_PERIOD_SOURCES
        },
        **{
            ("FSK", item["period_end"]): {
                "reported_non_accrual_cost_pct": None,
                "reported_non_accrual_fv_pct": item["reported_non_accrual_fv_pct"],
                "reported_non_accrual_cost_mm": None,
                "reported_non_accrual_fv_mm": None,
                "source_title": item["source_title"].replace("schedule footnote (z)", "non-accrual portfolio metrics"),
                "source_file": item["source_file"],
                "source_pages": item["metric_pages"],
                "source_notes": [
                    "The filing discloses non-accrual fair-value percentage; issuer dollar amounts come from schedule rows tagged with footnote (z)."
                ],
            }
            for item in FSK_NON_ACCRUAL_PERIOD_SOURCES
        },
        **{
            ("TSLX", item["period_end"]): {
                "reported_non_accrual_cost_pct": item["reported_non_accrual_cost_pct"],
                "reported_non_accrual_fv_pct": item["reported_non_accrual_fv_pct"],
                "reported_non_accrual_cost_mm": item["reported_non_accrual_cost_mm"],
                "reported_non_accrual_fv_mm": item["reported_non_accrual_fv_mm"],
                "source_title": item["source_title"].replace(f"schedule footnote {item['footnote_token']}", "non-accrual portfolio metrics"),
                "source_file": item["source_file"],
                "source_pages": item["metric_pages"],
                "source_notes": item.get(
                    "source_notes",
                    [
                        "The filing discloses non-accrual cost/fair-value dollars and percentages.",
                        f"Issuer dollar amounts come from schedule rows tagged with footnote {item['footnote_token']}.",
                    ],
                ),
            }
            for item in TSLX_NON_ACCRUAL_PERIOD_SOURCES
        },
    }
    rows: list[dict[str, Any]] = []
    for (fund, period_end), disclosure in sorted(disclosure_by_fund_period.items()):
        issuer_rows = [
            row
            for row in non_accrual_issuer_rows
            if row["fund"] == fund and row["period_end"] == period_end
        ]
        row = {column: None for column in NON_ACCRUAL_SUMMARY_COLUMNS}
        row.update(
            {
                "fund": fund,
                "period_end": period_end,
                "issuer_count": len(issuer_rows),
                "security_count": sum(int(item["security_count"]) for item in issuer_rows),
                "amortized_cost_mm": round(sum(float(item["amortized_cost_mm"] or 0) for item in issuer_rows), 6),
                "fair_value_mm": round(sum(float(item["fair_value_mm"] or 0) for item in issuer_rows), 6),
                "reported_non_accrual_cost_pct": disclosure["reported_non_accrual_cost_pct"],
                "reported_non_accrual_fv_pct": disclosure["reported_non_accrual_fv_pct"],
                "reported_non_accrual_cost_mm": disclosure["reported_non_accrual_cost_mm"],
                "reported_non_accrual_fv_mm": disclosure["reported_non_accrual_fv_mm"],
                "source_title": disclosure["source_title"],
                "source_file": disclosure["source_file"],
                "source_pages_json": json.dumps(disclosure["source_pages"]),
                "source_notes_json": json.dumps(disclosure["source_notes"], ensure_ascii=False),
                "created_at_utc": created_at,
            }
        )
        rows.append(row)
    return rows


def issuer_identity_key(value: str | None) -> str:
    if not value:
        return ""
    text = "".join(character if character.isalnum() else " " for character in value.upper())
    drop_tokens = {
        "A",
        "AN",
        "AND",
        "CO",
        "COMPANY",
        "CORP",
        "CORPORATION",
        "HOLDING",
        "HOLDINGS",
        "INC",
        "INCORPORATED",
        "L",
        "LTD",
        "LLC",
        "LP",
        "PLC",
        "THE",
    }
    security_suffix_tokens = {
        "ABF",
        "CLASS",
        "COMMON",
        "EQUITY",
        "MEZZANINE",
        "PREFERRED",
        "STOCK",
        "STRUCTURED",
        "WARRANT",
        "WARRANTS",
    }
    tokens = []
    for token in text.split():
        if token in security_suffix_tokens:
            break
        if token not in drop_tokens:
            tokens.append(token)
    return " ".join(tokens)


def issuer_display_name_score(value: str | None) -> tuple[int, int]:
    if not value:
        return (999, 999)
    upper_value = value.upper()
    security_penalty = 100 if any(
        token in upper_value
        for token in [
            " ABF ",
            " CLASS ",
            " COMMON ",
            " EQUITY",
            " MEZZANINE",
            " PREFERRED ",
            " STOCK",
            " STRUCTURED ",
            " WARRANT",
        ]
    ) else 0
    return (security_penalty, len(value))


def ratio_below(value: float | None, threshold: float) -> bool:
    return value is not None and value < threshold


def choose_watchlist_bucket(is_non_accrual: bool, fv_to_cost_pct: float | None, fv_to_principal_pct: float | None) -> tuple[str | None, int | None]:
    comparable_values = [value for value in [fv_to_cost_pct, fv_to_principal_pct] if value is not None]
    if is_non_accrual:
        return "Non-accrual", 0
    if any(value < 80 for value in comparable_values):
        return "Shadow <80", 1
    if any(value < 90 for value in comparable_values):
        return "Shadow 80-90", 2
    if any(value < 97 for value in comparable_values):
        return "Watch 90-97", 3
    return None, None


def compact_label(value: str | None) -> str | None:
    if value is None:
        return None
    compacted = " ".join(str(value).split())
    return compacted or None


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def classify_watchlist_instrument_context(
    investment_category: str | None,
    instrument_type: str | None,
    investment_description: str | None,
    issuer_name: str | None,
) -> str:
    text = " ".join(
        value
        for value in [
            investment_category,
            instrument_type,
            investment_description,
            issuer_name,
        ]
        if value
    ).lower()
    normalized = f" {text.replace('-', ' ')} "
    category = f" {(investment_category or '').lower().replace('-', ' ')} "

    equity_like = contains_any(
        normalized,
        (
            " abf equity",
            " equity",
            " preferred",
            " common stock",
            " common shares",
            " ordinary shares",
            " partnership interest",
            " partnership",
            " membership interest",
            " warrant",
            " shares",
            " units",
            " interests",
        ),
    )
    debt_like = contains_any(
        normalized,
        (
            " loan",
            " note",
            " bond",
            " revolver",
            " revolving",
            " receivable",
            " facility",
            " debt",
            " structured mezzanine",
            " mezzanine",
        ),
    )
    abf_like = (
        " asset based finance " in category
        or " asset backed " in normalized
        or " abf " in normalized
        or normalized.strip().endswith(" abf")
    )
    structured_like = contains_any(
        normalized,
        (
            " structured credit",
            " trust certificate",
            " trust certificates",
            " abs ",
            " class a units",
            " class aa units",
            " class b units",
            " class c units",
        ),
    )

    if abf_like:
        if equity_like:
            return "ABF preferred / equity"
        if debt_like:
            return "ABF debt / loan"
        return "Asset based finance"
    if structured_like:
        return "Structured credit / ABS"
    if contains_any(normalized, (" first lien", " senior secured", " filo", " dip term loan", " super priority")):
        return "First-lien senior loan"
    if " second lien" in normalized:
        return "Second-lien debt"
    if contains_any(normalized, (" subordinated", " mezzanine", " holdco", " promissory note")):
        return "Subordinated / other debt"
    if debt_like:
        return "Other debt"
    if equity_like:
        return "Equity / other"
    return "Mixed / other"


def issuer_security_hint(value: str | None) -> str | None:
    if not value or "," not in value:
        return None
    parts = [part.strip() for part in value.split(",") if part.strip()]
    for part in reversed(parts[1:]):
        normalized = f" {part.lower().replace('-', ' ')} "
        if contains_any(
            normalized,
            (
                " abf equity",
                " preferred stock",
                " common stock",
                " partnership interest",
                " term loan",
                " subordinated bond",
                " bond",
                " revolver",
                " structured mezzanine",
                " mezzanine",
                " equity",
            ),
        ):
            return part
    return None


def watchlist_instrument_detail(
    investment_category: str | None,
    instrument_type: str | None,
    investment_description: str | None,
    issuer_name: str | None,
) -> str | None:
    details: list[str] = []
    issuer_key = issuer_identity_key(issuer_name)
    for value in [investment_category, instrument_type, investment_description]:
        label = compact_label(value)
        if not label:
            continue
        if issuer_key and issuer_identity_key(label) == issuer_key:
            continue
        if label not in details:
            details.append(label)

    hint = issuer_security_hint(issuer_name)
    if hint and hint not in details:
        details.append(hint)
    return " / ".join(details[:3]) if details else None


def summarize_watchlist_context(contexts: set[str]) -> str | None:
    labels = sorted(label for label in contexts if label)
    if not labels:
        return None
    if len(labels) == 1:
        return labels[0]
    debt_labels = {
        "First-lien senior loan",
        "Second-lien debt",
        "Subordinated / other debt",
        "Other debt",
    }
    abf_labels = {
        "ABF preferred / equity",
        "ABF debt / loan",
        "Asset based finance",
    }
    if all(label in debt_labels for label in labels):
        return "Mixed debt"
    if all(label in abf_labels for label in labels):
        return "Mixed ABF"
    return "Mixed instruments"


def summarize_label_set(values: set[str], limit: int = 3) -> str | None:
    def sort_key(label: str) -> tuple[int, str]:
        lower = label.lower()
        if "first lien" in lower or "senior secured" in lower:
            return (0, label)
        if "second lien" in lower or "subordinated" in lower:
            return (1, label)
        if "asset based" in lower or "abf" in lower:
            return (2, label)
        if "structured" in lower or "trust certificate" in lower:
            return (3, label)
        if "equity" in lower or "preferred" in lower or "common stock" in lower:
            return (4, label)
        return (9, label)

    labels = sorted((label for label in values if label), key=sort_key)
    if not labels:
        return None
    if len(labels) <= limit:
        return ", ".join(labels)
    return f"{', '.join(labels[:limit])} +{len(labels) - limit}"


def build_issuer_watchlist_rows(
    con: sqlite3.Connection,
    non_accrual_issuer_rows: list[dict[str, Any]],
    created_at: str,
) -> list[dict[str, Any]]:
    non_accrual_by_fund_period: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in non_accrual_issuer_rows:
        key = (item["fund"], item["period_end"])
        non_accrual_by_fund_period.setdefault(key, []).append(item)

    def matching_non_accrual_name(fund: str, period_end: str, issuer_match_key: str, issuer_name: str) -> str | None:
        candidate_keys = {
            issuer_identity_key(issuer_match_key),
            issuer_identity_key(issuer_name),
        }
        known_rows = non_accrual_by_fund_period.get((fund, period_end), [])
        for candidate in candidate_keys:
            if not candidate:
                continue
            for known_row in known_rows:
                known = issuer_identity_key(known_row["issuer_name"])
                if candidate == known or candidate.startswith(known) or known.startswith(candidate):
                    return known_row["issuer_name"]
        return None

    source_file = str(CENTRAL_DB_PATH.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
    grouped_holdings: dict[tuple[str, str, str], dict[str, Any]] = {}
    for holding in con.execute(
        """
        select
            fund,
            filing_period_end as period_end,
            coalesce(nullif(issuer_match_key, ''), issuer_name) as source_issuer_key,
            issuer_name,
            industry,
            investment_category,
            instrument_type,
            investment_description,
            principal_mm,
            amortized_cost_mm,
            fair_value_mm
        from funded_security_level_holdings
        where fund in ('BXSL', 'FSK', 'TSLX')
        """
    ):
        fund = holding["fund"]
        period_end = holding["period_end"]
        source_issuer_key = holding["source_issuer_key"] or holding["issuer_name"]
        issuer_match_key = issuer_identity_key(source_issuer_key) or source_issuer_key
        group_key = (fund, period_end, issuer_match_key)
        item = grouped_holdings.setdefault(
            group_key,
            {
                "fund": fund,
                "period_end": period_end,
                "issuer_match_key": issuer_match_key,
                "issuer_name": holding["issuer_name"] or source_issuer_key,
                "issuer_name_score": issuer_display_name_score(holding["issuer_name"] or source_issuer_key),
                "issuer_industries": set(),
                "instrument_contexts": set(),
                "instrument_details": set(),
                "security_count": 0,
                "principal_mm": 0.0,
                "principal_count": 0,
                "principal_fair_value_mm": 0.0,
                "principal_fair_value_count": 0,
                "amortized_cost_mm": 0.0,
                "amortized_cost_count": 0,
                "fair_value_mm": 0.0,
                "fair_value_count": 0,
            },
        )
        display_name = holding["issuer_name"] or source_issuer_key
        display_score = issuer_display_name_score(display_name)
        if display_name and display_score < item["issuer_name_score"]:
            item["issuer_name"] = display_name
            item["issuer_name_score"] = display_score
        if holding["industry"]:
            item["issuer_industries"].add(holding["industry"])
        item["instrument_contexts"].add(
            classify_watchlist_instrument_context(
                holding["investment_category"],
                holding["instrument_type"],
                holding["investment_description"],
                holding["issuer_name"],
            )
        )
        detail = watchlist_instrument_detail(
            holding["investment_category"],
            holding["instrument_type"],
            holding["investment_description"],
            holding["issuer_name"],
        )
        if detail:
            item["instrument_details"].add(detail)
        item["security_count"] += 1
        if holding["principal_mm"] is not None:
            item["principal_mm"] += float(holding["principal_mm"])
            item["principal_count"] += 1
            if holding["fair_value_mm"] is not None and float(holding["principal_mm"]) > 0:
                item["principal_fair_value_mm"] += float(holding["fair_value_mm"])
                item["principal_fair_value_count"] += 1
        if holding["amortized_cost_mm"] is not None:
            item["amortized_cost_mm"] += float(holding["amortized_cost_mm"])
            item["amortized_cost_count"] += 1
        if holding["fair_value_mm"] is not None:
            item["fair_value_mm"] += float(holding["fair_value_mm"])
            item["fair_value_count"] += 1

    rows_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for (fund, period_end, issuer_match_key), holding in grouped_holdings.items():
        issuer_name = holding["issuer_name"] or issuer_match_key
        principal_mm = round(holding["principal_mm"], 6) if holding["principal_count"] else None
        principal_fair_value_mm = (
            round(holding["principal_fair_value_mm"], 6) if holding["principal_fair_value_count"] else None
        )
        amortized_cost_mm = round(holding["amortized_cost_mm"], 6) if holding["amortized_cost_count"] else None
        fair_value_mm = round(holding["fair_value_mm"], 6) if holding["fair_value_count"] else None
        mark_vs_cost_mm = (
            round(float(fair_value_mm) - float(amortized_cost_mm), 6)
            if fair_value_mm is not None and amortized_cost_mm is not None
            else None
        )
        fv_to_cost_pct = pct(fair_value_mm, amortized_cost_mm)
        fv_to_principal_pct = pct(principal_fair_value_mm, principal_mm)
        non_accrual_name = matching_non_accrual_name(fund, period_end, issuer_match_key, issuer_name)
        if non_accrual_name:
            issuer_name = non_accrual_name
        is_non_accrual = non_accrual_name is not None
        bucket, severity = choose_watchlist_bucket(is_non_accrual, fv_to_cost_pct, fv_to_principal_pct)
        row = {column: None for column in ISSUER_WATCHLIST_COLUMNS}
        row.update(
            {
                "fund": fund,
                "period_end": period_end,
                "issuer_match_key": issuer_match_key,
                "issuer_name": issuer_name,
                "issuer_industries": ", ".join(sorted(holding["issuer_industries"])) or None,
                "instrument_context": summarize_watchlist_context(holding["instrument_contexts"]),
                "instrument_context_detail": summarize_label_set(holding["instrument_details"]),
                "security_count": int(holding["security_count"] or 0),
                "principal_mm": principal_mm,
                "principal_fair_value_mm": principal_fair_value_mm if principal_mm is not None else None,
                "amortized_cost_mm": amortized_cost_mm,
                "fair_value_mm": fair_value_mm,
                "mark_vs_cost_mm": mark_vs_cost_mm,
                "fv_to_cost_pct": fv_to_cost_pct,
                "fv_to_principal_pct": fv_to_principal_pct,
                "below_97_fv_to_cost": ratio_below(fv_to_cost_pct, 97),
                "below_90_fv_to_cost": ratio_below(fv_to_cost_pct, 90),
                "below_80_fv_to_cost": ratio_below(fv_to_cost_pct, 80),
                "below_97_fv_to_principal": ratio_below(fv_to_principal_pct, 97),
                "below_90_fv_to_principal": ratio_below(fv_to_principal_pct, 90),
                "below_80_fv_to_principal": ratio_below(fv_to_principal_pct, 80),
                "is_non_accrual": is_non_accrual,
                "shadow_non_accrual": (
                    not is_non_accrual
                    and (
                        ratio_below(fv_to_cost_pct, 90)
                        or ratio_below(fv_to_principal_pct, 90)
                    )
                ),
                "watchlist_bucket": bucket,
                "watchlist_severity": severity,
                "source_title": "Centralized holdings database",
                "source_file": source_file,
                "source_method": "Grouped central funded holdings by fund, period, and issuer match key; watchlist flags use FV/cost and FV/principal where principal is parsed.",
                "source_notes_json": json.dumps(
                    [
                        "FV/cost is fair value divided by amortized cost and is available broadly across the three-fund holdings database.",
                        "FV/principal is shown only where the source parser captured principal amount; BXSL principal coverage is limited in the current central database.",
                        "FSK footnote (x) unfunded-commitment rows are excluded from funded issuer watchlist grouping.",
                        "Shadow non-accrual means the issuer is not in the sourced non-accrual table but is marked below 90 on FV/cost or FV/principal.",
                        "Instrument context is derived from as-filed category, type, and description labels; it is a context aid, not a standalone loss-severity ranking.",
                    ],
                    ensure_ascii=False,
                ),
                "created_at_utc": created_at,
            }
        )
        rows_by_key[(fund, period_end, issuer_match_key)] = row

    for (fund, period_end), items in non_accrual_by_fund_period.items():
        for item in items:
            issuer_key = item["issuer_name"]
            item_identity_key = issuer_identity_key(item["issuer_name"])
            key = (fund, period_end, issuer_key)
            if any(
                existing["fund"] == fund
                and existing["period_end"] == period_end
                and (
                    issuer_identity_key(existing["issuer_name"]) == item_identity_key
                    or issuer_identity_key(existing["issuer_name"]).startswith(item_identity_key)
                    or item_identity_key.startswith(issuer_identity_key(existing["issuer_name"]))
                )
                for existing in rows_by_key.values()
            ):
                continue
            amortized_cost_mm = as_float(item["amortized_cost_mm"])
            fair_value_mm = as_float(item["fair_value_mm"])
            fv_to_cost_pct = pct(fair_value_mm, amortized_cost_mm)
            row = {column: None for column in ISSUER_WATCHLIST_COLUMNS}
            row.update(
                {
                    "fund": fund,
                    "period_end": period_end,
                    "issuer_match_key": issuer_key,
                    "issuer_name": item["issuer_name"],
                    "instrument_context": "Non-accrual table only",
                    "instrument_context_detail": "Underlying holdings instrument label unavailable",
                    "security_count": item["security_count"],
                    "amortized_cost_mm": amortized_cost_mm,
                    "fair_value_mm": fair_value_mm,
                    "mark_vs_cost_mm": round(float(fair_value_mm or 0) - float(amortized_cost_mm or 0), 6),
                    "fv_to_cost_pct": fv_to_cost_pct,
                    "below_97_fv_to_cost": ratio_below(fv_to_cost_pct, 97),
                    "below_90_fv_to_cost": ratio_below(fv_to_cost_pct, 90),
                    "below_80_fv_to_cost": ratio_below(fv_to_cost_pct, 80),
                    "below_97_fv_to_principal": False,
                    "below_90_fv_to_principal": False,
                    "below_80_fv_to_principal": False,
                    "is_non_accrual": True,
                    "shadow_non_accrual": False,
                    "watchlist_bucket": "Non-accrual",
                    "watchlist_severity": 0,
                    "source_title": item["source_title"],
                    "source_file": item["source_file"],
                    "source_method": "Sourced non-accrual issuer row retained in watchlist because no matching central holdings issuer-period row is present.",
                    "source_notes_json": item["source_notes_json"],
                    "created_at_utc": created_at,
                }
            )
            rows_by_key[key] = row

    all_rows = list(rows_by_key.values())
    rows_by_issuer: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in all_rows:
        rows_by_issuer.setdefault((row["fund"], row["issuer_match_key"]), []).append(row)

    for issuer_rows in rows_by_issuer.values():
        issuer_rows.sort(key=lambda item: item["period_end"])
        prior: dict[str, Any] | None = None
        for row in issuer_rows:
            if prior is not None:
                row["prior_period_end"] = prior["period_end"]
                row["prior_fv_to_cost_pct"] = prior["fv_to_cost_pct"]
                row["prior_fv_to_principal_pct"] = prior["fv_to_principal_pct"]
                if row["fv_to_cost_pct"] is not None and prior["fv_to_cost_pct"] is not None:
                    row["qoq_fv_to_cost_change_pct"] = round(row["fv_to_cost_pct"] - prior["fv_to_cost_pct"], 4)
                if row["fv_to_principal_pct"] is not None and prior["fv_to_principal_pct"] is not None:
                    row["qoq_fv_to_principal_change_pct"] = round(row["fv_to_principal_pct"] - prior["fv_to_principal_pct"], 4)
                if row["fair_value_mm"] is not None and prior["fair_value_mm"] is not None:
                    row["qoq_fair_value_change_mm"] = round(row["fair_value_mm"] - prior["fair_value_mm"], 6)
                if row["mark_vs_cost_mm"] is not None and prior["mark_vs_cost_mm"] is not None:
                    row["qoq_mark_vs_cost_change_mm"] = round(row["mark_vs_cost_mm"] - prior["mark_vs_cost_mm"], 6)

            material_qoq_deterioration = (
                ratio_below(row["qoq_fv_to_cost_change_pct"], -5)
                or ratio_below(row["qoq_fv_to_principal_change_pct"], -5)
            )
            row["material_qoq_deterioration"] = material_qoq_deterioration
            if row["watchlist_bucket"] is None and material_qoq_deterioration:
                row["watchlist_bucket"] = "QoQ deterioration"
                row["watchlist_severity"] = 4
            prior = row

    watchlist_rows = [
        row
        for row in all_rows
        if row["watchlist_bucket"] is not None
    ]
    return sorted(
        watchlist_rows,
        key=lambda item: (
            item["period_end"],
            item["watchlist_severity"],
            item["fund"],
            -(item["fair_value_mm"] or 0),
            item["issuer_name"],
        ),
    )


def build_market_price_nav_rows(quarterly_rows: list[dict[str, Any]], created_at: str) -> list[dict[str, Any]]:
    if not MARKET_CLOSE_CSV_PATH.exists():
        return []

    nav_sources = {
        (mark["fund"], mark["period_end"]): mark
        for mark in PRESENTATION_NAV_MARKS
    }
    nav_marks: dict[str, list[tuple[date, float, dict[str, Any] | None]]] = {fund: [] for fund in FUNDS}
    for row in quarterly_rows:
        nav_per_share = row.get("nav_per_share")
        if row.get("fund") in nav_marks and nav_per_share is not None:
            source = nav_sources.get((row["fund"], row["period_end"]))
            nav_marks[row["fund"]].append((date.fromisoformat(row["period_end"]), float(nav_per_share), source))

    for fund in FUNDS:
        nav_marks[fund].sort(key=lambda item: item[0])

    market_rows: list[dict[str, Any]] = []
    with MARKET_CLOSE_CSV_PATH.open(newline="", encoding="utf-8-sig") as source:
        for raw_row in DictReader(source):
            price_date = parse_close_date(raw_row["Date"])
            for fund in FUNDS:
                raw_close = (raw_row.get(fund) or "").strip()
                if not raw_close:
                    continue
                close_price = float(raw_close)
                available_marks = [mark for mark in nav_marks[fund] if mark[0] <= price_date]
                if not available_marks:
                    continue
                nav_period, nav_per_share, nav_source = available_marks[-1]
                price_to_nav_pct = round(close_price / nav_per_share * 100, 4)
                market_rows.append(
                    {
                        "fund": fund,
                        "price_date": price_date.isoformat(),
                        "close_price": round(close_price, 6),
                        "nav_per_share": round(nav_per_share, 6),
                        "nav_period_end": nav_period.isoformat(),
                        "nav_mark_age_days": (price_date - nav_period).days,
                        "price_to_nav_pct": price_to_nav_pct,
                        "premium_discount_to_nav_pct": round(price_to_nav_pct - 100, 4),
                        "close_price_source_file": MARKET_CLOSE_SOURCE_LABEL,
                        "nav_source_title": nav_source["source_title"] if nav_source else None,
                        "nav_source_file": nav_source["source_file"] if nav_source else None,
                        "nav_source_page": nav_source["source_page"] if nav_source else None,
                        "created_at_utc": created_at,
                    }
                )
    return market_rows


def build_quarterly_market_rows(quarterly_rows: list[dict[str, Any]], created_at: str) -> list[dict[str, Any]]:
    if not MARKET_CLOSE_CSV_PATH.exists():
        return []

    close_rows: list[dict[str, Any]] = []
    with MARKET_CLOSE_CSV_PATH.open(newline="", encoding="utf-8-sig") as source:
        for raw_row in DictReader(source):
            price_date = parse_close_date(raw_row["Date"])
            for fund in FUNDS:
                raw_close = (raw_row.get(fund) or "").strip()
                if raw_close:
                    close_rows.append(
                        {
                            "fund": fund,
                            "price_date": price_date,
                            "close_price": float(raw_close),
                        }
                    )

    nav_sources = {
        (mark["fund"], mark["period_end"]): mark
        for mark in PRESENTATION_NAV_MARKS
    }
    rows: list[dict[str, Any]] = []
    for row in quarterly_rows:
        fund = row.get("fund")
        nav_per_share = row.get("nav_per_share")
        period_end_value = row.get("period_end")
        if fund not in FUNDS or nav_per_share is None or not period_end_value:
            continue

        period_end = date.fromisoformat(period_end_value)
        quarter_start = quarter_start_for(period_end)
        quarter_closes = [
            item
            for item in close_rows
            if item["fund"] == fund and quarter_start <= item["price_date"] <= period_end
        ]
        if not quarter_closes:
            continue

        quarter_closes.sort(key=lambda item: item["price_date"])
        close_prices = [float(item["close_price"]) for item in quarter_closes]
        quarter_end_close = quarter_closes[-1]
        quarter_end_close_price = float(quarter_end_close["close_price"])
        avg_close_price = sum(close_prices) / len(close_prices)
        quarter_end_price_to_nav_pct = round(quarter_end_close_price / float(nav_per_share) * 100, 4)
        avg_price_to_nav_pct = round(avg_close_price / float(nav_per_share) * 100, 4)
        nav_source = nav_sources.get((fund, period_end_value))
        rows.append(
            {
                "fund": fund,
                "period_end": period_end.isoformat(),
                "quarter_start": quarter_start.isoformat(),
                "quarter_end": period_end.isoformat(),
                "trading_days": len(quarter_closes),
                "quarter_end_price_date": quarter_end_close["price_date"].isoformat(),
                "quarter_end_close_price": round(quarter_end_close_price, 6),
                "avg_daily_close_price": round(avg_close_price, 6),
                "min_daily_close_price": round(min(close_prices), 6),
                "max_daily_close_price": round(max(close_prices), 6),
                "nav_per_share": round(float(nav_per_share), 6),
                "nav_period_end": period_end.isoformat(),
                "price_date_to_nav_date_days": (quarter_end_close["price_date"] - period_end).days,
                "quarter_end_price_to_nav_pct": quarter_end_price_to_nav_pct,
                "quarter_end_premium_discount_to_nav_pct": round(quarter_end_price_to_nav_pct - 100, 4),
                "avg_price_to_nav_pct": avg_price_to_nav_pct,
                "avg_premium_discount_to_nav_pct": round(avg_price_to_nav_pct - 100, 4),
                "close_price_source_file": MARKET_CLOSE_SOURCE_LABEL,
                "nav_source_title": nav_source["source_title"] if nav_source else None,
                "nav_source_file": nav_source["source_file"] if nav_source else None,
                "nav_source_page": nav_source["source_page"] if nav_source else None,
                "source_notes_json": json.dumps(
                    [
                        "Quarter-end close price is the last available public close on or before the quarter end date.",
                        "Average daily close price uses all available trading days in the calendar quarter.",
                        "Price/NAV metrics use the sourced NAV/share mark for the same quarter end.",
                    ]
                ),
                "created_at_utc": created_at,
            }
        )
    return sorted(rows, key=lambda item: (item["period_end"], item["fund"]))


def create_model_db(
    rows: list[dict[str, Any]],
    market_price_nav_rows: list[dict[str, Any]],
    quarterly_market_rows: list[dict[str, Any]],
    expense_rows: list[dict[str, Any]],
    income_quality_rows: list[dict[str, Any]],
    dividend_declaration_rows: list[dict[str, Any]],
    non_accrual_issuer_rows: list[dict[str, Any]],
    non_accrual_summary_rows: list[dict[str, Any]],
    issuer_watchlist_rows: list[dict[str, Any]],
    created_at: str,
) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="bdc_quarterly_model_") as tmp_dir:
        tmp_db_path = Path(tmp_dir) / MODEL_DB_PATH.name
        con = sqlite3.connect(tmp_db_path)
        try:
            con.execute("pragma foreign_keys = on")
            con.executescript(
                """
                create table build_metadata (
                    key text primary key,
                    value text not null
                );

                create table quarterly_bdc_facts (
                    id integer primary key autoincrement,
                    fund text not null,
                    period_end text not null,
                    company_name text not null,
                    report_type text,
                    source_status text not null,
                    source_title text,
                    source_file text,
                    holding_rows integer,
                    holdings_amortized_cost_mm real,
                    holdings_fair_value_mm real,
                    holdings_mark_vs_cost_mm real,
                    holdings_mark_to_cost_pct real,
                    holdings_first_lien_pct real,
                    holdings_floating_rate_pct real,
                    holdings_pik_fair_value_mm real,
                    holdings_pik_fair_value_pct real,
                    holdings_below_90_fair_value_mm real,
                    holdings_below_80_fair_value_mm real,
                    holdings_weighted_avg_spread_bps real,
                    nav_per_share real,
                    nii_mm real,
                    nii_per_share real,
                    adjusted_nii_mm real,
                    adjusted_nii_per_share real,
                    base_dividend_per_share real,
                    total_dividend_per_share real,
                    base_dividend_coverage_pct real,
                    total_dividend_coverage_pct real,
                    reported_total_investments_fv_mm real,
                    total_debt_principal_mm real,
                    net_assets_mm real,
                    debt_to_equity_x real,
                    avg_debt_to_equity_x real,
                    net_debt_to_equity_x real,
                    liquidity_mm real,
                    debt_cost_pct real,
                    weighted_avg_yield_pct real,
                    weighted_avg_spread_over_base_rate_pct real,
                    first_lien_pct real,
                    floating_rate_debt_investments_pct real,
                    non_accrual_fv_pct real,
                    non_accrual_cost_pct real,
                    pik_income_mm real,
                    fee_income_mm real,
                    new_commitments_mm real,
                    fundings_mm real,
                    repayments_sales_mm real,
                    net_investment_activity_mm real,
                    new_investment_yield_pct real,
                    repayment_yield_pct real,
                    source_notes_json text not null,
                    created_at_utc text not null,
                    unique (fund, period_end)
                );

                create table market_price_nav_history (
                    id integer primary key autoincrement,
                    fund text not null,
                    price_date text not null,
                    close_price real not null,
                    nav_per_share real not null,
                    nav_period_end text not null,
                    nav_mark_age_days integer not null,
                    price_to_nav_pct real not null,
                    premium_discount_to_nav_pct real not null,
                    close_price_source_file text not null,
                    nav_source_title text,
                    nav_source_file text,
                    nav_source_page integer,
                    created_at_utc text not null,
                    unique (fund, price_date)
                );

                create table quarterly_market_facts (
                    id integer primary key autoincrement,
                    fund text not null,
                    period_end text not null,
                    quarter_start text not null,
                    quarter_end text not null,
                    trading_days integer not null,
                    quarter_end_price_date text not null,
                    quarter_end_close_price real not null,
                    avg_daily_close_price real not null,
                    min_daily_close_price real not null,
                    max_daily_close_price real not null,
                    nav_per_share real not null,
                    nav_period_end text not null,
                    price_date_to_nav_date_days integer not null,
                    quarter_end_price_to_nav_pct real not null,
                    quarter_end_premium_discount_to_nav_pct real not null,
                    avg_price_to_nav_pct real not null,
                    avg_premium_discount_to_nav_pct real not null,
                    close_price_source_file text not null,
                    nav_source_title text,
                    nav_source_file text,
                    nav_source_page integer,
                    source_notes_json text not null,
                    created_at_utc text not null,
                    unique (fund, period_end)
                );

                create table nav_per_share_marks (
                    id integer primary key autoincrement,
                    fund text not null,
                    period_end text not null,
                    nav_per_share real not null,
                    source_title text not null,
                    source_file text not null,
                    source_page integer not null,
                    source_excerpt text not null,
                    created_at_utc text not null,
                    unique (fund, period_end, source_file, source_page)
                );

                create table quarterly_income_expense_facts (
                    id integer primary key autoincrement,
                    fund text not null,
                    period_end text not null,
                    source_title text not null,
                    source_file text not null,
                    source_pages_json text not null,
                    total_investment_income_mm real,
                    interest_income_mm real,
                    pik_interest_income_mm real,
                    fee_income_mm real,
                    dividend_income_mm real,
                    other_income_mm real,
                    interest_expense_mm real,
                    base_management_fee_mm real,
                    income_incentive_fee_mm real,
                    capital_gains_incentive_fee_mm real,
                    total_incentive_fee_mm real,
                    professional_fees_mm real,
                    directors_or_board_fees_mm real,
                    administrative_service_expense_mm real,
                    accounting_administrative_fees_mm real,
                    other_g_and_a_mm real,
                    total_g_and_a_mm real,
                    fee_waivers_mm real,
                    total_operating_expenses_mm real,
                    net_expenses_mm real,
                    tax_expense_mm real,
                    nii_mm real,
                    source_notes_json text not null,
                    created_at_utc text not null,
                    unique (fund, period_end, source_file)
                );

                create table quarterly_income_quality_facts (
                    id integer primary key autoincrement,
                    fund text not null,
                    period_end text not null,
                    source_title text not null,
                    source_file text not null,
                    source_pages_json text not null,
                    total_investment_income_mm real,
                    reported_nii_mm real,
                    reported_nii_per_share real,
                    adjusted_nii_mm real,
                    adjusted_nii_per_share real,
                    weighted_average_shares integer,
                    pik_interest_income_mm real,
                    pik_income_tii_pct real,
                    pik_income_nii_pct real,
                    interest_from_investments_other_fees_mm real,
                    other_fees_tii_pct real,
                    other_income_mm real,
                    other_income_tii_pct real,
                    fee_waivers_mm real,
                    capital_gains_incentive_fee_not_payable_mm real,
                    capital_gains_incentive_fee_not_payable_per_share real,
                    cash_nii_ex_pik_mm real,
                    cash_nii_ex_pik_per_share real,
                    cash_like_recurring_nii_mm real,
                    cash_like_recurring_nii_per_share real,
                    base_dividend_per_share real,
                    record_date_distributions_per_share real,
                    quarter_related_supplemental_dividend_per_share real,
                    quarter_related_total_dividend_per_share real,
                    reported_base_dividend_coverage_pct real,
                    reported_record_date_distribution_coverage_pct real,
                    reported_quarter_related_distribution_coverage_pct real,
                    adjusted_base_dividend_coverage_pct real,
                    adjusted_record_date_distribution_coverage_pct real,
                    cash_like_base_dividend_coverage_pct real,
                    cash_like_record_date_distribution_coverage_pct real,
                    one_time_items_json text not null,
                    source_notes_json text not null,
                    created_at_utc text not null,
                    unique (fund, period_end)
                );

                create table dividend_declaration_facts (
                    id integer primary key autoincrement,
                    fund text not null,
                    declared_date text not null,
                    record_date text not null,
                    payment_date text not null,
                    amount_per_share real not null,
                    dividend_type text not null,
                    related_period_end text,
                    source_title text not null,
                    source_file text not null,
                    source_page integer not null,
                    source_notes_json text not null,
                    created_at_utc text not null,
                    unique (fund, declared_date, record_date, payment_date, amount_per_share, dividend_type)
                );

                create table non_accrual_issuer_facts (
                    id integer primary key autoincrement,
                    fund text not null,
                    period_end text not null,
                    issuer_name text not null,
                    security_count integer not null,
                    amortized_cost_mm real not null,
                    fair_value_mm real not null,
                    source_title text not null,
                    source_file text not null,
                    source_pages_json text not null,
                    source_method text not null,
                    source_notes_json text not null,
                    created_at_utc text not null,
                    unique (fund, period_end, issuer_name)
                );

                create table non_accrual_summary_facts (
                    id integer primary key autoincrement,
                    fund text not null,
                    period_end text not null,
                    issuer_count integer not null,
                    security_count integer not null,
                    amortized_cost_mm real not null,
                    fair_value_mm real not null,
                    reported_non_accrual_cost_pct real,
                    reported_non_accrual_fv_pct real,
                    reported_non_accrual_cost_mm real,
                    reported_non_accrual_fv_mm real,
                    source_title text not null,
                    source_file text not null,
                    source_pages_json text not null,
                    source_notes_json text not null,
                    created_at_utc text not null,
                    unique (fund, period_end)
                );

                create table issuer_watchlist_facts (
                    id integer primary key autoincrement,
                    fund text not null,
                    period_end text not null,
                    issuer_match_key text not null,
                    issuer_name text not null,
                    issuer_industries text,
                    instrument_context text,
                    instrument_context_detail text,
                    security_count integer not null,
                    principal_mm real,
                    principal_fair_value_mm real,
                    amortized_cost_mm real,
                    fair_value_mm real,
                    mark_vs_cost_mm real,
                    fv_to_cost_pct real,
                    fv_to_principal_pct real,
                    prior_period_end text,
                    prior_fv_to_cost_pct real,
                    prior_fv_to_principal_pct real,
                    qoq_fv_to_cost_change_pct real,
                    qoq_fv_to_principal_change_pct real,
                    qoq_fair_value_change_mm real,
                    qoq_mark_vs_cost_change_mm real,
                    below_97_fv_to_cost integer not null,
                    below_90_fv_to_cost integer not null,
                    below_80_fv_to_cost integer not null,
                    below_97_fv_to_principal integer not null,
                    below_90_fv_to_principal integer not null,
                    below_80_fv_to_principal integer not null,
                    is_non_accrual integer not null,
                    shadow_non_accrual integer not null,
                    material_qoq_deterioration integer not null,
                    watchlist_bucket text not null,
                    watchlist_severity integer not null,
                    source_title text not null,
                    source_file text not null,
                    source_method text not null,
                    source_notes_json text not null,
                    created_at_utc text not null,
                    unique (fund, period_end, issuer_match_key)
                );

                create index idx_market_price_nav_history_fund_date
                on market_price_nav_history (fund, price_date);

                create index idx_quarterly_market_facts_fund_period
                on quarterly_market_facts (fund, period_end);

                create index idx_nav_per_share_marks_fund_period
                on nav_per_share_marks (fund, period_end);

                create index idx_quarterly_income_quality_facts_fund_period
                on quarterly_income_quality_facts (fund, period_end);

                create index idx_dividend_declaration_facts_fund_record_date
                on dividend_declaration_facts (fund, record_date);

                create index idx_non_accrual_issuer_facts_fund_period
                on non_accrual_issuer_facts (fund, period_end);

                create index idx_issuer_watchlist_facts_fund_period
                on issuer_watchlist_facts (fund, period_end);

                create view latest_quarterly_bdc_facts as
                select *
                from quarterly_bdc_facts
                where period_end = (select max(period_end) from quarterly_bdc_facts);

                create view latest_market_price_nav as
                select *
                from market_price_nav_history
                where price_date = (select max(price_date) from market_price_nav_history);
                """
            )
            con.executemany(
                f"""
                insert into quarterly_bdc_facts ({", ".join(FACT_COLUMNS)})
                values ({", ".join("?" for _ in FACT_COLUMNS)})
                """,
                [[row.get(column) for column in FACT_COLUMNS] for row in rows],
            )
            con.executemany(
                f"""
                insert into market_price_nav_history ({", ".join(MARKET_PRICE_NAV_COLUMNS)})
                values ({", ".join("?" for _ in MARKET_PRICE_NAV_COLUMNS)})
                """,
                [[row.get(column) for column in MARKET_PRICE_NAV_COLUMNS] for row in market_price_nav_rows],
            )
            con.executemany(
                f"""
                insert into quarterly_market_facts ({", ".join(QUARTERLY_MARKET_FACT_COLUMNS)})
                values ({", ".join("?" for _ in QUARTERLY_MARKET_FACT_COLUMNS)})
                """,
                [[row.get(column) for column in QUARTERLY_MARKET_FACT_COLUMNS] for row in quarterly_market_rows],
            )
            con.executemany(
                f"""
                insert into nav_per_share_marks ({", ".join(NAV_MARK_COLUMNS)})
                values ({", ".join("?" for _ in NAV_MARK_COLUMNS)})
                """,
                [
                    [mark.get(column) if column != "created_at_utc" else created_at for column in NAV_MARK_COLUMNS]
                    for mark in PRESENTATION_NAV_MARKS
                ],
            )
            con.executemany(
                f"""
                insert into quarterly_income_expense_facts ({", ".join(EXPENSE_FACT_COLUMNS)})
                values ({", ".join("?" for _ in EXPENSE_FACT_COLUMNS)})
                """,
                [[row.get(column) for column in EXPENSE_FACT_COLUMNS] for row in expense_rows],
            )
            con.executemany(
                f"""
                insert into quarterly_income_quality_facts ({", ".join(INCOME_QUALITY_COLUMNS)})
                values ({", ".join("?" for _ in INCOME_QUALITY_COLUMNS)})
                """,
                [[row.get(column) for column in INCOME_QUALITY_COLUMNS] for row in income_quality_rows],
            )
            con.executemany(
                f"""
                insert into dividend_declaration_facts ({", ".join(DIVIDEND_DECLARATION_COLUMNS)})
                values ({", ".join("?" for _ in DIVIDEND_DECLARATION_COLUMNS)})
                """,
                [[row.get(column) for column in DIVIDEND_DECLARATION_COLUMNS] for row in dividend_declaration_rows],
            )
            con.executemany(
                f"""
                insert into non_accrual_issuer_facts ({", ".join(NON_ACCRUAL_ISSUER_COLUMNS)})
                values ({", ".join("?" for _ in NON_ACCRUAL_ISSUER_COLUMNS)})
                """,
                [[row.get(column) for column in NON_ACCRUAL_ISSUER_COLUMNS] for row in non_accrual_issuer_rows],
            )
            con.executemany(
                f"""
                insert into non_accrual_summary_facts ({", ".join(NON_ACCRUAL_SUMMARY_COLUMNS)})
                values ({", ".join("?" for _ in NON_ACCRUAL_SUMMARY_COLUMNS)})
                """,
                [[row.get(column) for column in NON_ACCRUAL_SUMMARY_COLUMNS] for row in non_accrual_summary_rows],
            )
            con.executemany(
                f"""
                insert into issuer_watchlist_facts ({", ".join(ISSUER_WATCHLIST_COLUMNS)})
                values ({", ".join("?" for _ in ISSUER_WATCHLIST_COLUMNS)})
                """,
                [[row.get(column) for column in ISSUER_WATCHLIST_COLUMNS] for row in issuer_watchlist_rows],
            )
            con.executemany(
                "insert into build_metadata (key, value) values (?, ?)",
                [
                    ("built_at_utc", created_at),
                    ("central_holdings_database", str(CENTRAL_DB_PATH.relative_to(WORKSPACE_ROOT)).replace("\\", "/")),
                    ("dashboard_json", str(JSON_OUTPUT_PATH.relative_to(WORKSPACE_ROOT)).replace("\\", "/")),
                    ("market_close_source_csv", MARKET_CLOSE_SOURCE_LABEL),
                    ("market_price_nav_rows", str(len(market_price_nav_rows))),
                    ("quarterly_market_facts", str(len(quarterly_market_rows))),
                    ("nav_per_share_marks", str(len(PRESENTATION_NAV_MARKS))),
                    ("investment_activity_backfilled_rows", str(len(INVESTMENT_ACTIVITY_FACTS))),
                    ("quarterly_income_expense_facts", str(len(expense_rows))),
                    ("quarterly_income_quality_facts", str(len(income_quality_rows))),
                    ("dividend_declaration_facts", str(len(dividend_declaration_rows))),
                    ("non_accrual_issuer_facts", str(len(non_accrual_issuer_rows))),
                    ("issuer_watchlist_facts", str(len(issuer_watchlist_rows))),
                    ("funds", ",".join(FUNDS)),
                ],
            )
            con.commit()
        finally:
            con.close()
        copy2_with_retries(tmp_db_path, MODEL_DB_PATH)


def export_json(
    rows: list[dict[str, Any]],
    market_price_nav_rows: list[dict[str, Any]],
    quarterly_market_rows: list[dict[str, Any]],
    expense_rows: list[dict[str, Any]],
    income_quality_rows: list[dict[str, Any]],
    dividend_declaration_rows: list[dict[str, Any]],
    non_accrual_issuer_rows: list[dict[str, Any]],
    non_accrual_summary_rows: list[dict[str, Any]],
    issuer_watchlist_rows: list[dict[str, Any]],
    created_at: str,
) -> None:
    periods = sorted({row["period_end"] for row in rows})
    latest_period = periods[-1] if periods else None
    price_dates = sorted({row["price_date"] for row in market_price_nav_rows})
    latest_price_date = price_dates[-1] if price_dates else None
    normalized_rows = []
    for row in sorted(rows, key=lambda item: (item["period_end"], item["fund"])):
        item = {key: value for key, value in row.items() if key != "source_notes_json"}
        item["source_notes"] = json.loads(row.get("source_notes_json") or "[]")
        normalized_rows.append(item)
    normalized_market_rows = sorted(market_price_nav_rows, key=lambda item: (item["price_date"], item["fund"]))
    normalized_quarterly_market_rows = []
    for row in sorted(quarterly_market_rows, key=lambda item: (item["period_end"], item["fund"])):
        item = {key: value for key, value in row.items() if key != "source_notes_json"}
        item["source_notes"] = json.loads(row.get("source_notes_json") or "[]")
        normalized_quarterly_market_rows.append(item)

    payload = {
        "meta": {
            "generated_at_utc": created_at,
            "source_database": str(CENTRAL_DB_PATH.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
            "model_database": str(MODEL_DB_PATH.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
            "market_close_source_csv": MARKET_CLOSE_SOURCE_LABEL,
            "funds": FUNDS,
            "fund_names": FUND_NAMES,
            "periods": periods,
            "latest_period_end": latest_period,
            "price_dates": price_dates,
            "latest_price_date": latest_price_date,
            "scope": "Three core BDCs only: BXSL, FSK, and TSLX.",
        },
        "rows": normalized_rows,
        "latest_rows": [row for row in normalized_rows if row["period_end"] == latest_period],
        "nav_per_share_marks": PRESENTATION_NAV_MARKS,
        "quarterly_income_expense_facts": expense_rows,
        "quarterly_income_quality_facts": sorted(
            income_quality_rows,
            key=lambda item: (item["period_end"], item["fund"]),
        ),
        "dividend_declaration_facts": sorted(
            dividend_declaration_rows,
            key=lambda item: (item["record_date"], item["fund"], item["dividend_type"]),
        ),
        "non_accrual_summary_facts": non_accrual_summary_rows,
        "non_accrual_issuer_facts": sorted(
            non_accrual_issuer_rows,
            key=lambda item: (item["period_end"], item["fund"], item["issuer_name"]),
        ),
        "issuer_watchlist_facts": sorted(
            issuer_watchlist_rows,
            key=lambda item: (
                item["period_end"],
                item["watchlist_severity"],
                item["fund"],
                -(item["fair_value_mm"] or 0),
                item["issuer_name"],
            ),
        ),
        "quarterly_market_facts": normalized_quarterly_market_rows,
        "market_price_nav_rows": normalized_market_rows,
        "latest_market_price_nav_rows": [row for row in normalized_market_rows if row["price_date"] == latest_price_date],
        "limitations": [
            "BXSL, FSK, and TSLX filing-level income/expense and non-accrual issuer facts are backfilled from Q1 2025 through Q1 2026.",
            "Q4 2025 income/expense facts are derived from each fund's 2025 Form 10-K less the Q3 2025 year-to-date 10-Q amounts.",
            "TSLX Q2 2025 issuer-level non-accrual rows are manually extracted from the Q2 2025 Form 10-Q schedule because the centralized holdings database does not yet include TSLX 2025-06-30 holdings.",
            "Daily price/NAV rows carry forward the latest available reported NAV/share mark on or before each close-price date; they do not re-mark the portfolio daily.",
            "Issuer watchlist rows use FV/cost across all funds and FV/principal only where principal amount is parsed; BXSL principal coverage remains limited in the current central database.",
            "Issuer watchlist instrument context is derived from as-filed category/type/description labels and should not be read as a standalone recovery or legal-seniority conclusion.",
            "Holdings-derived screeners are useful for direction, but PIK income detail and internal risk-rating migration still need filing-grade tables.",
            "Investment activity fields are backfilled from sourced BXSL, FSK, and TSLX presentation activity tables from Q1 2025 through Q1 2026.",
            "The income-quality bridge is populated for BXSL, FSK, and TSLX from Q1 2025 through Q1 2026 where supplied presentations disclose the needed bridge inputs.",
            "FSK supplements disclose distribution amounts but not declaration, record, or payment dates; FSK rows are therefore not added to dividend_declaration_facts.",
            "No BXSL, FSK, or TSLX taxable-income, spillover-income, or undistributed taxable-income table was found in the supplied Q1 2025 through Q1 2026 earnings presentations or supplements.",
            "Reported presentation totals and gross schedule totals can differ by scope. Both are retained instead of forcing a false reconciliation.",
        ],
    }
    JSON_OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_readme(
    rows: list[dict[str, Any]],
    market_price_nav_rows: list[dict[str, Any]],
    quarterly_market_rows: list[dict[str, Any]],
    expense_rows: list[dict[str, Any]],
    income_quality_rows: list[dict[str, Any]],
    dividend_declaration_rows: list[dict[str, Any]],
    non_accrual_summary_rows: list[dict[str, Any]],
    issuer_watchlist_rows: list[dict[str, Any]],
    created_at: str,
) -> None:
    def money_mm(value: float | int | None) -> str:
        if value is None:
            return "n/a"
        sign = "-" if float(value) < 0 else ""
        return f"{sign}${abs(float(value)):.1f}mm"

    latest = [row for row in rows if row["period_end"] == "2026-03-31"]
    latest_price_date = max((row["price_date"] for row in market_price_nav_rows), default=None)
    latest_market_rows = [row for row in market_price_nav_rows if row["price_date"] == latest_price_date]
    latest_quarterly_market_period = max((row["period_end"] for row in quarterly_market_rows), default=None)
    latest_quarterly_market_rows = [
        row for row in quarterly_market_rows if row["period_end"] == latest_quarterly_market_period
    ]
    latest_watchlist_rows = [
        row for row in issuer_watchlist_rows if row["period_end"] == "2026-03-31"
    ]
    lines = [
        "# Three-Fund Institutional BDC Model",
        "",
        "This is the first institutional facts layer for the three-fund dashboard scope.",
        "",
        "## Scope",
        "",
        "- BXSL",
        "- FSK",
        "- TSLX",
        "",
        "## Artifacts",
        "",
        f"- Database: `{MODEL_DB_PATH.relative_to(WORKSPACE_ROOT).as_posix()}`",
        f"- Dashboard JSON: `{JSON_OUTPUT_PATH.relative_to(WORKSPACE_ROOT).as_posix()}`",
        f"- Builder: `{Path(__file__).relative_to(WORKSPACE_ROOT).as_posix()}`",
        f"- Built at UTC: `{created_at}`",
        "",
        "## Tables",
        "",
        "- `quarterly_bdc_facts`: one row per fund and quarter, with holdings-derived screeners and sourced financial facts where available.",
        "- `nav_per_share_marks`: sourced presentation NAV/share marks by fund and quarter.",
        "- `quarterly_income_expense_facts`: filing-sourced operating income, fee, expense, tax, and waiver line items.",
        "- `quarterly_income_quality_facts`: presentation-and-filing bridge from reported NII to conservative cash-like recurring NII.",
        "- `dividend_declaration_facts`: sourced base and supplemental dividend declaration rows from presentation dividend disclosures.",
        "- `non_accrual_summary_facts`: non-accrual issuer counts, dollar amounts, and reported percentages.",
        "- `non_accrual_issuer_facts`: non-accrual issuer-level cost and fair value.",
        "- `issuer_watchlist_facts`: issuer-level below-97, below-90, below-80, non-accrual, and quarter-over-quarter mark migration flags.",
        "- `quarterly_market_facts`: quarter-end and average close-price facts paired with sourced NAV/share marks.",
        "- `market_price_nav_history`: one row per fund and close-price date, with the latest available NAV/share mark carried forward for price/NAV analysis.",
        "- `latest_quarterly_bdc_facts`: latest-quarter convenience view.",
        "- `latest_market_price_nav`: latest close-price date convenience view.",
        "",
        "## Latest Seed Facts",
        "",
        "| Fund | NAV/share | NII/share | Base dividend | Non-accrual FV | PIK income | Liquidity |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(latest, key=lambda item: item["fund"]):
        lines.append(
            "| {fund} | {nav} | {nii} | {dividend} | {non_accrual} | {pik} | {liquidity} |".format(
                fund=row["fund"],
                nav=f"${row['nav_per_share']:.2f}" if row.get("nav_per_share") is not None else "n/a",
                nii=f"${row['nii_per_share']:.2f}" if row.get("nii_per_share") is not None else "n/a",
                dividend=(
                    f"${row['base_dividend_per_share']:.2f}" if row.get("base_dividend_per_share") is not None else "n/a"
                ),
                non_accrual=f"{row['non_accrual_fv_pct']:.1f}%" if row.get("non_accrual_fv_pct") is not None else "n/a",
                pik=f"${row['pik_income_mm']:.1f}mm" if row.get("pik_income_mm") is not None else "n/a",
                liquidity=f"${row['liquidity_mm']:.1f}mm" if row.get("liquidity_mm") is not None else "n/a",
            )
        )
    activity_rows = [
        row
        for row in rows
        if any(
            row.get(column) is not None
            for column in [
                "new_commitments_mm",
                "fundings_mm",
                "repayments_sales_mm",
                "net_investment_activity_mm",
            ]
        )
    ]
    if activity_rows:
        lines.extend(
            [
                "",
                "## Investment Activity Backfill",
                "",
                "Presentation labels are preserved by fund: FSK's New column is Investment Purchases; BXSL and TSLX disclose both commitments and fundings.",
                "",
                "| Fund / period | New | Funded | Repaid / sold | Net | New yield | Repayment yield |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in sorted(activity_rows, key=lambda item: (item["fund"], item["period_end"])):
            lines.append(
                "| {fund} {period} | {new} | {funded} | {repaid} | {net} | {new_yield} | {repay_yield} |".format(
                    fund=row["fund"],
                    period=row["period_end"],
                    new=money_mm(row.get("new_commitments_mm")),
                    funded=money_mm(row.get("fundings_mm")),
                    repaid=money_mm(row.get("repayments_sales_mm")),
                    net=money_mm(row.get("net_investment_activity_mm")),
                    new_yield=f"{row['new_investment_yield_pct']:.1f}%" if row.get("new_investment_yield_pct") is not None else "n/a",
                    repay_yield=f"{row['repayment_yield_pct']:.1f}%" if row.get("repayment_yield_pct") is not None else "n/a",
                )
            )
    if expense_rows:
        lines.extend(
            [
                "",
                "## Filing Income And Expense Facts",
                "",
                "| Fund / period | Total investment income | Base mgmt fee | Income incentive fee | G&A | Fee waivers | NII |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in sorted(expense_rows, key=lambda item: (item["fund"], item["period_end"])):
            lines.append(
                "| {fund} {period} | {tii} | {mgmt} | {incentive} | {ga} | {waiver} | {nii} |".format(
                    fund=row["fund"],
                    period=row["period_end"],
                    tii=f"${row['total_investment_income_mm']:.1f}mm" if row.get("total_investment_income_mm") is not None else "n/a",
                    mgmt=f"${row['base_management_fee_mm']:.1f}mm" if row.get("base_management_fee_mm") is not None else "n/a",
                    incentive=f"${row['income_incentive_fee_mm']:.1f}mm" if row.get("income_incentive_fee_mm") is not None else "n/a",
                    ga=f"${row['total_g_and_a_mm']:.1f}mm" if row.get("total_g_and_a_mm") is not None else "n/a",
                    waiver=f"${row['fee_waivers_mm']:.1f}mm" if row.get("fee_waivers_mm") is not None else "n/a",
                    nii=f"${row['nii_mm']:.1f}mm" if row.get("nii_mm") is not None else "n/a",
                )
            )
    if income_quality_rows:
        lines.extend(
            [
                "",
                "## Income Quality Bridge",
                "",
                "Cash-like recurring NII is a conservative derived estimate: reported NII less PIK interest, investment other fees, other income, and management fee waiver benefit.",
                "",
                "| Fund / period | Reported NII | Reported NII/share | Cash NII ex-PIK/share | Cash-like recurring NII/share | PIK / TII | PIK / NII | Other fees | Fee waivers | Base coverage | Record-date total coverage |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in sorted(income_quality_rows, key=lambda item: (item["fund"], item["period_end"])):
            lines.append(
                "| {fund} {period} | {nii} | {nii_ps} | {cash_ps} | {recurring_ps} | {pik_tii_pct} | {pik_nii_pct} | {fees} | {waivers} | {base_cov} | {total_cov} |".format(
                    fund=row["fund"],
                    period=row["period_end"],
                    nii=f"${row['reported_nii_mm']:.1f}mm" if row.get("reported_nii_mm") is not None else "n/a",
                    nii_ps=f"${row['reported_nii_per_share']:.2f}" if row.get("reported_nii_per_share") is not None else "n/a",
                    cash_ps=f"${row['cash_nii_ex_pik_per_share']:.2f}" if row.get("cash_nii_ex_pik_per_share") is not None else "n/a",
                    recurring_ps=f"${row['cash_like_recurring_nii_per_share']:.2f}" if row.get("cash_like_recurring_nii_per_share") is not None else "n/a",
                    pik_tii_pct=f"{row['pik_income_tii_pct']:.1f}%" if row.get("pik_income_tii_pct") is not None else "n/a",
                    pik_nii_pct=f"{row['pik_income_nii_pct']:.1f}%" if row.get("pik_income_nii_pct") is not None else "n/a",
                    fees=f"${row['interest_from_investments_other_fees_mm']:.1f}mm" if row.get("interest_from_investments_other_fees_mm") is not None else "n/a",
                    waivers=f"${row['fee_waivers_mm']:.1f}mm" if row.get("fee_waivers_mm") is not None else "n/a",
                    base_cov=f"{row['reported_base_dividend_coverage_pct']:.1f}%" if row.get("reported_base_dividend_coverage_pct") is not None else "n/a",
                    total_cov=f"{row['reported_record_date_distribution_coverage_pct']:.1f}%" if row.get("reported_record_date_distribution_coverage_pct") is not None else "n/a",
                )
            )
    if dividend_declaration_rows:
        lines.extend(
            [
                "",
                "## Dividend Declarations",
                "",
                "| Fund | Declared | Record | Payment | Type | Related period | Amount/share |",
                "|---|---:|---:|---:|---|---:|---:|",
            ]
        )
        for row in sorted(dividend_declaration_rows, key=lambda item: (item["record_date"], item["dividend_type"])):
            lines.append(
                "| {fund} | {declared} | {record} | {payment} | {kind} | {related} | {amount} |".format(
                    fund=row["fund"],
                    declared=row["declared_date"],
                    record=row["record_date"],
                    payment=row["payment_date"],
                    kind=row["dividend_type"],
                    related=row["related_period_end"] or "n/a",
                    amount=f"${row['amount_per_share']:.2f}",
                )
            )
    if non_accrual_summary_rows:
        lines.extend(
            [
                "",
                "## Non-Accrual Summary",
                "",
                "| Fund / period | Issuers | Securities | Cost | Fair value | Reported FV % |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for row in sorted(non_accrual_summary_rows, key=lambda item: (item["fund"], item["period_end"])):
            lines.append(
                "| {fund} {period} | {issuers} | {securities} | {cost} | {fv} | {fv_pct} |".format(
                    fund=row["fund"],
                    period=row["period_end"],
                    issuers=row["issuer_count"],
                    securities=row["security_count"],
                    cost=f"${row['amortized_cost_mm']:.1f}mm",
                    fv=f"${row['fair_value_mm']:.1f}mm",
                    fv_pct=f"{row['reported_non_accrual_fv_pct']:.1f}%" if row.get("reported_non_accrual_fv_pct") is not None else "n/a",
                )
            )
    if latest_market_rows:
        lines.extend(
            [
                "",
                "## Latest Price/NAV Carry-Forward",
                "",
                "Daily close prices use the latest available reported NAV/share mark on or before the close date.",
                "",
                "| Fund | Close date | Close price | NAV/share used | NAV mark date | Price/NAV | Premium/(discount) |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in sorted(latest_market_rows, key=lambda item: item["fund"]):
            lines.append(
                "| {fund} | {price_date} | {close_price} | {nav} | {nav_period} | {price_nav} | {discount} |".format(
                    fund=row["fund"],
                    price_date=row["price_date"],
                    close_price=f"${row['close_price']:.2f}",
                    nav=f"${row['nav_per_share']:.2f}",
                    nav_period=row["nav_period_end"],
                    price_nav=f"{row['price_to_nav_pct']:.1f}%",
                    discount=f"{row['premium_discount_to_nav_pct']:.1f}%",
                )
            )
    if latest_watchlist_rows:
        lines.extend(
            [
                "",
                "## Latest Issuer Watchlist",
                "",
                "Watchlist flags use FV/cost across all funds and FV/principal where principal is parsed. Instrument context summarizes as-filed category/type/description labels so direct loan marks can be separated from ABF, structured, and equity-like marks.",
                "",
                "| Fund | Issuer | Instrument context | Bucket | Fair value | FV/cost | FV/principal | QoQ FV/cost change |",
                "|---|---|---|---|---:|---:|---:|---:|",
            ]
        )
        for row in sorted(
            latest_watchlist_rows,
            key=lambda item: (
                item["watchlist_severity"],
                item["fund"],
                -(item["fair_value_mm"] or 0),
                item["issuer_name"],
            ),
        )[:25]:
            lines.append(
                "| {fund} | {issuer} | {context} | {bucket} | {fv} | {fv_cost} | {fv_principal} | {qoq} |".format(
                    fund=row["fund"],
                    issuer=row["issuer_name"],
                    context=row.get("instrument_context") or "n/a",
                    bucket=row["watchlist_bucket"],
                    fv=f"${row['fair_value_mm']:.1f}mm" if row.get("fair_value_mm") is not None else "n/a",
                    fv_cost=f"{row['fv_to_cost_pct']:.1f}%" if row.get("fv_to_cost_pct") is not None else "n/a",
                    fv_principal=f"{row['fv_to_principal_pct']:.1f}%" if row.get("fv_to_principal_pct") is not None else "n/a",
                    qoq=f"{row['qoq_fv_to_cost_change_pct']:.1f} pp" if row.get("qoq_fv_to_cost_change_pct") is not None else "n/a",
                )
            )
    if latest_quarterly_market_rows:
        lines.extend(
            [
                "",
                "## Latest Quarterly Market Facts",
                "",
                "Quarterly market facts pair public close prices with the sourced NAV/share mark for the same quarter end.",
                "",
                "| Fund | Period | QE close date | QE close | Average close | NAV/share | QE Price/NAV | Avg Price/NAV |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in sorted(latest_quarterly_market_rows, key=lambda item: item["fund"]):
            lines.append(
                "| {fund} | {period} | {price_date} | {close_price} | {avg_close} | {nav} | {price_nav} | {avg_price_nav} |".format(
                    fund=row["fund"],
                    period=row["period_end"],
                    price_date=row["quarter_end_price_date"],
                    close_price=f"${row['quarter_end_close_price']:.2f}",
                    avg_close=f"${row['avg_daily_close_price']:.2f}",
                    nav=f"${row['nav_per_share']:.2f}",
                    price_nav=f"{row['quarter_end_price_to_nav_pct']:.1f}%",
                    avg_price_nav=f"{row['avg_price_to_nav_pct']:.1f}%",
                )
            )
    lines.extend(
        [
            "",
            "## Caveats",
            "",
            "- BXSL, FSK, and TSLX now have filing-level income/expense and non-accrual issuer facts from Q1 2025 through Q1 2026.",
            "- TSLX Q2 2025 issuer-level non-accrual rows are manually extracted from the Q2 2025 Form 10-Q schedule because the centralized holdings database does not yet include TSLX 2025-06-30 holdings.",
            "- Issuer watchlist rows use FV/cost across all funds and FV/principal only where principal amount is parsed; BXSL principal coverage remains limited in the current central database.",
            "- Issuer watchlist instrument context is derived from as-filed category/type/description labels and should not be read as a standalone recovery or legal-seniority conclusion.",
            "- NAV/share marks currently come from the Q1 2026 presentation tables for 2025 Q1 through 2026 Q1.",
            "- Investment activity fields are backfilled from sourced BXSL, FSK, and TSLX presentation activity tables from Q1 2025 through Q1 2026.",
            "- The income-quality bridge is populated for BXSL, FSK, and TSLX from Q1 2025 through Q1 2026 where supplied presentations disclose the needed bridge inputs.",
            "- FSK supplements disclose distribution amounts but not declaration, record, or payment dates; FSK rows are therefore not added to dividend_declaration_facts.",
            "- No BXSL, FSK, or TSLX taxable-income, spillover-income, or undistributed taxable-income table was found in the supplied Q1 2025 through Q1 2026 earnings presentations or supplements.",
            "- Price/NAV history begins when the first sourced NAV/share mark is available in the model.",
            "- Q1 2026 high-level presentation facts are still seeded from reviewed local decks; the investment activity fields now carry page-level source notes.",
            "- The dashboard keeps reported presentation fair value separate from gross holdings schedule fair value where the two do not foot by definition.",
            "",
        ]
    )
    MODEL_README_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if not CENTRAL_DB_PATH.exists():
        raise FileNotFoundError(f"Centralized holdings database not found: {CENTRAL_DB_PATH}")

    created_at = utc_now()
    with connect_central() as con:
        rows = build_holdings_rows(con, created_at)
        non_accrual_issuer_rows = build_non_accrual_issuer_rows(con, created_at)
        issuer_watchlist_rows = build_issuer_watchlist_rows(con, non_accrual_issuer_rows, created_at)
    overlay_q1_presentation_seed(rows, created_at)
    overlay_investment_activity_facts(rows, created_at)
    overlay_presentation_nav_marks(rows, created_at)
    expense_rows = build_filing_income_expense_rows(created_at)
    overlay_10q_expense_facts(rows, expense_rows)
    income_quality_rows = build_income_quality_rows(expense_rows, created_at)
    dividend_declaration_rows = build_dividend_declaration_rows(created_at)
    overlay_income_quality_facts(rows, income_quality_rows)
    non_accrual_summary_rows = build_non_accrual_summary_rows(non_accrual_issuer_rows, created_at)
    overlay_non_accrual_summary_facts(rows, non_accrual_summary_rows)
    market_price_nav_rows = build_market_price_nav_rows(rows, created_at)
    quarterly_market_rows = build_quarterly_market_rows(rows, created_at)
    create_model_db(
        rows,
        market_price_nav_rows,
        quarterly_market_rows,
        expense_rows,
        income_quality_rows,
        dividend_declaration_rows,
        non_accrual_issuer_rows,
        non_accrual_summary_rows,
        issuer_watchlist_rows,
        created_at,
    )
    export_json(
        rows,
        market_price_nav_rows,
        quarterly_market_rows,
        expense_rows,
        income_quality_rows,
        dividend_declaration_rows,
        non_accrual_issuer_rows,
        non_accrual_summary_rows,
        issuer_watchlist_rows,
        created_at,
    )
    write_readme(
        rows,
        market_price_nav_rows,
        quarterly_market_rows,
        expense_rows,
        income_quality_rows,
        dividend_declaration_rows,
        non_accrual_summary_rows,
        issuer_watchlist_rows,
        created_at,
    )

    print(f"Wrote {len(rows)} quarterly_bdc_facts rows")
    print(f"Wrote {len(market_price_nav_rows)} market_price_nav_history rows")
    print(f"Wrote {len(quarterly_market_rows)} quarterly_market_facts rows")
    print(f"Wrote {len(expense_rows)} quarterly_income_expense_facts rows")
    print(f"Wrote {len(income_quality_rows)} quarterly_income_quality_facts rows")
    print(f"Wrote {len(dividend_declaration_rows)} dividend_declaration_facts rows")
    print(f"Wrote {len(non_accrual_issuer_rows)} non_accrual_issuer_facts rows")
    print(f"Wrote {len(issuer_watchlist_rows)} issuer_watchlist_facts rows")
    print(f"Database: {MODEL_DB_PATH}")
    print(f"Dashboard JSON: {JSON_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
