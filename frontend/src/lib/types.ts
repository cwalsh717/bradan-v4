// Dashboard
export interface DashboardTicker {
  id: number;
  category: string;
  display_name: string;
  symbol: string;
  data_source: string;
  display_format: string;
  display_order: number;
  is_active: boolean;
}

// Live price from WebSocket
export interface PriceUpdate {
  symbol: string;
  price: number;
  timestamp: string;
  change?: number;
  change_percent?: number;
}

// Stock profile
export interface StockProfile {
  symbol: string;
  name: string;
  exchange: string;
  sector: string;
  industry: string;
  currency: string;
}

// Search result
export interface SearchResult {
  symbol: string;
  name: string;
  exchange: string;
  cached: boolean;
}

// Financial ratios
export interface FinancialRatios {
  gross_margin: number | null;
  operating_margin: number | null;
  net_margin: number | null;
  roe: number | null;
  roa: number | null;
  roic: number | null;
  current_ratio: number | null;
  quick_ratio: number | null;
  debt_to_equity: number | null;
  debt_to_assets: number | null;
  interest_coverage: number | null;
  pe_ratio: number | null;
  pb_ratio: number | null;
  ps_ratio: number | null;
  ev_to_ebitda: number | null;
  asset_turnover: number | null;
  inventory_turnover: number | null;
}

// DCF computed inputs (matches backend DCFComputedInputs)
export interface DCFComputedInputs {
  effective_tax_rate: number;
  computed_tax_rate: number;
  ebit_after_tax: number;
  reinvestment: number;
  reinvestment_rate: number;
  return_on_capital: number;
  expected_growth: number;
  levered_beta: number;
  cost_of_equity: number;
  synthetic_rating: string;
  default_spread: number;
  cost_of_debt_pretax: number;
  cost_of_debt_aftertax: number;
  wacc: number;
  debt_ratio: number;
  market_cap: number;
}

// DCF terminal value (matches backend TerminalValue)
export interface TerminalValue {
  terminal_growth: number;
  terminal_roc: number;
  terminal_wacc: number;
  terminal_reinvestment_rate: number;
  terminal_fcff: number;
  terminal_value: number;
  pv_terminal: number;
}

// DCF equity bridge (matches backend EquityBridge)
export interface EquityBridge {
  enterprise_value: number;
  plus_cash: number;
  minus_debt: number;
  minus_minority_interests: number;
  minus_preferred_stock: number;
  equity_value: number;
  shares_outstanding: number;
  value_per_share: number;
}

// DCF year projection (matches backend YearProjection)
export interface YearProjection {
  year: number;
  growth_rate: number;
  revenue: number;
  ebit: number;
  ebit_after_tax: number;
  reinvestment_rate: number;
  reinvestment: number;
  fcff: number;
  beta: number;
  cost_of_equity: number;
  debt_ratio: number;
  wacc: number;
  roc: number;
  pv_factor: number;
  pv_fcff: number;
}

// DCF result (matches backend DCFResult)
export interface DCFResult {
  symbol: string;
  company_name: string;
  value_per_share: number;
  current_price: number;
  implied_upside: number;
  verdict: string;
  computed_inputs: DCFComputedInputs;
  projections: YearProjection[];
  terminal: TerminalValue;
  equity_bridge: EquityBridge;
  scenario: string;
  forecast_years: number;
  source_fiscal_date: string;
  computed_at: string;
  pv_operating_cashflows: number;
  terminal_value_pct: number;
}

// Sensitivity matrix (matches backend SensitivityMatrix)
export interface SensitivityMatrix {
  wacc_values: number[];
  growth_values: number[];
  matrix: number[][];
  base_wacc: number;
  base_growth: number;
  base_value: number;
}

// DCF constraints (matches backend DCFConstraints)
export interface DCFConstraints {
  forecast_years: { min: number; max: number; step: number };
  stable_growth_rate: { min: number; max: number; step: number };
  stable_beta: { min: number; max: number; step: number };
  stable_roc: { min: number; max: number; step: number };
  stable_debt_to_equity: { min: number; max: number; step: number };
  marginal_tax_rate: { min: number; max: number; step: number };
}

// Peer stock
export interface PeerStock {
  symbol: string;
  name: string;
  sector: string;
  industry: string;
}

// Dashboard category
export interface DashboardCategory {
  name: string;
  tickers: DashboardTicker[];
}

// Financial statement (matches backend FinancialRecord)
export interface FinancialStatement {
  id: number;
  statement_type: string;
  period: string;
  fiscal_date: string;
  data: Record<string, any>;
  fetched_at: string;
}

// Dividend (matches backend DividendRecord)
export interface Dividend {
  id: number;
  ex_date: string;
  amount: number;
  fetched_at: string;
}

// Stock split (matches backend SplitRecord)
export interface StockSplit {
  id: number;
  date: string;
  ratio_from: number;
  ratio_to: number;
}

// Portfolio
export interface Portfolio {
  id: number;
  name: string;
  mode: "watchlist" | "full";
  created_at: string;
  updated_at: string | null;
  holdings_count: number;
}

export interface Holding {
  id: number;
  stock_id: number;
  symbol: string;
  name: string;
  shares: number | null;
  cost_basis_per_share: number | null;
  added_at: string;
  current_price: number | null;
  market_value: number | null;
  gain_loss: number | null;
  gain_loss_pct: number | null;
}

export interface PerformanceSummary {
  total_value: number;
  total_cost_basis: number;
  total_gain_loss: number;
  total_gain_loss_pct: number | null;
  holdings: Holding[];
}

export interface PortfolioSnapshot {
  id: number;
  date: string;
  total_value: number;
  total_cost_basis: number;
  total_gain_loss: number;
  holdings_snapshot: Record<string, any>;
}
