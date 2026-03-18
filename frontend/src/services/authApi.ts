import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';
const POST_AUTH_REDIRECT_KEY = 'flowdeck_post_auth_redirect';

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
  googleLogin: (): void => {
    const currentPath = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    localStorage.setItem(POST_AUTH_REDIRECT_KEY, currentPath);
    // Redirect to backend Google OAuth endpoint
    window.location.href = `${API_BASE_URL}/api/auth/google`;
  },
  deleteAccount: async (password?: string): Promise<void> => {
    const token = getStoredToken();
    if (!token) throw new Error('Not authenticated');
    await api.delete('/api/auth/account', {
      data: { password: password || null },
      headers: { Authorization: `Bearer ${token}` },
    });
  },
};

export function consumePostAuthRedirect(): string | null {
  const value = localStorage.getItem(POST_AUTH_REDIRECT_KEY);
  localStorage.removeItem(POST_AUTH_REDIRECT_KEY);
  if (!value) return null;
  // Only allow same-origin relative paths to avoid open redirects.
  if (!value.startsWith('/') || value.startsWith('//')) return null;
  if (value.startsWith('/auth/callback')) return null;
  return value;
}

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
  hasCompletedInvestorProfile?: boolean,
): void {
  localStorage.setItem(AUTH_KEY, token);
  localStorage.setItem(
    USER_KEY,
    JSON.stringify({
      email,
      userId,
      is_admin: isAdmin ?? false,
      has_completed_investor_profile: hasCompletedInvestorProfile ?? false,
    }),
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
  has_completed_investor_profile?: boolean;
} | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return {
      ...parsed,
      is_admin: parsed.is_admin === true,
      has_completed_investor_profile: parsed.has_completed_investor_profile === true,
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
  has_password?: boolean;  // True if user has email/password, false if Google-only
  has_completed_investor_profile?: boolean;
}

export interface InvestorProfile {
  user_id: number;
  date_of_birth: string | null;
  persona_type: string | null;
  experience_level: string | null;
  risk_tolerance: string | null;
  time_horizon: string | null;
  primary_goal: string | null;
  goals: string[];
  constraints: string[];
  preferred_style: string | null;
  ai_memory_text: string | null;
  has_completed_investor_profile: boolean;
  onboarding_completed_at: string | null;
  updated_at: string | null;
}

export interface UpdateInvestorProfileBody {
  date_of_birth?: string | null;
  persona_type?: string | null;
  experience_level?: string | null;
  risk_tolerance?: string | null;
  time_horizon?: string | null;
  primary_goal?: string | null;
  goals?: string[];
  constraints?: string[];
  preferred_style?: string | null;
  ai_memory_text?: string | null;
}

export interface UserStats {
  analyses_created: number;
  tokens_spent_on_analyses: number;
  tokens_earned_from_views: number;
  reports_viewed: number;
  unique_tickers_analyzed: number;
  subscriptions_count: number;
  member_since: string;
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
  getStats: async (): Promise<UserStats> => {
    const token = getStoredToken();
    if (!token) throw new Error('Not authenticated');
    const res = await api.get<UserStats>('/api/me/stats', {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.data;
  },
  getInvestorProfile: async (): Promise<InvestorProfile> => {
    const token = getStoredToken();
    if (!token) throw new Error('Not authenticated');
    const res = await api.get<InvestorProfile>('/api/me/investor-profile', {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.data;
  },
  updateInvestorProfile: async (body: UpdateInvestorProfileBody): Promise<InvestorProfile> => {
    const token = getStoredToken();
    if (!token) throw new Error('Not authenticated');
    const res = await api.patch<InvestorProfile>('/api/me/investor-profile', body, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.data;
  },
};

// API Key Management
export interface ApiKey {
  id: number;
  name: string;
  key_prefix: string;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
}

export interface CreateApiKeyRequest {
  name: string;
  expires_at?: string | null;
}

export interface CreateApiKeyResponse extends ApiKey {
  key: string;  // Full key - only shown once!
  warning: string;
}

export const apiKeyApi = {
  list: async (): Promise<ApiKey[]> => {
    const token = getStoredToken();
    if (!token) throw new Error('Not authenticated');
    const res = await api.get<ApiKey[]>('/api/api-keys', {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.data;
  },
  create: async (body: CreateApiKeyRequest): Promise<CreateApiKeyResponse> => {
    const token = getStoredToken();
    if (!token) throw new Error('Not authenticated');
    const res = await api.post<CreateApiKeyResponse>('/api/api-keys', body, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.data;
  },
  delete: async (keyId: number): Promise<void> => {
    const token = getStoredToken();
    if (!token) throw new Error('Not authenticated');
    await api.delete(`/api/api-keys/${keyId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  },
  deactivate: async (keyId: number): Promise<ApiKey> => {
    const token = getStoredToken();
    if (!token) throw new Error('Not authenticated');
    const res = await api.patch<ApiKey>(`/api/api-keys/${keyId}/deactivate`, {}, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.data;
  },
  activate: async (keyId: number): Promise<ApiKey> => {
    const token = getStoredToken();
    if (!token) throw new Error('Not authenticated');
    const res = await api.patch<ApiKey>(`/api/api-keys/${keyId}/activate`, {}, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.data;
  },
};
