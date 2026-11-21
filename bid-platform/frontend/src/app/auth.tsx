import { createContext, useContext, useEffect, useMemo, type ReactNode } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Spin } from 'antd';
import { Navigate, useLocation } from 'react-router-dom';
import { api, AUTH_EXPIRED_EVENT } from './api';
import { queryClient } from './queryClient';
import { queryKeys } from '../lib/query';
import type { User } from '../types';

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const me = useQuery({
    queryKey: queryKeys.me,
    queryFn: api.auth.me,
    retry: false,
    staleTime: 5 * 60_000,
  });

  useEffect(() => {
    const expire = () => queryClient.setQueryData(queryKeys.me, null);
    window.addEventListener(AUTH_EXPIRED_EVENT, expire);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, expire);
  }, []);

  const loginMutation = useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) =>
      api.auth.login(username, password),
    onSuccess: (user) => {
      queryClient.setQueryData(queryKeys.me, user);
    },
  });

  const logoutMutation = useMutation({
    mutationFn: api.auth.logout,
    onSettled: () => {
      queryClient.setQueryData(queryKeys.me, null);
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== 'auth' });
    },
  });

  const value = useMemo<AuthContextValue>(
    () => ({
      user: me.data ?? null,
      isLoading: me.isLoading,
      login: async (username, password) => loginMutation.mutateAsync({ username, password }),
      logout: async () => {
        await logoutMutation.mutateAsync();
      },
    }),
    [me.data, me.isLoading, loginMutation, logoutMutation],
  );

  if (me.isLoading) {
    return (
      <div className="app-loading">
        <Spin size="large" tip="正在恢复工作会话" />
      </div>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth 必须在 AuthProvider 内使用');
  return value;
}

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return children;
}
