// The vertical plan of the office for the phone: 192×336 logical pixels, drawn at an integer scale.
// From top to bottom: the entrance with Operación, the library and the kitchen with Relaciones;
// Observatorio and Estrategia; Mesa editorial and Revisión; El barrio on the sofa.
// A central corridor (x = 96) and three cross corridors (y = 110, 178, 254) are the only routes.

import { LIBRARY, TEAMS, type Direction, type Point, type TeamId, type ZoneId } from './roles';

export const PLAN_WIDTH = 192;
export const PLAN_HEIGHT = 336;
/** Central corridor. */
export const CORRIDOR_X = 96;
/** Cross corridors, top to bottom. */
export const CROSS_Y = [110, 178, 254] as const;

const [A1, A2, A3] = CROSS_Y;
const CX = CORRIDOR_X;

export interface Place {
  /** Route from the central corridor to the spot (first point on the corridor, last point the spot). */
  via: readonly Point[];
  /** Where the visitor looks once there. */
  facing: Direction;
}

export type PlaceId =
  | 'biblioteca1'
  | 'biblioteca2'
  | 'cafe'
  | 'puerta'
  | 'estrategia'
  | 'observatorio'
  | 'editorial'
  | 'barrio'
  | 'revision'
  | 'relaciones'
  | 'operacion';

/** Spots a character walks to on a visit: the library counter, the coffee machine, the door, each team. */
export const PLACES: Readonly<Record<PlaceId, Place>> = {
  biblioteca1: { via: [[CX, A1], [32, A1], [32, 112]], facing: 1 },
  biblioteca2: { via: [[CX, A1], [54, A1], [54, 112]], facing: 1 },
  cafe: { via: [[CX, A1], [126, A1], [126, 70]], facing: 1 },
  puerta: { via: [[CX, 58], [CX, 34]], facing: 1 },
  estrategia: { via: [[CX, A2], [150, A2], [150, 168]], facing: 0 },
  observatorio: { via: [[CX, A2], [42, A2], [42, 168]], facing: 0 },
  editorial: { via: [[CX, 214], [82, 214]], facing: 2 },
  barrio: { via: [[CX, A3], [128, A3], [128, 290]], facing: 2 },
  revision: { via: [[CX, A3], [134, A3], [134, 240]], facing: 0 },
  relaciones: { via: [[CX, A1], [158, A1]], facing: 1 },
  operacion: { via: [[CX, A1], [CX, 74]], facing: 1 },
};

export const LIBRARY_SPOTS = ['biblioteca1', 'biblioteca2'] as const;

/** The spot where a delivery for `team` is handed over. */
export function visitPlaceFor(team: TeamId): PlaceId {
  return team;
}

const same = (a: Point, b: Point) => a[0] === b[0] && a[1] === b[1];

/**
 * Route between two places, both given as their corridor-first `via`: back along `from` to the central
 * corridor, along the corridor to the cross corridor of `to`, and in along `to`. Consecutive repeated
 * points are dropped; every segment is horizontal or vertical.
 */
export function planRoute(from: readonly Point[], to: readonly Point[]): Point[] {
  const out: Point[] = [...from].reverse();
  const entry = to[0];
  const exit = out[out.length - 1];
  if (entry && exit && !same(entry, exit)) out.push([CX, exit[1]], [CX, entry[1]]);
  out.push(...to);
  const clean: Point[] = [];
  for (const point of out) {
    const last = clean[clean.length - 1];
    if (!last || !same(last, point)) clean.push(point);
  }
  return clean;
}

/** Total Manhattan length of a route, in logical pixels. */
export function routeLength(route: readonly Point[]): number {
  let total = 0;
  for (let i = 1; i < route.length; i++) total += Math.abs(route[i]![0] - route[i - 1]![0]) + Math.abs(route[i]![1] - route[i - 1]![1]);
  return total;
}

const inside = (x: number, y: number, [bx, by, bw, bh]: readonly number[]) => x >= bx! && x < bx! + bw! && y >= by! && y < by! + bh!;

/** The zone under a logical point: the library or a team's space. */
export function zoneAt(x: number, y: number): ZoneId | null {
  if (inside(x, y, LIBRARY.box)) return 'biblioteca';
  return TEAMS.find((team) => inside(x, y, team.box))?.id ?? null;
}

/** Zone labels over the scene, top-left in logical pixels (the design's positions at 2×, halved). */
export const ZONE_LABELS: readonly { zone: ZoneId; text: string; at: Point }[] = [
  { zone: 'biblioteca', text: 'BIBLIOTECA', at: [5, 48] },
  { zone: 'operacion', text: 'OPERACIÓN', at: [79, 64] },
  { zone: 'relaciones', text: 'RELACIONES', at: [140, 56] },
  { zone: 'observatorio', text: 'OBSERVATORIO', at: [5, 107] },
  { zone: 'estrategia', text: 'ESTRATEGIA', at: [113, 107] },
  { zone: 'editorial', text: 'MESA EDITORIAL', at: [5, 177] },
  { zone: 'revision', text: 'REVISIÓN', at: [113, 177] },
  { zone: 'barrio', text: 'EL BARRIO', at: [35, 264] },
];

/**
 * The integer scale for the scene. Phones get 2× even when the screen is a little narrower than 384 px:
 * up to 16 px per side may be cropped (the walls and the edge of the furniture). The height never pushes
 * the scale below 2×, and it never goes above 4×.
 */
export function sceneScale(availableWidth: number, availableHeight: number): number {
  const byWidth = Math.floor((availableWidth + 32) / PLAN_WIDTH);
  const byHeight = Math.floor(availableHeight / PLAN_HEIGHT);
  return Math.max(1, Math.min(4, byWidth, Math.max(2, byHeight)));
}
