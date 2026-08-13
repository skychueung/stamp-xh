import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from 'react';
import { parseFastApiError } from '@/lib/errorUtils';

const API_BASE = '/api/v1';

export interface User {
  id: string;
  username: string;
  email: string | null;
  role: 'user' | 'admin';
  status: 'pending' | 'active' | 'disabled';
  must_change_password: boolean;
  created_at: string;
}

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  csrfToken: string | null;
  login: (username: string, password: string) => Promise<{ ok: boolean; message: string; mustChangePassword: boolean }>;
  register: (username: string, password: string, email?: string) => Promise<{ ok: boolean; message: string; status?: User['status'] }>;
  logout: () => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<{ ok: boolean; message: string }>;
  refreshMe: () => Promise<void>;
  // Backward-compatible legacy API used by existing pages.
  role: 'viewer' | 'researcher' | 'admin';
  setRole: (role: 'viewer' | 'researcher' | 'admin') => void;
  isViewer: boolean;
  isResearcher: boolean;
  canSubmit: boolean;
  canManage: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function getCsrfCookie(): string | null {
  const match = document.cookie.match(/(^| )stamp_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[2]) : null;
}

async function apiFetch(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });
  let data: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  return { res, data };
}

const STORAGE_KEY = 'stamp_user_role';

function readLegacyRole(): 'viewer' | 'researcher' | 'admin' {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'viewer' || stored === 'researcher' || stored === 'admin') {
      return stored;
    }
  } catch {
    // ignore
  }
  return 'viewer';
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [csrfToken, setCsrfToken] = useState<string | null>(getCsrfCookie());
  const [legacyRole, setLegacyRoleState] = useState<'viewer' | 'researcher' | 'admin'>(readLegacyRole);

  const setRole = useCallback((role: 'viewer' | 'researcher' | 'admin') => {
    setLegacyRoleState(role);
    try {
      localStorage.setItem(STORAGE_KEY, role);
    } catch {
      // ignore
    }
  }, []);

  const derivedRole: 'viewer' | 'researcher' | 'admin' = user
    ? user.role === 'admin'
      ? 'admin'
      : 'researcher'
    : legacyRole;

  const refreshMe = useCallback(async () => {
    try {
      const { res, data } = await apiFetch('/auth/me');
      if (res.ok && data && typeof data === 'object' && 'data' in data) {
        setUser((data as { data: User }).data);
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setCsrfToken(getCsrfCookie());
    }
  }, []);

  useEffect(() => {
    refreshMe().finally(() => setIsLoading(false));
  }, [refreshMe]);

  const login = useCallback(async (username: string, password: string) => {
    const { res, data } = await apiFetch('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    setCsrfToken(getCsrfCookie());
    if (res.ok && data && typeof data === 'object' && 'data' in data) {
      const me = (data as { data: User }).data;
      setUser(me);
      return { ok: true, message: (data as { message?: string }).message || 'Login successful.', mustChangePassword: me.must_change_password };
    }
    const msg = parseFastApiError(data) || 'Login failed.';
    return { ok: false, message: msg, mustChangePassword: false };
  }, []);

  const register = useCallback(async (username: string, password: string, email?: string) => {
    const payload: Record<string, string> = { username, password };
    if (email) payload.email = email;
    const { res, data } = await apiFetch('/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      const body = data as {
        data?: { status?: User['status']; message?: string };
        message?: string;
      } | null;
      const registrationStatus = body?.data?.status;
      const message = body?.message
        || body?.data?.message
        || (registrationStatus === 'pending'
          ? 'Registration successful. Waiting for administrator approval.'
          : 'Registration successful. You can now sign in.');
      return { ok: true, message, status: registrationStatus };
    }
    const msg = parseFastApiError(data) || 'Registration failed.';
    return { ok: false, message: msg };
  }, []);

  const logout = useCallback(async () => {
    const token = getCsrfCookie();
    await apiFetch('/auth/logout', {
      method: 'POST',
      headers: token ? { 'X-CSRF-Token': token } : {},
    });
    setUser(null);
    setCsrfToken(null);
  }, []);

  const changePassword = useCallback(async (currentPassword: string, newPassword: string) => {
    const token = getCsrfCookie();
    const { res, data } = await apiFetch('/auth/change-password', {
      method: 'POST',
      headers: token ? { 'X-CSRF-Token': token } : {},
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    if (res.ok && data && typeof data === 'object' && 'data' in data) {
      setUser((data as { data: User }).data);
      return { ok: true, message: 'Password changed successfully.' };
    }
    const msg = parseFastApiError(data) || 'Password change failed.';
    return { ok: false, message: msg };
  }, []);

  const isAdmin = user?.role === 'admin';
  const isViewer = derivedRole === 'viewer';
  const isResearcher = derivedRole === 'researcher';

  const value: AuthContextValue = {
    user,
    isLoading,
    isAuthenticated: !!user,
    isAdmin,
    csrfToken,
    login,
    register,
    logout,
    changePassword,
    refreshMe,
    role: derivedRole,
    setRole,
    isViewer,
    isResearcher,
    canSubmit: isResearcher || isAdmin,
    canManage: isAdmin,
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
