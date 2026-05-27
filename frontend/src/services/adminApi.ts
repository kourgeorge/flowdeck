import axios from 'axios';
import { getStoredToken } from './authApi';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

const api = axios.create({
  baseURL: API_BASE_URL || undefined,
  headers: { 'Content-Type': 'application/json' },
});

function authHeaders(): { Authorization: string } | object {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function getFilenameFromDisposition(disposition?: string): string | null {
  if (!disposition) return null;
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]);
  }
  const simpleMatch = disposition.match(/filename="?([^"]+)"?/i);
  return simpleMatch?.[1] ?? null;
}

export interface AdminStats {
  total_users: number;
  total_reports: number;
  total_analysis_runs: number;
  total_report_views: number;
  total_subscriptions: number;
  analyses_last_24h: number;
  analyses_last_7d: number;
  reports_last_24h: number;
  reports_last_7d: number;
}

export interface AdminUserItem {
  id: number;
  email: string;
  name: string | null;
  token_balance: number;
  created_at: string;
  subscription_count: number;
}

export interface AdminReportItem {
  id: number;
  ticker: string;
  analysis_run_id: number;
  report_type: string;
  created_at: string;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  cost_usd?: number;
}

export interface AdminReportDetail {
  id: number;
  ticker: string;
  analysis_run_id: number;
  report_type: string;
  created_at: string;
  content: string | null;
  metadata: Record<string, unknown> | null;
  metadata_raw: string | null;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  cost_usd?: number;
}

export interface AdminAnalysisItem {
  id: number;
  ticker: string;
  creator_id: number;
  creator_email: string;
  earned_tokens: number;
  created_at: string;
  status: string;
  error_message?: string;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  cost_usd?: number;
}

export interface AdminSubscriptionItem {
  id: number;
  user_id: number;
  user_email: string;
  ticker: string;
  email_updates: boolean;
  created_at: string;
}

export interface AdminAccuracySummary {
  total_rows: number;
  scored_rows: number;
  correct_count: number;
  incorrect_count: number;
  hold_count: number;
  unavailable_count: number;
  buy_count: number;
  sell_count: number;
  accuracy_percent: number | null;
}

export interface AdminAccuracyRow {
  analysis_run_id: number;
  ticker: string;
  created_at: string;
  recommendation: string | null;
  analysis_price: number | null;
  current_price: number | null;
  return_percent: number | null;
  outcome: string;
  is_scored: boolean;
  quote_status: string;
}

export interface AdminAccuracyResponse {
  period_days: number;
  summary: AdminAccuracySummary;
  rows: AdminAccuracyRow[];
}

export interface AnalysisDailyCount {
  date: string;
  count: number;
}

export interface ViewsDailyCount {
  date: string;
  count: number;
}

export interface AdminReportViewRunItem {
  ticker: string;
  analysis_run_id: number;
  unique_views: number;
  last_viewed_at: string;
}

export interface AdminReportViewItem {
  id: number;
  ticker: string;
  analysis_run_id: number;
  viewer_id: number;
  viewer_email: string;
  viewer_name: string | null;
  viewed_at: string;
}

export interface MissionControlTickerItem {
  ticker: string;
  name: string | null;
  quote_type: string | null;
  market_cap: number | null;
  last_completed_at: string | null;
  report_count: number | null;
  sector: string | null;
  industry: string | null;
  is_running: boolean;
  running_analysis_id: number | null;
  subscription_count: number;
  priority_score: number;
  last_status: string | null;
}

export interface MissionControlResponse {
  items: MissionControlTickerItem[];
}

export interface MissionControlRunItem {
  ticker: string;
  analysis_run_id: number;
}

export interface MissionControlRunErrorItem {
  ticker: string;
  error: string;
}

export interface MissionControlRunResponse {
  requested: string[];
  triggered: MissionControlRunItem[];
  already_running: MissionControlRunItem[];
  skipped_existing: string[];
  invalid_tickers: string[];
  failed: MissionControlRunErrorItem[];
}

export interface RunningAnalysisItem {
  analysis_run_id: number;
  ticker: string;
  date: string | null;
  status: string;
  agent_statuses: Record<string, string>;
  current_agent: string | null;
  current_agents: string[] | null;
  created_at: string | null;
  updated_at: string | null;
}

// Analytics types
export interface AnalyticsOperationBreakdown {
  operation_type: string;
  count: number;
  total_cost_usd: number;
  total_llm_tokens: number;
  avg_cost_usd: number;
  avg_llm_tokens: number;
}

export interface AnalyticsCostBreakdown {
  period_days: number;
  total_cost_usd: number;
  total_llm_tokens: number;
  operations: AnalyticsOperationBreakdown[];
}

