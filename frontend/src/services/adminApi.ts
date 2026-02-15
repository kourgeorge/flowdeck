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
  run_id: string;
  report_type: string;
  created_at: string;
}

export interface AdminAnalysisItem {
  id: number;
  ticker: string;
  run_id: string;
  creator_id: number;
  creator_email: string;
  earned_tokens: number;
  created_at: string;
}

export interface AdminSubscriptionItem {
  id: number;
  user_id: number;
  user_email: string;
  ticker: string;
  created_at: string;
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

  getAnalyses: async (
    limit = 50,
  ): Promise<{ analyses: AdminAnalysisItem[]; total: number }> => {
    const res = await api.get<{ analyses: AdminAnalysisItem[]; total: number }>(
      '/api/admin/analyses',
      { params: { limit }, headers: authHeaders() },
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
};
