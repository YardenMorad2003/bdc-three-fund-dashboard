"use client";

import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowDownRight,
  ArrowUp,
  ArrowUpRight,
  ArrowUpDown,
  BarChart3,
  Calendar,
  CheckCircle2,
  Database,
  ExternalLink,
  FileSearch,
  Gauge,
  History,
  Info,
  Layers3,
  LineChart,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Table2,
  TrendingUp,
  WalletCards
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useMemo, useState } from "react";
import dashboardData from "../lib/dashboard-data.json";
import bdcUniverseData from "../lib/bdc-universe.json";
import companyEnrichmentData from "../lib/company-enrichment.json";
import fundingMarketData from "../lib/bdc-funding-market.json";
import liabilityStackData from "../lib/liability-stack.json";
import quarterlyFactsData from "../lib/quarterly-bdc-facts.json";
import researchSignalsData from "../lib/research-signals.json";
import trancheComparisonData from "../lib/tranche-comparison.json";

type Fund =
  | "ARCC"
  | "BBDC"
  | "BCSF"
  | "BXSL"
  | "CCAP"
  | "CSWC"
  | "FSK"
  | "GBDC"
  | "HTGC"
  | "MAIN"
  | "NMFC"
  | "OBDC"
  | "OCSL"
  | "PSEC"
  | "TCPC"
  | "TSLX";
type Tab = "overview" | "financials" | "deterioration" | "exposure" | "timeline" | "holdings" | "liabilities" | "universe" | "quality";
type WatchlistBucketFilter = "All" | "Non-accrual" | "Shadow below 90" | "Watch 90-97" | "QoQ deterioration";
type SortDirection = "asc" | "desc";
type HoldingsSortKey = "amortized_cost_mm" | "fair_value_mm" | "mark_vs_cost_mm" | "fv_to_cost";
type MarkComparisonMode = "facility" | "company" | "structure";
type SignalFilter = "all" | "review" | "discount" | "deterioration" | "disagreement" | "crowding" | "structure";
type DeteriorationExposureFilter = "All" | "Debt" | "Equity / ABF" | "Mixed / Other";
type DeteriorationInstrumentBucket = "Debt" | "Equity / ABF" | "Mixed / Other";

type PeriodPoint = {
  filing_period_end: string;
  coverage_count: number;
  total_fair_value_mm: number;
} & Partial<Record<Fund, number | null>>;

type FundPeriod = {
  fund: Fund;
  filing_period_end: string;
  report_type?: string;
  holding_rows: number;
  amortized_cost_mm: number;
  fair_value_mm: number;
  mark_vs_cost_mm: number;
};

type FundTotal = {
  fund: Fund;
  holding_rows: number;
  periods: number;
  amortized_cost_mm: number;
  fair_value_mm: number;
  mark_vs_cost_mm: number;
};

type ChangeByFund = {
  fund: Fund;
  current_period: string;
  prior_period: string | null;
  current_fair_value_mm: number;
  prior_fair_value_mm: number | null;
  change_mm: number | null;
  change_pct: number | null;
  holding_rows: number;
};

type ExposureRow = {
  fund: Fund;
  investment_category?: string;
  issuer_name?: string;
  holding_rows: number;
  fair_value_mm: number;
  amortized_cost_mm?: number;
};

type CrossFundIssuer = {
  issuer_match_key: string;
  representative_issuer_name: string;
  funds: Fund[];
  fund_count: number;
  holding_rows: number;
  amortized_cost_mm: number;
  fair_value_mm: number;
  issuer_name_variants: string[];
  fund_breakdown: Array<{
    fund: Fund;
    holding_rows: number;
    amortized_cost_mm: number;
    fair_value_mm: number;
    issuer_names: string[];
  }>;
};

type HoldingRow = {
  fund: Fund;
  issuer_name: string | null;
  issuer_match_key: string | null;
  industry: string | null;
  investment_category: string | null;
  instrument_type: string | null;
  investment_description: string | null;
  rate_raw: string | null;
  reference_base_rate: string | null;
  spread_pct: number | null;
  fixed_coupon_pct: number | null;
  pik_rate_pct: number | null;
  maturity_date: string | null;
  amount_kind: string | null;
  amount_currency: string | null;
  amount_value: number | null;
  principal_mm: number | null;
  shares_units: number | null;
  exposure_type: string | null;
  is_unfunded_commitment: number | boolean | null;
  amortized_cost_mm: number;
  fair_value_mm: number;
  mark_vs_cost_mm: number;
  pct_net_assets: number | null;
  rate_type: string;
  maturity_bucket: string;
};

type FacilityGapRow = {
  issuer_match_key: string;
  period_end: string;
  fund_pair: string;
  fund_a: Fund;
  fund_b: Fund;
  facility_match_confidence: "high" | "medium";
  fund_a_principal_mm: number;
  fund_a_fair_value_mm: number;
  fund_a_fv_to_principal_pct: number;
  fund_b_principal_mm: number;
  fund_b_fair_value_mm: number;
  fund_b_fv_to_principal_pct: number;
  fund_a_minus_fund_b_gap_pp: number;
  inter_fund_gap_pp: number;
  conservative_fund: Fund | "Tie";
  maturity_month: string | null;
  reference_base_rate: string | null;
  spread_pct_a: number | null;
  spread_pct_b: number | null;
  fixed_coupon_pct_a: number | null;
  fixed_coupon_pct_b: number | null;
  currency: string;
};

type CompanyGapRow = {
  issuer_match_key: string;
  period_end: string;
  fund_pair: string;
  funds: string;
  comparable_facility_pair_count: number;
  abstention_count: number;
  fund_a: Fund;
  fund_b: Fund;
  fund_a_matched_principal_mm: number;
  fund_a_matched_fair_value_mm: number;
  fund_a_fv_to_principal_pct: number;
  fund_b_matched_principal_mm: number;
  fund_b_matched_fair_value_mm: number;
  fund_b_fv_to_principal_pct: number;
  fund_a_minus_fund_b_gap_pp: number;
  inter_fund_gap_pp: number;
  conservative_fund: Fund | "Tie";
  non_comparable_reasons: string | null;
};

type DifferentTrancheGapRow = {
  issuer_match_key: string;
  period_end: string;
  comparison_scope: "cross-fund" | "within-fund";
  fund_a: Fund;
  fund_b: Fund;
  fund_pair: string;
  fund_a_group_id: string;
  fund_b_group_id: string;
  fund_a_lien_tier: string;
  fund_b_lien_tier: string;
  fund_a_facility_type: string;
  fund_b_facility_type: string;
  fund_a_maturity_month: string;
  fund_b_maturity_month: string;
  fund_a_reference_base_rate: string | null;
  fund_b_reference_base_rate: string | null;
  fund_a_spread_pct: number | null;
  fund_b_spread_pct: number | null;
  fund_a_fixed_coupon_pct: number | null;
  fund_b_fixed_coupon_pct: number | null;
  fund_a_principal_mm: number;
  fund_b_principal_mm: number;
  fund_a_fair_value_mm: number;
  fund_b_fair_value_mm: number;
  fund_a_fv_to_principal_pct: number;
  fund_b_fv_to_principal_pct: number;
  inter_tranche_gap_pp: number;
  lower_mark_fund: Fund | "Tie";
  structural_differences: string[];
};

type CapitalStructurePairRow = {
  issuer_match_key: string;
  comparison_scope: "cross-fund" | "within-fund";
  junior_fund: Fund;
  senior_fund: Fund;
  junior_tier: string;
  senior_tier: string;
  junior_holding_rows: number;
  senior_holding_rows: number;
  junior_amortized_cost_mm: number;
  junior_fair_value_mm: number;
  junior_fv_to_cost_pct: number;
  senior_amortized_cost_mm: number;
  senior_fair_value_mm: number;
  senior_fv_to_cost_pct: number;
  senior_minus_junior_gap_pp: number;
  absolute_gap_pp: number;
  waterfall_status: "expected_waterfall" | "inversion" | "flat";
  junior_instrument_labels: string[];
  senior_instrument_labels: string[];
};

type CapitalStructureTimelineRow = {
  issuer_match_key: string;
  filing_period_end: string;
  tier: string;
  tier_rank: number;
  amortized_cost_mm: number;
  fair_value_mm: number;
  holding_rows: number;
  funds: Fund[];
  fv_to_cost_pct: number;
};

type LeadLagSummaryRow = {
  issuer_match_key: string;
  junior_tier: string;
  senior_tier: string;
  common_period_count: number;
  first_common_period: string;
  latest_common_period: string;
  junior_first_below_95_period: string | null;
  senior_first_below_95_period: string | null;
  junior_first_below_90_period: string | null;
  senior_first_below_90_period: string | null;
  lead_lag_status: "junior_first" | "simultaneous" | "senior_first" | "no_breach";
  lead_quarters_at_95: number | null;
  latest_junior_fv_to_cost_pct: number;
  latest_senior_fv_to_cost_pct: number;
  latest_senior_minus_junior_gap_pp: number;
  minimum_junior_fv_to_cost_pct: number;
  minimum_senior_fv_to_cost_pct: number;
  periods: string[];
};

type SignalTag =
  | "deep_discount"
  | "below_cost"
  | "rapid_deterioration"
  | "emerging_deterioration"
  | "audited_disagreement"
  | "crowded"
  | "senior_first"
  | "junior_first"
  | "stable_context";

type IssuerResearchSignal = {
  issuer_match_key: string;
  display_name: string;
  mapped_company: string;
  funds: Fund[];
  fund_count: number;
  fair_value_mm: number;
  amortized_cost_mm: number;
  latest_fv_to_cost_pct: number | null;
  prior_period: string | null;
  prior_fv_to_cost_pct: number | null;
  qoq_change_pp: number | null;
  portfolio_mark_spread_pp: number | null;
  audited_same_facility_gap_pp: number | null;
  audited_fund_pair: string | null;
  audited_conservative_fund: Fund | "Tie" | null;
  pairwise_lead_lag_tests: number;
  senior_first_pair_count: number;
  junior_first_pair_count: number;
  priority_score: number;
  priority_band: "review" | "watch" | "monitor" | "context";
  priority_rank: number;
  score_components: Record<string, number>;
  signal_tags: SignalTag[];
};

type FundPairLeadLagRow = LeadLagSummaryRow & {
  comparison_scope: "cross-fund" | "within-fund";
  junior_fund: Fund;
  senior_fund: Fund;
};

type ResearchSignalsData = {
  meta: {
    generated_at_utc: string;
    latest_period: string;
    methodology: string;
    pairwise_lead_lag_methodology: string;
    signal_count: number;
    review_count: number;
    watch_count: number;
    monitor_count: number;
    deep_discount_count: number;
    rapid_deterioration_count: number;
    audited_disagreement_count: number;
    crowded_count: number;
    pairwise_lead_lag_count: number;
    cross_fund_pairwise_count: number;
    junior_first_pair_count: number;
    senior_first_pair_count: number;
  };
  signal_definitions: Record<SignalTag, { label: string; description: string }>;
  issuer_signals: IssuerResearchSignal[];
  fund_pair_lead_lag: FundPairLeadLagRow[];
  headline_insights: {
    largest_material_decline: IssuerResearchSignal | null;
    largest_material_discount: IssuerResearchSignal | null;
    widest_audited_gap: IssuerResearchSignal | null;
    most_crowded: IssuerResearchSignal | null;
  };
};

type TrancheComparisonData = {
  meta: {
    generated_at_utc: string;
    latest_period: string;
    candidate_count: number;
    par_covered_candidate_count: number;
    comparable_candidate_count: number;
    abstained_candidate_count: number;
    comparable_facility_pair_count: number;
    different_tranche_pair_count: number;
    different_tranche_company_count: number;
    material_principal_floor_mm: number;
    capital_structure_pair_count: number;
    capital_structure_company_count: number;
    expected_waterfall_count: number;
    capital_structure_inversion_count: number;
    capital_structure_flat_count: number;
    material_tier_cost_floor_mm: number;
    lead_lag_summary_count: number;
    lead_lag_company_count: number;
    junior_first_count: number;
    simultaneous_count: number;
    senior_first_count: number;
    no_breach_count: number;
    spread_tolerance_bps: number;
    methodology: string;
    different_tranche_methodology: string;
    capital_structure_methodology: string;
    lead_lag_methodology: string;
  };
  facility_gaps: FacilityGapRow[];
  company_gaps: CompanyGapRow[];
  different_tranche_gaps: DifferentTrancheGapRow[];
  capital_structure_pairs: CapitalStructurePairRow[];
  capital_structure_timeline: CapitalStructureTimelineRow[];
  lead_lag_summary: LeadLagSummaryRow[];
  persistence: Array<{
    issuer_match_key: string;
    fund_pair: string;
    comparable_period_count: number;
    latest_period_status: string;
    latest_inter_fund_gap_pp: number | null;
    latest_conservative_fund: Fund | "Tie" | null;
    avg_abs_gap_pp: number | null;
    max_abs_gap_pp: number | null;
    persistent_conservative_fund: Fund | "Tie" | "Mixed" | null;
    conservative_fund_sequence: string | null;
  }>;
  abstention_reasons: Array<{ reason: string; count: number }>;
};

type LoanTimelineIssuer = {
  issuer_match_key: string;
  display_name: string;
  funds: Fund[];
  first_period: string | null;
  latest_period: string | null;
  period_count: number;
  security_rows: number;
  latest_fair_value_mm: number;
  max_fair_value_mm: number;
};

type LoanTimelinePeriod = {
  issuer_match_key: string;
  fund: Fund;
  filing_period_end: string;
  holding_rows: number;
  amortized_cost_mm: number;
  fair_value_mm: number;
  mark_vs_cost_mm: number;
  principal_mm: number | null;
};

type IssuerPeriodHistoryRow = {
  fund: Fund;
  filing_period_end: string;
  issuer_match_key: string;
  representative_issuer_name: string;
  holding_rows: number;
  amortized_cost_mm: number;
  fair_value_mm: number;
  fv_to_cost_pct: number | null;
};

type LoanTimelineSecurity = {
  issuer_match_key: string;
  fund: Fund;
  filing_period_end: string;
  issuer_name: string | null;
  industry: string | null;
  investment_category: string | null;
  instrument_type: string | null;
  investment_description: string | null;
  maturity_date: string | null;
  rate_raw: string | null;
  amount_kind: string | null;
  amount_currency: string | null;
  amount_value: number | null;
  principal_mm: number | null;
  exposure_type: string | null;
  is_unfunded_commitment: number | boolean | null;
  amortized_cost_mm: number;
  fair_value_mm: number;
  mark_vs_cost_mm: number;
  security_signature: string;
};

type SpreadPeriod = {
  fund: Fund;
  filing_period_end: string;
  holding_rows: number;
  spread_rows: number;
  fair_value_mm: number;
  spread_fair_value_mm: number;
  weighted_avg_spread_bps: number | null;
};

type CompanyEnrichment = {
  issuer_match_key: string;
  display_name: string;
  mapped_company: string;
  description: string;
  current_sponsor: string;
  sponsor_history: Array<{
    date: string;
    event: string;
    source_url: string;
  }>;
  sources: Array<{
    title: string;
    url: string;
  }>;
  confidence: "high" | "medium" | "low";
  notes: string;
};

type LiabilityInstrument = {
  name: string;
  type: string;
  secured: boolean;
  rate_type: string;
  rate_text: string;
  swap_adjusted_rate_text?: string;
  outstanding_principal_mm: number;
  committed_mm?: number;
  available_mm?: number;
  carrying_value_mm?: number;
  fair_value_mm?: number;
  maturity_date: string;
  source_page: number;
  notes?: string;
};

type LiabilityFund = {
  fund: Fund;
  company_name: string;
  source_file: string;
  source_pages: number[];
  asset_coverage_pct: number;
  debt_cost_pct: number;
  debt_cost_label: string;
  total_committed_mm?: number;
  total_outstanding_principal_mm: number;
  total_carrying_value_mm?: number;
  total_available_mm: number;
  notes: string[];
  instruments: LiabilityInstrument[];
};

type LiabilityInstrumentRow = LiabilityInstrument & {
  fund: Fund;
  company_name: string;
  source_file: string;
};

type LiabilityStackData = {
  as_of_date: string;
  currency: string;
  units: string;
  sofr: {
    source_file: string;
    sheet: string;
    debt_date_rate_date: string;
    debt_date_rate_pct: number;
    average_2025_pct: number;
    average_december_2025_pct: number;
    latest_rate_date: string;
    latest_rate_pct: number;
  };
  funds: LiabilityFund[];
};

type TracePoint = { date: string; price: number | null; yield_pct: number | null };
type FundingSeries = {
  series_id: string;
  ticker: Fund;
  company_name: string;
  security_title: string;
  coupon_pct: number;
  maturity_year: number;
  maturity_date: string;
  cusip: string | null;
  issuance_event_count: number;
  gross_issued_mm: number | null;
  first_pricing_date: string;
  latest_pricing_date: string;
  status: "matured" | "outstanding_candidate";
  finra_url: string | null;
  trace_status: "matched" | "matched_no_trades" | "no_cusip" | "query_error";
  last_trade_date: string | null;
  last_price: number | null;
  last_yield_pct: number | null;
  price_change_30d: number | null;
  yield_change_30d_pp: number | null;
  price_change_90d: number | null;
  yield_change_90d_pp: number | null;
  observation_count: number;
  history: TracePoint[];
};
type FundingEvent = {
  event_id: string;
  ticker: Fund;
  pricing_date: string;
  settlement_date: string | null;
  coupon_pct: number;
  maturity_year: number;
  maturity_date: string | null;
  offering_amount_mm: number | null;
  issue_price_pct: number | null;
  offering_yield_pct: number | null;
  treasury_spread_bps: number | null;
  cusip: string | null;
  is_reopening: boolean;
  security_title: string;
  extraction_confidence: "high" | "review";
  source_documents: { form: string; filed_date: string; url: string }[];
};
type FundingFund = {
  ticker: Fund;
  company_name: string;
  cik: number;
  issuance_event_count: number;
  recent_issuance_event_count: number;
  recent_gross_issued_mm: number;
  outstanding_candidate_series_count: number;
  outstanding_candidate_gross_mm: number;
  weighted_coupon_pct: number | null;
  trace_matched_series_count: number;
  trace_last_yield_pct: number | null;
};
type FundingMarketData = {
  meta: {
    generated_at_utc: string;
    sec_start_date: string;
    trace_start_date: string;
    as_of_date: string;
    fund_count: number;
    issuance_event_count: number;
    series_count: number;
    outstanding_candidate_series_count: number;
    cusip_matched_series_count: number;
    trace_matched_series_count: number;
    finra_status: string;
    methodology: string;
  };
  funds: FundingFund[];
  series: FundingSeries[];
  issuance_events: FundingEvent[];
  filing_audit: unknown[];
  sources: { name: string; url: string; role: string }[];
};

type QuarterlyFactRow = {
  fund: Fund;
  period_end: string;
  company_name: string;
  report_type: string | null;
  source_status: string;
  source_title: string | null;
  source_file: string | null;
  holding_rows: number | null;
  holdings_amortized_cost_mm: number | null;
  holdings_fair_value_mm: number | null;
  holdings_mark_vs_cost_mm: number | null;
  holdings_mark_to_cost_pct: number | null;
  holdings_first_lien_pct: number | null;
  holdings_floating_rate_pct: number | null;
  holdings_pik_fair_value_mm: number | null;
  holdings_pik_fair_value_pct: number | null;
  holdings_below_90_fair_value_mm: number | null;
  holdings_below_80_fair_value_mm: number | null;
  holdings_weighted_avg_spread_bps: number | null;
  nav_per_share: number | null;
  nii_mm: number | null;
  nii_per_share: number | null;
  adjusted_nii_mm: number | null;
  adjusted_nii_per_share: number | null;
  base_dividend_per_share: number | null;
  total_dividend_per_share: number | null;
  base_dividend_coverage_pct: number | null;
  total_dividend_coverage_pct: number | null;
  reported_total_investments_fv_mm: number | null;
  total_debt_principal_mm: number | null;
  net_assets_mm: number | null;
  debt_to_equity_x: number | null;
  avg_debt_to_equity_x: number | null;
  net_debt_to_equity_x: number | null;
  liquidity_mm: number | null;
  debt_cost_pct: number | null;
  weighted_avg_yield_pct: number | null;
  weighted_avg_spread_over_base_rate_pct: number | null;
  first_lien_pct: number | null;
  floating_rate_debt_investments_pct: number | null;
  non_accrual_fv_pct: number | null;
  non_accrual_cost_pct: number | null;
  pik_income_mm: number | null;
  fee_income_mm: number | null;
  new_commitments_mm: number | null;
  fundings_mm: number | null;
  repayments_sales_mm: number | null;
  net_investment_activity_mm: number | null;
  new_investment_yield_pct: number | null;
  repayment_yield_pct: number | null;
  created_at_utc: string;
  source_notes: string[];
};

type QuarterlyMarketFactRow = {
  fund: Fund;
  period_end: string;
  quarter_start: string;
  quarter_end: string;
  trading_days: number;
  quarter_end_price_date: string;
  quarter_end_close_price: number;
  avg_daily_close_price: number;
  min_daily_close_price: number;
  max_daily_close_price: number;
  nav_per_share: number;
  nav_period_end: string;
  price_date_to_nav_date_days: number;
  quarter_end_price_to_nav_pct: number;
  quarter_end_premium_discount_to_nav_pct: number;
  avg_price_to_nav_pct: number;
  avg_premium_discount_to_nav_pct: number;
  close_price_source_file: string;
  nav_source_title: string | null;
  nav_source_file: string | null;
  nav_source_page: number | null;
  source_notes: string[];
  created_at_utc: string;
};

type QuarterlyIncomeExpenseFactRow = {
  fund: Fund;
  period_end: string;
  source_title: string;
  source_file: string;
  source_pages_json: string;
  total_investment_income_mm: number | null;
  interest_income_mm: number | null;
  pik_interest_income_mm: number | null;
  fee_income_mm: number | null;
  dividend_income_mm: number | null;
  other_income_mm: number | null;
  interest_expense_mm: number | null;
  base_management_fee_mm: number | null;
  income_incentive_fee_mm: number | null;
  capital_gains_incentive_fee_mm: number | null;
  total_incentive_fee_mm: number | null;
  professional_fees_mm: number | null;
  directors_or_board_fees_mm: number | null;
  administrative_service_expense_mm: number | null;
  accounting_administrative_fees_mm: number | null;
  other_g_and_a_mm: number | null;
  total_g_and_a_mm: number | null;
  fee_waivers_mm: number | null;
  total_operating_expenses_mm: number | null;
  net_expenses_mm: number | null;
  tax_expense_mm: number | null;
  nii_mm: number | null;
  source_notes_json: string;
  created_at_utc: string;
};

type QuarterlyIncomeQualityFactRow = {
  fund: Fund;
  period_end: string;
  source_title: string;
  source_file: string;
  source_pages_json: string;
  total_investment_income_mm: number | null;
  reported_nii_mm: number | null;
  reported_nii_per_share: number | null;
  adjusted_nii_mm: number | null;
  adjusted_nii_per_share: number | null;
  weighted_average_shares: number | null;
  pik_interest_income_mm: number | null;
  pik_income_tii_pct: number | null;
  pik_income_nii_pct: number | null;
  interest_from_investments_other_fees_mm: number | null;
  other_fees_tii_pct: number | null;
  other_income_mm: number | null;
  other_income_tii_pct: number | null;
  fee_waivers_mm: number | null;
  capital_gains_incentive_fee_not_payable_mm: number | null;
  capital_gains_incentive_fee_not_payable_per_share: number | null;
  cash_nii_ex_pik_mm: number | null;
  cash_nii_ex_pik_per_share: number | null;
  cash_like_recurring_nii_mm: number | null;
  cash_like_recurring_nii_per_share: number | null;
  base_dividend_per_share: number | null;
  record_date_distributions_per_share: number | null;
  quarter_related_supplemental_dividend_per_share: number | null;
  quarter_related_total_dividend_per_share: number | null;
  reported_base_dividend_coverage_pct: number | null;
  reported_record_date_distribution_coverage_pct: number | null;
  reported_quarter_related_distribution_coverage_pct: number | null;
  adjusted_base_dividend_coverage_pct: number | null;
  adjusted_record_date_distribution_coverage_pct: number | null;
  cash_like_base_dividend_coverage_pct: number | null;
  cash_like_record_date_distribution_coverage_pct: number | null;
  one_time_items_json: string;
  source_notes_json: string;
  created_at_utc: string;
};

type DividendDeclarationFactRow = {
  fund: Fund;
  declared_date: string;
  record_date: string;
  payment_date: string;
  amount_per_share: number;
  dividend_type: string;
  related_period_end: string | null;
  source_title: string;
  source_file: string;
  source_page: number;
  source_notes_json: string;
  created_at_utc: string;
};

type NonAccrualSummaryFactRow = {
  fund: Fund;
  period_end: string;
  issuer_count: number;
  security_count: number;
  amortized_cost_mm: number;
  fair_value_mm: number;
  reported_non_accrual_cost_pct: number | null;
  reported_non_accrual_fv_pct: number | null;
  reported_non_accrual_cost_mm: number | null;
  reported_non_accrual_fv_mm: number | null;
  source_title: string;
  source_file: string;
  source_pages_json: string;
  source_notes_json: string;
  created_at_utc: string;
};

type NonAccrualIssuerFactRow = {
  fund: Fund;
  period_end: string;
  issuer_name: string;
  security_count: number;
  amortized_cost_mm: number;
  fair_value_mm: number;
  source_title: string;
  source_file: string;
  source_pages_json: string;
  source_method: string;
  source_notes_json: string;
  created_at_utc: string;
};

type IssuerWatchlistFactRow = {
  fund: Fund;
  period_end: string;
  issuer_match_key: string;
  issuer_name: string;
  issuer_industries: string | null;
  instrument_context: string | null;
  instrument_context_detail: string | null;
  security_count: number;
  principal_mm: number | null;
  principal_fair_value_mm: number | null;
  amortized_cost_mm: number | null;
  fair_value_mm: number | null;
  mark_vs_cost_mm: number | null;
  fv_to_cost_pct: number | null;
  fv_to_principal_pct: number | null;
  prior_period_end: string | null;
  prior_fv_to_cost_pct: number | null;
  prior_fv_to_principal_pct: number | null;
  qoq_fv_to_cost_change_pct: number | null;
  qoq_fv_to_principal_change_pct: number | null;
  qoq_fair_value_change_mm: number | null;
  qoq_mark_vs_cost_change_mm: number | null;
  below_97_fv_to_cost: boolean;
  below_90_fv_to_cost: boolean;
  below_80_fv_to_cost: boolean;
  below_97_fv_to_principal: boolean;
  below_90_fv_to_principal: boolean;
  below_80_fv_to_principal: boolean;
  is_non_accrual: boolean;
  shadow_non_accrual: boolean;
  material_qoq_deterioration: boolean;
  watchlist_bucket: string;
  watchlist_severity: number;
  source_title: string;
  source_file: string;
  source_method: string;
  source_notes_json: string;
  created_at_utc: string;
};

type DeteriorationGroup = {
  issuer_match_key: string;
  issuer_name: string;
  funds: Fund[];
  security_count: number;
  amortized_cost_mm: number;
  fair_value_mm: number;
  fv_to_cost_pct: number | null;
  prior_fv_to_cost_pct: number | null;
  qoq_fv_to_cost_change_pct: number | null;
  two_quarter_fv_to_cost_change_pct: number | null;
  three_quarter_fv_to_cost_change_pct: number | null;
  qoq_fair_value_change_mm: number | null;
  qoq_mark_vs_cost_change_mm: number | null;
  down_quarter_count: number;
  material_down_quarter_count: number;
  recent_period_count: number;
  shadow_non_accrual: boolean;
  material_qoq_deterioration: boolean;
  sustained_deterioration: boolean;
  watchlist_buckets: string[];
  shadow_signal_label: string | null;
  instrument_bucket: DeteriorationInstrumentBucket;
  category_label: string;
  instrument_label: string;
  rate_label: string;
  maturity_label: string;
  source_non_accrual_match: boolean;
  score: number;
  severity_label: string;
  trend_label: string;
  reason: string;
};

type DeteriorationTrendMetrics = {
  recent_periods: string[];
  down_quarter_count: number;
  material_down_quarter_count: number;
  two_quarter_fv_to_cost_change_pct: number | null;
  three_quarter_fv_to_cost_change_pct: number | null;
  sustained_deterioration: boolean;
};

type QuarterlyFactsData = {
  meta: {
    generated_at_utc: string;
    source_database: string;
    model_database: string;
    funds: Fund[];
    fund_names: Partial<Record<Fund, string>>;
    periods: string[];
    latest_period_end: string;
    scope: string;
  };
  rows: QuarterlyFactRow[];
  latest_rows: QuarterlyFactRow[];
  quarterly_income_expense_facts: QuarterlyIncomeExpenseFactRow[];
  quarterly_income_quality_facts: QuarterlyIncomeQualityFactRow[];
  dividend_declaration_facts: DividendDeclarationFactRow[];
  non_accrual_summary_facts: NonAccrualSummaryFactRow[];
  non_accrual_issuer_facts: NonAccrualIssuerFactRow[];
  issuer_watchlist_facts: IssuerWatchlistFactRow[];
  quarterly_market_facts: QuarterlyMarketFactRow[];
  limitations: string[];
};

type DashboardData = {
  meta: {
    generated_at_utc: string;
    source_database: string;
    sqlite_integrity: string;
    funds: Fund[];
    fund_names: Record<Fund, string>;
    latest_common_period: string;
    latest_period_label: string;
  };
  narrative: Record<string, string>;
  raw_cross_fund_issuer_count_latest: number;
  cross_fund_issuer_latest: CrossFundIssuer[];
  loan_timeline_issuers: LoanTimelineIssuer[];
  loan_timeline_periods: LoanTimelinePeriod[];
  loan_timeline_securities: LoanTimelineSecurity[];
  issuer_period_history: IssuerPeriodHistoryRow[];
  fund_totals: FundTotal[];
  latest_by_fund: FundPeriod[];
  change_by_fund: ChangeByFund[];
  period_summary: FundPeriod[];
  time_series: PeriodPoint[];
  category_latest: ExposureRow[];
  category_totals_latest: Array<{
    investment_category: string;
    holding_rows: number;
    fair_value_mm: number;
    amortized_cost_mm: number;
  }>;
  top_issuers_latest: ExposureRow[];
  issuer_concentration: Array<{
    fund: Fund;
    top_5_fair_value_mm: number;
    top_5_pct: number | null;
    top_10_fair_value_mm: number;
    top_10_pct: number | null;
  }>;
  holdings_latest: HoldingRow[];
  holdings_detail_latest: HoldingRow[];
  rate_mix_latest: Array<{ fund: Fund; rate_type: string; fair_value_mm: number; rows: number }>;
  maturity_buckets_latest: Array<{ fund: Fund; maturity_bucket: string; fair_value_mm: number; rows: number }>;
  amount_field_summary_latest: Array<{
    fund: Fund;
    amount_kind: string;
    amount_currency: string;
    fair_value_mm: number;
    rows: number;
  }>;
  base_rate_latest: Array<{
    fund: Fund;
    reference_base_rate: string;
    holding_rows: number;
    fair_value_mm: number;
  }>;
  spread_time_series: SpreadPeriod[];
  source_databases: Array<{
    fund: Fund;
    source_db_path: string;
    source_view: string;
    expected_rows: number;
    actual_rows: number;
    integrity_check: string;
    notes: string;
  }>;
  validation_counts: Array<{ status: string; rows: number }>;
  validation_results: Array<{
    check_name: string;
    fund: Fund | null;
    status: string;
    expected: string | null;
    actual: string | null;
    details_json: string;
  }>;
  source_qc_status: Array<{
    fund: Fund;
    source_object: string;
    source_status: string;
    check_rows: number;
  }>;
  limitations: Array<{ title: string; body: string }>;
};

type UniverseCoverageStatus = "verified_holdings" | "bulk_soi_available" | "registry_only";

type BdcUniverseRow = {
  cik: number;
  ticker: Fund | null;
  name: string;
  file_number: string | null;
  city: string | null;
  state: string | null;
  last_filing_date: string | null;
  last_filing_type: string | null;
  is_active: boolean | null;
  edgartools_registry: boolean;
  manual_registry_exception: boolean;
  bulk_period: string | null;
  bulk_soi_fact_rows: number;
  bulk_forms: string[];
  bulk_latest_filed: string | null;
  coverage_status: UniverseCoverageStatus;
  coverage_label: string;
  verified_latest_period: string | null;
  verified_latest_rows: number;
  verified_latest_fair_value_mm: number | null;
  tracker_audit_status: "verified" | "review" | null;
  tracker_audit_forms: Record<string, { status: string; residual_fair_value_pct: number | null }>;
};

type BdcUniverseData = {
  meta: {
    generated_at_utc: string;
    edgartools_version: string;
    registry_entities: number;
    universe_entities: number;
    active_registry_entities: number;
    verified_funds: number;
    expansion_cohort_funds: number;
    expansion_cohort_verified: number;
    expansion_cohort_review: number;
    bulk_period: string;
    bulk_companies: number;
    bulk_soi_entries: number;
    bulk_available_periods_note: string;
  };
  rows: BdcUniverseRow[];
  limitations: string[];
};

const data = dashboardData as unknown as DashboardData;
const bdcUniverse = bdcUniverseData as unknown as BdcUniverseData;
const companyEnrichment = companyEnrichmentData as CompanyEnrichment[];
const fundingMarket = fundingMarketData as unknown as FundingMarketData;
const liabilityStack = liabilityStackData as LiabilityStackData;
const quarterlyFacts = quarterlyFactsData as QuarterlyFactsData;
const researchSignals = researchSignalsData as ResearchSignalsData;
const trancheComparison = trancheComparisonData as TrancheComparisonData;
const funds: Fund[] = ["ARCC", "BBDC", "BXSL", "FSK", "GBDC", "MAIN", "OBDC", "TSLX"];
const institutionalFunds: Fund[] = ["BXSL", "FSK", "TSLX"];
const timelineIssuerKeys = new Set(data.loan_timeline_issuers.map((issuer) => issuer.issuer_match_key));
const fundColors: Record<Fund, string> = {
  ARCC: "#7c3aed",
  BBDC: "#0f766e",
  BCSF: "#4f46e5",
  BXSL: "#2563eb",
  CCAP: "#8b5cf6",
  CSWC: "#ca8a04",
  FSK: "#16a34a",
  GBDC: "#0891b2",
  HTGC: "#dc2626",
  MAIN: "#c2410c",
  NMFC: "#e11d48",
  OBDC: "#db2777",
  OCSL: "#059669",
  PSEC: "#a16207",
  TCPC: "#475569",
  TSLX: "#d97706"
};

const rateColors: Record<string, string> = {
  "Floating-rate": "#2563eb",
  "Fixed-rate": "#16a34a",
  "Rate not stated": "#a1a1aa",
  "Other rate text": "#7c3aed"
};

const capitalTierColors: Record<string, string> = {
  "Common equity / warrants": "#d36b52",
  "Preferred equity": "#d59a55",
  "Junior / unsecured debt": "#a789bd",
  "First-lien senior secured": "#77a8a0"
};

const bucketColors: Record<string, string> = {
  "2026 and earlier": "#dc2626",
  "2027": "#d97706",
  "2028": "#2563eb",
  "2029": "#16a34a",
  "2030+": "#7c3aed",
  "No stated maturity": "#a1a1aa"
};

const liabilityTypeColors: Record<string, string> = {
  "Revolving Credit Facility": "#2563eb",
  "Unsecured Notes": "#16a34a",
  "CLO / Securitization": "#d97706",
  Other: "#7c3aed"
};

