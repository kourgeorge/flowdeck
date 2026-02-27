export interface ReportScoreSummary {
  score: number | null;
  score_label: string | null;
}

export interface StockWidget {
  ticker: string;
  name?: string | null;
  current_price: number;
  daily_change: number;
  daily_change_percent: number;
  recommendation: string | null;
  /** AI confidence 0-1 (from risk_score/10); shown in list as Confidence */
  confidence?: number | null;
  report_date: string | null;
  has_report: boolean;
  market_status: string;
  /** AI analysis scores by report type (e.g. investment_plan, final_trade_decision) for list view */
  report_scores?: Record<string, ReportScoreSummary> | null;
  /** True when ticker is in the major-stocks list (only set when widgets requested without explicit tickers) */
  is_major?: boolean | null;
}

export interface WidgetsResponse {
  widgets: StockWidget[];
  /** Set when using only_date with limit (paginated recently analyzed). */
  total?: number;
}

export interface StockQuote {
  ticker: string;
  current_price: number;
  daily_change: number;
  daily_change_percent: number;
  bid_price: number | null;
  ask_price: number | null;
  bid_size: number | null;
  ask_size: number | null;
  volume: number | null;
  previous_close: number | null;
  day_high: number | null;
  day_low: number | null;
  fifty_two_week_high: number | null;
  fifty_two_week_low: number | null;
  market_status: string;
  last_update_time: string;
}

export interface Recommendation {
  recommendation: string;
  confidence: number | null;
  source: string;
  date: string;
}

export interface HistoricalAnalysis {
  date: string;
  available_reports: string[];
  recommendation: string | null;
}

export interface ModelsUsed {
  provider?: string;
  deep_think?: string;
  quick_think?: string;
}

export interface ReportData {
  content: string | null;
  score: number | null;
  score_label: string | null;
  key_takeaways?: string[];
  analysis_date?: string | null;
  generated_at?: string | null;
  days_ago?: number | null;
  models_used?: ModelsUsed | null;
  bull_viewpoint?: string[] | null;
  bear_viewpoint?: string[] | null;
  risky_viewpoint?: string[] | null;
  safe_viewpoint?: string[] | null;
  neutral_viewpoint?: string[] | null;
}

export interface StockPageData {
  ticker: string;
  quote: StockQuote | null;
  recommendation: Recommendation | null;
  report_date: string | null;
  report_days_ago?: number | null;
  reports: Record<string, string | null>;
  reports_with_scores?: Record<string, ReportData>;
  historical_analyses: HistoricalAnalysis[];
  has_reports: boolean;
  is_generating: boolean;
  generation_analysis_id: string | null;
  /** Agent return expectations (base / bear / bull) from Research Manager */
  expected_return_pct?: number | null;
  bear_case_return_pct?: number | null;
  bull_case_return_pct?: number | null;
  /** Token economy: unique view count and tokens earned for this report run */
  report_view_count?: number | null;
  report_earned_tokens?: number | null;
}