export interface AnalyticsUserCost {
  user_id: number;
  email: string;
  total_cost_usd: number;
  total_llm_tokens: number;
  operation_count: number;
  chat_count: number;
  analysis_count: number;
  digest_count: number;
}

export interface AnalyticsCostPerUser {
  period_days: number;
  users: AnalyticsUserCost[];
}

export interface AnalyticsExpensiveOperation {
  operation_type: string;
  operation_id: number;
  user_id: number;
  user_email: string;
  subject: string;
  cost_usd: number;
  llm_tokens: number;
  created_at: string;
}

export interface AnalyticsExpensiveOperations {
  period_days: number;
  operations: AnalyticsExpensiveOperation[];
}

export interface AnalyticsDailyData {
  date: string;
  total_cost_usd: number;
  total_llm_tokens: number;
  chat_cost: number;
  analysis_cost: number;
  digest_cost: number;
  operation_count: number;
}

export interface AnalyticsUsageTrends {
  period_days: number;
  daily_data: AnalyticsDailyData[];
}

export interface AnalyticsModelUsage {
  model: string;
  provider: string;
  count: number;
  total_cost_usd: number;
  total_tokens: number;
}

export interface AnalyticsModelDistribution {
  period_days: number;
  models: AnalyticsModelUsage[];
}

export interface AnalyticsRecommendation {
  priority: string;
  category: string;
  title: string;
  description: string;
  potential_savings_usd: number;
}

export interface AnalyticsRecommendations {
  period_days: number;
  recommendations: AnalyticsRecommendation[];
}

