// The queue of real backend events that move the characters (FUNCIONES-NUEVAS «Qué mueve a cada
// personaje»). Events play in order; when many arrive at once, or they are already old, they are
// summarized in one line instead of walking everyone around.

import type { OficinaEvento, OficinaEventoTipo } from '../api/oficina';

import { CHARACTER_BY_ID, isCharacterId } from './roles';

export type OfficeEvent = OficinaEvento;

export type EventKind = OficinaEventoTipo;

export const EVENT_KINDS: readonly EventKind[] = ['consulta_biblioteca', 'entrega', 'publicacion'];

export type SummaryReason = 'backlog' | 'overflow';

export type KindCounts = Record<EventKind, number>;

export interface EventSummary {
  /** backlog: already old when it arrived (e.g. the first page); overflow: too many at once. */
  reason: SummaryReason;
  counts: KindCounts;
  total: number;
  /** The summarized events, oldest first (the last 50), for each role's «Lo último que hizo». */
  events: OfficeEvent[];
}

export type PlayItem = { kind: 'event'; event: OfficeEvent } | { kind: 'summary'; summary: EventSummary };

export interface QueueOptions {
  /** More pending events than this are summarized... */
  maxPending: number;
  /** ...keeping only the newest ones to play. */
  keep: number;
  /** Events older than this (against the server's `now`) are summarized, not played. */
  staleMs: number;
}

export const QUEUE_DEFAULTS: QueueOptions = { maxPending: 4, keep: 2, staleMs: 120_000 };

const SEEN_LIMIT = 1000;

const SUMMARY_EVENTS_LIMIT = 50;

const time = (event: OfficeEvent) => { 'worklet'; return Date.parse(event.ts); };

export interface QueueState {
  options: QueueOptions;
  seen: Record<string, boolean>;
  seenOrder: string[];
  pending: OfficeEvent[];
  summary: EventSummary | null;
  lastTs: string | null;
}

/** JS facade retained for existing PWA callers and tests. The UI runtime uses the same functions. */
export class EventQueue {
  readonly state: QueueState;
  constructor(options: Partial<QueueOptions> = {}, state?: QueueState) { this.state = state ?? createQueue(options); }
  get size() { return queueSize(this.state); }
  get lastTs() { return this.state.lastTs; }
  ingest(events: readonly unknown[] | null | undefined, serverNow?: string | null) { return queueIngest(this.state, events, serverNow); }
  peek() { return queuePeek(this.state); }
  shift() { return queueShift(this.state); }
  clear() { queueClear(this.state); }
}

const quoted = (detail: string | null | undefined) => { 'worklet'; return detail && detail.trim() ? `: “${detail.trim()}”` : ''; };

const KIND_WORDS: Record<EventKind, [string, string]> = {
  consulta_biblioteca: ['consulta a la biblioteca', 'consultas a la biblioteca'],
  entrega: ['entrega', 'entregas'],
  publicacion: ['publicación', 'publicaciones'],
};

// Dependencies precede callers: worklets capture their closures during module initialization.

function byTime(a: OfficeEvent, b: OfficeEvent): number {
  'worklet';
  const delta = time(a) - time(b);
  if (delta) return delta;
  const na = Number(a.id);
  const nb = Number(b.id);
  if (!Number.isNaN(na) && !Number.isNaN(nb)) return na - nb;
  return String(a.id).localeCompare(String(b.id));
}

/** A usable event: known kind, an id and a parseable timestamp. */
export function isOfficeEvent(value: unknown): value is OfficeEvent {
  'worklet';
  if (!value || typeof value !== 'object') return false;
  const event = value as Partial<OfficeEvent>;
  return (
    (typeof event.id === 'string' || typeof event.id === 'number') &&
    typeof event.ts === 'string' &&
    !Number.isNaN(Date.parse(event.ts)) &&
    EVENT_KINDS.includes(event.tipo as EventKind)
  );
}

export function emptyCounts(): KindCounts {
  'worklet';
  return { consulta_biblioteca: 0, entrega: 0, publicacion: 0 };
}

export function createQueue(options: Partial<QueueOptions> = {}): QueueState {
  'worklet';
  return { options: { ...QUEUE_DEFAULTS, ...options }, seen: {}, seenOrder: [], pending: [], summary: null, lastTs: null };
}

export function queueSize(s: QueueState): number {
  'worklet';
  return s.pending.length + (s.summary ? 1 : 0);
}

export function queueRemember(s: QueueState, key: string) {
  'worklet';
    s.seen[key] = true;
    s.seenOrder.push(key);
    if (s.seenOrder.length > SEEN_LIMIT) delete s.seen[s.seenOrder.shift()!];
  }

