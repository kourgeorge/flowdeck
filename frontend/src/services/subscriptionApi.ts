import axios from 'axios';
import { getStoredToken } from './authApi';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

function createAuthClient() {
  const client = axios.create({
    baseURL: API_BASE_URL || undefined,
    headers: { 'Content-Type': 'application/json' },
  });
  client.interceptors.request.use((config) => {
    const token = getStoredToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });
  return client;
}

export interface Subscription {
  id: number;
  ticker: string;
  email_updates: boolean;
  created_at: string;
}

export const subscriptionApi = {
  list: async (): Promise<Subscription[]> => {
    const res = await createAuthClient().get<{ subscriptions: Subscription[] }>('/api/subscriptions');
    return res.data.subscriptions;
  },
  subscribe: async (ticker: string, email_updates = true): Promise<Subscription> => {
    const res = await createAuthClient().post<Subscription>('/api/subscriptions', {
      ticker: ticker.toUpperCase(),
      email_updates,
    });
    return res.data;
  },
  updateEmailPreference: async (ticker: string, email_updates: boolean): Promise<Subscription> => {
    const res = await createAuthClient().patch<Subscription>(
      `/api/subscriptions/${encodeURIComponent(ticker.toUpperCase())}`,
      { email_updates }
    );
    return res.data;
  },
  unsubscribe: async (ticker: string): Promise<void> => {
    await createAuthClient().delete(`/api/subscriptions/${encodeURIComponent(ticker.toUpperCase())}`);
  },
};
