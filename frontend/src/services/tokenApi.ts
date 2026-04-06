import axios from 'axios';
import { getStoredToken } from './authApi';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

const api = axios.create({
  baseURL: API_BASE_URL || undefined,
  headers: { 'Content-Type': 'application/json' },
});

export interface UsageOperationItem {
  kind: 'analysis' | 'chat' | 'digest' | string;
  title: string;
  subject_label: string;
  status: string;
  platform_tokens: number | null;
  llm_tokens: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number | null;
  created_at: string | null;
  execution_id: number | null;
  chat_turn_id: number | null;
  chat_session_id: number | null;
  tools_called: number | null;
}

export interface UsageSummary {
  period_days: number;
  total_operations: number;
  total_platform_tokens: number;
  total_llm_tokens: number;
  analysis_count: number;
  analysis_platform_tokens: number;
  analysis_llm_tokens: number;
  chat_count: number;
  chat_platform_tokens: number;
  chat_llm_tokens: number;
  digest_count: number;
  digest_platform_tokens: number;
  digest_llm_tokens: number;
}

export interface UsageHistoryResponse {
  summary: UsageSummary;
  items: UsageOperationItem[];
  returned_operations: number;
}

export const tokenApi = {
  getUsageHistory: async (days = 90, limit = 200): Promise<UsageHistoryResponse> => {
    const token = getStoredToken();
    if (!token) throw new Error('Not authenticated');
    const res = await api.get<UsageHistoryResponse>('/api/tokens/usage-history', {
      params: { days, limit },
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.data;
  },
};
