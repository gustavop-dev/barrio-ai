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

const time = (event: OfficeEvent) => Date.parse(event.ts);

function byTime(a: OfficeEvent, b: OfficeEvent): number {
  const delta = time(a) - time(b);
  if (delta) return delta;
  const na = Number(a.id);
  const nb = Number(b.id);
  if (!Number.isNaN(na) && !Number.isNaN(nb)) return na - nb;
  return String(a.id).localeCompare(String(b.id));
}

/** A usable event: known kind, an id and a parseable timestamp. */
export function isOfficeEvent(value: unknown): value is OfficeEvent {
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
  return { consulta_biblioteca: 0, entrega: 0, publicacion: 0 };
}

export class EventQueue {
  private readonly options: QueueOptions;
  private readonly seen = new Set<string>();
  private readonly seenOrder: string[] = [];
  private pending: OfficeEvent[] = [];
  private summary: EventSummary | null = null;
  /** The newest `ts` accepted so far. */
  lastTs: string | null = null;

  constructor(options: Partial<QueueOptions> = {}) {
    this.options = { ...QUEUE_DEFAULTS, ...options };
  }

  /** Items waiting: the summary (if any) plus each pending event. */
  get size(): number {
    return this.pending.length + (this.summary ? 1 : 0);
  }

  /** Adds a page of events. Returns how many were new and valid. */
  ingest(events: readonly unknown[] | null | undefined, serverNow?: string | null): number {
    const fresh: OfficeEvent[] = [];
    const stale: OfficeEvent[] = [];
    const now = serverNow ? Date.parse(serverNow) : Number.NaN;
    for (const raw of events ?? []) {
      if (!isOfficeEvent(raw)) continue;
      const key = String(raw.id);
      if (this.seen.has(key)) continue;
      this.remember(key);
      if (!this.lastTs || time(raw) > Date.parse(this.lastTs)) this.lastTs = raw.ts;
      if (!Number.isNaN(now) && now - time(raw) > this.options.staleMs) stale.push(raw);
      else fresh.push(raw);
    }
    if (stale.length) this.addToSummary(stale.sort(byTime), 'backlog');
    if (fresh.length) {
      this.pending = [...this.pending, ...fresh].sort(byTime);
      if (this.pending.length > this.options.maxPending) {
        const cut = this.pending.length - this.options.keep;
        this.addToSummary(this.pending.slice(0, cut), 'overflow');
        this.pending = this.pending.slice(cut);
      }
    }
    return fresh.length + stale.length;
  }

  peek(): PlayItem | null {
    if (this.summary) return { kind: 'summary', summary: this.summary };
    const event = this.pending[0];
    return event ? { kind: 'event', event } : null;
  }

  shift(): PlayItem | null {
    const item = this.peek();
    if (!item) return null;
    if (item.kind === 'summary') this.summary = null;
    else this.pending = this.pending.slice(1);
    return item;
  }

  /** Drops everything waiting (ids stay remembered, so nothing replays). */
  clear(): void {
    this.pending = [];
    this.summary = null;
  }

  private remember(key: string) {
    this.seen.add(key);
    this.seenOrder.push(key);
    if (this.seenOrder.length > SEEN_LIMIT) this.seen.delete(this.seenOrder.shift()!);
  }

  private addToSummary(events: readonly OfficeEvent[], reason: SummaryReason) {
    const summary = this.summary ?? { reason, counts: emptyCounts(), total: 0, events: [] };
    if (summary.reason !== reason) summary.reason = 'overflow';
    for (const event of events) {
      summary.counts[event.tipo] += 1;
      summary.total += 1;
    }
    summary.events = [...summary.events, ...events].sort(byTime).slice(-SUMMARY_EVENTS_LIMIT);
    this.summary = summary;
  }
}

// ---------------------------------------------------------------- narration

/** Short name of the role that moves («Copywriter A», «Operación»); «El equipo» when unknown. */
export function actorName(id: string | null | undefined): string {
  return isCharacterId(id) ? CHARACTER_BY_ID[id].short : 'El equipo';
}

const quoted = (detail: string | null | undefined) => (detail && detail.trim() ? `: “${detail.trim()}”` : '');

/** The «now» line for an event: «Copywriter A va a la biblioteca: “clase 03”». */
export function describeEvent(event: OfficeEvent): string {
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

const KIND_WORDS: Record<EventKind, [string, string]> = {
  consulta_biblioteca: ['consulta a la biblioteca', 'consultas a la biblioteca'],
  entrega: ['entrega', 'entregas'],
  publicacion: ['publicación', 'publicaciones'],
};

/** «Mientras tanto: 3 consultas a la biblioteca, 2 entregas y 1 publicación.» */
export function describeSummary(summary: Pick<EventSummary, 'reason' | 'counts'>): string {
  const parts = EVENT_KINDS.filter((kind) => summary.counts[kind] > 0).map((kind) => {
    const n = summary.counts[kind];
    return `${n} ${KIND_WORDS[kind][n === 1 ? 0 : 1]}`;
  });
  const list = parts.length > 1 ? `${parts.slice(0, -1).join(', ')} y ${parts[parts.length - 1]}` : (parts[0] ?? 'sin movimientos');
  return `${summary.reason === 'backlog' ? 'Hace un rato' : 'Mientras tanto'}: ${list}.`;
}

/** The role whose portrait goes with a summary: the one that moved the most. */
export function summaryActor(summary: EventSummary): string | null {
  const counts = new Map<string, number>();
  for (const event of summary.events) counts.set(event.rol, (counts.get(event.rol) ?? 0) + 1);
  let best: string | null = null;
  for (const [rol, n] of counts) if (best === null || n > (counts.get(best) ?? 0)) best = rol;
  return best;
}