export const adminApi = {
  getStats: async (): Promise<AdminStats> => {
    const res = await api.get<AdminStats>('/api/admin/stats', {
      headers: authHeaders(),
    });
    return res.data;
  },

  getUsers: async (
    limit = 50,
    offset = 0,
  ): Promise<{ users: AdminUserItem[]; total: number }> => {
    const res = await api.get<{ users: AdminUserItem[]; total: number }>(
      '/api/admin/users',
      { params: { limit, offset }, headers: authHeaders() },
    );
    return res.data;
  },

  getReports: async (
    limit = 50,
  ): Promise<{ reports: AdminReportItem[]; total: number }> => {
    const res = await api.get<{ reports: AdminReportItem[]; total: number }>(
      '/api/admin/reports',
      { params: { limit }, headers: authHeaders() },
    );
    return res.data;
  },

  getReport: async (reportId: number): Promise<AdminReportDetail> => {
    const res = await api.get<AdminReportDetail>(
      `/api/admin/reports/${reportId}`,
      { headers: authHeaders() },
    );
    return res.data;
  },

  getAnalyses: async (
    limit = 50,
    offset = 0,
  ): Promise<{ analyses: AdminAnalysisItem[]; total: number }> => {
    const res = await api.get<{ analyses: AdminAnalysisItem[]; total: number }>(
      '/api/admin/analyses',
      { params: { limit, offset }, headers: authHeaders() },
    );
    return res.data;
  },

  downloadAnalysisReportsZip: async (
    analysisRunId: number,
  ): Promise<{ blob: Blob; filename: string }> => {
    const res = await api.get<Blob>(
      `/api/admin/analyses/${analysisRunId}/download`,
      {
        headers: authHeaders(),
        responseType: 'blob',
      },
    );
    const filename =
      getFilenameFromDisposition(res.headers['content-disposition']) ??
      `analysis_${analysisRunId}_reports.zip`;
    return { blob: res.data, filename };
  },

  deleteAnalysis: async (analysisRunId: number): Promise<{ ok: boolean; id: number }> => {
    const res = await api.delete<{ ok: boolean; id: number }>(
      `/api/admin/analyses/${analysisRunId}`,
      { headers: authHeaders() },
    );
    return res.data;
  },

  getSubscriptions: async (
    limit = 100,
    offset = 0,
  ): Promise<{ subscriptions: AdminSubscriptionItem[]; total: number }> => {
    const res = await api.get<{
      subscriptions: AdminSubscriptionItem[];
      total: number;
    }>('/api/admin/subscriptions', {
      params: { limit, offset },
      headers: authHeaders(),
    });
    return res.data;
  },

  addTokensToUser: async (
    userId: number,
    amount: number,
  ): Promise<{ token_balance: number }> => {
    const res = await api.post<{ token_balance: number }>(
      `/api/admin/users/${userId}/tokens`,
      { amount },
      { headers: authHeaders() },
    );
    return res.data;
  },

  getAnalysesDaily: async (
    days = 30,
  ): Promise<{ data: AnalysisDailyCount[] }> => {
    const res = await api.get<{ data: AnalysisDailyCount[] }>(
      '/api/admin/analyses/daily',
      { params: { days }, headers: authHeaders() },
    );
    return res.data;
  },

  getAnalysisAccuracy: async (days = 30): Promise<AdminAccuracyResponse> => {
    const res = await api.get<AdminAccuracyResponse>(
      '/api/admin/analysis-accuracy',
      { params: { days }, headers: authHeaders() },
    );
    return res.data;
  },

  getViewsDaily: async (
    days = 30,
  ): Promise<{ data: ViewsDailyCount[] }> => {
    const res = await api.get<{ data: ViewsDailyCount[] }>(
      '/api/admin/views/daily',
      { params: { days }, headers: authHeaders() },
    );
    return res.data;
  },

  getViewRuns: async (
    limit = 100,
  ): Promise<{ runs: AdminReportViewRunItem[]; total_runs_with_views: number }> => {
    const res = await api.get<{
      runs: AdminReportViewRunItem[];
      total_runs_with_views: number;
    }>('/api/admin/views/runs', {
      params: { limit },
      headers: authHeaders(),
    });
    return res.data;
  },

  getViews: async (
    limit = 200,
    offset = 0,
  ): Promise<{ views: AdminReportViewItem[]; total: number }> => {
    const res = await api.get<{ views: AdminReportViewItem[]; total: number }>(
      '/api/admin/views',
      { params: { limit, offset }, headers: authHeaders() },
    );
    return res.data;
  },

  getViewsForRun: async (
    analysisRunId: number,
    limit = 5000,
    offset = 0,
  ): Promise<{ views: AdminReportViewItem[]; total: number }> => {
    const res = await api.get<{ views: AdminReportViewItem[]; total: number }>(
      '/api/admin/views/run',
      { params: { analysis_run_id: analysisRunId, limit, offset }, headers: authHeaders() },
    );
    return res.data;
  },

  getMissionControl: async (): Promise<MissionControlResponse> => {
    const res = await api.get<MissionControlResponse>(
      '/api/admin/mission-control',
      { headers: authHeaders() },
    );
    return res.data;
  },

  runMissionControl: async (
    tickers: string[],
    force = false,
  ): Promise<MissionControlRunResponse> => {
    const res = await api.post<MissionControlRunResponse>(
      '/api/admin/mission-control/run',
      { tickers, force },
      { headers: authHeaders() },
    );
    return res.data;
  },

  getRunningAnalyses: async (): Promise<RunningAnalysisItem[]> => {
    const res = await api.get<RunningAnalysisItem[]>(
      '/api/admin/running-analyses',
      { headers: authHeaders() },
    );
    return res.data;
  },

  stopRunningAnalysis: async (runId: number): Promise<{ ok: boolean; run_id: number }> => {
    const res = await api.post<{ ok: boolean; run_id: number }>(
      `/api/admin/running-analyses/${runId}/stop`,
      {},
      { headers: authHeaders() },
    );
    return res.data;
  },

  // Analytics endpoints
  getAnalyticsCostBreakdown: async (days = 30): Promise<AnalyticsCostBreakdown> => {
    const res = await api.get<AnalyticsCostBreakdown>(
      '/api/admin/analytics/cost-breakdown',
      { params: { days }, headers: authHeaders() },
    );
    return res.data;
  },

  getAnalyticsCostPerUser: async (days = 30, limit = 100): Promise<AnalyticsCostPerUser> => {
    const res = await api.get<AnalyticsCostPerUser>(
      '/api/admin/analytics/cost-per-user',
      { params: { days, limit }, headers: authHeaders() },
    );
    return res.data;
  },

  getAnalyticsExpensiveOperations: async (
    days = 30,
    limit = 50,
  ): Promise<AnalyticsExpensiveOperations> => {
    const res = await api.get<AnalyticsExpensiveOperations>(
      '/api/admin/analytics/expensive-operations',
      { params: { days, limit }, headers: authHeaders() },
    );
    return res.data;
  },

  getAnalyticsUsageTrends: async (days = 30): Promise<AnalyticsUsageTrends> => {
    const res = await api.get<AnalyticsUsageTrends>(
      '/api/admin/analytics/usage-trends',
      { params: { days }, headers: authHeaders() },
    );
    return res.data;
  },

  getAnalyticsModelDistribution: async (days = 30): Promise<AnalyticsModelDistribution> => {
    const res = await api.get<AnalyticsModelDistribution>(
      '/api/admin/analytics/model-distribution',
      { params: { days }, headers: authHeaders() },
    );
    return res.data;
  },

  getAnalyticsRecommendations: async (days = 30): Promise<AnalyticsRecommendations> => {
    const res = await api.get<AnalyticsRecommendations>(
      '/api/admin/analytics/recommendations',
      { params: { days }, headers: authHeaders() },
    );
    return res.data;
  },
};