const bxslRecentPricedOffering = {
  priced_date: "2026-05-14",
  settlement_date: "2026-05-21",
  maturity_date: "2031-05-21",
  principal_mm: 650,
  coupon_pct: 5.9,
  yield_pct: 6.171,
  source_file: "PRICED Blackstone Sec Lending.pdf"
};

const bxslQ12026DebtUpdate = {
  source_file: "f0cb87a2-e0bd-4243-85e1-5816094738a1 (3).pdf",
  period_end: "2026-03-31",
  paid_note_name: "2026 Notes",
  paid_note_principal_mm: 800,
  paid_note_coupon_pct: 3.625,
  paid_note_maturity_date: "2026-01-15",
  new_note_name: "September 2029 Notes",
  new_note_issue_date: "2026-03-03",
  new_note_principal_mm: 400,
  new_note_coupon_pct: 5.25,
  new_note_maturity_date: "2029-09-04"
};

const bxslLowCouponRefiNames = new Set(["2026 Notes", "New 2026 Notes", "2027 Notes"]);

const watchlistBucketFilters: Array<{ value: WatchlistBucketFilter; label: string }> = [
  { value: "All", label: "All flags" },
  { value: "Non-accrual", label: "Non-accrual" },
  { value: "Shadow below 90", label: "Shadow below 90" },
  { value: "Watch 90-97", label: "Watch 90-97" },
  { value: "QoQ deterioration", label: "QoQ deterioration" }
];

const deteriorationExposureFilters: Array<{ value: DeteriorationExposureFilter; label: string }> = [
  { value: "All", label: "All instruments" },
  { value: "Debt", label: "Debt" },
  { value: "Equity / ABF", label: "Equity / ABF" },
  { value: "Mixed / Other", label: "Mixed / other" }
];

const deteriorationFairValueFloorMm = 5;
const deteriorationCostFloorMm = 5;
const materialQoqDeteriorationThresholdPct = -5;
const twoQuarterDeteriorationThresholdPct = -5;
const threeQuarterDeteriorationThresholdPct = -7.5;

const holdingsSortLabels: Record<HoldingsSortKey, string> = {
  amortized_cost_mm: "Cost",
  fair_value_mm: "Fair value",
  mark_vs_cost_mm: "Mark",
  fv_to_cost: "FV / cost"
};

function formatMm(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  const absValue = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  return `${sign}$${new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits
  }).format(absValue)}mm`;
}

function formatPerShare(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return `$${new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2
  }).format(value)}`;
}

function formatSignedPerShare(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}$${new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2
  }).format(Math.abs(value))}`;
}

function formatMultiple(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return `${new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2
  }).format(value)}x`;
}

function formatNumber(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return new Intl.NumberFormat("en-US").format(value);
}

function formatSourceAmount(row: Pick<LoanTimelineSecurity, "amount_kind" | "amount_currency" | "amount_value" | "principal_mm">) {
  if (row.principal_mm !== null && row.principal_mm !== undefined) return formatMm(row.principal_mm);
  if (row.amount_value === null || row.amount_value === undefined || Number.isNaN(row.amount_value)) return "n/a";
  if (row.amount_kind === "number_of_shares") return `${formatNumber(row.amount_value)} sh`;
  return `${formatNumber(row.amount_value)}${row.amount_currency ? ` ${row.amount_currency}` : ""}`;
}

function formatPct(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return `${new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits
  }).format(value)}%`;
}

function formatSignedPp(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}${new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits
  }).format(Math.abs(value))} pp`;
}

function toneClass(value: number | null | undefined) {
  if (value === null || value === undefined || Math.abs(value) < 0.0001) return "";
  return value > 0 ? "positive" : "negative";
}

function formatCentsOnDollar(fairValue: number | null | undefined, cost: number | null | undefined) {
  if (
    fairValue === null ||
    fairValue === undefined ||
    cost === null ||
    cost === undefined ||
    Number.isNaN(fairValue) ||
    Number.isNaN(cost) ||
    cost === 0
  ) {
    return "n/a";
  }

  return `${new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 1,
    minimumFractionDigits: 1
  }).format((fairValue / cost) * 100)}\u00a2`;
}

function holdingSortValue(row: HoldingRow, key: HoldingsSortKey) {
  if (key === "fv_to_cost") {
    if (!row.amortized_cost_mm) return null;
    return (row.fair_value_mm / row.amortized_cost_mm) * 100;
  }

  return row[key];
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(
    new Date(`${value}T00:00:00`)
  );
}

function formatShortDate(value: string) {
  return new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric" }).format(new Date(`${value}T00:00:00`));
}

function formatSlashDate(value: string) {
  const [year, month, day] = value.split("-");
  return `${Number(month)}/${Number(day)}/${year.slice(2)}`;
}

function sumBy<T>(items: T[], selector: (item: T) => number | null | undefined) {
  return items.reduce((total, item) => total + Number(selector(item) || 0), 0);
}

function firstPercentFromText(value: string | null | undefined) {
  const match = String(value || "").match(/(\d+(?:\.\d+)?)%/);
  return match ? Number(match[1]) : null;
}

function averageDefined(values: Array<number | null | undefined>) {
  const defined = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!defined.length) return null;
  return defined.reduce((total, value) => total + value, 0) / defined.length;
}

function maxDefined(values: Array<number | null | undefined>) {
  const defined = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  return defined.length ? Math.max(...defined) : null;
}

function minDefined(values: Array<number | null | undefined>) {
  const defined = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  return defined.length ? Math.min(...defined) : null;
}

function sumDefined(values: Array<number | null | undefined>) {
  const defined = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  return defined.length ? defined.reduce((total, value) => total + value, 0) : null;
}

function uniqueSorted(values: string[]) {
  return Array.from(new Set(values.filter((value) => value.trim()))).sort();
}

function isSourceDerivedEnrichment(enrichment: CompanyEnrichment | undefined) {
  if (!enrichment) return false;
  return enrichment.notes.startsWith("Source-derived schedule context");
}

function findCompanyEnrichment(issuerMatchKey: string) {
  const matches = companyEnrichment.filter((item) => item.issuer_match_key === issuerMatchKey);
  return matches.find((item) => !isSourceDerivedEnrichment(item)) || matches[0];
}

function parseJsonStringArray(value: string | null | undefined) {
  if (!value) return [];
  try {
    const parsed: unknown = JSON.parse(value);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
  } catch {
    return [];
  }
}

function shortPeriod(value: string) {
  const [year, month] = value.split("-");
  return `${month}/${year.slice(2)}`;
}

function niceAxisMax(value: number) {
  if (!Number.isFinite(value) || value <= 0) return 1;
  const exponent = Math.pow(10, Math.floor(Math.log10(value)));
  const normalized = value / exponent;
  const niceNormalized = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return niceNormalized * exponent;
}

function axisTicks(max: number, segments = 4) {
  return Array.from({ length: segments + 1 }, (_, index) => max - (max / segments) * index);
}

function formatAxisNumber(value: number) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

