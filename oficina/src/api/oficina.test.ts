import { describe, expect, it } from 'vitest';
import { nextCursor, type OficinaEvento } from './oficina';

const event = (id: number, ts: string): OficinaEvento => ({ id, ts, tipo: 'entrega', rol: 'perfil', destino: 'posicionamiento', detalle: '' });

describe('event feed cursor', () => {
  it('moves to the last ts seen', () => {
    const page = { events: [event(1, '2026-11-07T15:00:01Z'), event(2, '2026-11-07T15:00:05Z')], now: '2026-11-07T15:00:09Z' };
    expect(nextCursor(null, page)).toBe('2026-11-07T15:00:05Z');
    expect(nextCursor('2026-11-07T15:00:07Z', page)).toBe('2026-11-07T15:00:07Z');
  });

  it('keeps the last ts seen when a page is empty', () => {
    expect(nextCursor('2026-11-07T15:00:05Z', { events: [], now: '2026-11-07T15:10:00Z' })).toBe('2026-11-07T15:00:05Z');
  });

  it('starts from the server’s now, with a small overlap, before any event is seen', () => {
    expect(nextCursor(null, { events: [], now: '2026-11-07T15:10:00.000Z' })).toBe('2026-11-07T15:09:55.000Z');
    expect(nextCursor(null, undefined)).toBeNull();
  });
});
