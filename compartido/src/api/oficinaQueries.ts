// Focus-aware observers for Oficina. Query keys, cursor, intervals and error policy stay shared.
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from './client';
import { getActivity, getOverview } from './endpoints';
import { REFRESH } from './hooks';
import { getOficinaEventos, nextCursor, oficinaEventosKey, type OficinaEventos } from './oficina';
import { keys } from './queryClient';

export function feedUnavailable(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 403 || error.status === 404);
}
export function useOfficeQueries(enabled: boolean) {
  const client = useQueryClient();
  const activity = useQuery({ queryKey: keys.activity, queryFn: getActivity, enabled, refetchInterval: enabled ? REFRESH.scene : false });
  const overview = useQuery({ queryKey: keys.overview, queryFn: getOverview, enabled, refetchInterval: enabled ? REFRESH.overview : false });
  const events = useQuery({
    queryKey: oficinaEventosKey,
    queryFn: async ({ signal }) => {
      const previous = client.getQueryData<OficinaEventos & { cursor: string | null }>(oficinaEventosKey);
      const page = await getOficinaEventos(previous?.cursor ?? null, signal);
      return { ...page, cursor: nextCursor(previous?.cursor ?? null, page) };
    },
    enabled,
    refetchInterval: (q) => enabled && !feedUnavailable(q.state.error) ? REFRESH.scene : false,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: enabled,
    gcTime: 0, staleTime: 0, structuralSharing: false,
  });
  return { activity, overview, events };
}
