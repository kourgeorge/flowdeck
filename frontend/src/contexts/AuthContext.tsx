import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { authApi } from '../services/authApi';
import {
  getStoredToken,
  setStoredAuth,
  clearStoredAuth,
  getStoredUser,
} from '../services/authApi';

interface User {
  email: string;
  userId: number;
}

interface AuthContextValue {
  user: User | null;
  token: string | null;
  isReady: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
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
      setUser(u);
    }
    setIsReady(true);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await authApi.login(email, password);
    setStoredAuth(data.access_token, data.email, data.user_id);
    setToken(data.access_token);
    setUser({ email: data.email, userId: data.user_id });
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const data = await authApi.register(email, password);
    setStoredAuth(data.access_token, data.email, data.user_id);
    setToken(data.access_token);
    setUser({ email: data.email, userId: data.user_id });
  }, []);

  const logout = useCallback(() => {
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