export function queueAddToSummary(s: QueueState, events: readonly OfficeEvent[], reason: SummaryReason) {
  'worklet';
    const summary = s.summary ?? { reason, counts: emptyCounts(), total: 0, events: [] };
    if (summary.reason !== reason) summary.reason = 'overflow';
    for (const event of events) {
      summary.counts[event.tipo] += 1;
      summary.total += 1;
    }
    summary.events = [...summary.events, ...events].sort(byTime).slice(-SUMMARY_EVENTS_LIMIT);
    s.summary = summary;
  }

export function queueIngest(s: QueueState, events: readonly unknown[] | null | undefined, serverNow?: string | null): number {
  'worklet';
    const fresh: OfficeEvent[] = [];
    const stale: OfficeEvent[] = [];
    const now = serverNow ? Date.parse(serverNow) : Number.NaN;
    for (const raw of events ?? []) {
      if (!isOfficeEvent(raw)) continue;
      const key = `id:${raw.id}`;
      if (s.seen[key]) continue;
      queueRemember(s, key);
      if (!s.lastTs || time(raw) > Date.parse(s.lastTs)) s.lastTs = raw.ts;
      if (!Number.isNaN(now) && now - time(raw) > s.options.staleMs) stale.push(raw);
      else fresh.push(raw);
    }
    if (stale.length) queueAddToSummary(s, stale.sort(byTime), 'backlog');
    if (fresh.length) {
      s.pending = [...s.pending, ...fresh].sort(byTime);
      if (s.pending.length > s.options.maxPending) {
        const cut = s.pending.length - s.options.keep;
        queueAddToSummary(s, s.pending.slice(0, cut), 'overflow');
        s.pending = s.pending.slice(cut);
      }
    }
    return fresh.length + stale.length;
  }

export function queuePeek(s: QueueState): PlayItem | null {
  'worklet';
    if (s.summary) return { kind: 'summary', summary: s.summary };
    const event = s.pending[0];
    return event ? { kind: 'event', event } : null;
  }

export function queueShift(s: QueueState): PlayItem | null {
  'worklet';
    const item = queuePeek(s);
    if (!item) return null;
    if (item.kind === 'summary') s.summary = null;
    else s.pending = s.pending.slice(1);
    return item;
  }

export function queueClear(s: QueueState): void {
  'worklet';
    s.pending = [];
    s.summary = null;
  }

// ---------------------------------------------------------------- narration

/** Short name of the role that moves («Copywriter A», «Operación»); «El equipo» when unknown. */
export function actorName(id: string | null | undefined): string {
  'worklet';
  return isCharacterId(id) ? CHARACTER_BY_ID[id].short : 'El equipo';
}

/** The «now» line for an event: «Copywriter A va a la biblioteca: “clase 03”». */
export function describeEvent(event: OfficeEvent): string {
  'worklet';
  switch (event.tipo) {
    case 'consulta_biblioteca':
      return `${actorName(event.rol)} va a la biblioteca${quoted(event.detalle)}`;
    case 'entrega': {
      const to = isCharacterId(event.destino) ? CHARACTER_BY_ID[event.destino].short : null;
      return `${actorName(event.rol)} ${to ? `entrega a ${to}` : 'entrega su trabajo'}${quoted(event.detalle)}`;
    }
    case 'publicacion':
      return `${actorName(event.rol)} publica en LinkedIn${quoted(event.detalle)}`;
    default:
      return actorName(event.rol);
  }
}

/** «Mientras tanto: 3 consultas a la biblioteca, 2 entregas y 1 publicación.» */
export function describeSummary(summary: Pick<EventSummary, 'reason' | 'counts'>): string {
  'worklet';
  const parts = EVENT_KINDS.filter((kind) => summary.counts[kind] > 0).map((kind) => {
    const n = summary.counts[kind];
    return `${n} ${KIND_WORDS[kind][n === 1 ? 0 : 1]}`;
  });
  const list = parts.length > 1 ? `${parts.slice(0, -1).join(', ')} y ${parts[parts.length - 1]}` : (parts[0] ?? 'sin movimientos');
  return `${summary.reason === 'backlog' ? 'Hace un rato' : 'Mientras tanto'}: ${list}.`;
}

/** The role whose portrait goes with a summary: the one that moved the most. */
export function summaryActor(summary: EventSummary): string | null {
  'worklet';
  const counts = new Map<string, number>();
  for (const event of summary.events) counts.set(event.rol, (counts.get(event.rol) ?? 0) + 1);
  let best: string | null = null;
  for (const [rol, n] of counts) if (best === null || n > (counts.get(best) ?? 0)) best = rol;
  return best;
}
