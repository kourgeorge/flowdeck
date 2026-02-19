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
  deleteAccount: async (password: string): Promise<void> => {
    const token = getStoredToken();
    if (!token) throw new Error('Not authenticated');
    await api.delete('/api/auth/account', {
      data: { password },
      headers: { Authorization: `Bearer ${token}` },
    });
  },
};

const AUTH_KEY = 'flowdeck_token';
const USER_KEY = 'flowdeck_user';

export function getStoredToken(): string | null {
  return localStorage.getItem(AUTH_KEY);
}

export function setStoredAuth(
  token: string,
  email: string,
  userId: number,
  isAdmin?: boolean,
): void {
  localStorage.setItem(AUTH_KEY, token);
  localStorage.setItem(
    USER_KEY,
    JSON.stringify({ email, userId, is_admin: isAdmin ?? false }),
  );
}

export function clearStoredAuth(): void {
  localStorage.removeItem(AUTH_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getStoredUser(): {
  email: string;
  userId: number;
  name?: string | null;
  is_admin?: boolean;
} | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return {
      ...parsed,
      is_admin: parsed.is_admin === true,
    };
  } catch {
    return null;
  }
}

export interface MeProfile {
  user_id: number;
  email: string;
  name: string | null;
  token_balance: number;
  is_admin?: boolean;
}

export interface UpdateProfileBody {
  name?: string | null;
  current_password?: string;
  new_password?: string;
}

export const profileApi = {
  getMe: async (): Promise<MeProfile> => {
    const token = getStoredToken();
    if (!token) throw new Error('Not authenticated');
    const res = await api.get<MeProfile>('/api/me', {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.data;
  },
  updateProfile: async (body: UpdateProfileBody): Promise<MeProfile> => {
    const token = getStoredToken();
    if (!token) throw new Error('Not authenticated');
    const res = await api.patch<MeProfile>('/api/me', body, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.data;
  },
};
