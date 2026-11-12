import type { QueueOptions } from './events';
import type { Pastime, RestId } from './plan';
import type { CharacterId, Direction, Point, Role } from './roles';
/** Work icons (the first seven) and the emotes of the agents at rest. */
export type BubbleIcon = 'libro' | 'hoja' | 'cafe' | 'listo' | 'pregunta' | 'busca' | 'charla'
  | 'corazon' | 'nota' | 'exclama' | 'risa' | 'estrella' | 'zzz' | 'idea' | 'juego' | 'gota' | 'pizza';

export interface Actor {
  id: CharacterId;
  role: Role;
  index: number;
  x: number;
  y: number;
  dir: Direction;
  /** Points still to walk; null while standing. */
  path: Point[] | null;
  /** `via` of the place where it stands; null at home. */
  at: readonly Point[] | null;
  /** Off its seat (chairs are drawn behind it, the monitor turns off). */
  away: boolean;
  reading: boolean;
  alpha: number;
  /** -1 fading out, 1 fading in (Operación at the door). */
  fade: number;
  bubble: { icon: BubbleIcon; until: number } | null;
  busy: boolean;
  /** What it is doing because of an event («Consultando la biblioteca: “clase 03”»). */
  doing: string | null;
  /** The rest spot it holds while it rests (walking there or at it); null at its seat or on an errand. */
  spot: RestId | null;
  /** What it does at that spot, once there. */
  pastime: Pastime | null;
  /** Scene clock until which it stays at its seat: after its own work, or called by a colleague. */
  duty: number;
  /** At its seat: when it leaves to rest (-1 not decided). At rest: when it changes pastime. */
  restAt: number;
  /** When it next says something at rest, and the reply it owes a partner. */
  emoteAt: number;
  reply: BubbleIcon | null;
  /** Walks faster: called to its seat, or on its way to an event. */
  hurry: boolean;
}

/** The «now» line: the last thing narrated. */
export interface NowEntry {
  key: number;
  text: string;
  role: CharacterId | null;
  /** Wall-clock ms when it was narrated. */
  at: number;
}

/** One real event in a role's «Lo último que hizo». */
export interface FeedEntry {
  key: string;
  role: CharacterId;
  text: string;
  /** ms of the event's `ts`. */
  at: number;
}

export interface EngineSnapshot {
  version: number;
  now: NowEntry | null;
  /** Newest first. */
  feed: readonly FeedEntry[];
  doing: Partial<Record<CharacterId, string>>;
  librarianBusy: boolean;
  paused: boolean;
  /** Paused or frozen: the clock does not advance. */
  halted: boolean;
  still: boolean;
}

export interface EngineOptions {
  queue?: Partial<QueueOptions>;
  /** Wall clock for the «now» line; Date.now by default. */
  wallClock?: () => number;
  /** Start still (prefers-reduced-motion). */
  still?: boolean;
  /** Start frozen (activity not loaded yet). */
  frozen?: boolean;
}

