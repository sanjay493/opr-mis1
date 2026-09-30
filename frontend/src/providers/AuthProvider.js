'use client';

import { createContext, useContext, useEffect, useState, useCallback } from 'react';

// Default to relative /api/* URLs: next.config.mjs rewrites them to the
// backend (127.0.0.1:8082), so every request is same-origin with the page.
// That makes the SameSite=Lax session cookie flow automatically — no CORS,
// no credentials:'include', and no localhost-vs-127.0.0.1-vs-LAN-IP host
// mismatch (the backend only listens on loopback, so the proxy is also the
// only path that works from another machine). NEXT_PUBLIC_API_URL still wins
// when explicitly set (e.g. a deployment where the API is exposed directly —
// note that case is cross-origin, so fetches would need credentials).
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

const AuthContext = createContext({
  user: null,
  loading: true,
  refresh: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/me`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setUser(data.user);
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Sessions end after 30 min idle (backend/auth.py). Check once a minute and
  // when the tab regains focus, so a lapsed session shows as logged out right
  // away rather than on the next click. The X-Session-Check header tells the
  // backend this poll isn't user activity, so it doesn't extend the session.
  useEffect(() => {
    if (!user) return undefined;
    const check = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/auth/me`, {
          credentials: 'include', headers: { 'X-Session-Check': '1' },
        });
        if (res.status === 401) setUser(null);
      } catch {
        // offline / backend restarting — leave the state alone
      }
    };
    const timer = setInterval(check, 60_000);
    window.addEventListener('focus', check);
    return () => {
      clearInterval(timer);
      window.removeEventListener('focus', check);
    };
  }, [user]);

  const logout = useCallback(async () => {
    try {
      await fetch(`${API_BASE_URL}/api/auth/logout`, { method: 'POST', credentials: 'include' });
    } finally {
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, refresh, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

export { API_BASE_URL };
