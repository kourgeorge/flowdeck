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
  updated_at: string | null;
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
};
