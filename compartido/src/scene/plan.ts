// The vertical plan of the office for the phone: 192×452 logical pixels, drawn at an integer scale.
// From top to bottom: the entrance with Operación, the library and the kitchen with Relaciones;
// Observatorio and Estrategia; Mesa editorial and Revisión; El barrio on the sofa; and under it the
// game room (Sala de juegos), where the agents rest while nothing needs them.
// A central corridor (x = 96) and three cross corridors (y = 110, 178, 254) are the office's routes; the
// game room is reached from the third one, past the sofa (x = 124), through its doorway.

import { LIBRARY, TEAMS, type Box, type Direction, type Point, type TeamId, type ZoneId } from './roles';

export const PLAN_WIDTH = 192;
export const PLAN_HEIGHT = 452;
/** The office above the game room: 192×332, as before the game room existed. */
export const OFFICE_HEIGHT = 332;
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
  'worklet';
  return team;
}

const inside = (x: number, y: number, [bx, by, bw, bh]: readonly number[]) => { 'worklet'; return x >= bx! && x < bx! + bw! && y >= by! && y < by! + bh!; };

// ---------------------------------------------------------------- the game room
/** Its north wall (plaster, wainscot, skirting) starts where the office ended; its floor follows. */
export const GAME_WALL_Y = OFFICE_HEIGHT;
export const GAME_FLOOR_Y = GAME_WALL_Y + 21;
/** The doorway in its wall, on the path that goes past the sofa. */
export const GAME_DOOR_X = 124;
/** The lane inside the game room, between the furniture against the wall and the floor games. */
export const GAME_LANE_Y = 397;
/** The dance floor: 5×5 tiles of 8 px. */
export const DANCE_FLOOR: Box = [76, 405, 40, 40];
const DOOR_PATH: readonly Point[] = [[CX, A3], [GAME_DOOR_X, A3], [GAME_DOOR_X, GAME_LANE_Y]];
const inGame = (x: number, y: number): Point[] => [...DOOR_PATH, [x, GAME_LANE_Y], [x, y]];

export type RestId =
  | 'consola1' | 'consola2' | 'arcade1' | 'arcade2' | 'billar1' | 'billar2' | 'bateria' | 'microfono'
  | 'pista1' | 'pista2' | 'pista3' | 'charla1' | 'charla2' | 'cafe' | 'nevera' | 'estante'
  | 'estante2' | 'billar3' | 'pista4';

/** What a resting agent does at its spot: how it is drawn and what it says. */
export type Pastime = 'consola' | 'arcade' | 'billar' | 'bateria' | 'canta' | 'baila' | 'charla' | 'cafe' | 'nevera' | 'lee';

export interface RestSpot extends Place {
  pastime: Pastime;
  /** The other spot of a pair (they talk to each other). */
  partner?: RestId;
  /** Furniture drawn again over the agent (a pouf over the legs, the drum kit). */
  front?: { sprite: string; at: Point };
  /** «Juega en la consola», for the panel and the «now» line. */
  label: string;
}

