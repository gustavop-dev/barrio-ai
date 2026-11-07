// Oficina screen: the event feed that moves the scene's characters. The shapes, the call and the
// cursor live in compartido/src/api/oficina.ts; the polling hook stays here with the scene.
import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { ApiError } from './client';
import { REFRESH } from './hooks';
import { getOficinaEventos, nextCursor, oficinaEventosKey, type OficinaEventos } from '../../../compartido/src/api/oficina';

export * from '../../../compartido/src/api/oficina';

/**
 * Polls the event feed every 15 s (REFRESH.scene) with `desde` set to the last `ts` seen and hands every
 * page to `onPage`. A 403 or 404 (no permission, older backend) stops the polling: the scene then only
 * shows the per-role states.
 */
export function useOficinaEventos(onPage: (page: OficinaEventos) => void) {
  const cursor = useRef<string | null>(null);
  const handler = useRef(onPage);
  useEffect(() => {
    handler.current = onPage;
  });

  const query = useQuery({
    queryKey: oficinaEventosKey,
    queryFn: async ({ signal }) => {
      const page = await getOficinaEventos(cursor.current, signal);
      cursor.current = nextCursor(cursor.current, page);
      return page;
    },
    refetchInterval: (q) => {
      const error = q.state.error;
      return error instanceof ApiError && (error.status === 403 || error.status === 404) ? false : REFRESH.scene;
    },
    // Each page is new information: never serve it twice from the cache.
    gcTime: 0,
    staleTime: 0,
    structuralSharing: false,
  });

  useEffect(() => {
    if (query.data) handler.current(query.data);
  }, [query.data]);

  return query;
}