function formatBps(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value)} bps`;
}

function watchlistBucketMatches(row: IssuerWatchlistFactRow, filter: WatchlistBucketFilter) {
  if (filter === "All") return true;
  if (filter === "Non-accrual") return row.is_non_accrual;
  if (filter === "Shadow below 90") return row.shadow_non_accrual;
  if (filter === "Watch 90-97") return row.watchlist_bucket === "Watch 90-97";
  return row.material_qoq_deterioration;
}

function hasPreNonAccrualDeteriorationSignal(row: IssuerWatchlistFactRow) {
  return (
    row.material_qoq_deterioration ||
    (typeof row.qoq_fv_to_cost_change_pct === "number" &&
      row.qoq_fv_to_cost_change_pct <= materialQoqDeteriorationThresholdPct) ||
    row.shadow_non_accrual
  );
}

function deteriorationTrendKey(row: Pick<IssuerWatchlistFactRow, "fund" | "issuer_match_key" | "period_end">) {
  return `${row.fund}|${row.issuer_match_key}|${row.period_end}`;
}

function hasSustainedDeterioration(metrics: DeteriorationTrendMetrics) {
  return (
    (typeof metrics.two_quarter_fv_to_cost_change_pct === "number" &&
      metrics.two_quarter_fv_to_cost_change_pct <= twoQuarterDeteriorationThresholdPct) ||
    (typeof metrics.three_quarter_fv_to_cost_change_pct === "number" &&
      metrics.three_quarter_fv_to_cost_change_pct <= threeQuarterDeteriorationThresholdPct) ||
    metrics.material_down_quarter_count >= 2 ||
    (metrics.down_quarter_count >= 2 &&
      ((typeof metrics.two_quarter_fv_to_cost_change_pct === "number" &&
        metrics.two_quarter_fv_to_cost_change_pct <= -3) ||
        (typeof metrics.three_quarter_fv_to_cost_change_pct === "number" &&
          metrics.three_quarter_fv_to_cost_change_pct <= -5)))
  );
}

function previousQuarterEnd(periodEnd: string, quartersBack: number) {
  const [yearText, monthText] = periodEnd.split("-");
  const year = Number(yearText);
  const month = Number(monthText);
  const quarterIndex = month === 3 ? 0 : month === 6 ? 1 : month === 9 ? 2 : month === 12 ? 3 : null;
  if (!Number.isFinite(year) || quarterIndex === null) return null;
  const totalQuarter = year * 4 + quarterIndex - quartersBack;
  const nextYear = Math.floor(totalQuarter / 4);
  const nextQuarterIndex = ((totalQuarter % 4) + 4) % 4;
  return `${nextYear}-${["03-31", "06-30", "09-30", "12-31"][nextQuarterIndex]}`;
}

function fvToCostChange(current: IssuerPeriodHistoryRow | undefined, prior: IssuerPeriodHistoryRow | undefined) {
  return typeof current?.fv_to_cost_pct === "number" && typeof prior?.fv_to_cost_pct === "number"
    ? current.fv_to_cost_pct - prior.fv_to_cost_pct
    : null;
}

function buildDeteriorationTrendMetricsMap(rows: IssuerPeriodHistoryRow[]) {
  const byFundIssuer = new Map<string, IssuerPeriodHistoryRow[]>();
  for (const row of rows) {
    const key = `${row.fund}|${row.issuer_match_key}`;
    const group = byFundIssuer.get(key) || [];
    group.push(row);
    byFundIssuer.set(key, group);
  }

  const trendMap = new Map<string, DeteriorationTrendMetrics>();
  for (const group of byFundIssuer.values()) {
    const sorted = group.slice().sort((a, b) => a.filing_period_end.localeCompare(b.filing_period_end));
    const rowsByPeriod = new Map(sorted.map((item) => [item.filing_period_end, item]));
    for (const row of sorted) {
      const prior1 = rowsByPeriod.get(previousQuarterEnd(row.filing_period_end, 1) || "");
      const prior2 = rowsByPeriod.get(previousQuarterEnd(row.filing_period_end, 2) || "");
      const prior3 = rowsByPeriod.get(previousQuarterEnd(row.filing_period_end, 3) || "");
      const recent = [prior3, prior2, prior1, row].filter((item): item is IssuerPeriodHistoryRow => Boolean(item));
      const recentMoves = [
        fvToCostChange(row, prior1),
        fvToCostChange(prior1, prior2),
        fvToCostChange(prior2, prior3)
      ];
      const metrics: Omit<DeteriorationTrendMetrics, "sustained_deterioration"> = {
        recent_periods: recent.map((item) => item.filing_period_end),
        down_quarter_count: recentMoves.filter((value) => typeof value === "number" && value < 0).length,
        material_down_quarter_count: recentMoves.filter(
          (value) => typeof value === "number" && value <= materialQoqDeteriorationThresholdPct
        ).length,
        two_quarter_fv_to_cost_change_pct: fvToCostChange(row, prior2),
        three_quarter_fv_to_cost_change_pct: fvToCostChange(row, prior3)
      };
      trendMap.set(
        deteriorationTrendKey({
          fund: row.fund,
          issuer_match_key: row.issuer_match_key,
          period_end: row.filing_period_end
        }),
        {
          ...metrics,
          sustained_deterioration: hasSustainedDeterioration({ ...metrics, sustained_deterioration: false })
        }
      );
    }
  }

  return trendMap;
}

function emptyDeteriorationTrendMetrics(): DeteriorationTrendMetrics {
  return {
    recent_periods: [],
    down_quarter_count: 0,
    material_down_quarter_count: 0,
    two_quarter_fv_to_cost_change_pct: null,
    three_quarter_fv_to_cost_change_pct: null,
    sustained_deterioration: false
  };
}

function deteriorationTrendLabel(group: Pick<DeteriorationGroup, "down_quarter_count" | "recent_period_count" | "two_quarter_fv_to_cost_change_pct" | "three_quarter_fv_to_cost_change_pct">) {
  const changes = [
    typeof group.two_quarter_fv_to_cost_change_pct === "number" ? `2Q ${formatSignedPp(group.two_quarter_fv_to_cost_change_pct)}` : null,
    typeof group.three_quarter_fv_to_cost_change_pct === "number" ? `3Q ${formatSignedPp(group.three_quarter_fv_to_cost_change_pct)}` : null
  ].filter(Boolean);
  const trend = `${group.down_quarter_count}/${Math.min(3, Math.max(group.recent_period_count, 1))} down`;
  return changes.length ? `${trend}; ${changes.join("; ")}` : trend;
}

function deteriorationSeverityLabel(score: number) {
  if (score >= 100) return "High";
  if (score >= 70) return "Elevated";
  return "Watch";
}

function historyWatchlistBucket(row: IssuerPeriodHistoryRow) {
  if (typeof row.fv_to_cost_pct === "number") {
    if (row.fv_to_cost_pct < 80) return "Shadow <80";
    if (row.fv_to_cost_pct < 90) return "Shadow 80-90";
    if (row.fv_to_cost_pct < 97) return "Watch 90-97";
  }
  return "2-3Q deterioration";
}

function historyWatchlistSeverity(row: IssuerPeriodHistoryRow) {
  if (typeof row.fv_to_cost_pct === "number") {
    if (row.fv_to_cost_pct < 80) return 1;
    if (row.fv_to_cost_pct < 90) return 2;
    if (row.fv_to_cost_pct < 97) return 3;
  }
  return 4;
}

function buildHistoryCandidateRow(
  row: IssuerPeriodHistoryRow,
  trend: DeteriorationTrendMetrics,
  priorRow: IssuerPeriodHistoryRow | undefined,
  watchRow: IssuerWatchlistFactRow | undefined
): IssuerWatchlistFactRow {
  const markVsCost = row.fair_value_mm - row.amortized_cost_mm;
  const priorMarkVsCost =
    priorRow && typeof priorRow.fair_value_mm === "number" && typeof priorRow.amortized_cost_mm === "number"
      ? priorRow.fair_value_mm - priorRow.amortized_cost_mm
      : null;
  const fvToCost = row.fv_to_cost_pct;
  const historyBucket = historyWatchlistBucket(row);
  const shadowNonAccrual = Boolean(watchRow?.shadow_non_accrual || (typeof fvToCost === "number" && fvToCost < 90));

  return {
    fund: row.fund,
    period_end: row.filing_period_end,
    issuer_match_key: row.issuer_match_key,
    issuer_name: row.representative_issuer_name,
    issuer_industries: null,
    instrument_context: watchRow?.instrument_context ?? null,
    instrument_context_detail: watchRow?.instrument_context_detail ?? null,
    security_count: row.holding_rows,
    principal_mm: watchRow?.principal_mm ?? null,
    principal_fair_value_mm: watchRow?.principal_fair_value_mm ?? null,
    amortized_cost_mm: row.amortized_cost_mm,
    fair_value_mm: row.fair_value_mm,
    mark_vs_cost_mm: markVsCost,
    fv_to_cost_pct: fvToCost,
    fv_to_principal_pct: watchRow?.fv_to_principal_pct ?? null,
    prior_period_end: priorRow?.filing_period_end ?? watchRow?.prior_period_end ?? null,
    prior_fv_to_cost_pct: priorRow?.fv_to_cost_pct ?? watchRow?.prior_fv_to_cost_pct ?? null,
    prior_fv_to_principal_pct: watchRow?.prior_fv_to_principal_pct ?? null,
    qoq_fv_to_cost_change_pct: trend.recent_periods.includes(previousQuarterEnd(row.filing_period_end, 1) || "")
      ? fvToCostChange(row, priorRow)
      : watchRow?.qoq_fv_to_cost_change_pct ?? null,
    qoq_fv_to_principal_change_pct: watchRow?.qoq_fv_to_principal_change_pct ?? null,
    qoq_fair_value_change_mm:
      priorRow && typeof priorRow.fair_value_mm === "number" ? row.fair_value_mm - priorRow.fair_value_mm : watchRow?.qoq_fair_value_change_mm ?? null,
    qoq_mark_vs_cost_change_mm:
      priorMarkVsCost !== null ? markVsCost - priorMarkVsCost : watchRow?.qoq_mark_vs_cost_change_mm ?? null,
    below_97_fv_to_cost: typeof fvToCost === "number" && fvToCost < 97,
    below_90_fv_to_cost: typeof fvToCost === "number" && fvToCost < 90,
    below_80_fv_to_cost: typeof fvToCost === "number" && fvToCost < 80,
    below_97_fv_to_principal: watchRow?.below_97_fv_to_principal ?? false,
    below_90_fv_to_principal: watchRow?.below_90_fv_to_principal ?? false,
    below_80_fv_to_principal: watchRow?.below_80_fv_to_principal ?? false,
    is_non_accrual: Boolean(watchRow?.is_non_accrual),
    shadow_non_accrual: shadowNonAccrual,
    material_qoq_deterioration:
      watchRow?.material_qoq_deterioration ||
      (typeof fvToCostChange(row, priorRow) === "number" && Number(fvToCostChange(row, priorRow)) <= materialQoqDeteriorationThresholdPct),
    watchlist_bucket: watchRow?.watchlist_bucket ?? historyBucket,
    watchlist_severity: watchRow?.watchlist_severity ?? historyWatchlistSeverity(row),
    source_title: watchRow?.source_title ?? "Central holdings issuer-period history",
    source_file: watchRow?.source_file ?? "",
    source_method:
      watchRow?.source_method ??
      "Synthesized from full issuer-period holdings history for sustained 2-3 quarter deterioration screening.",
    source_notes_json: watchRow?.source_notes_json ?? "[]",
    created_at_utc: watchRow?.created_at_utc ?? quarterlyFacts.meta.generated_at_utc
  };
}

function normalizeIssuerForSourceCheck(value: string | null | undefined) {
  return (value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toUpperCase()
    .replace(/&/g, " AND ")
    .replace(/[^A-Z0-9]+/g, " ")
    .replace(
      /\b(INC|LLC|LTD|LP|CORP|CO|COMPANY|HOLDINGS|HOLDING|ABF|EQUITY|PREFERRED|PREF|COMMON|STOCK|SHARES|UNITS|WARRANT|WARRANTS|PARTNERSHIP|INTEREST|CLASS|SERIES|STRUCTURED|MEZZANINE|SENIOR)\b/g,
      ""
    )
    .replace(/\s+/g, " ")
    .trim();
}

function summarizeValues(values: Array<string | null | undefined>, fallback = "n/a", limit = 2) {
  const unique = uniqueSorted(values.map((value) => value || "").filter(Boolean));
  if (!unique.length) return fallback;
  if (unique.length <= limit) return unique.join(", ");
  return `${unique.slice(0, limit).join(", ")} +${unique.length - limit}`;
}

function maturityYearLabel(value: string | null | undefined) {
  if (!value) return null;
  const year = new Date(`${value}T00:00:00`).getFullYear();
  return Number.isFinite(year) ? String(year) : value;
}

function classifyDeteriorationText(value: string) {
  const lower = value.toLowerCase();
  if (
    lower.includes("abf equity") ||
    lower.includes("equity") ||
    lower.includes("preferred") ||
    lower.includes("common stock") ||
    lower.includes("partnership interest") ||
    lower.includes("warrant")
  ) {
    return "Equity / ABF";
  }

  if (
    lower.includes("first lien") ||
    lower.includes("second lien") ||
    lower.includes("term loan") ||
    lower.includes("revolver") ||
    lower.includes("loan") ||
    lower.includes("note") ||
    lower.includes("debt")
  ) {
    return "Debt";
  }

  return "Mixed / Other";
}

function classifyDeteriorationGroup(rows: IssuerWatchlistFactRow[], holdings: HoldingRow[]): DeteriorationInstrumentBucket {
  const labels = (holdings.length ? holdings : rows).map((row) =>
    classifyDeteriorationText(
      [
        "investment_category" in row ? row.investment_category : null,
        "instrument_type" in row ? row.instrument_type : null,
        "investment_description" in row ? row.investment_description : null,
        row.issuer_name
      ]
        .filter(Boolean)
        .join(" ")
    )
  );
  const hasDebt = labels.includes("Debt");
  const hasEquity = labels.includes("Equity / ABF");
  const hasOther = labels.includes("Mixed / Other");
  if (hasDebt && !hasEquity && !hasOther) return "Debt";
  if (hasEquity && !hasDebt && !hasOther) return "Equity / ABF";
  return "Mixed / Other";
}

function rateHint(row: HoldingRow) {
  const parts: string[] = [];
  if (row.reference_base_rate) parts.push(row.reference_base_rate);
  if (typeof row.spread_pct === "number") parts.push(`+${formatPct(row.spread_pct)}`);
  if (typeof row.fixed_coupon_pct === "number") parts.push(`${formatPct(row.fixed_coupon_pct)} fixed`);
  if (typeof row.pik_rate_pct === "number" && row.pik_rate_pct > 0) parts.push(`PIK ${formatPct(row.pik_rate_pct)}`);
  if (parts.length) return parts.join(" ");
  return row.rate_type !== "Rate not stated" ? row.rate_type : row.rate_raw;
}

function deteriorationSignalScore(input: {
  fv_to_cost_pct: number | null;
  qoq_fv_to_cost_change_pct: number | null;
  two_quarter_fv_to_cost_change_pct?: number | null;
  three_quarter_fv_to_cost_change_pct?: number | null;
  qoq_fair_value_change_mm: number | null;
  fair_value_mm: number;
  amortized_cost_mm: number;
  down_quarter_count?: number;
  material_down_quarter_count?: number;
  shadow_non_accrual: boolean;
  material_qoq_deterioration: boolean;
}) {
  let score = 0;
  if (typeof input.fv_to_cost_pct === "number") {
    if (input.fv_to_cost_pct < 80) score += 40;
    else if (input.fv_to_cost_pct < 90) score += 30;
    else if (input.fv_to_cost_pct < 97) score += 15;
  }
  if (typeof input.qoq_fv_to_cost_change_pct === "number") {
    if (input.qoq_fv_to_cost_change_pct <= -15) score += 30;
    else if (input.qoq_fv_to_cost_change_pct <= -10) score += 22;
    else if (input.qoq_fv_to_cost_change_pct <= -5) score += 14;
    else if (input.qoq_fv_to_cost_change_pct < 0) score += 4;
  }
  if (typeof input.two_quarter_fv_to_cost_change_pct === "number") {
    if (input.two_quarter_fv_to_cost_change_pct <= -15) score += 24;
    else if (input.two_quarter_fv_to_cost_change_pct <= -10) score += 18;
    else if (input.two_quarter_fv_to_cost_change_pct <= -5) score += 12;
  }
  if (typeof input.three_quarter_fv_to_cost_change_pct === "number") {
    if (input.three_quarter_fv_to_cost_change_pct <= -20) score += 24;
    else if (input.three_quarter_fv_to_cost_change_pct <= -12) score += 18;
    else if (input.three_quarter_fv_to_cost_change_pct <= threeQuarterDeteriorationThresholdPct) score += 12;
  }
  if (Number(input.material_down_quarter_count || 0) >= 2) score += 16;
  else if (Number(input.down_quarter_count || 0) >= 2) score += 8;
  if (typeof input.qoq_fair_value_change_mm === "number") {
    if (input.qoq_fair_value_change_mm <= -50) score += 22;
    else if (input.qoq_fair_value_change_mm <= -25) score += 18;
    else if (input.qoq_fair_value_change_mm <= -10) score += 12;
    else if (input.qoq_fair_value_change_mm <= -5) score += 7;
  }
  if (input.fair_value_mm >= 200) score += 12;
  else if (input.fair_value_mm >= 50) score += 8;
  else if (input.fair_value_mm >= deteriorationFairValueFloorMm) score += 3;
  if (input.amortized_cost_mm >= 100) score += 6;
  if (input.shadow_non_accrual) score += 15;
  if (input.material_qoq_deterioration) score += 8;
  return score;
}

function shadowSignalLabel(rows: IssuerWatchlistFactRow[]) {
  const shadowRows = rows.filter((row) => row.shadow_non_accrual);
  if (!shadowRows.length) return null;

  const checks: Array<{ label: string; matches: (row: IssuerWatchlistFactRow) => boolean }> = [
    { label: "shadow below 80 FV/cost", matches: (row) => row.below_80_fv_to_cost },
    { label: "shadow below 90 FV/cost", matches: (row) => row.below_90_fv_to_cost },
    { label: "shadow below 80 FV/principal", matches: (row) => row.below_80_fv_to_principal },
    { label: "shadow below 90 FV/principal", matches: (row) => row.below_90_fv_to_principal }
  ];

  return checks.find((check) => shadowRows.some(check.matches))?.label || "shadow below 90";
}

function buildDeteriorationReason(group: Omit<DeteriorationGroup, "reason">) {
  const reasons: string[] = [];
  if (group.down_quarter_count >= 2) reasons.push(`${group.down_quarter_count} recent down quarters`);
  if (group.two_quarter_fv_to_cost_change_pct !== null && group.two_quarter_fv_to_cost_change_pct <= twoQuarterDeteriorationThresholdPct) {
    reasons.push(`2Q ${formatSignedPp(group.two_quarter_fv_to_cost_change_pct)} FV/cost`);
  }
  if (group.three_quarter_fv_to_cost_change_pct !== null && group.three_quarter_fv_to_cost_change_pct <= threeQuarterDeteriorationThresholdPct) {
    reasons.push(`3Q ${formatSignedPp(group.three_quarter_fv_to_cost_change_pct)} FV/cost`);
  }
  if (group.shadow_non_accrual) reasons.push(group.shadow_signal_label || "shadow below 90");
  if (group.qoq_fv_to_cost_change_pct !== null && group.qoq_fv_to_cost_change_pct <= materialQoqDeteriorationThresholdPct) {
    reasons.push(`${formatSignedPp(group.qoq_fv_to_cost_change_pct)} FV/cost`);
  }
  if (group.qoq_fair_value_change_mm !== null && group.qoq_fair_value_change_mm <= -5) {
    reasons.push(`${formatMm(group.qoq_fair_value_change_mm)} FV QoQ`);
  }
  if (group.fair_value_mm >= 50) reasons.push(`${formatMm(group.fair_value_mm)} FV`);
  if (group.instrument_bucket !== "Debt") reasons.push(group.instrument_bucket);
  return reasons.length ? reasons.slice(0, 5).join("; ") : "material multi-quarter watchlist trigger";
}

function buildDeteriorationGroups(
  rows: IssuerWatchlistFactRow[],
  holdings: HoldingRow[],
  latestNonAccrualNameKeys: Set<string>,
  trendMetricsByRow: Map<string, DeteriorationTrendMetrics>
) {
  const holdingsByFundIssuer = new Map<string, HoldingRow[]>();
  for (const holding of holdings) {
    if (!holding.issuer_match_key) continue;
    const key = `${holding.fund}|${holding.issuer_match_key}`;
    const group = holdingsByFundIssuer.get(key) || [];
    group.push(holding);
    holdingsByFundIssuer.set(key, group);
  }

  const rowsByIssuer = new Map<string, IssuerWatchlistFactRow[]>();
  for (const row of rows) {
    const group = rowsByIssuer.get(row.issuer_match_key) || [];
    group.push(row);
    rowsByIssuer.set(row.issuer_match_key, group);
  }

  return Array.from(rowsByIssuer.entries())
    .map(([issuer_match_key, groupedRows]) => {
      const scoreRow = (row: IssuerWatchlistFactRow) => {
        const trend = trendMetricsByRow.get(deteriorationTrendKey(row)) || emptyDeteriorationTrendMetrics();
        return deteriorationSignalScore({
          fv_to_cost_pct: row.fv_to_cost_pct,
          qoq_fv_to_cost_change_pct: row.qoq_fv_to_cost_change_pct,
          two_quarter_fv_to_cost_change_pct: trend.two_quarter_fv_to_cost_change_pct,
          three_quarter_fv_to_cost_change_pct: trend.three_quarter_fv_to_cost_change_pct,
          qoq_fair_value_change_mm: row.qoq_fair_value_change_mm,
          fair_value_mm: Number(row.fair_value_mm || 0),
          amortized_cost_mm: Number(row.amortized_cost_mm || 0),
          down_quarter_count: trend.down_quarter_count,
          material_down_quarter_count: trend.material_down_quarter_count,
          shadow_non_accrual: row.shadow_non_accrual,
          material_qoq_deterioration: row.material_qoq_deterioration
        });
      };
      const sortedRows = groupedRows
        .slice()
        .sort((a, b) =>
          scoreRow(b) - scoreRow(a) ||
            Number(b.fair_value_mm || 0) - Number(a.fair_value_mm || 0)
        );
      const primary = sortedRows[0];
      const groupTrendMetrics = groupedRows.map((row) => trendMetricsByRow.get(deteriorationTrendKey(row)) || emptyDeteriorationTrendMetrics());
      const groupHoldings = groupedRows.flatMap((row) => holdingsByFundIssuer.get(`${row.fund}|${row.issuer_match_key}`) || []);
      const amortizedCost = sumBy(groupedRows, (row) => row.amortized_cost_mm);
      const fairValue = sumBy(groupedRows, (row) => row.fair_value_mm);
      const fvToCost = amortizedCost ? (fairValue / amortizedCost) * 100 : primary.fv_to_cost_pct;
      const qoqFairValueChange = sumDefined(groupedRows.map((row) => row.qoq_fair_value_change_mm));
      const qoqMarkChange = sumDefined(groupedRows.map((row) => row.qoq_mark_vs_cost_change_mm));
      const qoqFvToCostChange = minDefined(groupedRows.map((row) => row.qoq_fv_to_cost_change_pct));
      const twoQuarterFvToCostChange = minDefined(groupTrendMetrics.map((metrics) => metrics.two_quarter_fv_to_cost_change_pct));
      const threeQuarterFvToCostChange = minDefined(groupTrendMetrics.map((metrics) => metrics.three_quarter_fv_to_cost_change_pct));
      const downQuarterCount = maxDefined(groupTrendMetrics.map((metrics) => metrics.down_quarter_count)) || 0;
      const materialDownQuarterCount = maxDefined(groupTrendMetrics.map((metrics) => metrics.material_down_quarter_count)) || 0;
      const recentPeriodCount = maxDefined(groupTrendMetrics.map((metrics) => Math.max(0, metrics.recent_periods.length - 1))) || 1;
      const sustainedDeterioration = groupTrendMetrics.some((metrics) => metrics.sustained_deterioration);
      const instrumentBucket = classifyDeteriorationGroup(groupedRows, groupHoldings);
      const score = deteriorationSignalScore({
        fv_to_cost_pct: fvToCost,
        qoq_fv_to_cost_change_pct: qoqFvToCostChange,
        two_quarter_fv_to_cost_change_pct: twoQuarterFvToCostChange,
        three_quarter_fv_to_cost_change_pct: threeQuarterFvToCostChange,
        qoq_fair_value_change_mm: qoqFairValueChange,
        fair_value_mm: fairValue,
        amortized_cost_mm: amortizedCost,
        down_quarter_count: downQuarterCount,
        material_down_quarter_count: materialDownQuarterCount,
        shadow_non_accrual: groupedRows.some((row) => row.shadow_non_accrual),
        material_qoq_deterioration: groupedRows.some((row) => row.material_qoq_deterioration)
      });
      const baseGroup: Omit<DeteriorationGroup, "reason"> = {
        issuer_match_key,
        issuer_name: primary.issuer_name,
        funds: uniqueSorted(groupedRows.map((row) => row.fund)) as Fund[],
        security_count: sumBy(groupedRows, (row) => row.security_count),
        amortized_cost_mm: amortizedCost,
        fair_value_mm: fairValue,
        fv_to_cost_pct: fvToCost,
        prior_fv_to_cost_pct: primary.prior_fv_to_cost_pct,
        qoq_fv_to_cost_change_pct: qoqFvToCostChange,
        two_quarter_fv_to_cost_change_pct: twoQuarterFvToCostChange,
        three_quarter_fv_to_cost_change_pct: threeQuarterFvToCostChange,
        qoq_fair_value_change_mm: qoqFairValueChange,
        qoq_mark_vs_cost_change_mm: qoqMarkChange,
        down_quarter_count: downQuarterCount,
        material_down_quarter_count: materialDownQuarterCount,
        recent_period_count: recentPeriodCount,
        shadow_non_accrual: groupedRows.some((row) => row.shadow_non_accrual),
        material_qoq_deterioration: groupedRows.some((row) => row.material_qoq_deterioration),
        sustained_deterioration: sustainedDeterioration,
        watchlist_buckets: uniqueSorted(groupedRows.map((row) => row.watchlist_bucket)),
        shadow_signal_label: shadowSignalLabel(groupedRows),
        instrument_bucket: instrumentBucket,
        category_label:
          summarizeValues(groupHoldings.map((row) => row.industry), primary.issuer_industries || "No industry") ||
          primary.issuer_industries ||
          "No industry",
        instrument_label: summarizeValues(
          groupHoldings.map((row) => row.investment_category || row.instrument_type || row.investment_description),
          instrumentBucket
        ),
        rate_label: summarizeValues(groupHoldings.map(rateHint), "Rate n/a"),
        maturity_label: summarizeValues(groupHoldings.map((row) => maturityYearLabel(row.maturity_date) || row.maturity_bucket), "Maturity n/a"),
        source_non_accrual_match: groupedRows.some((row) =>
          latestNonAccrualNameKeys.has(`${row.fund}|${normalizeIssuerForSourceCheck(row.issuer_name)}`)
        ),
        score,
        severity_label: deteriorationSeverityLabel(score),
        trend_label: ""
      };
      baseGroup.trend_label = deteriorationTrendLabel(baseGroup);

      return { ...baseGroup, reason: buildDeteriorationReason(baseGroup) };
    })
    .sort((a, b) => {
      if (a.score !== b.score) return b.score - a.score;
      if ((a.qoq_fv_to_cost_change_pct ?? 0) !== (b.qoq_fv_to_cost_change_pct ?? 0)) {
        return Number(a.qoq_fv_to_cost_change_pct || 0) - Number(b.qoq_fv_to_cost_change_pct || 0);
      }
      return b.fair_value_mm - a.fair_value_mm;
    });
}

function liabilityTypeGroup(type: string) {
  if (type === "Collateralized Loan Obligation" || type === "Debt Securitization") return "CLO / Securitization";
  if (type === "Revolving Credit Facility") return "Revolving Credit Facility";
  if (type === "Unsecured Notes") return "Unsecured Notes";
  return "Other";
}

function maturityYear(value: string) {
  return new Date(`${value}T00:00:00`).getFullYear();
}

function isSofrLinked(instrument: LiabilityInstrument) {
  return instrument.rate_type.toLowerCase().includes("floating");
}

function MetricCard({
  title,
  value,
  note,
  icon: Icon,
  delta
}: {
  title: string;
  value: string;
  note: string;
  icon: LucideIcon;
  delta?: number | null;
}) {
  const isUp = typeof delta === "number" && delta >= 0;
  return (
    <section className="panel metric-card">
      <div className="metric-top">
        <span>{title}</span>
        <span className="metric-icon">
          <Icon />
        </span>
      </div>
      <div className="metric-value">{value}</div>
      <p className="metric-note">
        {typeof delta === "number" ? (
          <span className={`delta ${isUp ? "up" : "down"}`}>
            {isUp ? <ArrowUpRight /> : <ArrowDownRight />}
            {formatPct(Math.abs(delta))}
          </span>
        ) : null}{" "}
        {note}
      </p>
    </section>
  );
}

function Panel({
  title,
  subtitle,
  icon: Icon,
  children,
  action,
  id
}: {
  title: string;
  subtitle?: string;
  icon?: LucideIcon;
  children: React.ReactNode;
  action?: React.ReactNode;
  id?: string;
}) {
  return (
    <section className="panel" id={id}>
      <div className="panel-header">
        <div>
          <h2 className="panel-title">{Icon ? <Icon /> : null}{title}</h2>
          {subtitle ? <p className="panel-subtitle">{subtitle}</p> : null}
        </div>
        {action}
      </div>
      <div className="panel-body">{children}</div>
    </section>
  );
}

function Callout({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="callout">
      <Info />
      <div>
        <strong>{title}</strong>
        <p>{children}</p>
      </div>
    </div>
  );
}

function FundBadge({ fund }: { fund: Fund }) {
  return <span className={`badge fund-${fund}`}>{fund}</span>;
}

type ExposureFlaggedRow = {
  exposure_type?: string | null;
  is_unfunded_commitment?: number | boolean | null;
};

function isUnfundedCommitment(row: ExposureFlaggedRow) {
  return row.exposure_type === "unfunded_commitment" || row.is_unfunded_commitment === 1 || row.is_unfunded_commitment === true;
}

function ExposureTypeBadge({ row }: { row: ExposureFlaggedRow }) {
  if (!isUnfundedCommitment(row)) return null;
  return <span className="badge exposure-unfunded">Unfunded commitment</span>;
}

function Legend({ colors }: { colors: Record<string, string> }) {
  return (
    <div className="legend">
      {Object.entries(colors).map(([label, color]) => (
        <span className="legend-item" key={label}>
          <span className="swatch" style={{ "--swatch": color } as React.CSSProperties} />
          {label}
        </span>
      ))}
    </div>
  );
}

type ChartTooltipState = {
  title: string;
  value: string;
  detail?: string;
  color?: string;
  x: number;
  y: number;
};

function tooltipPosition(event: React.MouseEvent<Element>) {
  const tooltipWidth = 230;
  const tooltipHeight = 88;
  const viewportWidth = typeof window === "undefined" ? 1600 : window.innerWidth;
  const viewportHeight = typeof window === "undefined" ? 900 : window.innerHeight;
  return {
    x: Math.max(12, Math.min(event.clientX + 14, viewportWidth - tooltipWidth)),
    y: Math.max(12, Math.min(event.clientY + 14, viewportHeight - tooltipHeight))
  };
}

function useChartTooltip() {
  const [tooltip, setTooltip] = useState<ChartTooltipState | null>(null);
  const showTooltip = (
    event: React.MouseEvent<Element>,
    next: Omit<ChartTooltipState, "x" | "y">
  ) => {
    setTooltip({ ...next, ...tooltipPosition(event) });
  };

  return {
    tooltip,
    showTooltip,
    hideTooltip: () => setTooltip(null)
  };
}

function ChartTooltip({ tooltip }: { tooltip: ChartTooltipState | null }) {
  if (!tooltip) return null;
  return (
    <div
      className="chart-tooltip"
      style={
        {
          left: tooltip.x,
          top: tooltip.y,
          "--tooltip-color": tooltip.color || "var(--accent)"
        } as React.CSSProperties
      }
    >
      <div className="chart-tooltip-title">
        <span className="swatch" style={{ "--swatch": tooltip.color || "var(--accent)" } as React.CSSProperties} />
        {tooltip.title}
      </div>
      <strong>{tooltip.value}</strong>
      {tooltip.detail ? <span>{tooltip.detail}</span> : null}
    </div>
  );
}

function TimeSeriesChart({ points }: { points: PeriodPoint[] }) {
  const { tooltip, showTooltip, hideTooltip } = useChartTooltip();
  const max = Math.max(...points.map((point) => point.total_fair_value_mm));
  return (
    <div className="chart-shell" onMouseLeave={hideTooltip}>
      <Legend colors={fundColors} />
      <div className="stack-chart">
        {points.map((point) => (
          <div className="stack-row" key={point.filing_period_end}>
            <div className="stack-label">{shortPeriod(point.filing_period_end)}</div>
            <div
              className="stack-track"
              onMouseMove={(event) =>
                showTooltip(event, {
                  title: formatDate(point.filing_period_end),
                  value: formatMm(point.total_fair_value_mm),
                  detail: "Total fair value"
                })
              }
            >
              {funds.map((fund) => {
                const value = Number(point[fund] || 0);
                return (
                  <div
                    className="stack-segment"
                    key={fund}
                    style={{
                      "--segment-color": fundColors[fund],
                      width: `${max ? (value / max) * 100 : 0}%`
                    } as React.CSSProperties}
                    onMouseMove={(event) => {
                      event.stopPropagation();
                      showTooltip(event, {
                        title: `${fund} - ${formatDate(point.filing_period_end)}`,
                        value: value ? formatMm(value) : "not available",
                        detail: "Fair value",
                        color: fundColors[fund]
                      });
                    }}
                  />
                );
              })}
            </div>
            <div className="stack-value">
              {formatMm(point.total_fair_value_mm, 0)}
              {point.coverage_count < funds.length ? " *" : ""}
            </div>
          </div>
        ))}
      </div>
      <ChartTooltip tooltip={tooltip} />
    </div>
  );
}

function BarList({
  items,
  getLabel,
  getValue,
  color,
  limit = 10
}: {
  items: Array<Record<string, unknown>>;
  getLabel: (item: Record<string, unknown>) => string;
  getValue: (item: Record<string, unknown>) => number;
  color: string;
  limit?: number;
}) {
  const { tooltip, showTooltip, hideTooltip } = useChartTooltip();
  const sliced = items.slice(0, limit);
  const max = Math.max(...sliced.map(getValue), 1);
  return (
    <div className="bar-list" onMouseLeave={hideTooltip}>
      {sliced.map((item) => {
        const label = getLabel(item);
        const value = getValue(item);
        return (
          <div className="bar-item" key={`${label}-${value}`}>
            <div className="bar-line">
              <strong title={label}>{label}</strong>
              <span>{formatMm(value)}</span>
            </div>
            <div className="bar-track">
              <div
                className="bar-fill"
                style={{ "--bar-color": color, width: `${(value / max) * 100}%` } as React.CSSProperties}
                onMouseMove={(event) =>
                  showTooltip(event, {
                    title: label,
                    value: formatMm(value),
                    color
                  })
                }
              />
            </div>
          </div>
        );
      })}
      <ChartTooltip tooltip={tooltip} />
    </div>
  );
}

function FundLatestCards({ selectedFund }: { selectedFund: Fund | "All" }) {
  const visibleRows = data.latest_by_fund.filter((fund) => selectedFund === "All" || fund.fund === selectedFund);
  return (
    <div className="table-wrap">
      <table className="compact-table">
        <thead>
          <tr>
            <th>Fund</th>
            <th className="right">Rows</th>
            <th className="right">Fair value</th>
            <th className="right">Mark vs cost</th>
            <th className="right">QoQ change</th>
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((fund) => {
            const change = data.change_by_fund.find((item) => item.fund === fund.fund);
            return (
              <tr key={fund.fund}>
                <td>
                  <FundBadge fund={fund.fund} />
                </td>
                <td className="right">{formatNumber(fund.holding_rows)}</td>
                <td className="right">{formatMm(fund.fair_value_mm)}</td>
                <td className="right">{formatMm(fund.mark_vs_cost_mm)}</td>
                <td className="right">{change?.change_pct === null ? "n/a" : formatPct(change?.change_pct)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function GroupedStackedBars({
  rows,
  groupKey,
  segmentKey,
  colors
}: {
  rows: Array<Record<string, unknown>>;
  groupKey: string;
  segmentKey: string;
  colors: Record<string, string>;
}) {
  const { tooltip, showTooltip, hideTooltip } = useChartTooltip();
  const grouped = funds.map((fund) => {
    const fundRows = rows.filter((row) => row[groupKey] === fund);
    const total = sumBy(fundRows, (row) => Number(row.fair_value_mm || 0));
    return { fund, rows: fundRows, total };
  });
  return (
    <div className="chart-shell" onMouseLeave={hideTooltip}>
      <Legend colors={colors} />
      <div className="stack-chart">
        {grouped.map((group) => (
          <div className="stack-row" key={group.fund}>
            <div className="stack-label">{group.fund}</div>
            <div className="stack-track">
              {group.rows.map((row) => {
                const key = String(row[segmentKey]);
                const value = Number(row.fair_value_mm || 0);
                return (
                  <div
                    className="stack-segment"
                    key={`${group.fund}-${key}`}
                    style={{
                      "--segment-color": colors[key] || "#52525b",
                      width: `${group.total ? (value / group.total) * 100 : 0}%`
                    } as React.CSSProperties}
                    onMouseMove={(event) => {
                      event.stopPropagation();
                      showTooltip(event, {
                        title: `${group.fund} - ${key}`,
                        value: formatMm(value),
                        detail: `${formatPct(group.total ? (value / group.total) * 100 : 0)} of fund fair value`,
                        color: colors[key] || "#52525b"
                      });
                    }}
                  />
                );
              })}
            </div>
            <div className="stack-value">{formatMm(group.total, 0)}</div>
          </div>
        ))}
      </div>
      <ChartTooltip tooltip={tooltip} />
    </div>
  );
}

function PortfolioFairValueGroupedChart({
  points,
  visibleFunds = funds
}: {
  points: PeriodPoint[];
  visibleFunds?: Fund[];
}) {
  const { tooltip, showTooltip, hideTooltip } = useChartTooltip();
  const width = 940;
  const height = 330;
  const margin = { top: 18, right: 20, bottom: 48, left: 64 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const maxValue = niceAxisMax(Math.max(...points.flatMap((point) => visibleFunds.map((fund) => Number(point[fund] || 0))), 1));
  const ticks = axisTicks(maxValue);
  const slotWidth = plotWidth / Math.max(points.length, 1);
  const groupWidth = Math.min(92, slotWidth * 0.72);
  const barGap = 5;
  const barWidth = Math.max(10, (groupWidth - barGap * (visibleFunds.length - 1)) / Math.max(visibleFunds.length, 1));

  const yFor = (value: number) => margin.top + (1 - value / maxValue) * plotHeight;

  return (
    <div className="metric-chart-wrap" onMouseLeave={hideTooltip}>
      <svg className="metric-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Portfolio fair value over time">
        {ticks.map((tick) => {
          const y = yFor(tick);
          return (
            <g key={tick}>
              <line className="chart-grid-line" x1={margin.left} x2={width - margin.right} y1={y} y2={y} />
              <text className="chart-axis-label" x={margin.left - 12} y={y + 4} textAnchor="end">
                {formatAxisNumber(tick)}
              </text>
            </g>
          );
        })}
        <line className="chart-axis-line" x1={margin.left} x2={width - margin.right} y1={height - margin.bottom} y2={height - margin.bottom} />
        <line className="chart-axis-line" x1={margin.left} x2={margin.left} y1={margin.top} y2={height - margin.bottom} />
        <text className="chart-axis-title" transform={`translate(16 ${margin.top + plotHeight / 2}) rotate(-90)`} textAnchor="middle">
          Fair value ($mm)
        </text>
        {points.map((point, index) => {
          const groupX = margin.left + index * slotWidth + (slotWidth - groupWidth) / 2;
          return (
            <g key={point.filing_period_end}>
              {visibleFunds.map((fund, fundIndex) => {
                const value = Number(point[fund] || 0);
                const barHeight = value ? (value / maxValue) * plotHeight : 0;
                return (
                  <rect
                    key={`${point.filing_period_end}-${fund}`}
                    className="chart-bar"
                    x={groupX + fundIndex * (barWidth + barGap)}
                    y={height - margin.bottom - barHeight}
                    width={barWidth}
                    height={barHeight}
                    rx={3}
                    fill={fundColors[fund]}
                    onMouseMove={(event) =>
                      showTooltip(event, {
                        title: `${fund} - ${formatDate(point.filing_period_end)}`,
                        value: value ? formatMm(value) : "not available",
                        detail: "Portfolio fair value",
                        color: fundColors[fund]
                      })
                    }
                  />
                );
              })}
              <text className="chart-axis-label" x={margin.left + index * slotWidth + slotWidth / 2} y={height - 20} textAnchor="middle">
                {shortPeriod(point.filing_period_end)}
                {visibleFunds.some((fund) => point[fund] === null || point[fund] === undefined) ? "*" : ""}
              </text>
            </g>
          );
        })}
      </svg>
      <Legend colors={Object.fromEntries(visibleFunds.map((fund) => [fund, fundColors[fund]]))} />
      <ChartTooltip tooltip={tooltip} />
    </div>
  );
}

function MultiFundLineChart({
  periods,
  getValue,
  yLabel,
  yMax,
  yMin = 0,
  yTicks,
  tickFormatter,
  valueFormatter,
  visibleFunds = funds
}: {
  periods: string[];
  getValue: (fund: Fund, period: string) => number | null;
  yLabel: string;
  yMax: number;
  yMin?: number;
  yTicks?: number[];
  tickFormatter: (value: number) => string;
  valueFormatter: (value: number) => string;
  visibleFunds?: Fund[];
}) {
  const { tooltip, showTooltip, hideTooltip } = useChartTooltip();
  const width = 760;
  const height = 300;
  const margin = { top: 18, right: 18, bottom: 46, left: 58 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const yRange = Math.max(yMax - yMin, 1);
  const ticks = yTicks || axisTicks(yMax);
  const xFor = (index: number) =>
    periods.length <= 1 ? margin.left + plotWidth / 2 : margin.left + (index / (periods.length - 1)) * plotWidth;
  const yFor = (value: number) => margin.top + (1 - (value - yMin) / yRange) * plotHeight;

  return (
    <div className="metric-chart-wrap line-chart-wrap" onMouseLeave={hideTooltip}>
      <svg className="metric-svg line-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={yLabel}>
        {ticks.map((tick) => {
          const y = yFor(tick);
          return (
            <g key={tick}>
              <line className="chart-grid-line" x1={margin.left} x2={width - margin.right} y1={y} y2={y} />
              <text className="chart-axis-label" x={margin.left - 10} y={y + 4} textAnchor="end">
                {tickFormatter(tick)}
              </text>
            </g>
          );
        })}
        <line className="chart-axis-line" x1={margin.left} x2={width - margin.right} y1={height - margin.bottom} y2={height - margin.bottom} />
        <line className="chart-axis-line" x1={margin.left} x2={margin.left} y1={margin.top} y2={height - margin.bottom} />
        <text className="chart-axis-title" transform={`translate(15 ${margin.top + plotHeight / 2}) rotate(-90)`} textAnchor="middle">
          {yLabel}
        </text>
        {periods.map((period, index) => (
          <text className="chart-axis-label" key={period} x={xFor(index)} y={height - 18} textAnchor="middle">
            {shortPeriod(period)}
          </text>
        ))}
        {visibleFunds.map((fund) => {
          let drawing = false;
          const path = periods
            .map((period, index) => {
              const value = getValue(fund, period);
              if (value === null || Number.isNaN(value)) {
                drawing = false;
                return "";
              }
              const command = drawing ? "L" : "M";
              drawing = true;
              return `${command} ${xFor(index).toFixed(2)} ${yFor(value).toFixed(2)}`;
            })
            .filter(Boolean)
            .join(" ");

          return (
            <g key={fund}>
              <path className="chart-line" d={path} stroke={fundColors[fund]} />
              {periods.map((period, index) => {
                const value = getValue(fund, period);
                if (value === null || Number.isNaN(value)) return null;
                return (
                  <g key={`${fund}-${period}`}>
                    <circle
                      className="chart-point"
                      cx={xFor(index)}
                      cy={yFor(value)}
                      r={3.7}
                      fill={fundColors[fund]}
                    />
                    <circle
                      className="chart-point-hit"
                      cx={xFor(index)}
                      cy={yFor(value)}
                      r={10}
                      fill="transparent"
                      onMouseMove={(event) =>
                        showTooltip(event, {
                          title: `${fund} - ${formatDate(period)}`,
                          value: valueFormatter(value),
                          detail: yLabel,
                          color: fundColors[fund]
                        })
                      }
                    />
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
      <Legend colors={Object.fromEntries(visibleFunds.map((fund) => [fund, fundColors[fund]]))} />
      <ChartTooltip tooltip={tooltip} />
    </div>
  );
}

function OverviewTrendCharts({ selectedFund }: { selectedFund: Fund | "All" }) {
  const visibleFunds = selectedFund === "All" ? funds : [selectedFund];
  const periods = data.time_series.map((point) => point.filing_period_end);
  const periodMap = new Map(data.period_summary.map((row) => [`${row.fund}|${row.filing_period_end}`, row]));
  const spreadMap = new Map((data.spread_time_series || []).map((row) => [`${row.fund}|${row.filing_period_end}`, row]));

  const markToCost = (fund: Fund, period: string) => {
    const row = periodMap.get(`${fund}|${period}`);
    if (!row?.amortized_cost_mm) return null;
    return (row.fair_value_mm / row.amortized_cost_mm) * 100;
  };

  const weightedSpread = (fund: Fund, period: string) => {
    const row = spreadMap.get(`${fund}|${period}`);
    return row?.weighted_avg_spread_bps ?? null;
  };

  return (
    <>
      <Panel
        title="Portfolio Fair Value Over Time"
        subtitle="Grouped by fund and filing period; missing source periods simply omit that fund's bar."
        icon={BarChart3}
      >
        <PortfolioFairValueGroupedChart points={data.time_series} visibleFunds={visibleFunds} />
      </Panel>

      <div className="grid two-col chart-pair-grid">
        <Panel title="Mark-To-Cost Over Time" subtitle="Fair value divided by amortized cost by fund and filing period." icon={LineChart}>
          <MultiFundLineChart
            periods={periods}
            getValue={markToCost}
            yLabel="Fair value / amortized cost"
            yMax={120}
            yMin={80}
            yTicks={[120, 100, 80]}
            tickFormatter={(value) => formatAxisNumber(value)}
            valueFormatter={(value) => formatPct(value)}
            visibleFunds={visibleFunds}
          />
        </Panel>

        <Panel
          title="Weighted-Avg Spread"
          subtitle="Parsed spread rows only, weighted by fair value; values are bps over the stated base rate."
          icon={Activity}
        >
          <MultiFundLineChart
            periods={periods}
            getValue={weightedSpread}
            yLabel="Weighted-avg spread (bps)"
            yMax={750}
            yMin={250}
            yTicks={[750, 500, 250]}
            tickFormatter={(value) => formatAxisNumber(value)}
            valueFormatter={(value) => formatBps(value)}
            visibleFunds={visibleFunds}
          />
        </Panel>
      </div>
    </>
  );
}

function BdcPrimer({ selectedFund }: { selectedFund: Fund | "All" }) {
  const scope = selectedFund === "All" ? "the eight verified BDCs" : selectedFund;
  return (
    <Panel
      title="BDC Primer"
      subtitle={`Plain-language context for reading ${selectedFund === "All" ? "the eight-fund verified private credit dataset" : `${selectedFund}'s private credit data`}.`}
      icon={Info}
    >
      <div className="bdc-primer-grid">
        <section className="bdc-primer-section">
          <h3>What is a BDC?</h3>
          <p>
            A business development company is a public closed-end investment vehicle built to finance smaller and middle-market companies.
            It gives public-market investors a window into private credit, meaning loans and occasional equity stakes that usually do not trade on an exchange.
          </p>
          <p>
            BDCs elect a special status under the Investment Company Act. They must keep most assets in qualifying investments, including private-company securities and other eligible assets, and they operate with governance, reporting, leverage, and conflict rules that matter when reading the numbers.
          </p>
        </section>

        <section className="bdc-primer-section">
          <h3>What does this dataset describe?</h3>
          <p>
            This dashboard is a holding-level credit map. It starts with each fund's schedules of investments and related filing data, then normalizes each line into issuer, instrument, category, cost, fair value, maturity, rate type, reference base rate, spread, and cross-fund issuer match.
          </p>
          <p>
            For {scope}, the latest common period is {data.meta.latest_period_label}. The point is to compare credit exposure on the same footing, so issuer concentration, first-lien mix, rate exposure, maturities, and mark-to-cost can be read across funds without blending source formats.
          </p>
        </section>

        <section className="bdc-primer-section">
          <h3>How does the BDC business model work?</h3>
          <p>
            A BDC raises capital from shareholders and lenders, then lends that capital to portfolio companies. It earns interest, origination and structuring fees, dividends, and sometimes equity gains. The spread between asset yield and funding cost is the engine behind net investment income.
          </p>
          <p>
            The 2025 10-Ks for these funds frame the goal in similar language: current income comes first, with long-term capital appreciation second. That is why this overview focuses on seniority, fair value marks, floating-rate exposure, spreads, leverage-sensitive funding, and whether large borrowers dominate the portfolio.
          </p>
        </section>
      </div>
      <p className="bdc-primer-source">
        Source context: SEC Investor.gov BDC bulletin and the eight reconciled filing datasets in the verified tracker.
      </p>
    </Panel>
  );
}

function ProjectMotivation() {
  const timelineSecurityRows = data.loan_timeline_securities;
  const fundedTimelineRows = timelineSecurityRows.filter((row) => row.exposure_type === "funded").length;
  const unfundedTimelineRows = timelineSecurityRows.filter((row) => row.exposure_type === "unfunded_commitment").length;
  const fskUnfundedTimelineRows = timelineSecurityRows.filter(
    (row) => row.fund === "FSK" && row.exposure_type === "unfunded_commitment"
  ).length;

  const rawSampleRows = [
    ["48Forty Solutions LLC", "(e)(k)(n)", "Commercial & Professional Services", "SP + 6.0%", "1.0%", "11/2029", "$19.1mm", "$19.0mm"],
    ["Areon AG", "(e)(h)(i)(m)", "Software & Services", "E + 4.5%", "0.0%", "09/2031", "EUR", "66.1mm"],
    ["Advania Sverige AB", "(e)(h)(i)(m)", "Software & Services", "SA + 5.0%", "0.0%", "06/2031", "SEK", "66.9mm"],
    ["Affordable Care Inc", "(e)(h)", "Health Care Equipment & Services", "SF + 6.0%", "0.8%", "08/2028", "$78.1mm", "77.8mm"]
  ];

  return (
    <Panel
      title="Project Motivation"
      subtitle="Why the dashboard starts with data engineering before analysis."
      icon={Database}
    >
      <div className="motivation-layout">
        <div className="motivation-copy">
          <p>
            BDC filings contain valuable holding-level information, but the raw schedules are not analysis-ready. A page from
            FSK&apos;s 2025 Form 10-K, for example, arrives as a dense portfolio table with issuer names, footnote tokens,
            industries, rate text, base-rate floors, maturities, principal amounts, cost, and fair value packed into a layout
            designed for disclosure rather than querying.
          </p>
          <p>
            The first job is therefore processing: parse the filing, preserve the as-filed rows, normalize fields, tag source
            context, separate funded exposure from unfunded commitments, and only then aggregate the data. Once the rows are
            structured, the same database can support dashboard views, issuer timelines, reconciliation checks, and eventually
            more advanced data science or machine learning workflows.
          </p>
        </div>

        <div className="raw-filing-sample" aria-label="Sample FSK 2025 10-K portfolio schedule rows">
          <div className="raw-filing-topline">
            <span>FSK 2025 Form 10-K</span>
            <strong>Portfolio schedule excerpt</strong>
          </div>
          <div className="raw-filing-grid" role="table" aria-label="Raw portfolio holdings sample">
            <div className="raw-filing-row raw-filing-header" role="row">
              <span>Company</span>
              <span>Footnotes</span>
              <span>Industry</span>
              <span>Interest rate</span>
              <span>Floor</span>
              <span>Maturity</span>
              <span>Principal</span>
              <span>Cost</span>
            </div>
            {rawSampleRows.map((row) => (
              <div className="raw-filing-row" role="row" key={row.join("|")}>
                {row.map((cell, index) => (
                  <span role="cell" key={`${cell}-${index}`}>{cell}</span>
                ))}
              </div>
            ))}
          </div>
          <p>
            This is the kind of source shape the pipeline turns into normalized, queryable holdings rows.
          </p>
        </div>
      </div>

      <div className="processing-strip">
        <div>
          <span className="step-label">1. Preserve</span>
          <strong>As-filed rows stay visible</strong>
          <p>Schedule rows are kept for review, including separate tranches, revolvers, delayed draws, and commitments.</p>
        </div>
        <div>
          <span className="step-label">2. Tag</span>
          <strong>Funded versus unfunded</strong>
          <p>For FSK, footnote <code>(x)</code> rows are tagged as unfunded commitments and carried with explicit exposure flags.</p>
        </div>
        <div>
          <span className="step-label">3. Analyze</span>
          <strong>Clean funded aggregates</strong>
          <p>Timeline period totals use funded rows, while unfunded commitments remain in the security detail table.</p>
        </div>
      </div>

      <div className="timeline-count-strip" aria-label="Timeline processing counts">
        <span><strong>{formatNumber(data.loan_timeline_issuers.length)}</strong> timeline issuers</span>
        <span><strong>{formatNumber(data.loan_timeline_periods.length)}</strong> fund-period aggregates</span>
        <span><strong>{formatNumber(fundedTimelineRows)}</strong> funded security rows</span>
        <span><strong>{formatNumber(unfundedTimelineRows)}</strong> unfunded commitments retained in detail</span>
        <span><strong>{formatNumber(fskUnfundedTimelineRows)}</strong> FSK footnote <code>(x)</code> rows tagged</span>
      </div>
    </Panel>
  );
}

function issuerMarkPressure(fund: Fund) {
  const issuerMap = new Map<string, { issuerName: string; amortizedCostMm: number; fairValueMm: number }>();

  data.holdings_detail_latest
    .filter((row) => row.fund === fund && row.exposure_type === "funded")
    .forEach((row) => {
      const issuerKey = row.issuer_match_key || row.issuer_name || "UNKNOWN";
      const existing = issuerMap.get(issuerKey) ?? {
        issuerName: row.issuer_name || issuerKey,
        amortizedCostMm: 0,
        fairValueMm: 0
      };

      existing.amortizedCostMm += row.amortized_cost_mm;
      existing.fairValueMm += row.fair_value_mm;
      issuerMap.set(issuerKey, existing);
    });

  return Array.from(issuerMap.values())
    .map((issuer) => ({
      ...issuer,
      markVsCostMm: issuer.fairValueMm - issuer.amortizedCostMm
    }))
    .sort((a, b) => a.markVsCostMm - b.markVsCostMm);
}

function widestCrossFundMarkDifference() {
  return data.cross_fund_issuer_latest
    .map((issuer) => {
      const marks = issuer.fund_breakdown
        .map((fundRow) => ({
          fund: fundRow.fund,
          pct: fundRow.amortized_cost_mm ? (fundRow.fair_value_mm / fundRow.amortized_cost_mm) * 100 : null
        }))
        .filter((fundRow): fundRow is { fund: Fund; pct: number } => fundRow.pct !== null);

      if (marks.length < 2) return null;

      const highest = marks.reduce((current, row) => (row.pct > current.pct ? row : current), marks[0]);
      const lowest = marks.reduce((current, row) => (row.pct < current.pct ? row : current), marks[0]);

      return {
        issuerName: issuer.representative_issuer_name,
        highest,
        lowest,
        differencePp: highest.pct - lowest.pct
      };
    })
    .filter(
      (
        item
      ): item is {
        issuerName: string;
        highest: { fund: Fund; pct: number };
        lowest: { fund: Fund; pct: number };
        differencePp: number;
      } => item !== null
    )
    .sort((a, b) => b.differencePp - a.differencePp)[0];
}

function signalMatchesFilter(row: IssuerResearchSignal, filter: SignalFilter) {
  if (filter === "all") return true;
  if (filter === "review") return row.priority_band === "review" || row.priority_band === "watch";
  if (filter === "discount") return row.signal_tags.includes("deep_discount") || row.signal_tags.includes("below_cost");
  if (filter === "deterioration") {
    return row.signal_tags.includes("rapid_deterioration") || row.signal_tags.includes("emerging_deterioration");
  }
  if (filter === "disagreement") return row.signal_tags.includes("audited_disagreement");
  if (filter === "crowding") return row.signal_tags.includes("crowded");
  return row.signal_tags.includes("senior_first") || row.signal_tags.includes("junior_first");
}

function SignalChip({ tag }: { tag: SignalTag }) {
  const definition = researchSignals.signal_definitions[tag];
  return (
    <span className={`signal-chip ${tag}`} title={definition.description}>
      {definition.label}
    </span>
  );
}

function SignalRiskMap({
  rows,
  onOpenTimelineIssuer
}: {
  rows: IssuerResearchSignal[];
  onOpenTimelineIssuer: (issuerMatchKey: string) => void;
}) {
  const { tooltip, showTooltip, hideTooltip } = useChartTooltip();
  const chartRows = rows.filter(
    (row): row is IssuerResearchSignal & { latest_fv_to_cost_pct: number; qoq_change_pp: number } =>
      typeof row.latest_fv_to_cost_pct === "number" && typeof row.qoq_change_pp === "number"
  );
  const width = 760;
  const height = 380;
  const margin = { top: 24, right: 28, bottom: 48, left: 58 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  const xMin = 50;
  const xMax = 110;
  const yMin = -35;
  const yMax = 10;
  const x = (value: number) => margin.left + ((Math.max(xMin, Math.min(xMax, value)) - xMin) / (xMax - xMin)) * innerWidth;
  const y = (value: number) => margin.top + ((yMax - Math.max(yMin, Math.min(yMax, value))) / (yMax - yMin)) * innerHeight;
  const maximumFairValue = Math.max(...chartRows.map((row) => row.fair_value_mm), 1);
  const xTicks = [50, 60, 70, 80, 90, 100, 110];
  const yTicks = [-30, -20, -10, 0, 10];
  const labelledKeys = new Set(chartRows.slice(0, 6).map((row) => row.issuer_match_key));

  return (
    <div className="signal-map-shell" onMouseLeave={hideTooltip}>
      <svg
        className="signal-map"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Cross-fund issuer signal map. Horizontal position is latest fair value to cost; vertical position is quarter-over-quarter change. Larger points represent larger fair value."
      >
        <title>Cross-fund issuer signal map</title>
        <desc>Issuers further left trade at deeper discounts. Issuers lower on the chart deteriorated more in the latest quarter.</desc>
        {xTicks.map((tick) => (
          <g key={`signal-x-${tick}`}>
            <line className={tick === 100 ? "signal-map-par" : "signal-map-grid"} x1={x(tick)} x2={x(tick)} y1={margin.top} y2={height - margin.bottom} />
            <text className="signal-map-axis" x={x(tick)} y={height - margin.bottom + 20} textAnchor="middle">{tick}%</text>
          </g>
        ))}
        {yTicks.map((tick) => (
          <g key={`signal-y-${tick}`}>
            <line className={tick === 0 ? "signal-map-par" : "signal-map-grid"} x1={margin.left} x2={width - margin.right} y1={y(tick)} y2={y(tick)} />
            <text className="signal-map-axis" x={margin.left - 12} y={y(tick) + 4} textAnchor="end">{tick > 0 ? "+" : ""}{tick}pp</text>
          </g>
        ))}
        <text className="signal-map-caption" x={margin.left} y={14}>IMPROVING</text>
        <text className="signal-map-caption" x={margin.left} y={height - 8}>DETERIORATING</text>
        <text className="signal-map-title" x={margin.left + innerWidth / 2} y={height - 8} textAnchor="middle">Latest FV / cost →</text>
        {chartRows.map((row) => {
          const radius = 4 + Math.sqrt(row.fair_value_mm / maximumFairValue) * 8;
          return (
            <a
              className="signal-map-point"
              data-band={row.priority_band}
              href="#timeline"
              key={row.issuer_match_key}
              aria-label={`${row.display_name}: priority ${row.priority_score}, ${formatPct(row.latest_fv_to_cost_pct, 1)} of cost, ${formatSignedPp(row.qoq_change_pp)} quarter change`}
              onClick={(event) => {
                event.preventDefault();
                onOpenTimelineIssuer(row.issuer_match_key);
              }}
            >
              <circle
                className={`signal-map-dot band-${row.priority_band}`}
                cx={x(row.latest_fv_to_cost_pct)}
                cy={y(row.qoq_change_pp)}
                r={radius}
                onMouseMove={(event) =>
                  showTooltip(event, {
                    title: row.display_name,
                    value: `${formatPct(row.latest_fv_to_cost_pct, 1)} of cost`,
                    detail: `${formatSignedPp(row.qoq_change_pp)} QoQ · ${formatMm(row.fair_value_mm)} · ${row.fund_count} funds`
                  })
                }
              />
              {labelledKeys.has(row.issuer_match_key) ? (
                <text
                  className="signal-map-label"
                  x={x(row.latest_fv_to_cost_pct) + radius + 5}
                  y={y(row.qoq_change_pp) - radius - 3}
                >
                  {row.display_name}
                </text>
              ) : null}
            </a>
          );
        })}
      </svg>
      <ChartTooltip tooltip={tooltip} />
    </div>
  );
}

function ResearchSignalBriefing({
  selectedFund,
  onOpenTimelineIssuer
}: {
  selectedFund: Fund | "All";
  onOpenTimelineIssuer: (issuerMatchKey: string) => void;
}) {
  const [signalFilter, setSignalFilter] = useState<SignalFilter>("all");
  const [signalQuery, setSignalQuery] = useState("");
  const scopeRows = researchSignals.issuer_signals.filter(
    (row) => selectedFund === "All" || row.funds.includes(selectedFund)
  );
  const normalizedQuery = signalQuery.trim().toLowerCase();
  const filteredRows = scopeRows.filter((row) => {
    if (!signalMatchesFilter(row, signalFilter)) return false;
    if (!normalizedQuery) return true;
    return [row.display_name, row.mapped_company, row.issuer_match_key, row.funds.join(" "), row.signal_tags.join(" ")]
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery);
  });
  const visibleRows = filteredRows.slice(0, 12);
  const priorityRows = scopeRows.filter((row) => row.priority_band === "review" || row.priority_band === "watch");
  const priorityFairValue = sumBy(priorityRows, (row) => row.fair_value_mm);
  const materialRows = scopeRows.filter((row) => row.fair_value_mm >= 20);
  const largestDecline = materialRows
    .filter((row) => typeof row.qoq_change_pp === "number")
    .sort((a, b) => Number(a.qoq_change_pp) - Number(b.qoq_change_pp))[0];
  const largestDiscount = materialRows
    .filter((row) => typeof row.latest_fv_to_cost_pct === "number")
    .sort((a, b) => Number(a.latest_fv_to_cost_pct) - Number(b.latest_fv_to_cost_pct))[0];
  const widestGap = scopeRows
    .filter((row) => typeof row.audited_same_facility_gap_pp === "number")
    .sort((a, b) => Number(b.audited_same_facility_gap_pp) - Number(a.audited_same_facility_gap_pp))[0];
  const mostCrowded = [...scopeRows].sort((a, b) => b.fund_count - a.fund_count || b.fair_value_mm - a.fair_value_mm)[0];

  return (
    <section className="signal-briefing" aria-labelledby="signal-briefing-title">
      <header className="signal-briefing-header">
        <div>
          <span className="research-kicker">Decision layer / {selectedFund === "All" ? "cross-fund" : selectedFund}</span>
          <h2 id="signal-briefing-title">Where the portfolio needs attention</h2>
          <p>
            One queue combines discount, change, audited same-loan disagreement, materiality, and ownership breadth.
            Structural differences remain separate from directly comparable loan marks.
          </p>
        </div>
        <div className="signal-briefing-count">
          <span>Priority exposure</span>
          <strong>{formatMm(priorityFairValue)}</strong>
          <small>{formatNumber(priorityRows.length)} review or watch issuers</small>
        </div>
      </header>

      <div className="signal-headlines">
        <button className="signal-headline" type="button" onClick={() => largestDecline && onOpenTimelineIssuer(largestDecline.issuer_match_key)}>
          <span>Largest material decline</span>
          <strong>{largestDecline?.display_name || "No comparable quarter"}</strong>
          <small>{largestDecline ? `${formatSignedPp(largestDecline.qoq_change_pp)} QoQ · ${formatMm(largestDecline.fair_value_mm)}` : "—"}</small>
        </button>
        <button className="signal-headline" type="button" onClick={() => largestDiscount && onOpenTimelineIssuer(largestDiscount.issuer_match_key)}>
          <span>Deepest material discount</span>
          <strong>{largestDiscount?.display_name || "No cost mark"}</strong>
          <small>{largestDiscount ? `${formatPct(largestDiscount.latest_fv_to_cost_pct, 1)} of cost · ${formatMm(largestDiscount.fair_value_mm)}` : "—"}</small>
        </button>
        <button className="signal-headline" type="button" onClick={() => widestGap && onOpenTimelineIssuer(widestGap.issuer_match_key)}>
          <span>Widest audited loan gap</span>
          <strong>{widestGap?.display_name || "No matched loan"}</strong>
          <small>{widestGap ? `${formatPct(widestGap.audited_same_facility_gap_pp, 1)} · ${widestGap.audited_fund_pair}` : "—"}</small>
        </button>
        <button className="signal-headline" type="button" onClick={() => mostCrowded && onOpenTimelineIssuer(mostCrowded.issuer_match_key)}>
          <span>Most widely held</span>
          <strong>{mostCrowded?.display_name || "No overlap"}</strong>
          <small>{mostCrowded ? `${mostCrowded.fund_count} funds · ${formatMm(mostCrowded.fair_value_mm)}` : "—"}</small>
        </button>
      </div>

      <div className="signal-controls">
        <div className="view-switch signal-filter-row" aria-label="Research signal filter">
          {([
            ["all", "All"],
            ["review", "Priority"],
            ["discount", "Discount"],
            ["deterioration", "Deterioration"],
            ["disagreement", "Loan gaps"],
            ["crowding", "Crowding"],
            ["structure", "Structure"]
          ] as Array<[SignalFilter, string]>).map(([value, label]) => (
            <button key={value} type="button" className={signalFilter === value ? "active" : ""} onClick={() => setSignalFilter(value)}>
              {label}
            </button>
          ))}
        </div>
        <div className="search-wrap compact-search">
          <Search />
          <input
            className="search signal-search"
            value={signalQuery}
            onChange={(event) => setSignalQuery(event.target.value)}
            placeholder="Search company, fund, or signal"
            aria-label="Search research signals"
          />
        </div>
      </div>

      <div className="signal-workbench">
        <div className="signal-map-column">
          <div className="signal-section-heading">
            <div>
              <span>Change vs. valuation</span>
              <h3>Signal map</h3>
            </div>
            <small>Left is cheaper · lower is deteriorating · size is fair value</small>
          </div>
          <SignalRiskMap rows={filteredRows} onOpenTimelineIssuer={onOpenTimelineIssuer} />
        </div>

        <div className="signal-queue-column">
          <div className="signal-section-heading">
            <div>
              <span>Ranked for review</span>
              <h3>Issuer queue</h3>
            </div>
            <small>{formatNumber(filteredRows.length)} matches</small>
          </div>
          <div className="signal-queue">
            {visibleRows.map((row) => (
              <button className="signal-queue-row" type="button" key={row.issuer_match_key} onClick={() => onOpenTimelineIssuer(row.issuer_match_key)}>
                <span className={`signal-score ${row.priority_band}`}>{Math.round(row.priority_score)}</span>
                <span className="signal-queue-name">
                  <strong>{row.display_name}</strong>
                  <small>{row.funds.join(" · ")} · {formatMm(row.fair_value_mm)}</small>
                  <span className="signal-chip-row">
                    {row.signal_tags.filter((tag) => tag !== "stable_context").slice(0, 2).map((tag) => <SignalChip key={`${row.issuer_match_key}-${tag}`} tag={tag} />)}
                  </span>
                </span>
                <span className="signal-queue-metric">
                  <strong>{formatPct(row.latest_fv_to_cost_pct, 1)}</strong>
                  <small>{formatSignedPp(row.qoq_change_pp)}</small>
                </span>
                <ArrowUpRight />
              </button>
            ))}
          </div>
          {!visibleRows.length ? <div className="empty-state">No issuer signals match this research view.</div> : null}
        </div>
      </div>

      <footer className="signal-method">
        <strong>Method note</strong>
        <p><b>Triage, not a rating.</b> {researchSignals.meta.methodology}</p>
      </footer>
    </section>
  );
}

function KeyObservations() {
  const fundedLatestRows = data.holdings_detail_latest.filter((row) => row.exposure_type === "funded");
  const fundedFairValue = sumBy(fundedLatestRows, (row) => row.fair_value_mm);
  const fundedCost = sumBy(fundedLatestRows, (row) => row.amortized_cost_mm);
  const fundedMarkGap = fundedFairValue - fundedCost;
  const fskFundedMarkGap = sumBy(
    fundedLatestRows.filter((row) => row.fund === "FSK"),
    (row) => row.mark_vs_cost_mm
  );
  const fskGapShare = fundedMarkGap ? (Math.abs(fskFundedMarkGap) / Math.abs(fundedMarkGap)) * 100 : null;
  const fskPressureNames = issuerMarkPressure("FSK")
    .slice(0, 2)
    .map((issuer) => `${issuer.issuerName} (${formatMm(issuer.markVsCostMm)})`)
    .join(" and ");
  const concentrationByFund = new Map(data.issuer_concentration.map((row) => [row.fund, row]));
  const crossFundDifference = widestCrossFundMarkDifference();
  const fskUnfundedTimelineRows = data.loan_timeline_securities.filter(
    (row) => row.fund === "FSK" && row.exposure_type === "unfunded_commitment"
  );
  const currentFskUnfundedTimelineRows = fskUnfundedTimelineRows.filter(
    (row) => row.filing_period_end === data.meta.latest_common_period
  );
  const currentFskUnfundedPrincipal = sumBy(currentFskUnfundedTimelineRows, (row) => row.principal_mm);
  const totalFirstLienFairValue = sumBy(
    data.category_totals_latest.filter((row) => row.investment_category === "First Lien Debt"),
    (row) => row.fair_value_mm
  );
  const latestFundedCategoryFairValue = sumBy(data.category_totals_latest, (row) => row.fair_value_mm);
  const totalFirstLienShare = latestFundedCategoryFairValue ? (totalFirstLienFairValue / latestFundedCategoryFairValue) * 100 : null;
  const fskCategoryRows = data.category_latest.filter((row) => row.fund === "FSK");
  const fskFirstLienFairValue = sumBy(
    fskCategoryRows.filter((row) => row.investment_category === "First Lien Debt"),
    (row) => row.fair_value_mm
  );
  const fskOtherFundedCategoryFairValue = sumBy(
    fskCategoryRows.filter((row) => row.investment_category !== "First Lien Debt"),
    (row) => row.fair_value_mm
  );

  return (
    <Panel
      title={`Key Observations as of ${formatSlashDate(data.meta.latest_common_period)}`}
      subtitle="Quantitative read from the latest common-period eight-fund verified dataset."
      icon={Info}
    >
      <ul className="observations-list">
        <li>
          <strong>{formatMm(fundedFairValue)}</strong> of funded fair value sits{" "}
          <strong>{formatMm(Math.abs(fundedMarkGap))}</strong> below amortized cost; FSK accounts for{" "}
          <strong>{formatPct(fskGapShare)}</strong> of that funded gap, led by {fskPressureNames}.
        </li>
        <li>
          Concentration diverges sharply: FSK top-5 issuer exposure is{" "}
          <strong>{formatPct(concentrationByFund.get("FSK")?.top_5_pct)}</strong> of fair value, versus{" "}
          <strong>{formatPct(concentrationByFund.get("BXSL")?.top_5_pct)}</strong> at BXSL and{" "}
          <strong>{formatPct(concentrationByFund.get("TSLX")?.top_5_pct)}</strong> at TSLX.
        </li>
        <li>
          Normalized issuer matching finds <strong>{formatNumber(data.cross_fund_issuer_latest.length)}</strong>{" "}
          cross-fund issuers versus <strong>{formatNumber(data.raw_cross_fund_issuer_count_latest)}</strong> raw
          display-name matches; {crossFundDifference?.issuerName} has the widest current FV/cost split at{" "}
          <strong>{formatPct(crossFundDifference?.highest.pct)}</strong> in {crossFundDifference?.highest.fund} and{" "}
          <strong>{formatPct(crossFundDifference?.lowest.pct)}</strong> in {crossFundDifference?.lowest.fund}.
        </li>
        <li>
          FSK is the only fund with tagged unfunded commitments in the timeline layer:{" "}
          <strong>{formatNumber(fskUnfundedTimelineRows.length)}</strong> rows across history, including{" "}
          <strong>{formatNumber(currentFskUnfundedTimelineRows.length)}</strong> current-period rows and{" "}
          <strong>{formatMm(currentFskUnfundedPrincipal)}</strong> of principal at {data.meta.latest_period_label}.
        </li>
        <li>
          First-lien loans are <strong>{formatMm(totalFirstLienFairValue)}</strong>, or{" "}
          <strong>{formatPct(totalFirstLienShare)}</strong>{" "}
          of funded category fair value, but FSK&apos;s funded category mix is
          less senior: <strong>{formatMm(fskFirstLienFairValue)}</strong> first-lien versus{" "}
          <strong>{formatMm(fskOtherFundedCategoryFairValue)}</strong> in other funded categories.
        </li>
      </ul>
    </Panel>
  );
}

function Overview({
  selectedFund,
  onOpenTimelineIssuer
}: {
  selectedFund: Fund | "All";
  onOpenTimelineIssuer: (issuerMatchKey: string) => void;
}) {
  const isAllFunds = selectedFund === "All";
  const visibleLatest = data.latest_by_fund.filter((item) => isAllFunds || item.fund === selectedFund);
  const visibleChanges = data.change_by_fund.filter((item) => isAllFunds || item.fund === selectedFund);
  const latestTotal = sumBy(visibleLatest, (item) => item.fair_value_mm);
  const latestRows = sumBy(visibleLatest, (item) => item.holding_rows);
  const latestMark = sumBy(visibleLatest, (item) => item.mark_vs_cost_mm);
  const totalChange = sumBy(visibleChanges, (item) => item.change_mm);
  const priorTotal = sumBy(visibleChanges, (item) => item.prior_fair_value_mm);
  const totalChangePct = priorTotal ? (totalChange / priorTotal) * 100 : null;
  const crossFundIssuerRows = isAllFunds
    ? data.cross_fund_issuer_latest
    : data.cross_fund_issuer_latest.filter((row) => row.funds.includes(selectedFund));
  const categoryRows = isAllFunds
    ? data.category_totals_latest.map((item) => ({
        ...item,
        label: item.investment_category
      }))
    : data.category_latest
        .filter((item) => item.fund === selectedFund)
        .map((item) => ({ ...item, label: item.investment_category || "Uncategorized" }));
  const concentrationRows = data.issuer_concentration.filter((row) => isAllFunds || row.fund === selectedFund);
  const selectedName = isAllFunds ? "the eight-fund verified view" : selectedFund;
  const overviewNarrative = isAllFunds
    ? data.narrative.overview
    : `${selectedFund}'s latest common-period fair value is ${formatMm(latestTotal)} across ${formatNumber(
        latestRows
      )} holding rows, with mark vs cost of ${formatMm(latestMark)}. The fund appears in ${formatNumber(
        crossFundIssuerRows.length
      )} normalized cross-fund issuer match groups.`;

  return (
    <div className="grid">
      <ResearchSignalBriefing selectedFund={selectedFund} onOpenTimelineIssuer={onOpenTimelineIssuer} />

      <div className="grid kpi-grid">
        <MetricCard
          title="Latest fair value"
          value={formatMm(latestTotal)}
          note={`${isAllFunds ? `across ${funds.length} funds` : `for ${selectedFund}`} at ${data.meta.latest_period_label}.`}
          icon={WalletCards}
          delta={totalChangePct}
        />
        <MetricCard
          title="Holding rows"
          value={formatNumber(latestRows)}
          note={`${isAllFunds ? "across selected funds" : `for ${selectedFund}`} in the latest common period.`}
          icon={Layers3}
        />
        <MetricCard
          title="Mark vs cost"
          value={formatMm(latestMark)}
          note="latest fair value less amortized cost."
          icon={TrendingUp}
        />
        <MetricCard
          title={isAllFunds ? "Cross-fund issuers" : "Overlap issuers"}
          value={formatNumber(crossFundIssuerRows.length)}
          note={
            isAllFunds
              ? `${data.raw_cross_fund_issuer_count_latest} groups if joined on display names only.`
              : `normalized groups where ${selectedFund} overlaps another verified fund.`
          }
          icon={FileSearch}
        />
      </div>

      <Callout title={isAllFunds ? "Portfolio read" : `${selectedFund} portfolio read`}>{overviewNarrative}</Callout>

      <OverviewTrendCharts selectedFund={selectedFund} />

      <div className="grid two-col">
        <Panel
          title={isAllFunds ? "Latest Fund Snapshot" : `${selectedFund} Latest Snapshot`}
          subtitle="Current common period only, so the comparison is clean across the selected scope."
          icon={BarChart3}
        >
          <FundLatestCards selectedFund={selectedFund} />
        </Panel>

        <Panel
          title="Largest Current Categories"
          subtitle={`${isAllFunds ? "Normalized across source category and instrument labels" : `${selectedFund} normalized category view`} at the latest common period.`}
          icon={Layers3}
        >
          <BarList
            items={categoryRows as unknown as Array<Record<string, unknown>>}
            getLabel={(item) => String(item.label)}
            getValue={(item) => Number(item.fair_value_mm || 0)}
            color={isAllFunds ? "#2563eb" : fundColors[selectedFund]}
          />
        </Panel>
      </div>

      <Panel
        title="Concentration Read"
        subtitle={`Top issuer exposure is shown after normalized issuer-match aggregation for ${selectedName}.`}
        icon={Gauge}
      >
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Fund</th>
                <th className="right">Top 5</th>
                <th className="right">Top 5 %</th>
                <th className="right">Top 10</th>
                <th className="right">Top 10 %</th>
              </tr>
            </thead>
            <tbody>
              {concentrationRows.map((row) => (
                <tr key={row.fund}>
                  <td>
                    <FundBadge fund={row.fund} />
                  </td>
                  <td className="right">{formatMm(row.top_5_fair_value_mm)}</td>
                  <td className="right">{formatPct(row.top_5_pct)}</td>
                  <td className="right">{formatMm(row.top_10_fair_value_mm)}</td>
                  <td className="right">{formatPct(row.top_10_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function Deterioration({ selectedFund }: { selectedFund: Fund | "All" }) {
  const [deteriorationExposureFilter, setDeteriorationExposureFilter] =
    useState<DeteriorationExposureFilter>("All");
  if (selectedFund !== "All" && !institutionalFunds.includes(selectedFund)) {
    return (
      <div className="grid">
        <Callout title={`${selectedFund} deterioration model is not backfilled yet`}>
          Holdings marks and issuer timelines are available for {selectedFund}. The presentation- and filing-enriched
          non-accrual/watchlist model currently covers BXSL, FSK, and TSLX, so this screen does not infer missing credit
          statuses for funds outside the three-fund institutional facts layer.
        </Callout>
      </div>
    );
  }
  const selectedWatchlistRows = quarterlyFacts.issuer_watchlist_facts.filter(
    (row) => selectedFund === "All" || row.fund === selectedFund
  );
  const selectedIssuerHistoryRows = data.issuer_period_history.filter(
    (row) => selectedFund === "All" || row.fund === selectedFund
  );
  const trendMetricsByRow = buildDeteriorationTrendMetricsMap(selectedIssuerHistoryRows);
  const historyRowsByFundIssuerPeriod = new Map(
    selectedIssuerHistoryRows.map((row) => [`${row.fund}|${row.issuer_match_key}|${row.filing_period_end}`, row])
  );
  const latestWatchlistRowsByFundKey = new Map(
    selectedWatchlistRows
      .filter((row) => row.period_end === quarterlyFacts.meta.latest_period_end)
      .map((row) => [`${row.fund}|${row.issuer_match_key}`, row])
  );
  const latestWatchlistRowsByFundIssuerName = new Map(
    selectedWatchlistRows
      .filter((row) => row.period_end === quarterlyFacts.meta.latest_period_end)
      .map((row) => [`${row.fund}|${normalizeIssuerForSourceCheck(row.issuer_name)}`, row])
  );
  const latestNonAccrualNameKeys = new Set(
    quarterlyFacts.non_accrual_issuer_facts
      .filter((row) => row.period_end === quarterlyFacts.meta.latest_period_end && (selectedFund === "All" || row.fund === selectedFund))
      .map((row) => `${row.fund}|${normalizeIssuerForSourceCheck(row.issuer_name)}`)
  );
  const latestPreNonAccrualRows = selectedIssuerHistoryRows
    .filter(
      (row) =>
        row.filing_period_end === quarterlyFacts.meta.latest_period_end &&
        Number(row.fair_value_mm || 0) >= deteriorationFairValueFloorMm
    )
    .map((row) => {
      const watchRow =
        latestWatchlistRowsByFundKey.get(`${row.fund}|${row.issuer_match_key}`) ||
        latestWatchlistRowsByFundIssuerName.get(`${row.fund}|${normalizeIssuerForSourceCheck(row.representative_issuer_name)}`);
      const priorPeriod = previousQuarterEnd(row.filing_period_end, 1);
      const priorRow = priorPeriod ? historyRowsByFundIssuerPeriod.get(`${row.fund}|${row.issuer_match_key}|${priorPeriod}`) : undefined;
      const trend = trendMetricsByRow.get(
        deteriorationTrendKey({
          fund: row.fund,
          issuer_match_key: row.issuer_match_key,
          period_end: row.filing_period_end
        })
      ) || emptyDeteriorationTrendMetrics();
      return buildHistoryCandidateRow(row, trend, priorRow, watchRow);
    })
    .filter(
      (row) =>
        !row.is_non_accrual &&
        !latestNonAccrualNameKeys.has(`${row.fund}|${normalizeIssuerForSourceCheck(row.issuer_name)}`) &&
        (trendMetricsByRow.get(deteriorationTrendKey(row)) || emptyDeteriorationTrendMetrics()).sustained_deterioration
    );
  const hasSustainedRowTrend = (row: IssuerWatchlistFactRow) =>
    (trendMetricsByRow.get(deteriorationTrendKey(row)) || emptyDeteriorationTrendMetrics()).sustained_deterioration;
  const costQualifiedRows = latestPreNonAccrualRows.filter(
    (row) => Number(row.amortized_cost_mm || 0) >= deteriorationCostFloorMm
  );
  const sustainedCandidateRows = costQualifiedRows.filter(hasSustainedRowTrend);
  const singleQuarterOnlyRows = selectedWatchlistRows.filter(
    (row) =>
      row.period_end === quarterlyFacts.meta.latest_period_end &&
      !row.is_non_accrual &&
      hasPreNonAccrualDeteriorationSignal(row) &&
      Number(row.fair_value_mm || 0) >= deteriorationFairValueFloorMm &&
      Number(row.amortized_cost_mm || 0) >= deteriorationCostFloorMm &&
      !hasSustainedRowTrend(row)
  );
  const deteriorationCleanupRows = latestPreNonAccrualRows
    .filter((row) => Number(row.amortized_cost_mm || 0) < deteriorationCostFloorMm && hasSustainedRowTrend(row))
    .sort((a, b) => Number(a.amortized_cost_mm || 0) - Number(b.amortized_cost_mm || 0));
  const deteriorationGroups = buildDeteriorationGroups(
    sustainedCandidateRows,
    data.holdings_detail_latest.filter((row) => selectedFund === "All" || row.fund === selectedFund),
    latestNonAccrualNameKeys,
    trendMetricsByRow
  );
  const filteredDeteriorationGroups = deteriorationGroups.filter(
    (group) => deteriorationExposureFilter === "All" || group.instrument_bucket === deteriorationExposureFilter
  );
  const deteriorationCandidateFairValue = sumBy(filteredDeteriorationGroups, (group) => group.fair_value_mm);
  const deteriorationShadowCount = filteredDeteriorationGroups.filter((group) => group.shadow_non_accrual).length;
  const crossFundDeteriorationCount = filteredDeteriorationGroups.filter((group) => group.funds.length > 1).length;
  const largestTwoQuarterDeterioration = minDefined(
    filteredDeteriorationGroups.map((group) => group.two_quarter_fv_to_cost_change_pct)
  );
  const largestThreeQuarterDeterioration = minDefined(
    filteredDeteriorationGroups.map((group) => group.three_quarter_fv_to_cost_change_pct)
  );

  return (
    <div className="grid">
      <Callout title="Inclusion rule">
        The main table is latest-period, accruing-only, at least ${deteriorationFairValueFloorMm}mm fair value and ${deteriorationCostFloorMm}mm cost, with sustained 2-3 quarter FV/cost deterioration where the central holdings history has enough observations. Single-quarter-only marks stay out of the main table.
      </Callout>

      <Panel
        title="Sustained Deterioration Before Non-Accrual"
        subtitle={`${filteredDeteriorationGroups.length} latest-period accruing issuer groups after multi-quarter trend, fair-value, and cost filters; ${singleQuarterOnlyRows.length} single-quarter-only rows are excluded.`}
        icon={AlertTriangle}
        action={
          <div className="panel-controls">
            <select
              className="select"
              value={deteriorationExposureFilter}
              onChange={(event) => setDeteriorationExposureFilter(event.target.value as DeteriorationExposureFilter)}
              title="Deterioration instrument bucket"
            >
              {deteriorationExposureFilters.map((filter) => (
                <option key={filter.value} value={filter.value}>
                  {filter.label}
                </option>
              ))}
            </select>
          </div>
        }
      >
        <div className="deterioration-summary-grid">
          <div className="micro-stat">
            <span>Candidate FV</span>
            <strong>{formatMm(deteriorationCandidateFairValue)}</strong>
          </div>
          <div className="micro-stat">
            <span>Shadow rows</span>
            <strong>{formatNumber(deteriorationShadowCount)}</strong>
          </div>
          <div className="micro-stat">
            <span>Cross-fund</span>
            <strong>{formatNumber(crossFundDeteriorationCount)}</strong>
          </div>
          <div className="micro-stat">
            <span>Worst 2Q trend</span>
            <strong>{formatSignedPp(largestTwoQuarterDeterioration)}</strong>
          </div>
          <div className="micro-stat">
            <span>Worst 3Q trend</span>
            <strong>{formatSignedPp(largestThreeQuarterDeterioration)}</strong>
          </div>
          <div className="micro-stat">
            <span>Single-Q excluded</span>
            <strong>{formatNumber(singleQuarterOnlyRows.length)}</strong>
          </div>
          <div className="micro-stat">
            <span>Cleanup rows</span>
            <strong>{formatNumber(deteriorationCleanupRows.length)}</strong>
          </div>
        </div>

        {filteredDeteriorationGroups.length ? (
          <div className="table-wrap">
            <table className="compact-wide-table deterioration-table">
              <thead>
                <tr>
                  <th className="right">Rank</th>
                  <th>Issuer</th>
                  <th>Funds</th>
                  <th>Instrument</th>
                  <th>Severity</th>
                  <th className="right">Rows</th>
                  <th className="right">Cost</th>
                  <th className="right">Fair value</th>
                  <th className="right">FV / cost</th>
                  <th className="right">QoQ FV / cost</th>
                  <th className="right">2Q FV / cost</th>
                  <th className="right">3Q FV / cost</th>
                  <th className="right">QoQ FV</th>
                  <th>NA status</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {filteredDeteriorationGroups.map((group, index) => (
                  <tr key={`${group.issuer_match_key}-pre-non-accrual`}>
                    <td className="right">{formatNumber(index + 1)}</td>
                    <td className="issuer-cell">
                      <strong>{group.issuer_name}</strong>
                      <span>{group.category_label}</span>
                    </td>
                    <td>
                      <div className="badge-row">
                        {group.funds.map((fund) => (
                          <FundBadge fund={fund} key={`${group.issuer_match_key}-${fund}-deterioration`} />
                        ))}
                      </div>
                    </td>
                    <td className="issuer-cell">
                      <strong>{group.instrument_label}</strong>
                      <span>{group.rate_label}; {group.maturity_label}</span>
                      <span className={`pill ${group.instrument_bucket === "Debt" ? "ok" : "warn"}`}>
                        {group.instrument_bucket}
                      </span>
                    </td>
                    <td>
                      <span className={`pill ${group.severity_label === "High" ? "danger" : group.severity_label === "Elevated" ? "warn" : ""}`}>
                        {group.severity_label}
                      </span>
                    </td>
                    <td className="right">{formatNumber(group.security_count)}</td>
                    <td className="right">{formatMm(group.amortized_cost_mm)}</td>
                    <td className="right">{formatMm(group.fair_value_mm)}</td>
                    <td className="right">{formatPct(group.fv_to_cost_pct)}</td>
                    <td className="right">{formatSignedPp(group.qoq_fv_to_cost_change_pct)}</td>
                    <td className="right">{formatSignedPp(group.two_quarter_fv_to_cost_change_pct)}</td>
                    <td className="right">{formatSignedPp(group.three_quarter_fv_to_cost_change_pct)}</td>
                    <td className="right">{formatMm(group.qoq_fair_value_change_mm)}</td>
                    <td>
                      <span className={`pill ${group.source_non_accrual_match ? "warn" : "ok"}`}>
                        {group.source_non_accrual_match ? "Review NA table" : "Not in NA table"}
                      </span>
                    </td>
                    <td className="issuer-cell">
                      <strong>{group.trend_label}</strong>
                      <span>{group.reason}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">No sustained pre-non-accrual deterioration rows match the current filters.</div>
        )}

        {deteriorationCleanupRows.length ? (
          <div className="deterioration-cleanup">
            <h3>Cost-Basis Cleanup</h3>
            <div className="table-wrap">
              <table className="compact-wide-table">
                <thead>
                  <tr>
                    <th>Fund</th>
                    <th>Issuer</th>
                    <th>Bucket</th>
                    <th className="right">Cost</th>
                    <th className="right">Fair value</th>
                    <th className="right">FV / cost</th>
                    <th className="right">QoQ</th>
                    <th className="right">2Q</th>
                    <th className="right">3Q</th>
                  </tr>
                </thead>
                <tbody>
                  {deteriorationCleanupRows.map((row) => {
                    const metrics = trendMetricsByRow.get(deteriorationTrendKey(row)) || emptyDeteriorationTrendMetrics();
                    return (
                      <tr key={`${row.fund}-${row.issuer_match_key}-cleanup`}>
                        <td>
                          <FundBadge fund={row.fund} />
                        </td>
                        <td className="issuer-cell">
                          <strong>{row.issuer_name}</strong>
                          <span>{row.issuer_industries || row.issuer_match_key}</span>
                        </td>
                        <td>{row.watchlist_bucket}</td>
                        <td className="right">{formatMm(row.amortized_cost_mm)}</td>
                        <td className="right">{formatMm(row.fair_value_mm)}</td>
                        <td className="right">{formatPct(row.fv_to_cost_pct)}</td>
                        <td className="right">{formatSignedPp(row.qoq_fv_to_cost_change_pct)}</td>
                        <td className="right">{formatSignedPp(metrics.two_quarter_fv_to_cost_change_pct)}</td>
                        <td className="right">{formatSignedPp(metrics.three_quarter_fv_to_cost_change_pct)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </Panel>
    </div>
  );
}

function Financials({ selectedFund }: { selectedFund: Fund | "All" }) {
  const [watchlistFundFilter, setWatchlistFundFilter] = useState<Fund | "All">("All");
  const [watchlistBucketFilter, setWatchlistBucketFilter] = useState<WatchlistBucketFilter>("All");
  const [watchlistInstrumentFilter, setWatchlistInstrumentFilter] = useState("All");
  const visibleFunds =
    selectedFund === "All"
      ? institutionalFunds
      : institutionalFunds.includes(selectedFund)
        ? [selectedFund]
        : [];
  const rows = quarterlyFacts.rows.filter((row) => selectedFund === "All" || row.fund === selectedFund);
  const latestRows = quarterlyFacts.latest_rows.filter((row) => selectedFund === "All" || row.fund === selectedFund);
  const activityRows = rows
    .filter((row) =>
      [
        row.new_commitments_mm,
        row.fundings_mm,
        row.repayments_sales_mm,
        row.net_investment_activity_mm,
        row.new_investment_yield_pct
      ].some((value) => value !== null && value !== undefined)
    )
    .sort((a, b) => (a.period_end === b.period_end ? a.fund.localeCompare(b.fund) : b.period_end.localeCompare(a.period_end)));
  const activityPeriods = uniqueSorted(activityRows.map((row) => row.period_end));
  const activityRowMap = new Map(activityRows.map((row) => [`${row.fund}|${row.period_end}`, row]));
  const activityNetMax = Math.max(
    1,
    ...activityRows.map((row) => Math.abs(Number(row.net_investment_activity_mm || 0)))
  );
  const quarterlyMarketRows = quarterlyFacts.quarterly_market_facts.filter((row) => selectedFund === "All" || row.fund === selectedFund);
  const incomeExpenseRows = quarterlyFacts.quarterly_income_expense_facts.filter(
    (row) => selectedFund === "All" || row.fund === selectedFund
  );
  const incomeQualityRows = quarterlyFacts.quarterly_income_quality_facts.filter(
    (row) => selectedFund === "All" || row.fund === selectedFund
  );
  const dividendDeclarationRows = quarterlyFacts.dividend_declaration_facts.filter(
    (row) => selectedFund === "All" || row.fund === selectedFund
  );
  const nonAccrualSummaryRows = quarterlyFacts.non_accrual_summary_facts.filter(
    (row) => selectedFund === "All" || row.fund === selectedFund
  );
  const nonAccrualIssuerRows = quarterlyFacts.non_accrual_issuer_facts.filter(
    (row) => selectedFund === "All" || row.fund === selectedFund
  );
  const effectiveWatchlistFund = selectedFund === "All" ? watchlistFundFilter : selectedFund;
  const watchlistVisibleFunds = effectiveWatchlistFund === "All" ? visibleFunds : [effectiveWatchlistFund];
  const rowMap = new Map(quarterlyFacts.rows.map((row) => [`${row.fund}|${row.period_end}`, row]));
  const watchlistInstrumentOptions = uniqueSorted(
    quarterlyFacts.issuer_watchlist_facts
      .filter(
        (row) =>
          (selectedFund === "All" || row.fund === selectedFund) &&
          (effectiveWatchlistFund === "All" || row.fund === effectiveWatchlistFund) &&
          watchlistBucketMatches(row, watchlistBucketFilter)
      )
      .map((row) => row.instrument_context)
      .filter((value): value is string => Boolean(value))
  );
  const effectiveWatchlistInstrumentFilter = watchlistInstrumentOptions.includes(watchlistInstrumentFilter)
    ? watchlistInstrumentFilter
    : "All";
  const issuerWatchlistRows = quarterlyFacts.issuer_watchlist_facts.filter(
    (row) =>
      (selectedFund === "All" || row.fund === selectedFund) &&
      (effectiveWatchlistFund === "All" || row.fund === effectiveWatchlistFund) &&
      watchlistBucketMatches(row, watchlistBucketFilter) &&
      (effectiveWatchlistInstrumentFilter === "All" || row.instrument_context === effectiveWatchlistInstrumentFilter)
  );
  const latestWatchlistRows = issuerWatchlistRows.filter((row) => row.period_end === quarterlyFacts.meta.latest_period_end);
  const latestShadowRows = latestWatchlistRows.filter((row) => row.shadow_non_accrual);
  const watchlistTableRows = issuerWatchlistRows
    .slice()
    .sort((a, b) => {
      if (a.period_end !== b.period_end) return b.period_end.localeCompare(a.period_end);
      if (a.watchlist_severity !== b.watchlist_severity) return a.watchlist_severity - b.watchlist_severity;
      return Number(b.fair_value_mm || 0) - Number(a.fair_value_mm || 0);
    })
    .slice(0, 120);
  const latestPeriodLabel = formatDate(quarterlyFacts.meta.latest_period_end);
  const totalNii = sumBy(latestRows, (row) => row.nii_mm);
  const totalLiquidity = sumBy(latestRows, (row) => row.liquidity_mm);
  const averageBaseCoverage = averageDefined(latestRows.map((row) => row.base_dividend_coverage_pct));
  const averageLatestPriceNav = averageDefined(
    quarterlyMarketRows
      .filter((row) => row.period_end === quarterlyFacts.meta.latest_period_end)
      .map((row) => row.quarter_end_price_to_nav_pct)
  );
  const maxBelow90Pct = maxDefined(
    rows.map((row) =>
      row.holdings_fair_value_mm ? (Number(row.holdings_below_90_fair_value_mm || 0) / row.holdings_fair_value_mm) * 100 : null
    )
  );
  const maxMarkToCost = maxDefined(rows.map((row) => row.holdings_mark_to_cost_pct));
  const periodCount = uniqueSorted(rows.map((row) => row.period_end)).length;
  const seededLatestRows = latestRows.filter((row) => row.source_status.includes("presentation"));
  const latestIncomeQualityNotes = incomeQualityRows
    .filter((row) => row.period_end === quarterlyFacts.meta.latest_period_end)
    .flatMap((row) =>
      parseJsonStringArray(row.one_time_items_json).map((note, index) => ({
        key: `${row.fund}-${row.period_end}-${index}`,
        label: `${row.fund} ${shortPeriod(row.period_end)}`,
        note
      }))
    );

  const getQuarterlyValue = (fund: Fund, period: string, key: keyof QuarterlyFactRow) => {
    const value = rowMap.get(`${fund}|${period}`)?.[key];
    return typeof value === "number" ? value : null;
  };

  const getBelow90Pct = (fund: Fund, period: string) => {
    const row = rowMap.get(`${fund}|${period}`);
    if (!row?.holdings_fair_value_mm) return null;
    return (Number(row.holdings_below_90_fair_value_mm || 0) / row.holdings_fair_value_mm) * 100;
  };

  const getWatchlistTrendPct = (fund: Fund, period: string) => {
    const row = rowMap.get(`${fund}|${period}`);
    if (!row?.holdings_fair_value_mm) return null;
    const flaggedFairValue = sumBy(
      issuerWatchlistRows.filter((item) => item.fund === fund && item.period_end === period),
      (item) => item.fair_value_mm
    );
    return (flaggedFairValue / row.holdings_fair_value_mm) * 100;
  };

  const watchlistTrendPeriods = quarterlyFacts.meta.periods.filter((period) =>
    watchlistVisibleFunds.some((fund) => getWatchlistTrendPct(fund, period) !== null)
  );
  const maxWatchlistTrendPct = maxDefined(
    watchlistTrendPeriods.flatMap((period) => watchlistVisibleFunds.map((fund) => getWatchlistTrendPct(fund, period)))
  );
  const nonAccrualSummaryMap = new Map(nonAccrualSummaryRows.map((row) => [`${row.fund}|${row.period_end}`, row]));
  const getReportedNonAccrualFvPct = (fund: Fund, period: string) => {
    const value = nonAccrualSummaryMap.get(`${fund}|${period}`)?.reported_non_accrual_fv_pct;
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  };
  const nonAccrualTrendPeriods = quarterlyFacts.meta.periods.filter((period) =>
    visibleFunds.some((fund) => getReportedNonAccrualFvPct(fund, period) !== null)
  );
  const maxReportedNonAccrualFvPct = maxDefined(
    nonAccrualTrendPeriods.flatMap((period) => visibleFunds.map((fund) => getReportedNonAccrualFvPct(fund, period)))
  );
  const reportedNonAccrualFvAxisMax = Math.max(5, Math.ceil(Number(maxReportedNonAccrualFvPct || 1)));
  const reportedNonAccrualFvTicks = Array.from(
    { length: reportedNonAccrualFvAxisMax + 1 },
    (_, index) => reportedNonAccrualFvAxisMax - index
  );

  const navPeriods = quarterlyFacts.meta.periods.filter((period) =>
    visibleFunds.some((fund) => getQuarterlyValue(fund, period, "nav_per_share") !== null)
  );
  const navValues = navPeriods.flatMap((period) =>
    visibleFunds
      .map((fund) => getQuarterlyValue(fund, period, "nav_per_share"))
      .filter((value): value is number => value !== null)
  );
  const navAxisMin = navValues.length ? Math.max(0, Math.floor(Math.min(...navValues) / 5) * 5) : 0;
  const navAxisMax = navValues.length ? Math.ceil(Math.max(...navValues) / 5) * 5 : 30;
  const navAxisTicks = Array.from({ length: Math.max(2, Math.round((navAxisMax - navAxisMin) / 5) + 1) }, (_, index) => navAxisMax - index * 5).filter(
    (tick) => tick >= navAxisMin
  );

  if (selectedFund !== "All" && !institutionalFunds.includes(selectedFund)) {
    return (
      <div className="grid">
        <Callout title={`${selectedFund} financial facts are not backfilled yet`}>
          Verified holdings, issuer exposure, marks, rates, and timeline data are available for {selectedFund}. The
          presentation-sourced financial, dividend, non-accrual, and market-price model currently covers BXSL, FSK, and
          TSLX only, so this tab stays blank rather than substituting unsourced values.
        </Callout>
      </div>
    );
  }

  return (
    <div className="grid">
      <nav className="jump-links" aria-label="Financials tables">
        <a href="#financials-snapshot">Financial snapshot</a>
        <a href="#income-quality-bridge">Income quality</a>
        <a href="#dividend-declarations">Dividends</a>
        <a href="#income-expense-facts">Income / expense</a>
        <a href="#non-accrual-summary">Non-accrual summary</a>
        <a href="#issuer-watchlist">Issuer watchlist</a>
        <a href="#non-accrual-issuers">Non-accrual issuers</a>
        <a href="#quarterly-market-facts">Market facts</a>
        <a href="#portfolio-quality-screeners">Portfolio quality</a>
        <a href="#originations-repayments">Originations / repayments</a>
      </nav>

      <div className="grid kpi-grid">
        <MetricCard
          title="Q1 NII"
          value={formatMm(totalNii)}
          note={`${seededLatestRows.length} selected fund${seededLatestRows.length === 1 ? "" : "s"} presentation-backed for ${latestPeriodLabel}.`}
          icon={WalletCards}
        />
        <MetricCard
          title="Base coverage"
          value={formatPct(averageBaseCoverage)}
          note="average of latest available base dividend coverage rows."
          icon={Gauge}
        />
        <MetricCard
          title="Quarter-end P/NAV"
          value={formatPct(averageLatestPriceNav)}
          note="average of selected funds at the latest model quarter."
          icon={LineChart}
        />
        <MetricCard
          title="Liquidity"
          value={formatMm(totalLiquidity)}
          note="latest presentation liquidity across the selected funds."
          icon={ShieldCheck}
        />
      </div>

      <Callout title="Quarterly facts layer">
        The `quarterly_bdc_facts` table combines holdings-derived quarter history with filing-level income and non-accrual
        facts where available. BXSL, FSK, and TSLX are backfilled from Q1 2025 through Q1 2026; reported presentation
        totals and gross schedule totals stay separate so mismatches remain visible. TSLX&apos;s Q2 2025 holdings spreadsheet
        was not available, so that quarter is not included in spreadsheet-derived holdings coverage.
      </Callout>

      <div className="grid two-col chart-pair-grid">
        <Panel title="Holdings Mark-To-Cost" subtitle={`${periodCount} periods from the centralized holdings database.`} icon={LineChart}>
          <MultiFundLineChart
            periods={quarterlyFacts.meta.periods}
            getValue={(fund, period) => getQuarterlyValue(fund, period, "holdings_mark_to_cost_pct")}
            yLabel="Fair value / cost"
            yMax={120}
            yMin={80}
            yTicks={[120, 100, 80]}
            tickFormatter={(value) => formatAxisNumber(value)}
            valueFormatter={(value) => formatPct(value)}
            visibleFunds={visibleFunds}
          />
        </Panel>

        <Panel title="Below-90 Marks" subtitle="Fair value marked below 90 cents on amortized cost, as a share of holdings fair value." icon={Activity}>
          <MultiFundLineChart
            periods={quarterlyFacts.meta.periods}
            getValue={getBelow90Pct}
            yLabel="Below-90 FV share"
            yMax={Math.max(10, niceAxisMax(Number(maxBelow90Pct || 1)))}
            tickFormatter={(value) => formatAxisNumber(value)}
            valueFormatter={(value) => formatPct(value)}
            visibleFunds={visibleFunds}
          />
        </Panel>
      </div>

      <Panel
        id="financials-snapshot"
        title="Latest Financial Snapshot"
        subtitle="Latest presentation and filing metrics loaded into the quarterly facts table."
        icon={WalletCards}
      >
        <div className="table-wrap">
          <table className="compact-wide-table">
            <thead>
              <tr>
                <th>Fund</th>
                <th className="right">NAV/share</th>
                <th className="right">NII/share</th>
                <th className="right">Dividend</th>
                <th className="right">Coverage</th>
                <th className="right">Leverage*</th>
                <th className="right">Debt cost</th>
                <th className="right">Non-accrual FV</th>
                <th className="right">PIK income</th>
                <th className="right">Liquidity</th>
              </tr>
            </thead>
            <tbody>
              {latestRows.map((row) => (
                <tr key={`${row.fund}-${row.period_end}-financials`}>
                  <td>
                    <FundBadge fund={row.fund} />
                  </td>
                  <td className="right">{formatPerShare(row.nav_per_share)}</td>
                  <td className="right">{formatPerShare(row.nii_per_share)}</td>
                  <td className="right">{formatPerShare(row.base_dividend_per_share || row.total_dividend_per_share)}</td>
                  <td className="right">{formatPct(row.base_dividend_coverage_pct || row.total_dividend_coverage_pct)}</td>
                  <td className="right">{formatMultiple(row.debt_to_equity_x || row.net_debt_to_equity_x)}</td>
                  <td className="right">{formatPct(row.debt_cost_pct)}</td>
                  <td className="right">{formatPct(row.non_accrual_fv_pct)}</td>
                  <td className="right">{formatMm(row.pik_income_mm)}</td>
                  <td className="right">{formatMm(row.liquidity_mm)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {visibleFunds.includes("FSK") ? (
          <p className="activity-source-note">
            * Leverage uses gross debt/equity where disclosed; FSK is shown on net debt/equity because gross debt/equity
            was not separately disclosed in the loaded quarterly facts.
          </p>
        ) : null}
      </Panel>

      <Panel
        id="income-quality-bridge"
        title="Income Quality Bridge"
        subtitle={`${incomeQualityRows.length} presentation-sourced rows from reported NII to conservative cash-like recurring NII.`}
        icon={Gauge}
      >
        {incomeQualityRows.length ? (
          <div className="income-quality-stack">
            <dl className="bridge-explainer" aria-label="Income quality bridge definitions">
              <div>
                <dt>NII</dt>
                <dd>Reported net investment income for the quarter.</dd>
              </div>
              <div>
                <dt>NII/share</dt>
                <dd>Reported NII divided by weighted average shares.</dd>
              </div>
              <div>
                <dt>Cash ex-PIK/share</dt>
                <dd>NII/share after removing PIK interest income.</dd>
              </div>
              <div>
                <dt>Recurring/share</dt>
                <dd>Cash-like NII/share after removing PIK, other fees, other income, and fee waivers.</dd>
              </div>
              <div>
                <dt>PIK / TII</dt>
                <dd>PIK interest as a share of total investment income.</dd>
              </div>
              <div>
                <dt>PIK / NII</dt>
                <dd>PIK interest as a share of reported NII.</dd>
              </div>
              <div>
                <dt>Other fees</dt>
                <dd>Fee income that can be less repeatable, such as prepayment or amendment fees.</dd>
              </div>
              <div>
                <dt>Other income</dt>
                <dd>Miscellaneous income separated from regular interest and dividends.</dd>
              </div>
              <div>
                <dt>Waivers</dt>
                <dd>Management fee waivers that boosted reported income.</dd>
              </div>
              <div>
                <dt>CG fee adj.</dt>
                <dd>Capital gains incentive fee adjustment per share, when disclosed.</dd>
              </div>
              <div>
                <dt>Base cov.</dt>
                <dd>Reported NII/share divided by the quarter-related regular base dividend.</dd>
              </div>
              <div>
                <dt>Total cov.</dt>
                <dd>Reported NII/share divided by quarter-related total distributions.</dd>
              </div>
              <div>
                <dt>Recurring cov.</dt>
                <dd>Cash-like recurring NII/share divided by the quarter-related regular base dividend.</dd>
              </div>
            </dl>
            <div className="table-wrap">
              <table className="compact-wide-table">
                <thead>
                  <tr>
                    <th>Period</th>
                    <th>Fund</th>
                    <th className="right">NII</th>
                    <th className="right">NII/share</th>
                    <th className="right">Cash ex-PIK/share</th>
                    <th className="right">Recurring/share</th>
                    <th className="right">PIK / TII</th>
                    <th className="right">PIK / NII</th>
                    <th className="right">Other fees</th>
                    <th className="right">Other income</th>
                    <th className="right">Waivers</th>
                    <th className="right">CG fee adj.</th>
                    <th className="right">Base cov.</th>
                    <th className="right">Total cov.</th>
                    <th className="right">Recurring cov.</th>
                  </tr>
                </thead>
                <tbody>
                  {incomeQualityRows
                    .slice()
                    .sort((a, b) => (a.period_end === b.period_end ? a.fund.localeCompare(b.fund) : b.period_end.localeCompare(a.period_end)))
                    .map((row) => (
                      <tr key={`${row.fund}-${row.period_end}-income-quality`}>
                        <td>{shortPeriod(row.period_end)}</td>
                        <td>
                          <FundBadge fund={row.fund} />
                        </td>
                        <td className="right">{formatMm(row.reported_nii_mm)}</td>
                        <td className="right">{formatPerShare(row.reported_nii_per_share)}</td>
                        <td className="right">{formatPerShare(row.cash_nii_ex_pik_per_share)}</td>
                        <td className="right">{formatPerShare(row.cash_like_recurring_nii_per_share)}</td>
                        <td className="right">{formatPct(row.pik_income_tii_pct)}</td>
                        <td className="right">{formatPct(row.pik_income_nii_pct)}</td>
                        <td className="right">{formatMm(row.interest_from_investments_other_fees_mm)}</td>
                        <td className="right">{formatMm(row.other_income_mm)}</td>
                        <td className="right">{formatMm(row.fee_waivers_mm)}</td>
                        <td className="right">{formatSignedPerShare(row.capital_gains_incentive_fee_not_payable_per_share)}</td>
                        <td className="right">{formatPct(row.reported_base_dividend_coverage_pct)}</td>
                        <td className="right">{formatPct(row.reported_record_date_distribution_coverage_pct)}</td>
                        <td className="right">{formatPct(row.cash_like_base_dividend_coverage_pct)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
            {latestIncomeQualityNotes.length ? (
              <div className="bridge-source-notes">
                <h3>Latest bridge source notes</h3>
                <ul>
                  {latestIncomeQualityNotes.map((item) => (
                    <li key={item.key}>
                      <strong>{item.label}:</strong> {item.note}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="empty-state">No income-quality bridge rows match the current fund filter.</div>
        )}
      </Panel>

      <Panel
        id="dividend-declarations"
        title="Dividend Declarations"
        subtitle={`${dividendDeclarationRows.length} sourced base and supplemental rows extracted from presentation dividend disclosures.`}
        icon={Calendar}
      >
        {dividendDeclarationRows.length ? (
          <div className="dividend-declaration-stack">
            {selectedFund === "All" || selectedFund === "TSLX" ? (
              <Callout title="TSLX dividend signal">
                TSLX&apos;s declining supplemental dividend suggests less surplus earnings coverage. The May 5, 2026 release
                also declared a Q2 2026 base dividend of $0.42, down from the prior $0.46.
              </Callout>
            ) : null}
            <div className="table-wrap">
              <table className="compact-wide-table">
                <thead>
                  <tr>
                    <th>Record</th>
                    <th>Fund</th>
                    <th>Type</th>
                    <th className="right">Amount</th>
                    <th>Declared</th>
                    <th>Payment</th>
                    <th>Related period</th>
                  </tr>
                </thead>
                <tbody>
                  {dividendDeclarationRows
                    .slice()
                    .sort((a, b) => b.record_date.localeCompare(a.record_date) || a.dividend_type.localeCompare(b.dividend_type))
                    .map((row) => (
                      <tr key={`${row.fund}-${row.record_date}-${row.dividend_type}-${row.amount_per_share}`}>
                        <td>{formatDate(row.record_date)}</td>
                        <td>
                          <FundBadge fund={row.fund} />
                        </td>
                        <td>{row.dividend_type}</td>
                        <td className="right">{formatPerShare(row.amount_per_share)}</td>
                        <td>{formatDate(row.declared_date)}</td>
                        <td>{formatDate(row.payment_date)}</td>
                        <td>{row.related_period_end ? shortPeriod(row.related_period_end) : "n/a"}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="empty-state">No dividend declaration rows match the current fund filter.</div>
        )}
      </Panel>

      <Panel
        id="income-expense-facts"
        title="Income / Expense Facts"
        subtitle="Filing-sourced statement-of-operations rows. BXSL, FSK, and TSLX are backfilled from Q1 2025 through Q1 2026."
        icon={WalletCards}
      >
        <div className="table-wrap">
          <table className="compact-wide-table">
            <thead>
              <tr>
                <th>Period</th>
                <th>Fund</th>
                <th className="right">TII</th>
                <th className="right">Interest</th>
                <th className="right">PIK</th>
                <th className="right">Fee</th>
                <th className="right">Dividend</th>
                <th className="right">Mgmt fee</th>
                <th className="right">Incentive</th>
                <th className="right">G&A</th>
                <th className="right">Interest exp.</th>
                <th className="right">Tax</th>
                <th className="right">NII</th>
              </tr>
            </thead>
            <tbody>
              {incomeExpenseRows
                .slice()
                .sort((a, b) => (a.period_end === b.period_end ? a.fund.localeCompare(b.fund) : b.period_end.localeCompare(a.period_end)))
                .map((row) => (
                  <tr key={`${row.fund}-${row.period_end}-income-expense`}>
                    <td>{shortPeriod(row.period_end)}</td>
                    <td>
                      <FundBadge fund={row.fund} />
                    </td>
                    <td className="right">{formatMm(row.total_investment_income_mm)}</td>
                    <td className="right">{formatMm(row.interest_income_mm)}</td>
                    <td className="right">{formatMm(row.pik_interest_income_mm)}</td>
                    <td className="right">{formatMm(row.fee_income_mm)}</td>
                    <td className="right">{formatMm(row.dividend_income_mm)}</td>
                    <td className="right">{formatMm(row.base_management_fee_mm)}</td>
                    <td className="right">{formatMm(row.income_incentive_fee_mm)}</td>
                    <td className="right">{formatMm(row.total_g_and_a_mm)}</td>
                    <td className="right">{formatMm(row.interest_expense_mm)}</td>
                    <td className="right">{formatMm(row.tax_expense_mm)}</td>
                    <td className="right">{formatMm(row.nii_mm)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel
        id="non-accrual-summary"
        title="Non-Accrual Summary"
        subtitle="Issuer-level rows are grouped from schedule footnotes; reported FV percentage comes from the portfolio composition table."
        icon={ShieldCheck}
      >
        <div className="non-accrual-summary-stack">
          <div className="table-wrap">
            <table className="compact-wide-table">
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Fund</th>
                  <th className="right">Issuers</th>
                  <th className="right">Securities</th>
                  <th className="right">Cost</th>
                  <th className="right">Fair value</th>
                  <th className="right">FV / cost</th>
                  <th className="right">Reported FV %</th>
                </tr>
              </thead>
              <tbody>
                {nonAccrualSummaryRows
                  .slice()
                  .sort((a, b) => (a.period_end === b.period_end ? a.fund.localeCompare(b.fund) : b.period_end.localeCompare(a.period_end)))
                  .map((row) => (
                    <tr key={`${row.fund}-${row.period_end}-non-accrual-summary`}>
                      <td>{shortPeriod(row.period_end)}</td>
                      <td>
                        <FundBadge fund={row.fund} />
                      </td>
                      <td className="right">{formatNumber(row.issuer_count)}</td>
                      <td className="right">{formatNumber(row.security_count)}</td>
                      <td className="right">{formatMm(row.amortized_cost_mm)}</td>
                      <td className="right">{formatMm(row.fair_value_mm)}</td>
                      <td className="right">{formatCentsOnDollar(row.fair_value_mm, row.amortized_cost_mm)}</td>
                      <td className="right">{formatPct(row.reported_non_accrual_fv_pct)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <div className="chart-section">
            <MultiFundLineChart
              periods={nonAccrualTrendPeriods}
              getValue={getReportedNonAccrualFvPct}
              yLabel="Reported non-accrual FV %"
              yMax={reportedNonAccrualFvAxisMax}
              yTicks={reportedNonAccrualFvTicks}
              tickFormatter={(value) => formatAxisNumber(value)}
              valueFormatter={(value) => formatPct(value)}
              visibleFunds={visibleFunds}
            />
          </div>
        </div>
      </Panel>

      <Panel
        title="Watchlist Deterioration Trend"
        subtitle={`${watchlistBucketFilters.find((item) => item.value === watchlistBucketFilter)?.label || "All flags"}${
          effectiveWatchlistInstrumentFilter === "All" ? "" : `, ${effectiveWatchlistInstrumentFilter}`
        } fair value as a share of holdings fair value by quarter.`}
        icon={LineChart}
      >
        <MultiFundLineChart
          periods={watchlistTrendPeriods}
          getValue={getWatchlistTrendPct}
          yLabel="Flagged FV / holdings FV"
          yMax={Math.max(5, niceAxisMax(Number(maxWatchlistTrendPct || 1)))}
          tickFormatter={(value) => formatAxisNumber(value)}
          valueFormatter={(value) => formatPct(value)}
          visibleFunds={watchlistVisibleFunds}
        />
      </Panel>

      <Panel
        id="issuer-watchlist"
        title="Issuer Watchlist"
        subtitle={`${latestWatchlistRows.length} filtered latest-period flagged issuers; ${latestShadowRows.length} are accruing shadow rows below 90. Showing ${watchlistTableRows.length} issuer-period rows with period-level instrument context.`}
        icon={Activity}
        action={
          <div className="panel-controls">
            <select
              className="select"
              value={effectiveWatchlistFund}
              onChange={(event) => setWatchlistFundFilter(event.target.value as Fund | "All")}
              disabled={selectedFund !== "All"}
              title="Watchlist fund"
            >
              <option value="All">All funds</option>
              {institutionalFunds.map((fund) => (
                <option key={fund} value={fund}>
                  {fund}
                </option>
              ))}
            </select>
            <select
              className="select"
              value={watchlistBucketFilter}
              onChange={(event) => setWatchlistBucketFilter(event.target.value as WatchlistBucketFilter)}
              title="Watchlist credit bucket"
            >
              {watchlistBucketFilters.map((filter) => (
                <option key={filter.value} value={filter.value}>
                  {filter.label}
                </option>
              ))}
            </select>
            <select
              className="select"
              value={effectiveWatchlistInstrumentFilter}
              onChange={(event) => setWatchlistInstrumentFilter(event.target.value)}
              title="Watchlist instrument context"
            >
              <option value="All">All instruments</option>
              {watchlistInstrumentOptions.map((context) => (
                <option key={context} value={context}>
                  {context}
                </option>
              ))}
            </select>
          </div>
        }
      >
        <div className="table-wrap">
          <table className="compact-wide-table">
            <thead>
              <tr>
                <th>Period</th>
                <th>Fund</th>
                <th>Issuer</th>
                <th>Instrument</th>
                <th>Bucket</th>
                <th className="right">Rows</th>
                <th className="right">Fair value</th>
                <th className="right">FV / cost</th>
                <th className="right">FV / principal</th>
                <th className="right">QoQ FV / cost</th>
                <th className="right">QoQ mark</th>
                <th>Credit flag</th>
              </tr>
            </thead>
            <tbody>
              {watchlistTableRows.map((row) => (
                <tr key={`${row.fund}-${row.period_end}-${row.issuer_match_key}-watchlist`}>
                  <td>{shortPeriod(row.period_end)}</td>
                  <td>
                    <FundBadge fund={row.fund} />
                  </td>
                  <td className="issuer-cell">
                    <strong>{row.issuer_name}</strong>
                    <span>{row.issuer_industries || row.issuer_match_key}</span>
                  </td>
                  <td className="issuer-cell">
                    <strong>{row.instrument_context || "Instrument n/a"}</strong>
                    <span>{row.instrument_context_detail || "As-filed type unavailable"}</span>
                  </td>
                  <td>
                    <span className={`pill ${row.is_non_accrual ? "" : row.shadow_non_accrual ? "warn" : ""}`}>
                      {row.watchlist_bucket}
                    </span>
                  </td>
                  <td className="right">{formatNumber(row.security_count)}</td>
                  <td className="right">{formatMm(row.fair_value_mm)}</td>
                  <td className="right">{formatPct(row.fv_to_cost_pct)}</td>
                  <td className="right">{formatPct(row.fv_to_principal_pct)}</td>
                  <td className="right">{formatPct(row.qoq_fv_to_cost_change_pct)}</td>
                  <td className="right">{formatMm(row.qoq_mark_vs_cost_change_mm)}</td>
                  <td>{row.is_non_accrual ? "Non-accrual" : row.shadow_non_accrual ? "Shadow" : "Watch"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel
        id="non-accrual-issuers"
        title="Non-Accrual Issuers"
        subtitle={`${nonAccrualIssuerRows.length} issuer-period rows from schedule footnotes.`}
        icon={AlertTriangle}
      >
        <div className="table-wrap">
          <table className="compact-wide-table">
            <thead>
              <tr>
                <th>Period</th>
                <th>Fund</th>
                <th>Issuer</th>
                <th className="right">Securities</th>
                <th className="right">Cost</th>
                <th className="right">Fair value</th>
                <th className="right">FV / cost</th>
              </tr>
            </thead>
            <tbody>
              {nonAccrualIssuerRows
                .slice()
                .sort((a, b) =>
                  a.period_end === b.period_end
                    ? Number(b.fair_value_mm || 0) - Number(a.fair_value_mm || 0)
                    : b.period_end.localeCompare(a.period_end)
                )
                .map((row) => (
                  <tr key={`${row.fund}-${row.period_end}-${row.issuer_name}`}>
                    <td>{shortPeriod(row.period_end)}</td>
                    <td>
                      <FundBadge fund={row.fund} />
                    </td>
                    <td className="issuer-cell">
                      <strong>{row.issuer_name}</strong>
                      <span>{row.source_title}</span>
                    </td>
                    <td className="right">{formatNumber(row.security_count)}</td>
                    <td className="right">{formatMm(row.amortized_cost_mm)}</td>
                    <td className="right">{formatMm(row.fair_value_mm)}</td>
                    <td className="right">{formatCentsOnDollar(row.fair_value_mm, row.amortized_cost_mm)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="NAV Per Share" subtitle="Sourced quarterly NAV/share marks from the Q1 2026 presentation tables." icon={LineChart}>
        <MultiFundLineChart
          periods={navPeriods}
          getValue={(fund, period) => getQuarterlyValue(fund, period, "nav_per_share")}
          yLabel="NAV / share"
          yMax={navAxisMax}
          yMin={navAxisMin}
          yTicks={navAxisTicks}
          tickFormatter={(value) => formatPerShare(value)}
          valueFormatter={(value) => formatPerShare(value)}
          visibleFunds={visibleFunds}
        />
      </Panel>

      <Panel
        id="quarterly-market-facts"
        title="Quarterly Market Facts"
        subtitle="Quarter-end and average public closes paired with sourced NAV/share marks."
        icon={LineChart}
      >
        <div className="table-wrap">
          <table className="compact-wide-table">
            <thead>
              <tr>
                <th>Period</th>
                <th>Fund</th>
                <th className="right">QE close</th>
                <th className="right">Avg close</th>
                <th className="right">NAV/share</th>
                <th className="right">QE P/NAV</th>
                <th className="right">Avg P/NAV</th>
                <th className="right">Trading days</th>
              </tr>
            </thead>
            <tbody>
              {quarterlyMarketRows
                .slice()
                .sort((a, b) => (a.period_end === b.period_end ? a.fund.localeCompare(b.fund) : b.period_end.localeCompare(a.period_end)))
                .map((row) => (
                  <tr key={`${row.fund}-${row.period_end}-market`}>
                    <td>{shortPeriod(row.period_end)}</td>
                    <td>
                      <FundBadge fund={row.fund} />
                    </td>
                    <td className="right">{formatPerShare(row.quarter_end_close_price)}</td>
                    <td className="right">{formatPerShare(row.avg_daily_close_price)}</td>
                    <td className="right">{formatPerShare(row.nav_per_share)}</td>
                    <td className="right">{formatPct(row.quarter_end_price_to_nav_pct)}</td>
                    <td className="right">{formatPct(row.avg_price_to_nav_pct)}</td>
                    <td className="right">{formatNumber(row.trading_days)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid two-col">
        <Panel
          id="portfolio-quality-screeners"
          title="Portfolio Quality Screeners"
          subtitle="Holdings-derived first-pass metrics by fund and period."
          icon={ShieldCheck}
        >
          <div className="table-wrap">
            <table className="compact-wide-table">
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Fund</th>
                  <th className="right">Holdings FV</th>
                  <th className="right">Mark/cost</th>
                  <th className="right">First lien</th>
                  <th className="right">Floating</th>
                  <th className="right">PIK / FV</th>
                  <th className="right">Below 90</th>
                </tr>
              </thead>
              <tbody>
                {rows
                  .slice()
                  .sort((a, b) => (a.period_end === b.period_end ? a.fund.localeCompare(b.fund) : b.period_end.localeCompare(a.period_end)))
                  .map((row) => (
                    <tr key={`${row.fund}-${row.period_end}-quality`}>
                      <td>{shortPeriod(row.period_end)}</td>
                      <td>
                        <FundBadge fund={row.fund} />
                      </td>
                      <td className="right">{formatMm(row.holdings_fair_value_mm)}</td>
                      <td className="right">{formatPct(row.holdings_mark_to_cost_pct)}</td>
                      <td className="right">{formatPct(row.holdings_first_lien_pct)}</td>
                      <td className="right">{formatPct(row.holdings_floating_rate_pct)}</td>
                      <td className="right">{formatPct(row.holdings_pik_fair_value_pct)}</td>
                      <td className="right">{formatMm(row.holdings_below_90_fair_value_mm)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <dl className="quality-column-guide" aria-label="Portfolio quality screener column definitions">
            <div>
              <dt>Period</dt>
              <dd>The quarter-end date for the holdings snapshot.</dd>
            </div>
            <div>
              <dt>Fund</dt>
              <dd>The BDC ticker shown in that row.</dd>
            </div>
            <div>
              <dt>Holdings FV</dt>
              <dd>Total fair value of the holdings rows included for that fund and quarter.</dd>
            </div>
            <div>
              <dt>Mark/cost</dt>
              <dd>Fair value divided by amortized cost; lower values mean deeper marks below cost.</dd>
            </div>
            <div>
              <dt>First lien</dt>
              <dd>Share of holdings fair value invested in first-lien debt.</dd>
            </div>
            <div>
              <dt>Floating</dt>
              <dd>Share of holdings fair value with a floating-rate base rate.</dd>
            </div>
            <div>
              <dt>PIK / FV</dt>
              <dd>Share of holdings fair value invested in securities with a PIK interest feature.</dd>
            </div>
            <div>
              <dt>Below 90</dt>
              <dd>Fair value of holdings marked below 90% of amortized cost.</dd>
            </div>
          </dl>
        </Panel>

        <Panel
          id="originations-repayments"
          title="Originations / Repayments"
          subtitle="Presentation-derived activity values, Q1 2025 through Q1 2026."
          icon={TrendingUp}
        >
          <div className="table-wrap">
            <table className="compact-table activity-table">
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Fund</th>
                  <th className="right">New</th>
                  <th className="right">Funded</th>
                  <th className="right">Repaid / sold</th>
                  <th className="right">Net</th>
                  <th className="right">New yield</th>
                </tr>
              </thead>
              <tbody>
                {activityRows.map((row) => (
                  <tr key={`${row.fund}-${row.period_end}-activity`}>
                    <td className="nowrap">{shortPeriod(row.period_end)}</td>
                    <td>
                      <FundBadge fund={row.fund} />
                    </td>
                    <td className="right">{formatMm(row.new_commitments_mm)}</td>
                    <td className="right">{formatMm(row.fundings_mm)}</td>
                    <td className="right">{formatMm(row.repayments_sales_mm)}</td>
                    <td className="right">{formatMm(row.net_investment_activity_mm)}</td>
                    <td className="right">{formatPct(row.new_investment_yield_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="activity-source-note">
            n/a means the source did not separately disclose that field. FSK reports purchases and sales/repayments, but not a
            commitment/funding split or activity yield; TSLX reports activity dollars, but not activity yields.
          </p>
          <p className="activity-source-note">
            BXSL's new-investment yield declined from 9.8% in 06/25 to 7.7% in 03/26, below the 9.1% yield on investments fully
            sold or paid down in 03/26, pointing to negative reinvestment spread pressure.
          </p>
          <dl className="activity-column-guide">
            <div>
              <dt>Period</dt>
              <dd>Quarter-end tied to the activity disclosure.</dd>
            </div>
            <div>
              <dt>Fund</dt>
              <dd>The BDC reporting the activity.</dd>
            </div>
            <div>
              <dt>New</dt>
              <dd>New commitments or purchases, preserving the fund's label.</dd>
            </div>
            <div>
              <dt>Funded</dt>
              <dd>Capital actually funded during the quarter, when disclosed.</dd>
            </div>
            <div>
              <dt>Repaid / sold</dt>
              <dd>Investments sold, redeemed, paid down, or repaid.</dd>
            </div>
            <div>
              <dt>Net</dt>
              <dd>Reported new or funded activity less repaid / sold activity.</dd>
            </div>
            <div>
              <dt>New yield</dt>
              <dd>Weighted average yield on new investments, disclosed by BXSL.</dd>
            </div>
          </dl>
          <div className="activity-mini-chart" aria-label="Net investment activity by fund and quarter">
            <div className="activity-mini-title">
              <span>Net Activity</span>
              <span>positive bars add portfolio exposure; negative bars show repayments/sales above new activity</span>
            </div>
            <div className="activity-mini-periods">
              <span />
              {activityPeriods.map((period) => (
                <span key={period}>{shortPeriod(period)}</span>
              ))}
            </div>
            {visibleFunds.map((fund) => (
              <div className="activity-mini-row" key={`${fund}-activity-chart`}>
                <FundBadge fund={fund} />
                {activityPeriods.map((period) => {
                  const row = activityRowMap.get(`${fund}|${period}`);
                  const value = row?.net_investment_activity_mm;
                  const barWidth = value === null || value === undefined ? 0 : Math.min(50, (Math.abs(value) / activityNetMax) * 50);
                  const barStyle =
                    value === null || value === undefined
                      ? {}
                      : value >= 0
                        ? { left: "50%", width: `${barWidth}%` }
                        : { left: `${50 - barWidth}%`, width: `${barWidth}%` };
                  return (
                    <div
                      className="activity-mini-cell"
                      key={`${fund}-${period}-net`}
                      title={
                        row
                          ? `${fund} ${shortPeriod(period)}: new ${formatMm(row.new_commitments_mm)}, funded ${formatMm(row.fundings_mm)}, repaid/sold ${formatMm(row.repayments_sales_mm)}, net ${formatMm(row.net_investment_activity_mm)}`
                          : `${fund} ${shortPeriod(period)}: n/a`
                      }
                    >
                      <div className="activity-net-track">
                        {value !== null && value !== undefined ? (
                          <span className={`activity-net-bar ${value >= 0 ? "positive" : "negative"}`} style={barStyle} />
                        ) : null}
                      </div>
                      <span className="activity-net-label">{formatMm(value, 0)}</span>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div className="grid limitation-grid">
        {quarterlyFacts.limitations.map((limitation) => (
          <section className="panel limitation" key={limitation}>
            <h3>Model caveat</h3>
            <p>{limitation}</p>
          </section>
        ))}
      </div>
    </div>
  );
}

function CrossFundSpotlightCard({
  row,
  index,
  onOpenTimelineIssuer
}: {
  row: CrossFundIssuer;
  index: number;
  onOpenTimelineIssuer: (issuerMatchKey: string) => void;
}) {
  const enrichment = findCompanyEnrichment(row.issuer_match_key);
  const fundBreakdown = [...row.fund_breakdown].sort((a, b) => b.fair_value_mm - a.fair_value_mm);
  const maxFundValue = Math.max(...fundBreakdown.map((item) => item.fair_value_mm), 1);

  return (
    <article className="issuer-spotlight">
      <div className="spotlight-topline">
        <span>{String(index + 1).padStart(2, "0")} / Cross-fund</span>
        <button type="button" onClick={() => onOpenTimelineIssuer(row.issuer_match_key)}>
          Open timeline <ArrowUpRight />
        </button>
      </div>
      <h3>{enrichment?.display_name || row.representative_issuer_name}</h3>
      <p className="spotlight-legal">{enrichment?.mapped_company || row.representative_issuer_name}</p>

      <div className="spotlight-stat-grid">
        <div><span>Funds</span><strong>{row.fund_count}</strong></div>
        <div><span>Fair value</span><strong>{formatMm(row.fair_value_mm)}</strong></div>
        <div><span>FV / cost</span><strong>{formatCentsOnDollar(row.fair_value_mm, row.amortized_cost_mm)}</strong></div>
      </div>

      <p className="spotlight-description">
        {enrichment?.description || `The normalized issuer key links ${row.fund_count} verified BDC portfolios at the latest common period.`}
      </p>

      <div className="spotlight-sponsor">
        <span>{enrichment && !isSourceDerivedEnrichment(enrichment) ? "Current sponsor" : "Research status"}</span>
        <strong>{enrichment && !isSourceDerivedEnrichment(enrichment) ? enrichment.current_sponsor : "Schedule evidence mapped"}</strong>
      </div>

      <div className="spotlight-funds" aria-label={`${row.issuer_match_key} fund exposure`}>
        {fundBreakdown.map((item) => (
          <div className="spotlight-fund-row" key={`${row.issuer_match_key}-${item.fund}`}>
            <span>{item.fund}</span>
            <i><b style={{ width: `${(item.fair_value_mm / maxFundValue) * 100}%` }} /></i>
            <strong>{formatMm(item.fair_value_mm, 1)}</strong>
          </div>
        ))}
      </div>
    </article>
  );
}

function formatFacilityRate(row: FacilityGapRow) {
  if (typeof row.fixed_coupon_pct_a === "number") return `${formatPct(row.fixed_coupon_pct_a, 2)} fixed`;
  if (row.reference_base_rate && typeof row.spread_pct_a === "number") {
    return `${row.reference_base_rate} + ${formatPct(row.spread_pct_a, 2)}`;
  }
  return row.reference_base_rate || "Rate evidence matched";
}

function MarkDivergence({
  selectedFund,
  onOpenTimelineIssuer
}: {
  selectedFund: Fund | "All";
  onOpenTimelineIssuer: (issuerMatchKey: string) => void;
}) {
  const [mode, setMode] = useState<MarkComparisonMode>("facility");
  const [query, setQuery] = useState("");
  const [minimumGap, setMinimumGap] = useState(0);
  const normalizedQuery = query.trim().toLowerCase();
  const sourceRows: Array<FacilityGapRow | CompanyGapRow | CapitalStructurePairRow> =
    mode === "facility"
      ? trancheComparison.facility_gaps
      : mode === "company"
        ? trancheComparison.company_gaps
        : trancheComparison.capital_structure_pairs;
  const rows = sourceRows
    .map((row) => {
      const enrichment = findCompanyEnrichment(row.issuer_match_key);
      const facility = mode === "facility" ? (row as FacilityGapRow) : null;
      const company = mode === "company" ? (row as CompanyGapRow) : null;
      const structure = mode === "structure" ? (row as CapitalStructurePairRow) : null;
      const fundA = structure?.junior_fund ?? facility?.fund_a ?? company?.fund_a ?? "ARCC";
      const fundB = structure?.senior_fund ?? facility?.fund_b ?? company?.fund_b ?? "ARCC";
      return {
        issuer_match_key: row.issuer_match_key,
        display_name: enrichment?.display_name || row.issuer_match_key,
        mapped_company: enrichment?.mapped_company || row.issuer_match_key,
        fund_pair: structure ? `${fundA} vs ${fundB}` : facility?.fund_pair ?? company?.fund_pair ?? "",
        fund_a: fundA,
        fund_b: fundB,
        mark_a: structure?.junior_fv_to_cost_pct ?? facility?.fund_a_fv_to_principal_pct ?? company?.fund_a_fv_to_principal_pct ?? 0,
        mark_b: structure?.senior_fv_to_cost_pct ?? facility?.fund_b_fv_to_principal_pct ?? company?.fund_b_fv_to_principal_pct ?? 0,
        principal_a: structure?.junior_amortized_cost_mm ?? facility?.fund_a_principal_mm ?? company?.fund_a_matched_principal_mm ?? 0,
        principal_b: structure?.senior_amortized_cost_mm ?? facility?.fund_b_principal_mm ?? company?.fund_b_matched_principal_mm ?? 0,
        fair_value_a: structure?.junior_fair_value_mm ?? facility?.fund_a_fair_value_mm ?? company?.fund_a_matched_fair_value_mm ?? 0,
        fair_value_b: structure?.senior_fair_value_mm ?? facility?.fund_b_fair_value_mm ?? company?.fund_b_matched_fair_value_mm ?? 0,
        gap: structure?.absolute_gap_pp ?? facility?.inter_fund_gap_pp ?? company?.inter_fund_gap_pp ?? 0,
        conservative_fund: facility?.conservative_fund ?? company?.conservative_fund ?? "Tie",
        comparable_facilities: company?.comparable_facility_pair_count ?? 1,
        abstention_count: company?.abstention_count ?? 0,
        maturity_month: facility?.maturity_month ?? null,
        facility_rate: facility ? formatFacilityRate(facility) : null,
        confidence: facility?.facility_match_confidence ?? (structure ? "capital structure" : "aggregate"),
        comparison_scope: structure?.comparison_scope ?? "cross-fund",
        waterfall_status: structure?.waterfall_status ?? null,
        junior_tier: structure?.junior_tier ?? null,
        senior_tier: structure?.senior_tier ?? null,
        signed_waterfall_gap: structure?.senior_minus_junior_gap_pp ?? null,
        junior_labels: structure?.junior_instrument_labels ?? [],
        senior_labels: structure?.senior_instrument_labels ?? []
      };
    })
    .filter((row) => selectedFund === "All" || row.fund_a === selectedFund || row.fund_b === selectedFund)
    .filter((row) => row.gap >= minimumGap)
    .filter((row) => {
      if (!normalizedQuery) return true;
      return [row.issuer_match_key, row.display_name, row.mapped_company, row.fund_pair, row.junior_tier, row.senior_tier, row.waterfall_status]
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery);
    });
  const topRows = rows.slice(0, 4);
  const visibleStructureIssuers = new Set(rows.map((row) => row.issuer_match_key));
  const leadLagRows = researchSignals.fund_pair_lead_lag
    .filter((row) => visibleStructureIssuers.has(row.issuer_match_key))
    .slice(0, 6);
  const visibleLeadLagTests = researchSignals.fund_pair_lead_lag.filter((row) =>
    visibleStructureIssuers.has(row.issuer_match_key)
  );
  const visibleLeadLagCounts = {
    juniorFirst: visibleLeadLagTests.filter((row) => row.lead_lag_status === "junior_first").length,
    simultaneous: visibleLeadLagTests.filter((row) => row.lead_lag_status === "simultaneous").length,
    seniorFirst: visibleLeadLagTests.filter((row) => row.lead_lag_status === "senior_first").length
  };

  return (
    <Panel
      title="Capital-Structure & Inter-Fund Marks"
      subtitle={`At ${formatDate(trancheComparison.meta.latest_period)}, same-loan views use FV/principal while the capital-structure view uses FV/cost so equity, junior debt, and senior secured debt can be compared on one basis.`}
      icon={ArrowUpDown}
      action={
        <div className="mark-divergence-actions">
          <div className="view-switch" aria-label="Mark comparison level">
            <button type="button" className={mode === "facility" ? "active" : ""} onClick={() => setMode("facility")}>Same tranche</button>
            <button type="button" className={mode === "company" ? "active" : ""} onClick={() => setMode("company")}>Same company</button>
            <button type="button" className={mode === "structure" ? "active" : ""} onClick={() => setMode("structure")}>Capital structure</button>
          </div>
          <select className="select" value={minimumGap} onChange={(event) => setMinimumGap(Number(event.target.value))} aria-label="Minimum mark gap">
            <option value={0}>All gaps</option>
            <option value={1}>1+ pp gap</option>
            <option value={2}>2+ pp gap</option>
            <option value={5}>5+ pp gap</option>
          </select>
        </div>
      }
    >
      <div className="comparison-audit-strip">
        <div><span>Co-held companies screened</span><strong>{formatNumber(trancheComparison.meta.candidate_count)}</strong></div>
        <div>
          <span>{mode === "structure" ? "Companies with tier pairs" : "Complete principal coverage"}</span>
          <strong>{formatNumber(mode === "structure" ? trancheComparison.meta.capital_structure_company_count : trancheComparison.meta.par_covered_candidate_count)}</strong>
        </div>
        <div>
          <span>{mode === "structure" ? "Expected junior-first signals" : "Comparable tranches"}</span>
          <strong>{formatNumber(mode === "structure" ? trancheComparison.meta.expected_waterfall_count : trancheComparison.meta.comparable_facility_pair_count)}</strong>
        </div>
        <div>
          <span>{mode === "structure" ? "Mark-order inversions" : "Comparable companies"}</span>
          <strong>{formatNumber(mode === "structure" ? trancheComparison.meta.capital_structure_inversion_count : trancheComparison.meta.comparable_candidate_count)}</strong>
        </div>
      </div>

      {mode === "structure" ? (
        <div className="lead-lag-overview">
          <div className="lead-lag-overview-heading">
            <div>
              <span>Quarter-by-quarter evidence</span>
              <h3>Which fund&apos;s tier crossed below 95% first?</h3>
            </div>
            <p>{formatNumber(visibleLeadLagCounts.juniorFirst)} junior-first · {formatNumber(visibleLeadLagCounts.simultaneous)} same-quarter · {formatNumber(visibleLeadLagCounts.seniorFirst)} senior-first</p>
          </div>
          <div className="lead-lag-overview-grid">
            {leadLagRows.map((row) => {
              const enrichment = findCompanyEnrichment(row.issuer_match_key);
              return (
                <button type="button" key={`${row.issuer_match_key}-${row.junior_fund}-${row.senior_fund}-${row.junior_tier}`} onClick={() => onOpenTimelineIssuer(row.issuer_match_key)}>
                  <span className={`waterfall-signal lead-${row.lead_lag_status}`}>{leadLagLabel(row.lead_lag_status)}</span>
                  <strong>{enrichment?.display_name || row.issuer_match_key}</strong>
                  <small>{row.junior_fund} {row.junior_tier} → {row.senior_fund} first lien · {row.comparison_scope}</small>
                  <div>
                    <span>Junior {row.junior_first_below_95_period ? shortPeriod(row.junior_first_below_95_period) : "never"}</span>
                    <span>Senior {row.senior_first_below_95_period ? shortPeriod(row.senior_first_below_95_period) : "never"}</span>
                  </div>
                  <ArrowUpRight />
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      <div className="mark-gap-board">
        {topRows.map((row, index) => (
          <article className="mark-gap-card" key={`${mode}-${row.issuer_match_key}-${row.fund_pair}-${row.maturity_month || index}`}>
            <div className="mark-gap-card-topline">
              <span>{String(index + 1).padStart(2, "0")} / {mode === "facility" ? "Same tranche" : mode === "company" ? "Company set" : "Capital structure"}</span>
              <button type="button" onClick={() => onOpenTimelineIssuer(row.issuer_match_key)} aria-label={`Open ${row.display_name} timeline`}><ArrowUpRight /></button>
            </div>
            <h3>{row.display_name}</h3>
            <p>
              {mode === "facility"
                ? `${row.maturity_month || "Maturity matched"} · ${row.facility_rate}`
                : mode === "company"
                  ? `${row.comparable_facilities} comparable facilit${row.comparable_facilities === 1 ? "y" : "ies"}`
                  : `${row.junior_tier} → ${row.senior_tier}`}
            </p>
            <div className="mark-pair">
              <div><FundBadge fund={row.fund_a} /><strong>{formatPct(row.mark_a, 2)}</strong></div>
              <span><b>{formatPct(row.gap, 2)}</b> gap</span>
              <div><FundBadge fund={row.fund_b} /><strong>{formatPct(row.mark_b, 2)}</strong></div>
            </div>
            <div className="mark-gap-footer">
              <span>{mode === "structure" ? "Waterfall signal" : "Lower mark"}</span>
              <strong>
                {mode === "structure"
                  ? row.waterfall_status === "expected_waterfall"
                    ? "Junior impaired first"
                    : row.waterfall_status === "inversion"
                      ? "Mark-order inversion"
                      : "No clear separation"
                  : row.conservative_fund}
              </strong>
              <small>{mode === "structure" ? row.comparison_scope : row.confidence === "aggregate" ? "matched-loan aggregate" : `${row.confidence} match confidence`}</small>
            </div>
          </article>
        ))}
      </div>

      <div className="comparison-toolbar">
        <div className="search-wrap compact-search">
          <Search />
          <input className="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search company or fund pair" aria-label="Search comparable loan marks" />
        </div>
        <span>{formatNumber(rows.length)} {mode === "facility" ? "comparable facility pairs" : mode === "company" ? "comparable company / fund pairs" : "capital-structure tier pairs"}</span>
      </div>

      <div className="table-wrap">
        <table className="mark-comparison-table">
          <thead>
            <tr>
              <th>Company</th>
              <th>{mode === "facility" ? "Facility evidence" : mode === "company" ? "Matched loan set" : "Tier comparison"}</th>
              <th>{mode === "structure" ? "Junior / senior marks" : "Fund marks"}</th>
              <th className="right">Gap</th>
              <th>{mode === "structure" ? "Signal" : "Lower mark"}</th>
              <th className="right">{mode === "structure" ? "Combined cost" : "Matched principal"}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${mode}-table-${row.issuer_match_key}-${row.fund_pair}-${row.maturity_month || index}`}>
                <td className="issuer-cell">
                  <a className="issuer-link" href="#timeline" onClick={(event) => { event.preventDefault(); onOpenTimelineIssuer(row.issuer_match_key); }}><strong>{row.display_name}</strong></a>
                  <span>{row.issuer_match_key}</span>
                </td>
                <td className="comparison-evidence">
                  <strong>
                    {mode === "facility"
                      ? row.maturity_month || "Matched maturity"
                      : mode === "company"
                        ? `${row.comparable_facilities} comparable facilit${row.comparable_facilities === 1 ? "y" : "ies"}`
                        : row.junior_tier || "Junior tier"}
                  </strong>
                  <span>
                    {mode === "facility"
                      ? row.facility_rate
                      : mode === "company"
                        ? row.abstention_count
                          ? `${row.abstention_count} additional unmatched facilit${row.abstention_count === 1 ? "y" : "ies"}`
                          : "All identified facilities matched"
                        : `${row.senior_tier} · ${row.comparison_scope}`}
                  </span>
                </td>
                <td><div className="paired-marks"><span><FundBadge fund={row.fund_a} /> {formatPct(row.mark_a, 2)}</span><span><FundBadge fund={row.fund_b} /> {formatPct(row.mark_b, 2)}</span></div></td>
                <td className="right"><strong className={row.gap >= 5 ? "mark-gap-severe" : row.gap >= 2 ? "mark-gap-watch" : ""}>{formatPct(row.gap, 2)}</strong></td>
                <td>
                  {mode === "structure" ? (
                    <span className={`waterfall-signal signal-${row.waterfall_status}`}>
                      {row.waterfall_status === "expected_waterfall" ? "Junior first" : row.waterfall_status === "inversion" ? "Inversion" : "Flat"}
                    </span>
                  ) : (
                    <><FundBadge fund={row.conservative_fund === "Tie" ? row.fund_a : row.conservative_fund} />{row.conservative_fund === "Tie" ? <span className="tie-note">tie</span> : null}</>
                  )}
                </td>
                <td className="right nowrap">{formatMm(row.principal_a + row.principal_b)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!rows.length ? <div className="empty-state">No comparable facilities meet the current fund, search, and gap filters.</div> : null}
      <div className="comparison-method-note">
        <ShieldCheck />
        <p>
          <strong>{mode === "structure" ? "Capital-structure screen:" : "Conservative matching:"}</strong>{" "}
          {mode === "structure" ? trancheComparison.meta.capital_structure_methodology : trancheComparison.meta.methodology}{" "}
          FV/principal is a schedule-derived comparison measure, not a quoted loan price or proof that either fund is wrong.
        </p>
      </div>
    </Panel>
  );
}