/** Where the agents go while they rest: the game room, the kitchen and the library shelves. */
export const REST_SPOTS: Readonly<Record<RestId, RestSpot>> = {
  consola1: { via: inGame(23, 381), facing: 1, pastime: 'consola', partner: 'consola2', front: { sprite: 'pouf', at: [13, 373] }, label: 'Juega en la consola' },
  consola2: { via: inGame(51, 381), facing: 1, pastime: 'consola', partner: 'consola1', front: { sprite: 'pouf', at: [41, 373] }, label: 'Juega en la consola' },
  arcade1: { via: inGame(160, 381), facing: 1, pastime: 'arcade', partner: 'arcade2', label: 'Juega en la máquina de arcade' },
  arcade2: { via: inGame(177, 381), facing: 1, pastime: 'arcade', partner: 'arcade1', label: 'Juega en la máquina de arcade' },
  billar1: { via: inGame(120, 425), facing: 0, pastime: 'billar', partner: 'billar2', label: 'Juega billar' },
  billar2: { via: inGame(181, 425), facing: 2, pastime: 'billar', partner: 'billar1', label: 'Juega billar' },
  bateria: { via: inGame(29, 419), facing: 3, pastime: 'bateria', front: { sprite: 'drums', at: [8, 413] }, label: 'Toca la batería' },
  microfono: { via: inGame(56, 431), facing: 3, pastime: 'canta', label: 'Canta en el micrófono' },
  pista1: { via: inGame(84, 421), facing: 3, pastime: 'baila', label: 'Baila en la pista' },
  pista2: { via: inGame(104, 421), facing: 3, pastime: 'baila', label: 'Baila en la pista' },
  pista3: { via: inGame(84, 441), facing: 3, pastime: 'baila', label: 'Baila en la pista' },
  charla1: { via: inGame(91, 392), facing: 0, pastime: 'charla', partner: 'charla2', label: 'Conversa en la sala de juegos' },
  charla2: { via: inGame(107, 392), facing: 2, pastime: 'charla', partner: 'charla1', label: 'Conversa en la sala de juegos' },
  cafe: { via: [[CX, A1], [126, A1], [126, 70]], facing: 1, pastime: 'cafe', label: 'Se toma un café' },
  nevera: { via: [[CX, A1], [180, A1], [180, 64]], facing: 1, pastime: 'nevera', label: 'Busca algo de comer' },
  estante: { via: [[CX, A1], [16, A1], [16, 72]], facing: 1, pastime: 'lee', partner: 'estante2', label: 'Hojea un libro de la biblioteca' },
  // More spots than free agents, so that they can change pastime even when the whole team rests.
  estante2: { via: [[CX, A1], [64, A1], [64, 72]], facing: 1, pastime: 'lee', partner: 'estante', label: 'Hojea un libro de la biblioteca' },
  billar3: { via: inGame(140, 401), facing: 3, pastime: 'billar', label: 'Mira la partida de billar' },
  pista4: { via: inGame(104, 441), facing: 3, pastime: 'baila', label: 'Baila en la pista' },
};
export const REST_IDS = Object.keys(REST_SPOTS) as RestId[];

/** A zone the lights follow: each team, the library, the corridors and the game room. */
export type LightZone = ZoneId | 'pasillo' | 'juegos';
export const LIGHT_ZONES: readonly LightZone[] = ['biblioteca', 'operacion', 'relaciones', 'observatorio', 'estrategia', 'editorial', 'revision', 'barrio', 'pasillo', 'juegos'];
/**
 * The plan cut in rectangles, each lit by one zone (the walls go with the zone in front of them). The corridors
 * are what is left between the team spaces.
 */
export const LIGHT_AREAS: readonly { zone: LightZone; box: Box }[] = [
  { zone: 'biblioteca', box: [0, 0, 80, 110] },
  { zone: 'operacion', box: [80, 0, 32, 82] },
  { zone: 'relaciones', box: [112, 0, 80, 110] },
  { zone: 'observatorio', box: [0, 112, 80, 68] },
  { zone: 'estrategia', box: [112, 112, 80, 68] },
  { zone: 'editorial', box: [0, 182, 80, 72] },
  { zone: 'revision', box: [112, 182, 80, 72] },
  { zone: 'barrio', box: [0, 258, 192, 74] },
  { zone: 'pasillo', box: [80, 82, 32, 176] },
  { zone: 'pasillo', box: [0, 110, 80, 2] },
  { zone: 'pasillo', box: [112, 110, 80, 2] },
  { zone: 'pasillo', box: [0, 180, 80, 2] },
  { zone: 'pasillo', box: [112, 180, 80, 2] },
  { zone: 'pasillo', box: [0, 254, 80, 4] },
  { zone: 'pasillo', box: [112, 254, 80, 4] },
  { zone: 'juegos', box: [0, OFFICE_HEIGHT, 192, PLAN_HEIGHT - OFFICE_HEIGHT] },
];

