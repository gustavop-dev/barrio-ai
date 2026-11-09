// Oficina screen: the event feed that moves the scene's characters.
// GET /api/v1/oficina/eventos?desde=<iso> → { events: [...], now }, oldest first, `desde` exclusive.
// Without `desde` the server returns the last 10 minutes.

import { api } from './client';

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
  /** Additional dispatcher handoff; absent on the existing workflow events. */
  source?: 'orchestration';
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