function Exposure({
  selectedFund,
  onOpenTimelineIssuer
}: {
  selectedFund: Fund | "All";
  onOpenTimelineIssuer: (issuerMatchKey: string) => void;
}) {
  const [crossFundQuery, setCrossFundQuery] = useState("");
  const [minimumFundCount, setMinimumFundCount] = useState(2);
  const categoryRows =
    selectedFund === "All"
      ? data.category_totals_latest.map((item) => ({
          ...item,
          label: item.investment_category
        }))
      : data.category_latest
          .filter((item) => item.fund === selectedFund)
          .map((item) => ({ ...item, label: item.investment_category || "Uncategorized" }));

  const topIssuers =
    selectedFund === "All"
      ? data.top_issuers_latest
      : data.top_issuers_latest.filter((item) => item.fund === selectedFund);
  const crossFundIssuers =
    selectedFund === "All"
      ? data.cross_fund_issuer_latest
      : data.cross_fund_issuer_latest.filter((item) => item.funds.includes(selectedFund));
  const rankedCrossFundIssuers = [...crossFundIssuers].sort(
    (a, b) => b.fund_count - a.fund_count || b.fair_value_mm - a.fair_value_mm
  );
  const normalizedCrossFundQuery = crossFundQuery.trim().toLowerCase();
  const filteredCrossFundIssuers = rankedCrossFundIssuers.filter((row) => {
    if (row.fund_count < minimumFundCount) return false;
    if (!normalizedCrossFundQuery) return true;
    const enrichment = findCompanyEnrichment(row.issuer_match_key);
    return [
      row.issuer_match_key,
      row.representative_issuer_name,
      row.issuer_name_variants.join(" "),
      enrichment?.display_name,
      enrichment?.mapped_company,
      enrichment?.current_sponsor
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(normalizedCrossFundQuery);
  });
  const spotlightRows = rankedCrossFundIssuers
    .filter((row) => {
      const enrichment = findCompanyEnrichment(row.issuer_match_key);
      return enrichment && !isSourceDerivedEnrichment(enrichment);
    })
    .slice(0, 6);
  const crossFundFairValue = sumBy(crossFundIssuers, (row) => row.fair_value_mm);
  const maximumOverlap = Math.max(...crossFundIssuers.map((row) => row.fund_count), 0);
  const sourcedProfileCount = crossFundIssuers.filter((row) => {
    const enrichment = findCompanyEnrichment(row.issuer_match_key);
    return enrichment && !isSourceDerivedEnrichment(enrichment);
  }).length;

  return (
    <div className="grid">
      <div className="grid kpi-grid exposure-kpi-grid">
        <MetricCard
          title="Cross-fund issuer groups"
          value={formatNumber(crossFundIssuers.length)}
          note="normalized latest-period borrower overlaps."
          icon={FileSearch}
        />
        <MetricCard
          title="Matched fair value"
          value={formatMm(crossFundFairValue)}
          note="aggregate exposure represented by overlapping issuer groups."
          icon={WalletCards}
        />
        <MetricCard
          title="Maximum overlap"
          value={`${maximumOverlap} funds`}
          note="widest verified BDC footprint for one borrower key."
          icon={Layers3}
        />
        <MetricCard
          title="Sourced profiles"
          value={formatNumber(sourcedProfileCount)}
          note="company and sponsor records linked to cross-fund names."
          icon={History}
        />
      </div>

      <Callout title="How to read exposure">{data.narrative.exposure}</Callout>

      <MarkDivergence selectedFund={selectedFund} onOpenTimelineIssuer={onOpenTimelineIssuer} />

      <Panel
        title="Cross-Fund Research Board"
        subtitle="The highest-overlap borrowers with sourced company context, sponsor ownership, current fair value, and fund-by-fund footprint."
        icon={FileSearch}
      >
        <div className="issuer-spotlight-grid">
          {spotlightRows.map((row, index) => (
            <CrossFundSpotlightCard
              row={row}
              index={index}
              key={row.issuer_match_key}
              onOpenTimelineIssuer={onOpenTimelineIssuer}
            />
          ))}
        </div>
      </Panel>

      <Panel
        title="Cross-Fund Issuer Matches"
        subtitle={`${formatNumber(filteredCrossFundIssuers.length)} issuer groups match the current research filters. The derived match key lifts latest-period overlap from ${data.raw_cross_fund_issuer_count_latest} raw display-name groups to ${data.cross_fund_issuer_latest.length} normalized groups.`}
        icon={FileSearch}
        action={
          <div className="cross-fund-controls">
            <div className="search-wrap compact-search">
              <Search />
              <input
                className="search"
                value={crossFundQuery}
                onChange={(event) => setCrossFundQuery(event.target.value)}
                placeholder="Search company, sponsor, or match key"
                aria-label="Search cross-fund issuers"
              />
            </div>
            <select
              className="select"
              value={minimumFundCount}
              onChange={(event) => setMinimumFundCount(Number(event.target.value))}
              aria-label="Minimum number of overlapping funds"
            >
              <option value={2}>2+ funds</option>
              <option value={3}>3+ funds</option>
              <option value={4}>4+ funds</option>
              <option value={5}>5+ funds</option>
            </select>
          </div>
        }
      >
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Match key</th>
                <th>Company / sponsor</th>
                <th>Funds</th>
                <th className="right">Rows</th>
                <th className="right">Fair value</th>
                <th className="right">FV / cost</th>
                <th>Source display variants</th>
              </tr>
            </thead>
            <tbody>
              {filteredCrossFundIssuers.map((row) => {
                const hasTimelinePage = timelineIssuerKeys.has(row.issuer_match_key);
                const enrichment = findCompanyEnrichment(row.issuer_match_key);
                return (
                  <tr key={row.issuer_match_key}>
                    <td className="issuer-cell">
                      {hasTimelinePage ? (
                        <a
                          className="issuer-link"
                          href="#timeline"
                          onClick={(event) => {
                            event.preventDefault();
                            onOpenTimelineIssuer(row.issuer_match_key);
                          }}
                        >
                          <strong>{row.issuer_match_key}</strong>
                        </a>
                      ) : (
                        <strong>{row.issuer_match_key}</strong>
                      )}
                      <span>{row.representative_issuer_name}</span>
                    </td>
                    <td className="company-map-cell">
                      <strong>{enrichment?.display_name || "Research pending"}</strong>
                      <span>{enrichment && !isSourceDerivedEnrichment(enrichment) ? enrichment.current_sponsor : "Schedule evidence only"}</span>
                    </td>
                    <td>
                      <div className="badge-row">
                        {row.funds.map((fund) => (
                          <FundBadge fund={fund} key={`${row.issuer_match_key}-${fund}`} />
                        ))}
                      </div>
                    </td>
                    <td className="right">{formatNumber(row.holding_rows)}</td>
                    <td className="right nowrap">{formatMm(row.fair_value_mm)}</td>
                    <td className="right nowrap">{formatCentsOnDollar(row.fair_value_mm, row.amortized_cost_mm)}</td>
                    <td>
                      <div className="variant-list">{row.issuer_name_variants.join(" | ")}</div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid two-col">
        <Panel
          title={selectedFund === "All" ? "Category Exposure" : `${selectedFund} Category Exposure`}
          subtitle="Fair value by normalized investment category."
          icon={Layers3}
        >
          <BarList
            items={categoryRows as unknown as Array<Record<string, unknown>>}
            getLabel={(item) => String(item.label)}
            getValue={(item) => Number(item.fair_value_mm || 0)}
            color={selectedFund === "All" ? "#2563eb" : fundColors[selectedFund]}
            limit={14}
          />
        </Panel>

        <Panel title="Top Issuers" subtitle="Largest normalized issuer exposures in the latest common period." icon={FileSearch}>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Fund</th>
                  <th>Issuer</th>
                  <th className="right">Rows</th>
                  <th className="right">Fair value</th>
                </tr>
              </thead>
              <tbody>
                {topIssuers.slice(0, 18).map((row) => (
                  <tr key={`${row.fund}-${row.issuer_name}`}>
                    <td>
                      <FundBadge fund={row.fund} />
                    </td>
                    <td>{row.issuer_name}</td>
                    <td className="right">{formatNumber(row.holding_rows)}</td>
                    <td className="right">{formatMm(row.fair_value_mm)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      <div className="grid two-col">
        <Panel title="Rate Mix" subtitle="Classified from fixed coupon flags and reference base-rate fields." icon={Activity}>
          <GroupedStackedBars
            rows={data.rate_mix_latest as unknown as Array<Record<string, unknown>>}
            groupKey="fund"
            segmentKey="rate_type"
            colors={rateColors}
          />
        </Panel>

        <Panel title="Maturity Profile" subtitle="Buckets are parsed from source maturity text." icon={Calendar}>
          <GroupedStackedBars
            rows={data.maturity_buckets_latest as unknown as Array<Record<string, unknown>>}
            groupKey="fund"
            segmentKey="maturity_bucket"
            colors={bucketColors}
          />
        </Panel>
      </div>

      <Panel title="Reference Base Rates" subtitle="Floating-rate labels are carried forward from each source parser." icon={Gauge}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Fund</th>
                <th>Base rate</th>
                <th className="right">Rows</th>
                <th className="right">Fair value</th>
              </tr>
            </thead>
            <tbody>
              {data.base_rate_latest
                .filter((row) => selectedFund === "All" || row.fund === selectedFund)
                .map((row) => (
                  <tr key={`${row.fund}-${row.reference_base_rate}`}>
                    <td>
                      <FundBadge fund={row.fund} />
                    </td>
                    <td>{row.reference_base_rate}</td>
                    <td className="right">{formatNumber(row.holding_rows)}</td>
                    <td className="right">{formatMm(row.fair_value_mm)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function IssuerTimelineChart({ rows, visibleFunds }: { rows: LoanTimelinePeriod[]; visibleFunds: Fund[] }) {
  const { tooltip, showTooltip, hideTooltip } = useChartTooltip();
  const periods = Array.from(new Set(rows.map((row) => row.filing_period_end))).sort();
  const points = periods.map((period) => {
    const periodRows = rows.filter((row) => row.filing_period_end === period);
    const total = sumBy(periodRows, (row) => row.fair_value_mm);
    const values = visibleFunds.reduce(
      (acc, fund) => {
        acc[fund] = sumBy(
          periodRows.filter((row) => row.fund === fund),
          (row) => row.fair_value_mm
        );
        return acc;
      },
      {} as Record<Fund, number>
    );
    return { period, total, values };
  });
  const max = Math.max(...points.map((point) => point.total), 1);
  const colors = visibleFunds.reduce(
    (acc, fund) => {
      acc[fund] = fundColors[fund];
      return acc;
    },
    {} as Record<string, string>
  );

  if (!rows.length) return <div className="empty-state">No timeline rows match the current fund filter.</div>;

  return (
    <div className="chart-shell" onMouseLeave={hideTooltip}>
      <Legend colors={colors} />
      <div className="stack-chart">
        {points.map((point) => (
          <div className="stack-row" key={point.period}>
            <div className="stack-label">{shortPeriod(point.period)}</div>
            <div
              className="stack-track"
              onMouseMove={(event) =>
                showTooltip(event, {
                  title: formatDate(point.period),
                  value: formatMm(point.total),
                  detail: "Issuer fair value"
                })
              }
            >
              {visibleFunds.map((fund) => {
                const value = point.values[fund] || 0;
                if (!value) return null;
                return (
                  <div
                    className="stack-segment"
                    key={`${point.period}-${fund}`}
                    style={{
                      "--segment-color": fundColors[fund],
                      width: `${(value / max) * 100}%`
                    } as React.CSSProperties}
                    onMouseMove={(event) => {
                      event.stopPropagation();
                      showTooltip(event, {
                        title: `${fund} - ${formatDate(point.period)}`,
                        value: formatMm(value),
                        detail: "Issuer fair value",
                        color: fundColors[fund]
                      });
                    }}
                  />
                );
              })}
            </div>
            <div className="stack-value">{formatMm(point.total, 1)}</div>
          </div>
        ))}
      </div>
      <ChartTooltip tooltip={tooltip} />
    </div>
  );
}

function leadLagLabel(status: LeadLagSummaryRow["lead_lag_status"]) {
  if (status === "junior_first") return "Junior led";
  if (status === "simultaneous") return "Same-quarter breach";
  if (status === "senior_first") return "Senior led";
  return "No sub-95 breach";
}

function CapitalStructureTimelineChart({ rows }: { rows: CapitalStructureTimelineRow[] }) {
  const { tooltip, showTooltip, hideTooltip } = useChartTooltip();
  if (!rows.length) return <div className="empty-state">No multi-quarter capital-structure series is available for this issuer.</div>;

  const periods = uniqueSorted(rows.map((row) => row.filing_period_end));
  const tiers = uniqueSorted(rows.map((row) => row.tier)).sort(
    (a, b) => (rows.find((row) => row.tier === a)?.tier_rank || 0) - (rows.find((row) => row.tier === b)?.tier_rank || 0)
  );
  const values = rows.map((row) => row.fv_to_cost_pct);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const yMin = Math.max(0, Math.floor((minimum - 10) / 10) * 10);
  const yMax = Math.max(yMin + 20, Math.ceil((maximum + 10) / 10) * 10);
  const ticks = uniqueSorted([String(yMin), "90", "95", "100", String(yMax)])
    .map(Number)
    .filter((value) => value >= yMin && value <= yMax)
    .sort((a, b) => a - b);
  const width = 760;
  const height = 310;
  const margin = { top: 20, right: 20, bottom: 48, left: 58 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const xFor = (index: number) => periods.length <= 1 ? margin.left + plotWidth / 2 : margin.left + (index / (periods.length - 1)) * plotWidth;
  const yFor = (value: number) => margin.top + (1 - (value - yMin) / Math.max(yMax - yMin, 1)) * plotHeight;

  return (
    <div className="metric-chart-wrap line-chart-wrap capital-tier-chart" onMouseLeave={hideTooltip}>
      <svg className="metric-svg line-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Capital structure mark-to-cost over time">
        {ticks.map((tick) => (
          <g key={tick}>
            <line className={tick === 90 || tick === 95 ? "stress-threshold-line" : "chart-grid-line"} x1={margin.left} x2={width - margin.right} y1={yFor(tick)} y2={yFor(tick)} />
            <text className="chart-axis-label" x={margin.left - 10} y={yFor(tick) + 4} textAnchor="end">{formatPct(tick, 0)}</text>
          </g>
        ))}
        <line className="chart-axis-line" x1={margin.left} x2={width - margin.right} y1={height - margin.bottom} y2={height - margin.bottom} />
        {periods.map((period, index) => <text className="chart-axis-label" key={period} x={xFor(index)} y={height - 18} textAnchor="middle">{shortPeriod(period)}</text>)}
        {tiers.map((tier) => {
          let drawing = false;
          const tierRows = rows.filter((row) => row.tier === tier);
          const path = periods.map((period, index) => {
            const row = tierRows.find((item) => item.filing_period_end === period);
            if (!row) {
              drawing = false;
              return "";
            }
            const command = drawing ? "L" : "M";
            drawing = true;
            return `${command} ${xFor(index).toFixed(2)} ${yFor(row.fv_to_cost_pct).toFixed(2)}`;
          }).filter(Boolean).join(" ");
          return (
            <g key={tier}>
              <path className="chart-line" d={path} stroke={capitalTierColors[tier] || "#8d9797"} />
              {tierRows.map((row) => {
                const index = periods.indexOf(row.filing_period_end);
                return (
                  <circle
                    className="chart-point"
                    key={`${tier}-${row.filing_period_end}`}
                    cx={xFor(index)}
                    cy={yFor(row.fv_to_cost_pct)}
                    r={4}
                    fill={capitalTierColors[tier] || "#8d9797"}
                    onMouseMove={(event) => showTooltip(event, {
                      title: `${tier} · ${formatDate(row.filing_period_end)}`,
                      value: formatPct(row.fv_to_cost_pct, 1),
                      detail: `${row.funds.join(", ")} · ${formatMm(row.fair_value_mm)} fair value`,
                      color: capitalTierColors[tier]
                    })}
                  />
                );
              })}
            </g>
          );
        })}
      </svg>
      <Legend colors={Object.fromEntries(tiers.map((tier) => [tier, capitalTierColors[tier] || "#8d9797"]))} />
      <ChartTooltip tooltip={tooltip} />
    </div>
  );
}

function Timeline({
  selectedFund,
  selectedIssuerKey,
  onSelectIssuer
}: {
  selectedFund: Fund | "All";
  selectedIssuerKey: string;
  onSelectIssuer: (issuerMatchKey: string) => void;
}) {
  const visibleFunds = selectedFund === "All" ? funds : [selectedFund];
  const issuer = data.loan_timeline_issuers.find((item) => item.issuer_match_key === selectedIssuerKey);
  const enrichment = findCompanyEnrichment(selectedIssuerKey);
  const periodRows = useMemo(
    () =>
      data.loan_timeline_periods.filter(
        (row) => row.issuer_match_key === selectedIssuerKey && (selectedFund === "All" || row.fund === selectedFund)
      ),
    [selectedFund, selectedIssuerKey]
  );
  const securityRows = useMemo(
    () =>
      data.loan_timeline_securities.filter(
        (row) => row.issuer_match_key === selectedIssuerKey && (selectedFund === "All" || row.fund === selectedFund)
      ),
    [selectedFund, selectedIssuerKey]
  );

  const periodTotals = periodRows.reduce(
    (acc, row) => {
      acc[row.filing_period_end] = (acc[row.filing_period_end] || 0) + row.fair_value_mm;
      return acc;
    },
    {} as Record<string, number>
  );
  const periodKeys = Object.keys(periodTotals).sort();
  const latestPeriod = periodKeys[periodKeys.length - 1] || null;
  const firstPeriod = periodKeys[0] || null;
  const latestFairValue = latestPeriod ? periodTotals[latestPeriod] : 0;
  const maxFairValue = Math.max(...Object.values(periodTotals), 0);
  const priorPeriod = periodKeys.length > 1 ? periodKeys[periodKeys.length - 2] : null;
  const priorFairValue = priorPeriod ? periodTotals[priorPeriod] : null;
  const quarterChangePct = priorFairValue ? ((latestFairValue - priorFairValue) / priorFairValue) * 100 : null;
  const latestPeriodRows = latestPeriod ? periodRows.filter((row) => row.filing_period_end === latestPeriod) : [];
  const latestCost = sumBy(latestPeriodRows, (row) => row.amortized_cost_mm);
  const latestMark = latestFairValue - latestCost;
  const currentFundFootprint = latestPeriodRows
    .slice()
    .sort((a, b) => b.fair_value_mm - a.fair_value_mm);
  const maxCurrentFundValue = Math.max(...currentFundFootprint.map((row) => row.fair_value_mm), 1);
  const issuerFundSet = new Set(issuer?.funds || []);
  const relatedIssuers = data.cross_fund_issuer_latest
    .filter((row) => row.issuer_match_key !== selectedIssuerKey)
    .map((row) => ({
      ...row,
      sharedFunds: row.funds.filter((fund) => issuerFundSet.has(fund)).length
    }))
    .filter((row) => row.sharedFunds > 0)
    .sort((a, b) => b.sharedFunds - a.sharedFunds || b.fund_count - a.fund_count || b.fair_value_mm - a.fair_value_mm)
    .slice(0, 8);
  const sourceDerivedEnrichment = isSourceDerivedEnrichment(enrichment);
  const scheduleEvidenceRows = (latestPeriod ? periodRows.filter((row) => row.filing_period_end === latestPeriod) : periodRows)
    .slice()
    .sort((a, b) => b.fair_value_mm - a.fair_value_mm);
  const sortedPeriods = [...periodRows].sort((a, b) =>
    `${b.filing_period_end}-${b.fund}`.localeCompare(`${a.filing_period_end}-${a.fund}`)
  );
  const capitalTierRows = trancheComparison.capital_structure_timeline.filter(
    (row) => row.issuer_match_key === selectedIssuerKey
  );
  const issuerLeadLagRows = researchSignals.fund_pair_lead_lag.filter(
    (row) => row.issuer_match_key === selectedIssuerKey
  );

  return (
    <div className="grid">
      <div className="grid kpi-grid">
        <MetricCard
          title="Latest issuer fair value"
          value={formatMm(latestFairValue)}
          note={latestPeriod ? `at ${formatDate(latestPeriod)}.` : "No visible period."}
          icon={WalletCards}
        />
        <MetricCard
          title="Peak issuer fair value"
          value={formatMm(maxFairValue)}
          note="highest visible quarter in this dataset."
          icon={TrendingUp}
        />
        <MetricCard
          title="Observed quarters"
          value={formatNumber(periodKeys.length)}
          note={firstPeriod && latestPeriod ? `${shortPeriod(firstPeriod)} through ${shortPeriod(latestPeriod)}.` : "No coverage."}
          icon={Calendar}
        />
        <MetricCard
          title="Security rows"
          value={formatNumber(securityRows.length)}
          note={`${visibleFunds.join(", ")} tranche-level rows.`}
          icon={Layers3}
        />
      </div>

      <section className="issuer-research-brief">
        <div className="issuer-brief-copy">
          <span className="research-kicker">Issuer research brief / {selectedIssuerKey || "unmapped"}</span>
          <h2>{enrichment?.display_name || issuer?.display_name || selectedIssuerKey}</h2>
          <p>{enrichment?.description || "This borrower is currently represented by schedule-derived exposure and timeline evidence."}</p>
        </div>
        <div className="issuer-brief-facts">
          <div>
            <span>Current sponsor</span>
            <strong>{enrichment && !sourceDerivedEnrichment ? enrichment.current_sponsor : "Research pending"}</strong>
          </div>
          <div>
            <span>Verified footprint</span>
            <strong>{issuer?.funds.join(", ") || visibleFunds.join(", ")}</strong>
          </div>
          <div>
            <span>Current mark</span>
            <strong>{formatCentsOnDollar(latestFairValue, latestCost)} <small>{formatMm(latestMark)} vs cost</small></strong>
          </div>
          <div>
            <span>Quarter movement</span>
            <strong className={typeof quarterChangePct === "number" && quarterChangePct < 0 ? "negative" : "positive"}>
              {formatPct(quarterChangePct)} <small>{priorPeriod ? `since ${shortPeriod(priorPeriod)}` : "no prior quarter"}</small>
            </strong>
          </div>
        </div>
      </section>

      <div className="grid two-col capital-timeline-grid">
        <Panel
          title="Capital Structure Mark Path"
          subtitle="Quarterly FV/cost by explicit capital tier, aggregated across the verified funds holding this issuer. Dashed guides mark 95% and 90% of cost."
          icon={LineChart}
        >
          <CapitalStructureTimelineChart rows={capitalTierRows} />
        </Panel>

        <Panel
          title="Fund-Pair Junior-vs-Senior Test"
          subtitle="Each row isolates one junior-holding fund against one first-lien-holding fund. Cross-fund and within-fund evidence are labeled explicitly."
          icon={History}
        >
          {issuerLeadLagRows.length ? (
            <div className="lead-lag-detail-list">
              {issuerLeadLagRows.map((row) => (
                <section key={`${row.issuer_match_key}-${row.junior_fund}-${row.senior_fund}-${row.junior_tier}`}>
                  <div className="lead-lag-detail-topline">
                    <span className={`waterfall-signal lead-${row.lead_lag_status}`}>{leadLagLabel(row.lead_lag_status)}</span>
                    <small>{row.comparison_scope} · {row.common_period_count} common quarters</small>
                  </div>
                  <div className="lead-lag-fund-pair">
                    <div><FundBadge fund={row.junior_fund} /><span>{row.junior_tier}</span></div>
                    <strong>→</strong>
                    <div><FundBadge fund={row.senior_fund} /><span>{row.senior_tier}</span></div>
                  </div>
                  <div className="lead-lag-breach-grid">
                    <div><span>Junior first &lt;95</span><strong>{row.junior_first_below_95_period ? shortPeriod(row.junior_first_below_95_period) : "Never"}</strong></div>
                    <div><span>Senior first &lt;95</span><strong>{row.senior_first_below_95_period ? shortPeriod(row.senior_first_below_95_period) : "Never"}</strong></div>
                    <div><span>Latest junior</span><strong>{formatPct(row.latest_junior_fv_to_cost_pct, 1)}</strong></div>
                    <div><span>Latest senior</span><strong>{formatPct(row.latest_senior_fv_to_cost_pct, 1)}</strong></div>
                  </div>
                  <p>
                    {row.lead_lag_status === "junior_first"
                      ? row.senior_first_below_95_period
                        ? `Junior capital crossed first by ${formatNumber(row.lead_quarters_at_95)} quarter${row.lead_quarters_at_95 === 1 ? "" : "s"}.`
                        : "Junior capital crossed below 95% while first-lien senior debt has remained above the threshold."
                      : row.lead_lag_status === "simultaneous"
                        ? "Both tiers first crossed below 95% in the same observed quarter."
                        : row.lead_lag_status === "senior_first"
                          ? "Senior debt crossed below 95% before the junior tier—a mark-order inversion requiring instrument-level review."
                          : "Neither tier crossed below 95% during their common observation window."}
                  </p>
                </section>
              ))}
            </div>
          ) : (
            <div className="empty-state">No explicit junior-fund and senior-fund pair has two common quarters with at least $1mm of cost in each tier.</div>
          )}
          <div className="lead-lag-method">{researchSignals.meta.pairwise_lead_lag_methodology}</div>
        </Panel>
      </div>

      <div className="grid two-col">
        <Panel
          title="Loan Exposure Over Time"
          subtitle={`${issuer?.display_name || selectedIssuerKey} funded exposure by fund and filing period.`}
          icon={LineChart}
        >
          <IssuerTimelineChart rows={periodRows} visibleFunds={visibleFunds} />
        </Panel>

        <Panel
          title="Company And Sponsor"
          subtitle={enrichment ? enrichment.mapped_company : "No enrichment record for this issuer."}
          icon={History}
        >
          {enrichment ? (
            <div className="enrichment">
              <div className="company-heading">
                <div>
                  <h3>{enrichment.display_name}</h3>
                  <p>{enrichment.mapped_company}</p>
                </div>
                <div className="confidence-badge" aria-label={`Mapping confidence ${enrichment.confidence}`}>
                  <span>Mapping confidence</span>
                  <span className={`pill confidence-${enrichment.confidence}`}>{enrichment.confidence}</span>
                </div>
              </div>
              <p className="confidence-note">
                Confidence reflects how directly this issuer was matched to the sourced company and sponsor record; it is not an
                exposure or risk rating.
              </p>
              <p className="company-description">{enrichment.description}</p>
              <div className="sponsor-box">
                <span>{sourceDerivedEnrichment ? "Latest schedule coverage" : "Current sponsor"}</span>
                <strong>
                  {sourceDerivedEnrichment
                    ? `${formatMm(latestFairValue)} across ${visibleFunds.join(", ")}${latestPeriod ? ` at ${formatDate(latestPeriod)}` : ""}`
                    : enrichment.current_sponsor}
                </strong>
              </div>
              <div className="history-block">
                <h4>{sourceDerivedEnrichment ? "Schedule evidence" : "Sponsor history"}</h4>
                {sourceDerivedEnrichment && scheduleEvidenceRows.length ? (
                  <ol className="history-list">
                    {scheduleEvidenceRows.map((row) => (
                      <li key={`${row.fund}-${row.filing_period_end}`}>
                        <span>{shortPeriod(row.filing_period_end)}</span>
                        <a href={enrichment.sources[0]?.url || "#"} target="_blank" rel="noreferrer">
                          {row.fund} reported {formatMm(row.fair_value_mm)} fair value across{" "}
                          {formatNumber(row.holding_rows)} funded row{row.holding_rows === 1 ? "" : "s"}.
                        </a>
                      </li>
                    ))}
                  </ol>
                ) : enrichment.sponsor_history.length ? (
                  <ol className="history-list">
                    {enrichment.sponsor_history.map((item) => (
                      <li key={`${item.date}-${item.event}`}>
                        <span>{item.date}</span>
                        <a href={item.source_url} target="_blank" rel="noreferrer">
                          {item.event}
                        </a>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="footer-note">No sponsor events are available for this issuer yet.</p>
                )}
              </div>
              <div className="source-list">
                {enrichment.sources.map((source) => (
                  <a href={source.url} key={source.url} target="_blank" rel="noreferrer">
                    <ExternalLink />
                    {source.title}
                  </a>
                ))}
              </div>
              {enrichment.notes ? <p className="footer-note">{enrichment.notes}</p> : null}
            </div>
          ) : (
            <div className="empty-state">No sourced company enrichment is available for this issuer.</div>
          )}
        </Panel>
      </div>

      <div className="grid two-col timeline-overview-grid">
        <Panel
          title="Current Fund Footprint"
          subtitle={latestPeriod ? `Latest funded exposure by BDC at ${formatDate(latestPeriod)}.` : "No current-period footprint is available."}
          icon={Layers3}
        >
          {currentFundFootprint.length ? (
            <div className="timeline-fund-footprint">
              {currentFundFootprint.map((row) => (
                <div className="timeline-fund-row" key={`${row.fund}-${row.filing_period_end}`}>
                  <FundBadge fund={row.fund} />
                  <div className="timeline-fund-bar"><i style={{ width: `${(row.fair_value_mm / maxCurrentFundValue) * 100}%` }} /></div>
                  <div className="timeline-fund-values">
                    <strong>{formatMm(row.fair_value_mm)}</strong>
                    <span>{formatCentsOnDollar(row.fair_value_mm, row.amortized_cost_mm)} of cost</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">No current fund exposure matches this view.</div>
          )}
        </Panel>

        <Panel
          title="Related Cross-Fund Borrowers"
          subtitle="Other normalized borrowers with the closest verified-fund footprint."
          icon={FileSearch}
        >
          <div className="related-issuer-list">
            {relatedIssuers.map((row) => {
              const relatedEnrichment = findCompanyEnrichment(row.issuer_match_key);
              return (
                <button type="button" key={row.issuer_match_key} onClick={() => onSelectIssuer(row.issuer_match_key)}>
                  <span className="related-issuer-name">
                    <strong>{relatedEnrichment?.display_name || row.representative_issuer_name}</strong>
                    <small>{row.sharedFunds} shared funds · {row.funds.join(", ")}</small>
                  </span>
                  <span className="related-issuer-value">{formatMm(row.fair_value_mm)} <ArrowUpRight /></span>
                </button>
              );
            })}
          </div>
        </Panel>
      </div>

      <div className="grid two-col">
        <Panel title="Period Exposure" subtitle="Fund-quarter funded aggregates for the selected issuer." icon={BarChart3}>
          {periodRows.length ? (
            <div className="table-wrap">
              <table className="compact-wide-table">
                <thead>
                  <tr>
                    <th>Period</th>
                    <th>Fund</th>
                    <th className="right">Rows</th>
                    <th className="right">Cost</th>
                    <th className="right">Fair value</th>
                    <th className="right">Mark</th>
                    <th className="right">FV / cost</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedPeriods.map((row) => (
                    <tr key={`${row.issuer_match_key}-${row.fund}-${row.filing_period_end}`}>
                      <td className="nowrap">{formatDate(row.filing_period_end)}</td>
                      <td>
                        <FundBadge fund={row.fund} />
                      </td>
                      <td className="right">{formatNumber(row.holding_rows)}</td>
                      <td className="right nowrap">{formatMm(row.amortized_cost_mm)}</td>
                      <td className="right nowrap">{formatMm(row.fair_value_mm)}</td>
                      <td className="right nowrap">{formatMm(row.mark_vs_cost_mm)}</td>
                      <td className="right nowrap">{formatCentsOnDollar(row.fair_value_mm, row.amortized_cost_mm)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">No period aggregates match the current filter.</div>
          )}
        </Panel>

        <Panel title="Issuer Mapping" subtitle="Source issuer variants preserved under the match key." icon={FileSearch}>
          <div className="mapping-summary">
            <div className="micro-stat">
              <span>Match key</span>
              <strong>{selectedIssuerKey || "n/a"}</strong>
            </div>
            <div className="micro-stat">
              <span>Visible funds</span>
              <strong>{visibleFunds.join(", ")}</strong>
            </div>
            <div className="micro-stat">
              <span>All funds</span>
              <strong>{issuer?.funds.join(", ") || "n/a"}</strong>
            </div>
          </div>
          <div className="variant-list mapping-variants">
            {securityRows.length
              ? uniqueSorted(securityRows.map((row) => row.issuer_name || "").filter(Boolean)).join(" | ")
              : "No visible issuer variants."}
          </div>
        </Panel>
      </div>

      <Panel
        title="Underlying Loan Rows"
        subtitle={`${securityRows.length} as-filed security rows across the selected issuer and fund filter; rows may include unfunded commitments.`}
        icon={Table2}
      >
        {securityRows.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Fund</th>
                  <th>Issuer / Security</th>
                  <th>Rate</th>
                  <th>Maturity</th>
                  <th className="right">Principal</th>
                  <th className="right">Cost</th>
                  <th className="right">Fair value</th>
                </tr>
              </thead>
              <tbody>
                {securityRows.slice(0, 220).map((row, index) => (
                  <tr key={`${row.issuer_match_key}-${row.fund}-${row.filing_period_end}-${index}`}>
                    <td className="nowrap">{formatDate(row.filing_period_end)}</td>
                    <td>
                      <FundBadge fund={row.fund} />
                    </td>
                    <td className="issuer-cell loan-cell">
                      <div className="issuer-title-row">
                        <strong>{row.issuer_name || "Unknown issuer"}</strong>
                        <ExposureTypeBadge row={row} />
                      </div>
                      <span>{row.security_signature}</span>
                    </td>
                    <td>{row.rate_raw || "n/a"}</td>
                    <td className="nowrap">{row.maturity_date || "n/a"}</td>
                    <td className="right nowrap">{formatSourceAmount(row)}</td>
                    <td className="right nowrap">{formatMm(row.amortized_cost_mm)}</td>
                    <td className="right nowrap">{formatMm(row.fair_value_mm)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">No tranche rows match the current filter.</div>
        )}
      </Panel>
    </div>
  );
}

function Holdings({ selectedFund, searchTerm }: { selectedFund: Fund | "All"; searchTerm: string }) {
  const [sort, setSort] = useState<{ key: HoldingsSortKey; direction: SortDirection }>({
    key: "fair_value_mm",
    direction: "desc"
  });
  const normalizedSearch = searchTerm.trim().toLowerCase();
  const filtered = useMemo(() => {
    return data.holdings_latest.filter((row) => {
      if (selectedFund !== "All" && row.fund !== selectedFund) return false;
      if (!normalizedSearch) return true;
      const haystack = [
        row.issuer_name,
        row.issuer_match_key,
        row.industry,
        row.investment_category,
        row.instrument_type,
        row.investment_description,
        row.exposure_type,
        row.rate_raw,
        row.maturity_date
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalizedSearch);
    });
  }, [selectedFund, normalizedSearch]);
  const sorted = useMemo(() => {
    return filtered
      .map((row, index) => ({ row, index }))
      .sort((a, b) => {
        const aValue = holdingSortValue(a.row, sort.key);
        const bValue = holdingSortValue(b.row, sort.key);
        const aMissing = aValue === null || aValue === undefined || Number.isNaN(aValue);
        const bMissing = bValue === null || bValue === undefined || Number.isNaN(bValue);

        if (aMissing && bMissing) return a.index - b.index;
        if (aMissing) return 1;
        if (bMissing) return -1;

        const delta = aValue - bValue;
        if (delta === 0) return a.index - b.index;
        return sort.direction === "asc" ? delta : -delta;
      })
      .map(({ row }) => row);
  }, [filtered, sort]);
  const holdingsDisplayLimit = 120;
  const displayedHoldingCount = Math.min(filtered.length, holdingsDisplayLimit);
  const visibleAmountFieldRows = data.amount_field_summary_latest.filter((row) => selectedFund === "All" || row.fund === selectedFund);
  const amountFieldRowsCount = sumBy(visibleAmountFieldRows, (row) => row.rows);
  const amountFieldFairValue = sumBy(visibleAmountFieldRows, (row) => row.fair_value_mm);
  const selectedLatestFundRows = data.latest_by_fund.filter((row) => selectedFund === "All" || row.fund === selectedFund);
  const selectedLatestRows = sumBy(selectedLatestFundRows, (row) => row.holding_rows);
  const selectedLatestFairValue = sumBy(selectedLatestFundRows, (row) => row.fair_value_mm);
  const amountFieldRowGap = Math.max(0, selectedLatestRows - amountFieldRowsCount);
  const amountFieldFairValueGap = Math.max(0, selectedLatestFairValue - amountFieldFairValue);

  const updateSort = (key: HoldingsSortKey) => {
    setSort((current) => ({
      key,
      direction: current.key === key && current.direction === "desc" ? "asc" : "desc"
    }));
  };

  const renderSortableHeader = (key: HoldingsSortKey) => {
    const isActive = sort.key === key;
    const Icon = isActive ? (sort.direction === "desc" ? ArrowDown : ArrowUp) : ArrowUpDown;
    const nextDirection = isActive && sort.direction === "desc" ? "ascending" : "descending";
    const label = holdingsSortLabels[key];

    return (
      <th className="right sortable-th" aria-sort={isActive ? (sort.direction === "desc" ? "descending" : "ascending") : "none"}>
        <button
          type="button"
          className={`sortable-th-button${isActive ? " active" : ""}`}
          onClick={() => updateSort(key)}
          title={`Sort ${label} ${nextDirection}`}
          aria-label={`Sort holdings by ${label} ${nextDirection}`}
        >
          <span>{label}</span>
          <Icon size={13} strokeWidth={2.2} aria-hidden="true" />
        </button>
      </th>
    );
  };

  return (
    <div className="grid">
      <Callout title="A useful but not final security tape">
        The table preserves as-filed schedule rows in the dashboard snapshot and may include unfunded commitments.
      </Callout>

      <Panel
        title="Latest Holdings"
        subtitle={`Showing ${formatNumber(displayedHoldingCount)} of ${formatNumber(filtered.length)} rows that match filters, sorted by ${holdingsSortLabels[sort.key].toLowerCase()} ${
          sort.direction === "desc" ? "high to low" : "low to high"
        }.`}
        icon={Table2}
      >
        {filtered.length ? (
          <div className="table-wrap holdings-table-wrap">
            <table className="holdings-table">
              <thead>
                <tr>
                  <th>Fund</th>
                  <th>Issuer / Instrument</th>
                  <th>Category</th>
                  <th>Rate</th>
                  <th>Maturity</th>
                  {renderSortableHeader("amortized_cost_mm")}
                  {renderSortableHeader("fair_value_mm")}
                  {renderSortableHeader("mark_vs_cost_mm")}
                  {renderSortableHeader("fv_to_cost")}
                </tr>
              </thead>
              <tbody>
                {sorted.slice(0, holdingsDisplayLimit).map((row, index) => (
                  <tr key={`${row.fund}-${row.issuer_name}-${row.fair_value_mm}-${index}`}>
                    <td>
                      <FundBadge fund={row.fund} />
                    </td>
                    <td className="issuer-cell">
                      <div className="issuer-title-row">
                        <strong>{row.issuer_name || "Unknown issuer"}</strong>
                        <ExposureTypeBadge row={row} />
                      </div>
                      <span>{row.instrument_type || row.investment_description || row.industry || "No instrument text"}</span>
                    </td>
                    <td>
                      {row.investment_category || "Uncategorized"}
                      {row.industry ? <span className="issuer-cell"><span>{row.industry}</span></span> : null}
                    </td>
                    <td>
                      <span className="badge">{row.rate_type}</span>
                      <div className="muted">{row.rate_raw || row.reference_base_rate || "Not stated"}</div>
                    </td>
                    <td className="nowrap">{row.maturity_date || row.maturity_bucket}</td>
                    <td className="right nowrap">{formatMm(row.amortized_cost_mm)}</td>
                    <td className="right nowrap">{formatMm(row.fair_value_mm)}</td>
                    <td className="right nowrap">{formatMm(row.mark_vs_cost_mm)}</td>
                    <td className="right nowrap">{formatCentsOnDollar(row.fair_value_mm, row.amortized_cost_mm)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">No holdings match the current filter.</div>
        )}
      </Panel>

      <Panel title="Funded Amount Field Labels" subtitle="Source amount labels behind funded latest-period security rows." icon={SlidersHorizontal}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Fund</th>
                <th>Amount kind</th>
                <th>Currency</th>
                <th className="right">Rows</th>
                <th className="right">Fair value</th>
              </tr>
            </thead>
            <tbody>
              {visibleAmountFieldRows
                .slice(0, 24)
                .map((row) => (
                  <tr key={`${row.fund}-${row.amount_kind}-${row.amount_currency}`}>
                    <td>
                      <FundBadge fund={row.fund} />
                    </td>
                    <td>{row.amount_kind}</td>
                    <td>{row.amount_currency}</td>
                    <td className="right">{formatNumber(row.rows)}</td>
                    <td className="right">{formatMm(row.fair_value_mm)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <p className="activity-source-note">
          Funded amount-label rows cover {formatNumber(amountFieldRowsCount)} of {formatNumber(selectedLatestRows)} latest
          rows and {formatMm(amountFieldFairValue)} of {formatMm(selectedLatestFairValue)} headline fair value.
          {amountFieldRowGap || amountFieldFairValueGap
            ? ` The remaining ${formatNumber(amountFieldRowGap)} rows / ${formatMm(amountFieldFairValueGap)} are retained in headline holdings totals, primarily FSK footnote (x) unfunded commitments, but are excluded from funded category, rate, maturity, and amount-label summaries.`
            : " No unfunded-commitment gap is present for the selected fund view."}
        </p>
      </Panel>
    </div>
  );
}

function LiabilityMaturityWall({ instruments }: { instruments: LiabilityInstrumentRow[] }) {
  const { tooltip, showTooltip, hideTooltip } = useChartTooltip();
  const years = uniqueSorted(instruments.map((instrument) => String(maturityYear(instrument.maturity_date))));
  const rows = years.map((year) => {
    const yearInstruments = instruments.filter((instrument) => String(maturityYear(instrument.maturity_date)) === year);
    const byFund = funds.reduce(
      (acc, fund) => {
        acc[fund] = sumBy(
          yearInstruments.filter((instrument) => instrument.fund === fund),
          (instrument) => instrument.outstanding_principal_mm
        );
        return acc;
      },
      {} as Record<Fund, number>
    );
    return {
      year,
      byFund,
      total: sumBy(yearInstruments, (instrument) => instrument.outstanding_principal_mm)
    };
  });
  const max = Math.max(...rows.map((row) => row.total), 1);

  return (
    <div className="liability-stack-chart" onMouseLeave={hideTooltip}>
      <Legend colors={fundColors} />
      <div className="stack-chart">
        {rows.map((row) => (
          <div className="stack-row liability-row" key={row.year}>
            <div className="stack-label">{row.year}</div>
            <div
              className="stack-track"
              onMouseMove={(event) =>
                showTooltip(event, {
                  title: row.year,
                  value: formatMm(row.total),
                  detail: "Debt maturity total"
                })
              }
            >
              {funds.map((fund) => {
                const value = row.byFund[fund];
                if (!value) return null;
                return (
                  <div
                    className="stack-segment"
                    key={fund}
                    style={
                      {
                        "--segment-color": fundColors[fund],
                        width: `${(value / max) * 100}%`
                      } as React.CSSProperties
                    }
                    onMouseMove={(event) => {
                      event.stopPropagation();
                      showTooltip(event, {
                        title: `${fund} - ${row.year}`,
                        value: formatMm(value),
                        detail: "Debt maturity",
                        color: fundColors[fund]
                      });
                    }}
                  />
                );
              })}
            </div>
            <div className="stack-value">{formatMm(row.total, 0)}</div>
          </div>
        ))}
      </div>
      <ChartTooltip tooltip={tooltip} />
    </div>
  );
}

function LiabilityFundingMix({ selectedFunds }: { selectedFunds: LiabilityFund[] }) {
  const { tooltip, showTooltip, hideTooltip } = useChartTooltip();
  return (
    <div className="liability-stack-chart" onMouseLeave={hideTooltip}>
      <Legend colors={liabilityTypeColors} />
      <div className="stack-chart">
        {selectedFunds.map((fund) => {
          const total = sumBy(fund.instruments, (instrument) => instrument.outstanding_principal_mm);
          const byType = Object.keys(liabilityTypeColors).reduce(
            (acc, type) => {
              acc[type] = sumBy(
                fund.instruments.filter((instrument) => liabilityTypeGroup(instrument.type) === type),
                (instrument) => instrument.outstanding_principal_mm
              );
              return acc;
            },
            {} as Record<string, number>
          );

          return (
            <div className="stack-row liability-row" key={fund.fund}>
              <div className="stack-label">
                <FundBadge fund={fund.fund} />
              </div>
              <div
                className="stack-track"
                onMouseMove={(event) =>
                  showTooltip(event, {
                    title: fund.fund,
                    value: formatMm(total),
                    detail: "Total debt outstanding",
                    color: fundColors[fund.fund]
                  })
                }
              >
                {Object.entries(byType).map(([type, value]) => {
                  if (!value) return null;
                  return (
                    <div
                      className="stack-segment"
                      key={type}
                      style={
                        {
                          "--segment-color": liabilityTypeColors[type] || liabilityTypeColors.Other,
                          width: `${total ? (value / total) * 100 : 0}%`
                        } as React.CSSProperties
                      }
                      onMouseMove={(event) => {
                        event.stopPropagation();
                        showTooltip(event, {
                          title: `${fund.fund} - ${type}`,
                          value: formatMm(value),
                          detail: `${formatPct(total ? (value / total) * 100 : 0)} of debt`,
                          color: liabilityTypeColors[type] || liabilityTypeColors.Other
                        });
                      }}
                    />
                  );
                })}
              </div>
              <div className="stack-value">{formatMm(total, 0)}</div>
            </div>
          );
        })}
      </div>
      <ChartTooltip tooltip={tooltip} />
    </div>
  );
}

function LiabilitySnapshotTable({ selectedFunds }: { selectedFunds: LiabilityFund[] }) {
  return (
    <div className="table-wrap">
      <table className="compact-wide-table">
        <thead>
          <tr>
            <th>Fund</th>
            <th className="right">Debt outstanding</th>
            <th className="right">Carrying value</th>
            <th className="right">Availability</th>
            <th className="right">Asset coverage</th>
            <th className="right">Debt cost</th>
          </tr>
        </thead>
        <tbody>
          {selectedFunds.map((fund) => (
            <tr key={fund.fund}>
              <td>
                <FundBadge fund={fund.fund} />
                <div className="muted">{fund.company_name}</div>
              </td>
              <td className="right nowrap">{formatMm(fund.total_outstanding_principal_mm)}</td>
              <td className="right nowrap">{formatMm(fund.total_carrying_value_mm)}</td>
              <td className="right nowrap">{formatMm(fund.total_available_mm)}</td>
              <td className="right nowrap">{formatPct(fund.asset_coverage_pct)}</td>
              <td className="right nowrap" title={fund.debt_cost_label}>
                {formatPct(fund.debt_cost_pct)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LiabilityInstrumentTable({ instruments }: { instruments: LiabilityInstrumentRow[] }) {
  return (
    <div className="table-wrap">
      <table className="liability-table">
        <thead>
          <tr>
            <th>Fund</th>
            <th>Instrument</th>
            <th>Stack</th>
            <th>Rate</th>
            <th>Maturity</th>
            <th className="right">Outstanding</th>
            <th className="right">Available</th>
            <th className="right">Carrying</th>
            <th className="right">Source</th>
          </tr>
        </thead>
        <tbody>
          {instruments
            .slice()
            .sort((a, b) => a.maturity_date.localeCompare(b.maturity_date) || a.fund.localeCompare(b.fund))
            .map((instrument) => (
              <tr key={`${instrument.fund}-${instrument.name}`}>
                <td>
                  <FundBadge fund={instrument.fund} />
                </td>
                <td className="issuer-cell">
                  <strong>{instrument.name}</strong>
                  {instrument.notes ? <span>{instrument.notes}</span> : null}
                </td>
                <td>
                  <span className="badge">{liabilityTypeGroup(instrument.type)}</span>
                  <div className="muted">{instrument.secured ? "Secured" : "Unsecured"}</div>
                </td>
                <td>
                  <span className="badge">{instrument.rate_type}</span>
                  <div className="muted">{instrument.rate_text}</div>
                </td>
                <td className="nowrap">{formatDate(instrument.maturity_date)}</td>
                <td className="right nowrap">{formatMm(instrument.outstanding_principal_mm)}</td>
                <td className="right nowrap">{formatMm(instrument.available_mm || 0)}</td>
                <td className="right nowrap">{formatMm(instrument.carrying_value_mm)}</td>
                <td className="right nowrap">p. {instrument.source_page}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

function TracePriceChart({ points }: { points: TracePoint[] }) {
  const plotted = points.filter((point): point is TracePoint & { price: number } => point.price !== null);
  if (plotted.length < 2) {
    return <div className="funding-chart-empty">No executed-trade price history is available for this CUSIP.</div>;
  }
  const width = 760;
  const height = 210;
  const insetX = 18;
  const insetY = 18;
  const prices = plotted.map((point) => point.price);
  const rawMin = Math.min(...prices);
  const rawMax = Math.max(...prices);
  const padding = Math.max(0.35, (rawMax - rawMin) * 0.16);
  const min = rawMin - padding;
  const max = rawMax + padding;
  const x = (index: number) => insetX + (index / (plotted.length - 1)) * (width - insetX * 2);
  const y = (price: number) => insetY + ((max - price) / (max - min || 1)) * (height - insetY * 2);
  const line = plotted.map((point, index) => `${x(index)},${y(point.price)}`).join(" ");
  const area = `${insetX},${height - insetY} ${line} ${width - insetX},${height - insetY}`;
  return (
    <div className="funding-chart-shell">
      <svg className="funding-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="FINRA TRACE end-of-day price history">
        {[0.25, 0.5, 0.75].map((ratio) => (
          <line key={ratio} x1={insetX} x2={width - insetX} y1={height * ratio} y2={height * ratio} className="funding-chart-grid" />
        ))}
        <polygon points={area} className="funding-chart-area" />
        <polyline points={line} className="funding-chart-line" />
        <circle cx={x(plotted.length - 1)} cy={y(plotted[plotted.length - 1].price)} r="4" className="funding-chart-dot" />
      </svg>
      <div className="funding-chart-axis">
        <span>{formatShortDate(plotted[0].date)}</span>
        <span>{rawMin.toFixed(2)}–{rawMax.toFixed(2)} price range</span>
        <span>{formatShortDate(plotted[plotted.length - 1].date)}</span>
      </div>
    </div>
  );
}

function FundingMarket({ selectedFund }: { selectedFund: Fund | "All" }) {
  const [selectedSeriesId, setSelectedSeriesId] = useState<string | null>(null);
  const scopedSeries = fundingMarket.series.filter(
    (series) =>
      series.status === "outstanding_candidate" && (selectedFund === "All" || series.ticker === selectedFund)
  );
  const scopedEvents = fundingMarket.issuance_events.filter(
    (event) => selectedFund === "All" || event.ticker === selectedFund
  );
  const scopedFunds = fundingMarket.funds.filter((fund) => selectedFund === "All" || fund.ticker === selectedFund);
  const tradedSeries = scopedSeries.filter((series) => series.trace_status === "matched" && series.last_price !== null);
  const activeSeries =
    scopedSeries.find((series) => series.series_id === selectedSeriesId) ||
    tradedSeries.slice().sort((a, b) => b.observation_count - a.observation_count)[0] ||
    scopedSeries[0];
  const visibleTape = scopedSeries
    .slice()
    .sort((a, b) => {
      if (a.trace_status === "matched" && b.trace_status !== "matched") return -1;
      if (b.trace_status === "matched" && a.trace_status !== "matched") return 1;
      return a.maturity_date.localeCompare(b.maturity_date);
    });
  const maturityRows = Array.from(
    scopedSeries.reduce((map, series) => {
      const amount = series.gross_issued_mm || 0;
      map.set(series.maturity_year, (map.get(series.maturity_year) || 0) + amount);
      return map;
    }, new Map<number, number>())
  ).sort(([yearA], [yearB]) => yearA - yearB);
  const maxMaturity = Math.max(...maturityRows.map(([, amount]) => amount), 1);
  const grossCandidate = sumBy(scopedSeries, (series) => series.gross_issued_mm || 0);
  const nextMaturityYear = maturityRows[0]?.[0];
  const nextMaturityAmount = maturityRows[0]?.[1] || 0;
  const cusipCoverage = scopedSeries.length
    ? (scopedSeries.filter((series) => series.cusip).length / scopedSeries.length) * 100
    : 0;

  return (
    <div className="grid funding-market-layer">
      <section className="panel funding-hero">
        <div className="funding-hero-copy">
          <span className="funding-eyebrow">SEC issuance × FINRA TRACE</span>
          <h2>BDC funding market</h2>
          <p>
            Follow public note issuance from pricing through secondary-market trading, then read the maturity wall as a
            refinancing calendar—not just a debt footnote.
          </p>
        </div>
        <div className="funding-hero-stats">
          <div><span>Gross candidate notes</span><strong>{formatMm(grossCandidate, 0)}</strong></div>
          <div><span>TRACE-linked</span><strong>{tradedSeries.length}/{scopedSeries.length}</strong></div>
          <div><span>Next wall</span><strong>{nextMaturityYear ? `${nextMaturityYear} · ${formatMm(nextMaturityAmount, 0)}` : "—"}</strong></div>
          <div><span>CUSIP coverage</span><strong>{formatPct(cusipCoverage, 0)}</strong></div>
        </div>
      </section>

      {scopedSeries.length ? (
        <>
          <div className="grid funding-top-grid">
            <Panel
              title="Refinancing wall"
              subtitle="Gross issued principal for series that have not reached legal maturity; tenders and repurchases may reduce actual outstanding debt."
              icon={Calendar}
            >
              <div className="funding-wall">
                {maturityRows.map(([year, amount]) => (
                  <div className="funding-wall-row" key={year}>
                    <span>{year}</span>
                    <div className="funding-wall-track"><i style={{ width: `${Math.max(3, (amount / maxMaturity) * 100)}%` }} /></div>
                    <strong>{formatMm(amount, 0)}</strong>
                  </div>
                ))}
              </div>
            </Panel>

            <Panel
              title={activeSeries ? `${activeSeries.ticker} · ${activeSeries.security_title}` : "TRACE price history"}
              subtitle={activeSeries?.cusip ? `CUSIP ${activeSeries.cusip} · executed-trade EOD observations` : "No verified CUSIP selected"}
              icon={LineChart}
            >
              {activeSeries ? (
                <>
                  <div className="funding-bond-strip">
                    <div><span>Last price</span><strong>{activeSeries.last_price?.toFixed(3) || "—"}</strong></div>
                    <div><span>Last yield</span><strong>{formatPct(activeSeries.last_yield_pct, 2)}</strong></div>
                    <div><span>30d price</span><strong className={toneClass(activeSeries.price_change_30d)}>{activeSeries.price_change_30d === null ? "—" : `${activeSeries.price_change_30d >= 0 ? "+" : ""}${activeSeries.price_change_30d.toFixed(2)}`}</strong></div>
                    <div><span>Last trade</span><strong>{activeSeries.last_trade_date ? formatShortDate(activeSeries.last_trade_date) : "—"}</strong></div>
                  </div>
                  <TracePriceChart points={activeSeries.history} />
                </>
              ) : null}
            </Panel>
          </div>

          <Panel
            title="Public bond tape"
            subtitle={`${visibleTape.length} current candidate series · click a row to change the TRACE chart.`}
            icon={Activity}
          >
            <div className="table-wrap funding-tape-wrap">
              <table className="compact-wide-table funding-tape">
                <thead><tr><th>Fund / note</th><th className="right">Gross issued</th><th>Maturity</th><th className="right">Price</th><th className="right">Yield</th><th className="right">30d Δ</th><th>TRACE date</th><th>CUSIP</th></tr></thead>
                <tbody>
                  {visibleTape.map((series) => (
                    <tr key={series.series_id} className={activeSeries?.series_id === series.series_id ? "selected" : ""} onClick={() => setSelectedSeriesId(series.series_id)}>
                      <td className="issuer-cell"><strong>{series.ticker} · {series.security_title}</strong><span>{series.company_name}</span></td>
                      <td className="right">{series.gross_issued_mm === null ? "—" : formatMm(series.gross_issued_mm, 0)}</td>
                      <td>{formatShortDate(series.maturity_date)}</td>
                      <td className="right">{series.last_price?.toFixed(3) || "—"}</td>
                      <td className="right">{formatPct(series.last_yield_pct, 2)}</td>
                      <td className={`right ${toneClass(series.price_change_30d)}`}>{series.price_change_30d === null ? "—" : `${series.price_change_30d >= 0 ? "+" : ""}${series.price_change_30d.toFixed(2)}`}</td>
                      <td>{series.last_trade_date ? formatShortDate(series.last_trade_date) : <span className="coverage-badge registry_only">unmatched</span>}</td>
                      <td>{series.finra_url ? <a href={series.finra_url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>{series.cusip}<ExternalLink className="inline-link-icon" /></a> : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <div className="grid funding-bottom-grid">
            <Panel title="Issuer funding comparison" subtitle="Current candidate public notes and observable secondary yields." icon={BarChart3}>
              <div className="funding-fund-list">
                {scopedFunds.map((fund) => (
                  <div className="funding-fund-row" key={fund.ticker}>
                    <FundBadge fund={fund.ticker} />
                    <div><span>{fund.outstanding_candidate_series_count} series</span><strong>{formatMm(fund.outstanding_candidate_gross_mm, 0)}</strong></div>
                    <div><span>weighted coupon</span><strong>{formatPct(fund.weighted_coupon_pct, 2)}</strong></div>
                    <div><span>TRACE yield</span><strong>{formatPct(fund.trace_last_yield_pct, 2)}</strong></div>
                  </div>
                ))}
              </div>
            </Panel>
            <Panel title="Latest issuance" subtitle="Most recent SEC pricing documents in the selected scope." icon={History}>
              <div className="funding-event-list">
                {scopedEvents.slice(0, 8).map((event) => (
                  <a className="funding-event" key={event.event_id} href={event.source_documents[0]?.url} target="_blank" rel="noreferrer">
                    <span>{formatShortDate(event.pricing_date)}</span>
                    <strong>{event.ticker} · {event.security_title}</strong>
                    <em>{event.offering_amount_mm === null ? "amount under review" : formatMm(event.offering_amount_mm, 0)}{event.is_reopening ? " · reopening" : ""}</em>
                  </a>
                ))}
              </div>
            </Panel>
          </div>

          <Callout title="Coverage and interpretation">
            The issuance ledger begins {formatDate(fundingMarket.meta.sec_start_date)} and is rebuilt from SEC 424B2,
            424B3, 424B5, and FWP documents. TRACE adds executed-trade end-of-day prices and yields where a verified
            CUSIP is present; it is not a quote feed. Gross issued principal is intentionally labeled as a candidate
            outstanding amount until tenders, open-market repurchases, and paydowns are reconciled.
          </Callout>
        </>
      ) : (
        <Callout title={`${selectedFund} is outside the current funding build`}>
          The automated SEC issuance and TRACE layer currently covers ARCC, BBDC, BXSL, FSK, GBDC, MAIN, OBDC, and TSLX.
        </Callout>
      )}
    </div>
  );
}

function Liabilities({ selectedFund }: { selectedFund: Fund | "All" }) {
  return (
    <div className="grid">
      <FundingMarket selectedFund={selectedFund} />
      <FiledLiabilities selectedFund={selectedFund} />
    </div>
  );
}

function FiledLiabilities({ selectedFund }: { selectedFund: Fund | "All" }) {
  const selectedFunds = liabilityStack.funds.filter((fund) => selectedFund === "All" || fund.fund === selectedFund);
  if (!selectedFunds.length) {
    return (
      <div className="grid">
        <Callout title={`${selectedFund} liability stack is not backfilled yet`}>
          The verified holdings expansion is complete for {selectedFund}, but the instrument-level debt and liquidity
          model currently covers BXSL, FSK, and TSLX. This tab remains blank until the same filing-sourced liability
          review is completed for the selected fund.
        </Callout>
      </div>
    );
  }
  const instruments = selectedFunds.flatMap((fund) =>
    fund.instruments.map((instrument) => ({
      ...instrument,
      fund: fund.fund,
      company_name: fund.company_name,
      source_file: fund.source_file
    }))
  );
  const totalOutstanding = sumBy(instruments, (instrument) => instrument.outstanding_principal_mm);
  const totalAvailability = sumBy(selectedFunds, (fund) => fund.total_available_mm);
  const securedDebt = sumBy(
    instruments.filter((instrument) => instrument.secured),
    (instrument) => instrument.outstanding_principal_mm
  );
  const sofrLinkedDebt = sumBy(
    instruments.filter((instrument) => isSofrLinked(instrument)),
    (instrument) => instrument.outstanding_principal_mm
  );
  const minAssetCoverage = Math.min(...selectedFunds.map((fund) => fund.asset_coverage_pct));
  const nextMaturity = instruments
    .slice()
    .sort((a, b) => a.maturity_date.localeCompare(b.maturity_date))[0];
  const sofrSensitivity = sofrLinkedDebt * 0.01;
  const asOfDate = new Date(`${liabilityStack.as_of_date}T00:00:00`);
  const nearTermCutoff = new Date(asOfDate);
  nearTermCutoff.setMonth(nearTermCutoff.getMonth() + 18);
  const nearTermMaturityDebt = sumBy(
    instruments.filter((instrument) => {
      const maturity = new Date(`${instrument.maturity_date}T00:00:00`);
      return maturity >= asOfDate && maturity <= nearTermCutoff;
    }),
    (instrument) => instrument.outstanding_principal_mm
  );
  const securedDebtPct = totalOutstanding ? (securedDebt / totalOutstanding) * 100 : 0;
  const unsecuredDebtPct = totalOutstanding ? ((totalOutstanding - securedDebt) / totalOutstanding) * 100 : 0;
  const nearTermMaturityPct = totalOutstanding ? (nearTermMaturityDebt / totalOutstanding) * 100 : 0;
  const sofrLinkedDebtPct = totalOutstanding ? (sofrLinkedDebt / totalOutstanding) * 100 : 0;
  const liabilityPrimerCards = [
    {
      title: "Borrowing-base pressure",
      value: formatPct(securedDebtPct),
      detail: "selected debt is secured",
      body:
        "Secured facilities are usually cheapest, but collateral eligibility and advance rates can shrink capacity when marks or non-accruals move.",
      icon: Database
    },
    {
      title: "Unsecured cushion",
      value: formatPct(unsecuredDebtPct),
      detail: "selected debt is unsecured",
      body:
        "Unsecured notes cost more, but they do not carry the same borrowing-base tripwire and can preserve unencumbered asset flexibility.",
      icon: ShieldCheck
    },
    {
      title: "Refinancing window",
      value: formatPct(nearTermMaturityPct),
      detail: `${formatMm(nearTermMaturityDebt, 0)} due within 18 months`,
      body:
        "A maturity wall matters most when low-coupon debt has to roll into a wider market, because the drag flows directly into NII.",
      icon: Calendar
    },
    {
      title: "Base-rate exposure",
      value: formatPct(sofrLinkedDebtPct),
      detail: "floating or swapped floating",
      body:
        "Floating assets and floating liabilities partly hedge each other, but lower SOFR can still compress asset yields before every funding cost resets.",
      icon: Activity
    }
  ];
  const bxslFund = liabilityStack.funds.find((fund) => fund.fund === "BXSL");
  const bxslRefiNotes = bxslFund?.instruments.filter((instrument) => bxslLowCouponRefiNames.has(instrument.name)) || [];
  const bxslOriginalLowCouponPrincipal = sumBy(bxslRefiNotes, (instrument) => instrument.outstanding_principal_mm);
  const bxslOriginalLowCouponCost = sumBy(bxslRefiNotes, (instrument) => {
    const coupon = firstPercentFromText(instrument.rate_text);
    return coupon === null ? 0 : (instrument.outstanding_principal_mm * coupon) / 100;
  });
  const bxslAlreadyRepricedPrincipal = bxslQ12026DebtUpdate.new_note_principal_mm;
  const bxslAlreadyRepricedAnnualDrag =
    (bxslAlreadyRepricedPrincipal *
      (bxslQ12026DebtUpdate.new_note_coupon_pct - bxslQ12026DebtUpdate.paid_note_coupon_pct)) /
    100;
  const bxslRefiPrincipal = Math.max(0, bxslOriginalLowCouponPrincipal - bxslAlreadyRepricedPrincipal);
  const bxslRefiOldCouponCost = Math.max(
    0,
    bxslOriginalLowCouponCost -
      (bxslAlreadyRepricedPrincipal * bxslQ12026DebtUpdate.paid_note_coupon_pct) / 100
  );
  const bxslRefiOldCouponPct = bxslRefiPrincipal ? (bxslRefiOldCouponCost / bxslRefiPrincipal) * 100 : null;
  const bxslRefiCouponDrag =
    bxslRefiOldCouponPct === null
      ? 0
      : (bxslRefiPrincipal * (bxslRecentPricedOffering.coupon_pct - bxslRefiOldCouponPct)) / 100;
  const bxslRefiYieldDrag =
    bxslRefiOldCouponPct === null
      ? 0
      : (bxslRefiPrincipal * (bxslRecentPricedOffering.yield_pct - bxslRefiOldCouponPct)) / 100;
  const bxslAllInResetCouponDrag = bxslAlreadyRepricedAnnualDrag + bxslRefiCouponDrag;
  const bxslAllInResetYieldDrag = bxslAlreadyRepricedAnnualDrag + bxslRefiYieldDrag;
  const latestBxslFact = quarterlyFacts.latest_rows.find((row) => row.fund === "BXSL");
  const bxslAnnualizedNii = latestBxslFact?.nii_mm ? latestBxslFact.nii_mm * 4 : null;
  const bxslRefiCouponDragPctOfNii = bxslAnnualizedNii ? (bxslRefiCouponDrag / bxslAnnualizedNii) * 100 : null;
  const bxslRefiYieldDragPctOfNii = bxslAnnualizedNii ? (bxslRefiYieldDrag / bxslAnnualizedNii) * 100 : null;
  const bxslAllInResetCouponDragPctOfNii = bxslAnnualizedNii ? (bxslAllInResetCouponDrag / bxslAnnualizedNii) * 100 : null;
  const bxslAllInResetYieldDragPctOfNii = bxslAnnualizedNii ? (bxslAllInResetYieldDrag / bxslAnnualizedNii) * 100 : null;
  const showBxslRefiThought = (selectedFund === "All" || selectedFund === "BXSL") && bxslRefiNotes.length > 0;

  return (
    <div className="grid">
      <div className="grid kpi-grid">
        <MetricCard
          title="Debt outstanding"
          value={formatMm(totalOutstanding)}
          note={`principal across ${selectedFunds.length} selected fund${selectedFunds.length === 1 ? "" : "s"}.`}
          icon={WalletCards}
        />
        <MetricCard
          title="Available capacity"
          value={formatMm(totalAvailability)}
          note="subject to borrowing-base, LC, and asset-coverage constraints."
          icon={Database}
        />
        <MetricCard
          title="Lowest coverage"
          value={formatPct(minAssetCoverage)}
          note={`1940 Act floor is 150%; next maturity is ${nextMaturity ? `${nextMaturity.fund} ${formatShortDate(nextMaturity.maturity_date)}` : "n/a"}.`}
          icon={ShieldCheck}
        />
        <MetricCard
          title="+100 bps SOFR hit"
          value={formatMm(sofrSensitivity)}
          note={`${formatPct((sofrLinkedDebt / totalOutstanding) * 100)} of selected debt is floating or swapped floating.`}
          icon={Activity}
        />
      </div>

      <div className="grid liability-primer-grid">
        {liabilityPrimerCards.map((card) => {
          const Icon = card.icon;
          return (
            <section className="panel liability-primer-card" key={card.title}>
              <div className="liability-primer-top">
                <span className="liability-primer-icon">
                  <Icon />
                </span>
                <span>{card.title}</span>
              </div>
              <div className="liability-primer-value">{card.value}</div>
              <p className="liability-primer-detail">{card.detail}</p>
              <p className="liability-primer-body">{card.body}</p>
            </section>
          );
        })}
      </div>

      <Callout title="SOFR anchor">
        The debt tables are as of {formatDate(liabilityStack.as_of_date)}. The SOFR workbook shows{" "}
        {formatPct(liabilityStack.sofr.debt_date_rate_pct)} on {formatDate(liabilityStack.sofr.debt_date_rate_date)} and{" "}
        {formatPct(liabilityStack.sofr.latest_rate_pct)} on the latest row, {formatDate(liabilityStack.sofr.latest_rate_date)}.
      </Callout>

      {showBxslRefiThought ? (
        <Panel
          title="Food for Thought"
          subtitle={`Low-coupon reset framing: BXSL had ${formatMm(
            bxslOriginalLowCouponPrincipal,
            0
          )} of cheap 2026/2027 fixed notes at year-end; Q1 replaced ${formatMm(
            bxslAlreadyRepricedPrincipal,
            0
          )} with the September 2029 note, leaving about ${formatMm(bxslRefiPrincipal, 0)} as the simple stress base.`}
          icon={Gauge}
        >
          <div className="refi-thought-grid">
            <div className="micro-stat">
              <span>May 2026 deal</span>
              <strong>{formatPct(bxslRecentPricedOffering.coupon_pct, 2)} coupon</strong>
            </div>
            <div className="micro-stat">
              <span>Original cheap stack</span>
              <strong>{formatMm(bxslOriginalLowCouponPrincipal, 0)}</strong>
            </div>
            <div className="micro-stat">
              <span>Less Sep. 2029 note</span>
              <strong>{formatMm(bxslQ12026DebtUpdate.new_note_principal_mm, 0)} at {formatPct(bxslQ12026DebtUpdate.new_note_coupon_pct, 2)}</strong>
            </div>
            <div className="micro-stat">
              <span>Stress base</span>
              <strong>{formatMm(bxslRefiPrincipal, 0)}</strong>
            </div>
            <div className="micro-stat">
              <span>Forward NII hit</span>
              <strong>
                {formatPct(bxslRefiCouponDragPctOfNii, 1)}-{formatPct(bxslRefiYieldDragPctOfNii, 1)}
              </strong>
            </div>
          </div>
          <p className="refi-thought-copy">
            The Q1 2026 filing says the {bxslQ12026DebtUpdate.paid_note_name} matured and were paid off on{" "}
            {formatDate(bxslQ12026DebtUpdate.paid_note_maturity_date)}, and BXSL issued {formatMm(bxslQ12026DebtUpdate.new_note_principal_mm, 0)} of{" "}
            {formatPct(bxslQ12026DebtUpdate.new_note_coupon_pct, 2)} {bxslQ12026DebtUpdate.new_note_name} on{" "}
            {formatDate(bxslQ12026DebtUpdate.new_note_issue_date)}. The later May 14, 2026 priced offering came at a{" "}
            {formatPct(bxslRecentPricedOffering.coupon_pct, 2)} coupon and {formatPct(bxslRecentPricedOffering.yield_pct, 3)} yield. If BXSL's remaining{" "}
            {formatMm(bxslRefiPrincipal, 0)} old-note equivalent at roughly {formatPct(bxslRefiOldCouponPct, 2)} were replaced at that level, annual
            interest expense would rise about {formatMm(bxslRefiCouponDrag)}-{formatMm(bxslRefiYieldDrag)}, or roughly{" "}
            {formatPct(bxslRefiCouponDragPctOfNii, 1)}-{formatPct(bxslRefiYieldDragPctOfNii, 1)} of annualized Q1 2026
            NII. Including the March 2026 5.25% note as part of the broader low-coupon reset, the all-in gross drag is
            about {formatMm(bxslAllInResetCouponDrag)}-{formatMm(bxslAllInResetYieldDrag)}, or roughly{" "}
            {formatPct(bxslAllInResetCouponDragPctOfNii, 1)}-{formatPct(bxslAllInResetYieldDragPctOfNii, 1)} of annualized
            Q1 NII. The May 2026 bond is post-Q1, so its interest cost has not shown up in any reviewed 10-Q yet. This is a
            gross stress, not a forecast; timing, swaps, repayment mix, incentive-fee offsets, asset yields, and
            secured-facility usage can change the realized hit. FSK also has low-coupon fixed-rate unsecured bonds coming
            up, so this reset question is not unique to BXSL.
          </p>
          <p className="refi-thought-source">
            Sources: {bxslQ12026DebtUpdate.source_file}; {bxslRecentPricedOffering.source_file}; dashboard debt stack as of{" "}
            {formatDate(liabilityStack.as_of_date)}.
          </p>
        </Panel>
      ) : null}

      <div className="grid two-col">
        <Panel title="Maturity Wall" subtitle="Outstanding principal by legal maturity year, stacked by fund." icon={Calendar}>
          <LiabilityMaturityWall instruments={instruments} />
        </Panel>
        <Panel title="Funding Mix" subtitle="Debt stack by fund: secured facilities, unsecured notes, and CLO/securitization debt." icon={Layers3}>
          <LiabilityFundingMix selectedFunds={selectedFunds} />
        </Panel>
      </div>

      <Panel title="Fund Liability Snapshot" subtitle="Source values from the 2025 10-K debt footnotes." icon={Gauge}>
        <LiabilitySnapshotTable selectedFunds={selectedFunds} />
      </Panel>

      <Panel
        title="Instrument Detail"
        subtitle={`${instruments.length} debt instruments, sorted by maturity. Carrying value appears where the 10-K table disclosed it.`}
        icon={Table2}
      >
        <LiabilityInstrumentTable instruments={instruments} />
      </Panel>

      <div className="grid three-col source-note-grid">
        {selectedFunds.map((fund) => (
          <section className="panel source-note" key={fund.fund}>
            <div className="fund-row">
              <div>
                <h3 className="fund-name">{fund.fund} source notes</h3>
                <p className="fund-full">
                  {fund.source_file.split("/").pop()} pages {fund.source_pages.join(", ")}
                </p>
              </div>
              <FundBadge fund={fund.fund} />
            </div>
            <ul>
              {fund.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

function Universe() {
  const [query, setQuery] = useState("");
  const [coverageFilter, setCoverageFilter] = useState<UniverseCoverageStatus | "all">("all");
  const normalizedQuery = query.trim().toLowerCase();
  const rows = bdcUniverse.rows.filter((row) => {
    const matchesCoverage = coverageFilter === "all" || row.coverage_status === coverageFilter;
    const haystack = [row.name, row.ticker, row.cik, row.file_number, row.city, row.state]
      .filter((value) => value !== null && value !== undefined)
      .join(" ")
      .toLowerCase();
    return matchesCoverage && (!normalizedQuery || haystack.includes(normalizedQuery));
  });
  const bulkCoverageRows = bdcUniverse.rows.filter((row) => row.bulk_soi_fact_rows > 0).length;

  return (
    <div className="grid">
      <div className="section-heading">
        <Database />
        <div>
          <h2>EdgarTools BDC Universe</h2>
          <p>Discovery coverage is broad; verified holdings remain behind reconciliation gates.</p>
        </div>
      </div>

      <div className="grid kpi-grid">
        <MetricCard
          title="Universe entities"
          value={formatNumber(bdcUniverse.meta.universe_entities)}
          note={`${formatNumber(bdcUniverse.meta.registry_entities)} in the current EdgarTools registry plus companies found in SEC bulk data.`}
          icon={Database}
        />
        <MetricCard
          title="Active registry"
          value={formatNumber(bdcUniverse.meta.active_registry_entities)}
          note="Entities marked active in the current EdgarTools BDC report."
          icon={Activity}
        />
        <MetricCard
          title="Bulk SOI coverage"
          value={formatNumber(bulkCoverageRows)}
          note={`${bdcUniverse.meta.bulk_period}; ${formatNumber(bdcUniverse.meta.bulk_soi_entries)} tagged schedule rows.`}
          icon={Layers3}
        />
        <MetricCard
          title="Verified holdings"
          value={formatNumber(bdcUniverse.meta.verified_funds)}
          note="Eight reconciled holdings funds through Q1 2026."
          icon={ShieldCheck}
        />
      </div>

      <Callout title="How to read coverage">
        The universe screen includes every entity found in EdgarTools&apos; current BDC registry or its latest SEC bulk
        Schedule of Investments dataset. A bulk-data badge is a discovery signal, not a validation stamp. Only the eight
        verified funds feed portfolio rankings, issuer overlap, marks, rates, and maturity analytics. The requested
        eleven-fund cohort also shows its tracker audit result below.
      </Callout>

      <Panel
        title="BDC Coverage Directory"
        subtitle={`${formatNumber(rows.length)} of ${formatNumber(bdcUniverse.rows.length)} entities match the current filters.`}
        icon={FileSearch}
        action={
          <div className="panel-controls universe-controls">
            <div className="search-wrap">
              <Search />
              <input
                className="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search name, ticker, CIK, state"
                aria-label="Search BDC universe"
              />
            </div>
            <select
              className="select"
              value={coverageFilter}
              onChange={(event) => setCoverageFilter(event.target.value as UniverseCoverageStatus | "all")}
              aria-label="Coverage status"
            >
              <option value="all">All coverage</option>
              <option value="verified_holdings">Verified holdings</option>
              <option value="bulk_soi_available">SEC bulk SOI available</option>
              <option value="registry_only">Registry only</option>
            </select>
          </div>
        }
      >
        <div className="table-wrap universe-table-wrap">
          <table className="compact-wide-table">
            <thead>
              <tr>
                <th>BDC</th>
                <th>Coverage</th>
                <th>Tracker audit</th>
                <th>Location</th>
                <th>Active</th>
                <th>Latest registry filing</th>
                <th className="right">Bulk SOI facts</th>
                <th className="right">Verified FV</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.cik}>
                  <td className="issuer-cell">
                    <strong>{row.ticker ? <FundBadge fund={row.ticker} /> : row.name}</strong>
                    <span>{row.ticker ? row.name : `CIK ${row.cik}`}</span>
                  </td>
                  <td>
                    <span className={`coverage-badge ${row.coverage_status}`}>{row.coverage_label}</span>
                  </td>
                  <td>
                    {row.tracker_audit_status ? (
                      <span className={`coverage-badge audit-${row.tracker_audit_status}`}>
                        {row.tracker_audit_status === "verified" ? "Promoted" : "Needs custom extraction"}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>{[row.city, row.state].filter(Boolean).join(", ") || "n/a"}</td>
                  <td>{row.is_active === null ? "Unknown" : row.is_active ? "Yes" : "No"}</td>
                  <td>
                    {row.last_filing_date ? `${formatDate(row.last_filing_date)} · ${row.last_filing_type || "filing"}` : "n/a"}
                  </td>
                  <td className="right">
                    {row.bulk_soi_fact_rows ? formatNumber(row.bulk_soi_fact_rows) : "—"}
                  </td>
                  <td className="right">
                    {row.verified_latest_fair_value_mm !== null ? formatMm(row.verified_latest_fair_value_mm) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid limitation-grid">
        {bdcUniverse.limitations.map((limitation) => (
          <section className="panel limitation" key={limitation}>
            <h3>Coverage guardrail</h3>
            <p>{limitation}</p>
          </section>
        ))}
      </div>
    </div>
  );
}

function Quality() {
  return (
    <div className="grid">
      <Panel title="Methodology" subtitle="How this dashboard turns filed data into comparable analytics." icon={FileSearch}>
        <div className="quality-methodology-grid">
          <section>
            <h3>Source first</h3>
            <p>
              The Schedule of Investments is the primary audit trail for holdings. The dashboard keeps source labels,
              filing periods, cost, fair value, principal text, rate text, maturity text, and footnote context before it
              adds normalized fields. The goal is to improve comparability without rewriting what the fund actually
              filed.
            </p>
          </section>
          <section>
            <h3>As-filed rows</h3>
            <p>
              Holdings and underlying timeline tables show individual schedule rows. These rows can include separate
              tranches, delayed draw commitments, revolvers, preferred equity, JV interests, and other line items that
              appear in the filing. Those tables are meant for review, not for clean funded exposure totals.
            </p>
          </section>
          <section>
            <h3>Funded analytics</h3>
            <p>
              The portfolio charts, issuer concentration views, deterioration screen, rate mix, maturity mix, spread
              series, and timeline period totals use funded security-level aggregates. When a filing identifies an item
              as an unfunded commitment, it should remain visible in the detail rows but stay out of funded exposure
              math.
            </p>
          </section>
          <section>
            <h3>Commitments</h3>
            <p>
              Unfunded commitments are real economic exposures, but they answer a different question than funded loan
              balance. The methodology keeps them visible where they are listed in the schedule, then separates them
              from funded concentration and credit screeners when a reliable filing tag is available.
            </p>
          </section>
          <section>
            <h3>Issuer matching</h3>
            <p>
              Issuer match keys are join tools. They group clear naming variants across funds and periods while the
              dashboard still preserves each filing&apos;s display name. Match keys are useful for cross-fund overlap and
              timeline pages, but they are not treated as a replacement for the original issuer label.
            </p>
          </section>
          <section>
            <h3>Quarterly facts</h3>
            <p>
              Presentation items such as originations, repayments, NAV, dividends, income quality, and non-accrual facts
              live in a separate quarterly layer. They are kept separate when labels or scope differ from schedule totals.
              Dividend coverage uses the distribution tied to the earnings quarter when declaration timing differs from
              the period shown in a source table.
              Presentation-derived activity is useful for business momentum, while schedule-derived holdings are used for
              portfolio composition and credit marks.
            </p>
          </section>
          <section>
            <h3>Deterioration</h3>
            <p>
              The deterioration page is an issuer-level funded screen. It focuses on accruing issuers with enough history
              to show sustained mark decline, then excludes single-quarter-only moves from the main table. It is a
              triage tool for credit follow-up, not a formal impairment conclusion.
            </p>
          </section>
          <section>
            <h3>Liabilities</h3>
            <p>
              The liabilities page starts with filed debt tables and separates secured facilities, unsecured notes, and
              securitization debt. Funding cost notes, maturity walls, and SOFR sensitivity are analytical views layered
              on top of those tables. New bond pricing is shown as a thought exercise when it has not yet flowed through
              reported NII.
            </p>
          </section>
          <section>
            <h3>Reconciliation</h3>
            <p>
              The builder keeps source row counts, central row counts, integrity checks, and period totals so mismatches
              can be reviewed directly. When a source total and a dashboard view are intentionally different, the reason
              should be visible in the notes rather than hidden in the code.
            </p>
          </section>
          <section>
            <h3>Visible checks</h3>
            <p>
              Row counts, reconciliation checks, database integrity results, and known limitations are copied into this
              page so data issues stay visible instead of being hidden behind the charts.
            </p>
          </section>
        </div>
      </Panel>

      <Callout title="Data quality posture">{data.narrative.quality}</Callout>

      <div className="grid three-col">
        {data.source_databases.map((source) => (
          <section className="panel fund-card" key={source.fund}>
            <div className="fund-row">
              <div>
                <h3 className="fund-name">{source.fund}</h3>
                <p className="fund-full">{source.source_view}</p>
              </div>
              <span className={`pill ${source.integrity_check === "ok" ? "ok" : ""}`}>
                <CheckCircle2 />
                {source.integrity_check}
              </span>
            </div>
            <div className="fund-meta">
              <div className="micro-stat">
                <span>Expected</span>
                <strong>{formatNumber(source.expected_rows)}</strong>
              </div>
              <div className="micro-stat">
                <span>Loaded</span>
                <strong>{formatNumber(source.actual_rows)}</strong>
              </div>
              <div className="micro-stat">
                <span>Delta</span>
                <strong>{formatNumber(source.actual_rows - source.expected_rows)}</strong>
              </div>
            </div>
            <p className="footer-note">{source.source_db_path}</p>
          </section>
        ))}
      </div>

      <div className="grid two-col">
        <Panel title="Central Validation Checks" subtitle="Every builder validation row is copied into the dashboard snapshot." icon={ShieldCheck}>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Check</th>
                  <th>Fund</th>
                  <th>Status</th>
                  <th>Expected</th>
                  <th>Actual</th>
                </tr>
              </thead>
              <tbody>
                {data.validation_results.map((row, index) => (
                  <tr key={`${row.check_name}-${row.fund || "all"}-${row.actual}-${index}`}>
                    <td>{row.check_name}</td>
                    <td>{row.fund ? <FundBadge fund={row.fund} /> : "All"}</td>
                    <td>
                      <span className={`pill ${row.status === "ok" ? "ok" : ""}`}>{row.status}</span>
                    </td>
                    <td>{row.expected || "n/a"}</td>
                    <td>{row.actual || "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel title="Source QC Summary" subtitle="Source reconciliation and integrity rows, preserved by fund." icon={Database}>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Fund</th>
                  <th>Source object</th>
                  <th>Status</th>
                  <th className="right">Rows</th>
                </tr>
              </thead>
              <tbody>
                {data.source_qc_status.map((row) => (
                  <tr key={`${row.fund}-${row.source_object}-${row.source_status}`}>
                    <td>
                      <FundBadge fund={row.fund} />
                    </td>
                    <td>{row.source_object}</td>
                    <td>{row.source_status}</td>
                    <td className="right">{formatNumber(row.check_rows)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      <div className="section-heading">
        <AlertTriangle />
        <div>
          <h2>Data Limitations</h2>
          <p>Important guardrails before this becomes a broader investment analysis surface.</p>
        </div>
      </div>

      <div className="grid limitation-grid">
        {data.limitations.map((limitation) => (
          <section className="panel limitation" key={limitation.title}>
            <h3>{limitation.title}</h3>
            <p>{limitation.body}</p>
          </section>
        ))}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [selectedFund, setSelectedFund] = useState<Fund | "All">("All");
  const [selectedTimelineIssuer, setSelectedTimelineIssuer] = useState(() =>
    [...data.loan_timeline_issuers].sort(
      (a, b) => b.funds.length - a.funds.length || b.latest_fair_value_mm - a.latest_fair_value_mm
    )[0]?.issuer_match_key || ""
  );
  const [searchTerm, setSearchTerm] = useState("");
  const openTimelineIssuer = (issuerMatchKey: string) => {
    setSelectedTimelineIssuer(issuerMatchKey);
    setActiveTab("timeline");
  };

  const tabs: Array<{ id: Tab; label: string; icon: LucideIcon; group: string; description: string }> = [
    { id: "overview", label: "Research briefing", icon: BarChart3, group: "Decide", description: "Ranked portfolio signals and the latest cross-fund read." },
    { id: "deterioration", label: "Credit migration", icon: AlertTriangle, group: "Decide", description: "Issuer marks moving toward potential non-accrual stress." },
    { id: "exposure", label: "Cross-fund exposure", icon: Layers3, group: "Decide", description: "Crowding, matched-loan marks, and capital-structure comparisons." },
    { id: "timeline", label: "Issuer timeline", icon: LineChart, group: "Investigate", description: "Quarterly exposure, tier marks, fund-pair lead-lag, and sponsor history." },
    { id: "holdings", label: "Security detail", icon: Table2, group: "Investigate", description: "Searchable as-filed schedule rows and instrument evidence." },
    { id: "financials", label: "Fund financials", icon: WalletCards, group: "Fund", description: "NAV, income quality, dividends, leverage, and investment activity." },
    { id: "liabilities", label: "Funding market", icon: Gauge, group: "Fund", description: "SEC note issuance, TRACE trading, maturity walls, and filed liability detail." },
    { id: "universe", label: "BDC coverage", icon: Database, group: "Reference", description: "EdgarTools coverage and the wider BDC expansion universe." },
    { id: "quality", label: "Methods + quality", icon: ShieldCheck, group: "Reference", description: "Reconciliation, methodology, sources, and limitations." }
  ];
  const activeTabMeta = tabs.find((tab) => tab.id === activeTab) || tabs[0];
  const activeTabLabel = activeTabMeta.label;
  const sortedTimelineIssuers = [...data.loan_timeline_issuers].sort(
    (a, b) => b.funds.length - a.funds.length || b.latest_fair_value_mm - a.latest_fair_value_mm
  );

  return (
    <main className="app-shell">
      <aside className="research-rail">
        <div className="rail-brand">
          <strong>BDC Tracker</strong>
          <span>EDGAR filing monitor · {data.meta.latest_period_label}</span>
        </div>

        <p className="rail-label">Portfolio workbench</p>
        <nav className="tabs" aria-label="Dashboard sections">
          {tabs.map((tab, index) => (
            <div className="rail-nav-entry" key={tab.id}>
              {index === 0 || tabs[index - 1].group !== tab.group ? <p className="rail-nav-group">{tab.group}</p> : null}
              <button
                className={`tab-button ${activeTab === tab.id ? "active" : ""}`}
                onClick={() => setActiveTab(tab.id)}
                title={tab.description}
                type="button"
              >
                <tab.icon aria-hidden="true" />
                <span>{tab.label}</span>
              </button>
            </div>
          ))}
        </nav>

        <section className="rail-studies" aria-label="Pinned research views">
          <p className="rail-label">Pinned studies</p>
          <button type="button" onClick={() => setActiveTab("overview")}><span>01</span>Priority issuer queue</button>
          <button type="button" onClick={() => setActiveTab("exposure")}><span>02</span>Comparable loan gaps</button>
          <button type="button" onClick={() => setActiveTab("timeline")}><span>03</span>Fund-pair lead-lag</button>
        </section>

        <section className="rail-status" aria-label="Research coverage status">
          <p className="rail-label">Current research set</p>
          <strong>{funds.length} verified funds</strong>
          <span>Normalized through {data.meta.latest_period_label}</span>
          <span>{formatNumber(data.latest_by_fund.reduce((total, row) => total + row.holding_rows, 0))} holding rows</span>
          <small><i />Synced</small>
        </section>
      </aside>

      <section className="research-workspace">
        <header className="topbar">
          <div className="topbar-inner">
          <div className="brand">
            <p className="eyebrow">Eight public BDCs / {data.meta.latest_period_label}</p>
            <h1>{activeTabLabel}</h1>
            <p className="workspace-description">{activeTabMeta.description}</p>
          </div>
          <div className="mast-meta">
            <div>
              <span>Coverage</span>
              <strong>{funds.length} verified funds · {data.meta.latest_period_label}</strong>
            </div>
            <div>
              <span>As of</span>
              <strong>{formatDate(data.meta.latest_common_period)}</strong>
            </div>
          </div>
        </div>
      </header>

      <div className="content">
        <div className="toolbar">
          <div className="control-row">
            <span className="control-label">Research scope</span>
            <select
              className="select"
              value={selectedFund}
              onChange={(event) => setSelectedFund(event.target.value as Fund | "All")}
              title="Fund filter"
            >
              <option value="All">All funds</option>
              {funds.map((fund) => (
                <option key={fund} value={fund}>
                  {fund}
                </option>
              ))}
            </select>

            {activeTab === "timeline" ? (
              <select
                className="select issuer-select"
                value={selectedTimelineIssuer}
                onChange={(event) => setSelectedTimelineIssuer(event.target.value)}
                title="Issuer timeline"
              >
                {sortedTimelineIssuers.map((issuer) => {
                  const enriched = findCompanyEnrichment(issuer.issuer_match_key);
                  return (
                    <option key={issuer.issuer_match_key} value={issuer.issuer_match_key}>
                      {enriched?.display_name || issuer.display_name || issuer.issuer_match_key} · {issuer.funds.length} fund{issuer.funds.length === 1 ? "" : "s"}
                    </option>
                  );
                })}
              </select>
            ) : null}

            {activeTab === "holdings" ? (
              <div className="search-wrap">
                <Search />
                <input
                  className="search"
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="Search issuer, category, rate, maturity"
                />
              </div>
            ) : null}
          </div>
        </div>

        {activeTab === "overview" ? <Overview selectedFund={selectedFund} onOpenTimelineIssuer={openTimelineIssuer} /> : null}
        {activeTab === "financials" ? <Financials selectedFund={selectedFund} /> : null}
        {activeTab === "deterioration" ? <Deterioration selectedFund={selectedFund} /> : null}
        {activeTab === "exposure" ? (
          <Exposure selectedFund={selectedFund} onOpenTimelineIssuer={openTimelineIssuer} />
        ) : null}
        {activeTab === "timeline" ? (
          <Timeline
            selectedFund={selectedFund}
            selectedIssuerKey={selectedTimelineIssuer}
            onSelectIssuer={setSelectedTimelineIssuer}
          />
        ) : null}
        {activeTab === "holdings" ? <Holdings selectedFund={selectedFund} searchTerm={searchTerm} /> : null}
        {activeTab === "liabilities" ? <Liabilities selectedFund={selectedFund} /> : null}
        {activeTab === "universe" ? <Universe /> : null}
        {activeTab === "quality" ? <Quality /> : null}
      </div>
      </section>
    </main>
  );
}
