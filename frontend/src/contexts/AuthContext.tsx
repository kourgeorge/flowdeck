import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { authApi, profileApi } from '../services/authApi';
import {
  getStoredToken,
  setStoredAuth,
  clearStoredAuth,
  getStoredUser,
} from '../services/authApi';

interface User {
  email: string;
  userId: number;
  is_admin?: boolean;
}

interface AuthContextValue {
  user: User | null;
  token: string | null;
  isReady: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  deleteAccount: (password: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const t = getStoredToken();
    const u = getStoredUser();
    if (t && u) {
      setToken(t);
      setUser({ ...u, is_admin: u.is_admin });
      profileApi.getMe().then((me) => {
        setStoredAuth(t, me.email, me.user_id, me.is_admin);
        setUser((prev) => (prev ? { ...prev, is_admin: me.is_admin } : null));
      }).catch(() => { /* keep stored user as-is */ });
    }
    setIsReady(true);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await authApi.login(email, password);
    setStoredAuth(data.access_token, data.email, data.user_id);
    setToken(data.access_token);
    const profile = await profileApi.getMe();
    setStoredAuth(data.access_token, profile.email, profile.user_id, profile.is_admin);
    setUser({ email: profile.email, userId: profile.user_id, is_admin: profile.is_admin });
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const data = await authApi.register(email, password);
    setStoredAuth(data.access_token, data.email, data.user_id);
    setToken(data.access_token);
    const profile = await profileApi.getMe();
    setStoredAuth(data.access_token, profile.email, profile.user_id, profile.is_admin);
    setUser({ email: profile.email, userId: profile.user_id, is_admin: profile.is_admin });
  }, []);

  const logout = useCallback(() => {
    clearStoredAuth();
    setToken(null);
    setUser(null);
  }, []);

  const deleteAccount = useCallback(async (password: string) => {
    await authApi.deleteAccount(password);
    clearStoredAuth();
    setToken(null);
    setUser(null);
  }, []);

  const value: AuthContextValue = {
    user,
    token,
    isReady,
    login,
    register,
    logout,
    deleteAccount,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
}
