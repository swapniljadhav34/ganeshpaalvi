// Who is signed in to the Studio, their role and permissions (from /api/staff/auth/me).
// The server enforces every permission; the browser only uses them to show the right tabs/buttons.
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useMemo } from 'react';
import { api, ensureCsrf } from './api';

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const qc = useQueryClient();
  const me = useQuery({
    queryKey: ['studio', 'me'],
    queryFn: async () => {
      await ensureCsrf();
      try {
        return await api('/auth/me');
      } catch (e) {
        if (e.status === 401 || e.status === 403) return null;
        throw e;
      }
    },
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  // Forget the previous person's Studio data (but keep the 'me' query that the screen is watching).
  const forgetOthers = useCallback(() => qc.removeQueries({
    predicate: (q) => q.queryKey[0] === 'studio' && q.queryKey[1] !== 'me',
  }), [qc]);

  const login = useCallback(async (username, password) => {
    await ensureCsrf();
    const data = await api('/auth/login', { method: 'POST', body: { username, password } });
    forgetOthers();
    qc.setQueryData(['studio', 'me'], data);
    return data;
  }, [qc, forgetOthers]);

  const logout = useCallback(async () => {
    try { await api('/auth/logout', { method: 'POST' }); } finally {
      forgetOthers();
      qc.setQueryData(['studio', 'me'], null);
    }
  }, [qc, forgetOthers]);

  const value = useMemo(() => {
    const perms = new Set(me.data?.permissions || []);
    return { me: me.data, loading: me.isLoading, error: me.error, can: (p) => perms.has(p), login, logout };
  }, [me.data, me.isLoading, me.error, login, logout]);
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
