import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { onUnauthorized } from '../api/client';
import { getSession } from '../api/endpoints';
import { keys } from '../api/queryClient';
import type { Session } from '../api/types';
import { ErrorNote, Loading } from '../components/ui';

export const SIGNED_OUT: Session = { authenticated: false, user: null };

export function useSession() {
  return useQuery({ queryKey: keys.session, queryFn: getSession, staleTime: 60_000 });
}

/** When any request finds the session gone, forget cached data and show the login. */
export function SessionBridge({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  useEffect(
    () =>
      onUnauthorized(() => {
        queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== keys.session[0] });
        queryClient.setQueryData(keys.session, SIGNED_OUT);
      }),
    [queryClient],
  );
  return <>{children}</>;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const session = useSession();
  const location = useLocation();
  if (session.isPending) return <Loading label="Abriendo la oficina…" full />;
  if (session.isError && !session.data) {
    return (
      <div className="centered">
        <ErrorNote error={session.error} onRetry={() => void session.refetch()} />
      </div>
    );
  }
  if (!session.data?.authenticated) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={next === '/' ? '/login' : `/login?next=${encodeURIComponent(next)}`} replace />;
  }
  return <>{children}</>;
}
