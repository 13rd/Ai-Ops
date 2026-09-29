import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import apiClient, { setAccessToken } from '@/shared/api/client';
import { ApiError, unwrap } from '@/shared/api/types';

export interface UserInfo {
  id: number;
  username: string;
  email: string;
  role: 'admin' | 'operator';
  is_active: boolean;
  created_at?: string;
}

interface TokenPairData {
  access_token: string;
  token_type: string;
  user: UserInfo;
}

interface AuthState {
  user: UserInfo | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  loading: boolean;
}

export interface AuthContextType extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

function jwtExp(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1])) as { exp?: unknown };
    return typeof payload.exp === 'number' ? payload.exp : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isAdmin: false,
    loading: true,
  });

  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const silentRefreshRef = useRef<() => Promise<boolean>>(async () => false);

  const scheduleRefresh = useCallback((token: string) => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    const exp = jwtExp(token);
    if (!exp) return;
    const delay = exp * 1000 - Date.now() - 60_000;
    if (delay <= 0) return;
    refreshTimerRef.current = setTimeout(() => {
      void silentRefreshRef.current();
    }, delay);
  }, []);

  const applyTokenPair = useCallback(
    (data: TokenPairData) => {
      setAccessToken(data.access_token);
      setState({
        user: data.user,
        isAuthenticated: true,
        isAdmin: data.user.role === 'admin',
        loading: false,
      });
      scheduleRefresh(data.access_token);
    },
    [scheduleRefresh],
  );

  const clearAuth = useCallback(() => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    setAccessToken(null);
    setState({ user: null, isAuthenticated: false, isAdmin: false, loading: false });
  }, []);

  const silentRefresh = useCallback(async (): Promise<boolean> => {
    try {
      const data = unwrap(
        await apiClient.post<{
          success: boolean;
          data: TokenPairData;
          message: string;
          error: null;
        }>('/auth/refresh'),
      );
      applyTokenPair(data);
      return true;
    } catch {
      setState({ user: null, isAuthenticated: false, isAdmin: false, loading: false });
      setAccessToken(null);
      return false;
    }
  }, [applyTokenPair]);

  useEffect(() => {
    silentRefreshRef.current = silentRefresh;
  }, [silentRefresh]);

  useEffect(() => {
    void silentRefresh();
  }, [silentRefresh]);

  useEffect(() => {
    const handler = () => clearAuth();
    window.addEventListener('auth:logout', handler);
    return () => window.removeEventListener('auth:logout', handler);
  }, [clearAuth]);

  const login = useCallback(
    async (username: string, password: string): Promise<void> => {
      const data = unwrap(
        await apiClient.post<{
          success: boolean;
          data: TokenPairData;
          message: string;
          error: null;
        }>('/auth/login', { username, password }),
      );
      applyTokenPair(data);
    },
    [applyTokenPair],
  );

  const logout = useCallback(async (): Promise<void> => {
    try {
      await apiClient.post('/auth/logout');
    } catch (err) {
      if (!(err instanceof ApiError) && !(err instanceof Error)) throw err;
    }
    clearAuth();
  }, [clearAuth]);

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
