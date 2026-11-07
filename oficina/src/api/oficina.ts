// Oficina screen: the event feed that moves the scene's characters.
// GET /api/v1/oficina/eventos?desde=<iso> → { events: [...], now }, oldest first, `desde` exclusive.
// Without `desde` the server returns the last 10 minutes.

import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { api, ApiError } from './client';
import { REFRESH } from './hooks';

export type OficinaEventoTipo = 'consulta_biblioteca' | 'entrega' | 'publicacion';

export interface OficinaEvento {
  id: string | number;
  /** ISO timestamp of the real work that emitted it. */
  ts: string;
  tipo: OficinaEventoTipo;
  /** Role id that moves (scene/roles.ts). */
  rol: string;
  /** Receiving role for `entrega`; `biblioteca` or `linkedin` otherwise. */
  destino: string;
  detalle: string;
}

export interface OficinaEventos {
  events: OficinaEvento[];
  now: string;
}

export function getOficinaEventos(desde?: string | null, signal?: AbortSignal): Promise<OficinaEventos> {
  const query = desde ? `?desde=${encodeURIComponent(desde)}` : '';
  return api.get<OficinaEventos>(`/api/v1/oficina/eventos${query}`, signal);
}

export const oficinaEventosKey = ['oficina', 'eventos'] as const;

/** Seconds of overlap when no event has been seen yet: repeats are dropped by id, gaps would be lost. */
const OVERLAP_MS = 5_000;

/** Where the next poll starts: the last `ts` seen, or the server's `now` (minus a small overlap) before any. */
export function nextCursor(previous: string | null, page: OficinaEventos | undefined): string | null {
  let cursor = previous;
  for (const event of page?.events ?? []) {
    if (typeof event?.ts === 'string' && (!cursor || Date.parse(event.ts) > Date.parse(cursor))) cursor = event.ts;
  }
  if (cursor) return cursor;
  const now = page?.now ? Date.parse(page.now) : Number.NaN;
  return Number.isNaN(now) ? null : new Date(now - OVERLAP_MS).toISOString();
}

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