/** The light zone under a logical point. */
export function lightZoneAt(x: number, y: number): LightZone {
  'worklet';
  for (const area of LIGHT_AREAS) if (inside(x, y, area.box)) return area.zone;
  return 'pasillo';
}

const same = (a: Point, b: Point) => { 'worklet'; return a[0] === b[0] && a[1] === b[1]; };

/** Whether b lies on the straight segment from a to c (a turn that goes back on itself does not). */
const between = (a: Point, b: Point, c: Point) => {
  'worklet';
  return (a[1] === b[1] && b[1] === c[1] && (b[0] - a[0]) * (c[0] - b[0]) >= 0)
    || (a[0] === b[0] && b[0] === c[0] && (b[1] - a[1]) * (c[1] - b[1]) >= 0);
};
const backtracks = (a: Point, b: Point, c: Point) => {
  'worklet';
  return (a[1] === b[1] && b[1] === c[1] || a[0] === b[0] && b[0] === c[0]) && !between(a, b, c);
};

/** Whether a route ends at a rest spot (the game room, the kitchen, the library shelf). */
const atRest = (route: readonly Point[]) => {
  'worklet';
  const end = route[route.length - 1];
  if (!end) return false;
  if (end[1] > OFFICE_HEIGHT) return true;
  for (const id of REST_IDS) {
    const via = REST_SPOTS[id].via;
    const last = via[via.length - 1]!;
    if (last[0] === end[0] && last[1] === end[1]) return true;
  }
  return false;
};

/**
 * Route between two places, both given as their corridor-first `via`: back along `from` to the central
 * corridor, along the corridor to the cross corridor of `to`, and in along `to`. Consecutive repeated
 * points are dropped; every segment is horizontal or vertical. Two places that share more than the corridor
 * point (the game room and El barrio, through the path past the sofa) join where their routes part, without
 * walking back to the corridor; a walk to or from a rest spot never turns back on itself either.
 */
export function planRoute(from: readonly Point[], to: readonly Point[]): Point[] {
  'worklet';
  const tidy = atRest(from) || atRest(to);
  let shared = 0;
  while (shared < from.length && shared < to.length && same(from[shared]!, to[shared]!)) shared++;
  const out: Point[] = shared > 1 ? from.slice(shared - 1).reverse() : [...from].reverse();
  if (shared > 1) out.push(...to.slice(shared));
  else {
    const entry = to[0];
    const exit = out[out.length - 1];
    if (entry && exit && !same(entry, exit)) out.push([CX, exit[1]], [CX, entry[1]]);
    out.push(...to);
  }
  const clean: Point[] = [];
  for (const point of out) {
    const last = clean[clean.length - 1];
    if (last && same(last, point)) continue;
    // To a rest spot and past the sofa a route never turns back on itself (the shared path is cut).
    if ((shared > 1 || tidy) && clean.length >= 2 && backtracks(clean[clean.length - 2]!, last!, point)) clean.pop();
    clean.push(point);
  }
  return clean;
}

/** Total Manhattan length of a route, in logical pixels. */
export function routeLength(route: readonly Point[]): number {
  'worklet';
  let total = 0;
  for (let i = 1; i < route.length; i++) total += Math.abs(route[i]![0] - route[i - 1]![0]) + Math.abs(route[i]![1] - route[i - 1]![1]);
  return total;
}

/** The zone under a logical point: the library or a team's space. */
export function zoneAt(x: number, y: number): ZoneId | null {
  'worklet';
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
  'worklet';
  const byWidth = Math.floor((availableWidth + 32) / PLAN_WIDTH);
  const byHeight = Math.floor(availableHeight / PLAN_HEIGHT);
  return Math.max(1, Math.min(4, byWidth, Math.max(2, byHeight)));
}
