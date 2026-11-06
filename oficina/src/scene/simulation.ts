// Pure scene logic: where each character is and which animation it plays.
// The pose of every character comes from its real status; nothing is invented.

import type { Activity, RoleStatus } from '../api/types';
import { ROLES, ROLE_BY_ID, SPRITES_WITHOUT_READING, WALKERS, type Direction, type Point, type Role, type RoleId } from './roles';

/** `desconocido` when the activity endpoint has not answered for this role. */
export type SceneStatus = RoleStatus | 'desconocido';
export type SpriteAction = 'idle_anim' | 'reading' | 'run';
export type StatusMap = Partial<Record<RoleId, SceneStatus>>;

export interface Actor {
  role: RoleId;
  index: number;
  sprite: number;
  x: number;
  y: number;
  direction: Direction;
  action: SpriteAction;
  /** Whether frames advance. Roles in design or with unknown status stay still. */
  animated: boolean;
  /** Drawn faded, with the «en diseño» tag. */
  dimmed: boolean;
  tag: string | null;
  away: boolean;
  talking: boolean;
  status: SceneStatus;
}

export const STATUS_LABEL: Record<SceneStatus, string> = {
  trabajando: 'Trabajando',
  en_espera: 'En espera',
  diseno: 'En diseño',
  desconocido: 'Sin datos',
};

const KNOWN: ReadonlySet<string> = new Set(['trabajando', 'en_espera', 'diseno']);

export function statusesFrom(activity: Activity | null | undefined): StatusMap {
  const map: StatusMap = {};
  for (const role of ROLES) {
    const status = activity?.roles?.[role.id]?.status;
    map[role.id] = status && KNOWN.has(status) ? status : 'desconocido';
  }
  return map;
}

export interface Pose {
  action: SpriteAction;
  animated: boolean;
  dimmed: boolean;
  tag: string | null;
  direction: Direction;
}

/** Translate a real status into what the character does at its seat. */
export function poseFor(role: Role, status: SceneStatus): Pose {
  switch (status) {
    case 'trabajando':
      return {
        // Reading is the pack's working animation; one sheet lacks it and idles instead.
        action: SPRITES_WITHOUT_READING.has(role.sprite) ? 'idle_anim' : 'reading',
        animated: true,
        dimmed: false,
        tag: null,
        direction: role.facing,
      };
    case 'en_espera':
      return { action: 'idle_anim', animated: true, dimmed: false, tag: null, direction: role.facing };
    case 'diseno':
      return { action: 'idle_anim', animated: false, dimmed: true, tag: 'en diseño', direction: role.facing };
    default:
      return { action: 'idle_anim', animated: false, dimmed: false, tag: null, direction: role.facing };
  }
}

const SPEED = 30; // logical px per second
const START_DELAY = 6000;
const CYCLE = 65000;
const HOLD = 8500;

const distance = (a: Point, b: Point) => Math.hypot(a[0] - b[0], a[1] - b[1]);

export function along(route: readonly Point[], travel: number): { x: number; y: number; direction: Direction } {
  let rest = travel;
  for (let i = 1; i < route.length; i++) {
    const a = route[i - 1]!;
    const b = route[i]!;
    const len = distance(a, b);
    if (rest <= len) {
      const f = len ? rest / len : 1;
      const horizontal = Math.abs(b[0] - a[0]) > Math.abs(b[1] - a[1]);
      const direction: Direction = horizontal ? (b[0] > a[0] ? 0 : 2) : b[1] > a[1] ? 3 : 1;
      return { x: a[0] + (b[0] - a[0]) * f, y: a[1] + (b[1] - a[1]) * f, direction };
    }
    rest -= len;
  }
  const last = route[route.length - 1]!;
  return { x: last[0], y: last[1], direction: 3 };
}

/** The two original characters whose turn it is for a stroll at time `ms`. */
export function walkersAt(ms: number): RoleId[] {
  if (ms < START_DELAY) return [];
  const cycle = Math.floor((ms - START_DELAY) / CYCLE);
  const n = WALKERS.length;
  return [WALKERS[cycle % n]!, WALKERS[(cycle + 5) % n]!];
}

/**
 * Every character at time `ms` of the ambient clock. Only characters really
 * waiting (`en_espera`) take the scheduled strolls to the kitchen or corridor;
 * working ones stay at their seat and roles in design never move.
 */
export function actorsAt(ms: number, statuses: StatusMap): Actor[] {
  const cycle = Math.floor(Math.max(0, ms - START_DELAY) / CYCLE);
  const phase = Math.max(0, ms - START_DELAY) % CYCLE;
  const pair = walkersAt(ms);

  return ROLES.map((role, index) => {
    const status = statuses[role.id] ?? 'desconocido';
    const pose = poseFor(role, status);
    const home: Actor = {
      role: role.id,
      index,
      sprite: role.sprite,
      x: role.home[0],
      y: role.home[1],
      direction: pose.direction,
      action: pose.action,
      animated: pose.animated,
      dimmed: pose.dimmed,
      tag: pose.tag,
      away: false,
      talking: false,
      status,
    };
    const slot = pair.indexOf(role.id);
    if (slot < 0 || status !== 'en_espera' || !role.exit) return home;

    const kitchen = cycle % 2 === 0;
    const destination: Point = kitchen ? [390 + slot * 26, 101] : [174 + slot * 24, 186];
    const tail: Point[] = kitchen ? [[345, 186], [345, 101], destination] : [destination];
    const route: Point[] = [role.home, ...role.exit, ...tail];
    const length = route.slice(1).reduce((sum, p, j) => sum + distance(route[j]!, p), 0);
    const travelTime = (length / SPEED) * 1000;
    const local = phase - slot * 800;
    if (local < 0 || local > travelTime * 2 + HOLD) return home;
    if (local < travelTime) return { ...home, ...along(route, (local / 1000) * SPEED), action: 'run', away: true };
    if (local < travelTime + HOLD) {
      return { ...home, x: destination[0], y: destination[1], direction: slot === 0 ? 0 : 2, action: 'idle_anim', away: true, talking: true };
    }
    return { ...home, ...along([...route].reverse(), ((local - travelTime - HOLD) / 1000) * SPEED), action: 'run', away: true };
  });
}

export interface TeamSummary {
  trabajando: number;
  en_espera: number;
  diseno: number;
  desconocido: number;
}

export function summarize(roles: readonly RoleId[], statuses: StatusMap): TeamSummary {
  const summary: TeamSummary = { trabajando: 0, en_espera: 0, diseno: 0, desconocido: 0 };
  for (const id of roles) summary[statuses[id] ?? 'desconocido'] += 1;
  return summary;
}

/** Hit test in logical coordinates: the character under the pointer, if any. */
export function actorAt(actors: readonly Actor[], x: number, y: number): Actor | null {
  let best: Actor | null = null;
  for (const actor of actors) {
    if (Math.abs(x - actor.x) <= 9 && y >= actor.y - 30 && y <= actor.y + 4) {
      if (!best || actor.y > best.y) best = actor;
    }
  }
  return best;
}

export function roleName(id: RoleId): string {
  return ROLE_BY_ID[id].name;
}
