import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

const api = axios.create({
  baseURL: API_BASE_URL || undefined,
  headers: { 'Content-Type': 'application/json' },
});

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: number;
  email: string;
}

export const authApi = {
  register: async (email: string, password: string): Promise<TokenResponse> => {
    const res = await api.post<TokenResponse>('/api/auth/register', { email, password });
    return res.data;
  },
  login: async (email: string, password: string): Promise<TokenResponse> => {
    const res = await api.post<TokenResponse>('/api/auth/login', { email, password });
    return res.data;
  },
};

const AUTH_KEY = 'flowdeck_token';
const USER_KEY = 'flowdeck_user';

export function getStoredToken(): string | null {
  return localStorage.getItem(AUTH_KEY);
}

export function setStoredAuth(token: string, email: string, userId: number): void {
  localStorage.setItem(AUTH_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify({ email, userId }));
}

export function clearStoredAuth(): void {
  localStorage.removeItem(AUTH_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getStoredUser(): { email: string; userId: number } | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}
