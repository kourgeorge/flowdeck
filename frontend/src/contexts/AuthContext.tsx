import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { authApi, profileApi } from '../services/authApi';
import {
  getStoredToken,
  setStoredAuth,
  clearStoredAuth,
  getStoredUser,
  type MeProfile,
} from '../services/authApi';

interface User {
  email: string;
  userId: number;
  is_admin?: boolean;
  has_completed_investor_profile?: boolean;
}

interface AuthContextValue {
  user: User | null;
  token: string | null;
  isReady: boolean;
  login: (email: string, password: string) => Promise<MeProfile>;
  register: (email: string, password: string) => Promise<MeProfile>;
  logout: () => void;
  deleteAccount: (password?: string) => Promise<void>;
  refreshUser: () => Promise<void>;
  setProfileCompletion: (completed: boolean) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);

  const applyMeProfile = useCallback((authToken: string, profile: MeProfile) => {
    setStoredAuth(
      authToken,
      profile.email,
      profile.user_id,
      profile.is_admin,
      profile.has_completed_investor_profile,
    );
    setUser({
      email: profile.email,
      userId: profile.user_id,
      is_admin: profile.is_admin,
      has_completed_investor_profile: profile.has_completed_investor_profile,
    });
  }, []);

  const refreshUser = useCallback(async () => {
    const authToken = getStoredToken();
    if (!authToken) return;
    const me = await profileApi.getMe();
    applyMeProfile(authToken, me);
  }, [applyMeProfile]);

  const setProfileCompletion = useCallback((completed: boolean) => {
    setUser((prev) => {
      if (!prev) return prev;
      const authToken = getStoredToken();
      if (authToken) {
        setStoredAuth(
          authToken,
          prev.email,
          prev.userId,
          prev.is_admin,
          completed,
        );
      }
      return { ...prev, has_completed_investor_profile: completed };
    });
  }, []);

  useEffect(() => {
    let cancelled = false;

    const initAuth = async () => {
      const t = getStoredToken();
      const u = getStoredUser();
      if (!t || !u) {
        setIsReady(true);
        return;
      }

      setToken(t);
      setUser({
        email: u.email,
        userId: u.userId,
        is_admin: u.is_admin,
        has_completed_investor_profile: u.has_completed_investor_profile,
      });

      try {
        const me = await profileApi.getMe();
        if (!cancelled) {
          applyMeProfile(t, me);
        }
      } catch (error) {
        // If token validation fails, clear stored auth and sign out
        if (!cancelled) {
          clearStoredAuth();
          setToken(null);
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setIsReady(true);
        }
      }
    };

    initAuth();
    return () => {
      cancelled = true;
    };
  }, [applyMeProfile]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await authApi.login(email, password);
    setStoredAuth(data.access_token, data.email, data.user_id);
    setToken(data.access_token);
    const profile = await profileApi.getMe();
    applyMeProfile(data.access_token, profile);
    return profile;
  }, [applyMeProfile]);

  const register = useCallback(async (email: string, password: string) => {
    const data = await authApi.register(email, password);
    setStoredAuth(data.access_token, data.email, data.user_id);
    setToken(data.access_token);
    const profile = await profileApi.getMe();
    applyMeProfile(data.access_token, profile);
    return profile;
  }, [applyMeProfile]);

  const logout = useCallback(() => {
    clearStoredAuth();
    setToken(null);
    setUser(null);
  }, []);

  const deleteAccount = useCallback(async (password?: string) => {
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
    refreshUser,
    setProfileCompletion,
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
