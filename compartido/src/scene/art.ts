// The office's pixel art, drawn the same way by both renderers through a Pen over their own canvas:
// - paintRoom: the still room (the PWA draws it each frame, the native app records it once);
// - paintFloor: what lights up on the floor under the people (the dance floor);
// - paintLights: over the people, the dark of the zones nobody uses, the screens in use, the game room's lights,
//   the working lights and the speech bubbles.
// The light layers are worklets: the native app runs them on the UI thread, once per frame.

import { ATLAS, type Rect } from './atlas';
import type { Actor, BubbleIcon } from './model';
import {
  DANCE_FLOOR, GAME_DOOR_X, GAME_FLOOR_Y, GAME_WALL_Y, LIGHT_AREAS, OFFICE_HEIGHT, PLAN_HEIGHT, PLAN_WIDTH, REST_SPOTS,
} from './plan';
import { sceneHop, sceneStatus, type SceneState } from './runtime';
import { CHARACTERS, LIBRARIAN_ID, type Point } from './roles';

/** The room's own colours (walls, floor edges, screens, bubble icons). Artwork, not theme tokens. */
export const ROOM = {
  outside: '#4b5655',
  plaster: '#eee5cc',
  plasterLight: '#fff5dd',
  wainscot: '#9ba998',
  skirting: '#667b70',
  wall: '#536b61',
  wallLight: '#b9c5ae',
  base: '#526c61',
  kitchenEdge: '#aa987f',
  screenOff: '#33403f',
  screenOffLine: '#3f4e4c',
  screenLine: '#7fd9c9',
  white: '#ffffff',
  book: '#a54e35',
  bookSpine: '#7a3624',
  coffee: '#8a6552',
  steam: '#b9b5ad',
  // The game room: a plum wall, the dark of the lights off, the colours of its lights.
  gameWall: '#4a3f63',
  gameWallLight: '#625483',
  gameWainscot: '#3a3150',
  gameSkirting: '#2b2440',
  night: '#0e1326',
  pink: '#f06aa6',
  yellow: '#f6d046',
  orange: '#f39b38',
  violet: '#9a6cf0',
  red: '#e0465a',
  blue: '#4c9be8',
  green: '#4fc27a',
  warm: '#ffe7a8',
} as const;

/** The brand colours the scene uses (the PWA reads them from its CSS tokens). */
export interface ScenePalette {
  tinta: string;
  tintaSuave: string;
  papel: string;
  ofc: string;
  hondo: string;
  claro: string;
  postit: string;
}

export const DEFAULT_PALETTE: ScenePalette = {
  tinta: '#1e1e2b',
  tintaSuave: '#565972',
  papel: '#f7f6f0',
  ofc: '#0ff1ce',
  hondo: '#00715e',
  claro: '#d2fbf3',
  postit: '#f8d47d',
};

export interface Pen {
  rect(x: number, y: number, w: number, h: number, color: string, alpha?: number): void;
  sprite(name: string, x: number, y: number): void;
}
export interface RoomPen extends Pen {
  /** Repeats a sprite over the box, clipped. */
  tile(name: string, x: number, y: number, w: number, h: number): void;
  /** Nine-slice: fixed corners of k px, repeated edges and centre. */
  rug(name: string, x: number, y: number, w: number, h: number, k: number): void;
}

/** Desk monitors (roles.ts `monitor`, the top-left of each). */
const MONITOR = ATLAS.monitorFront!;
export const MONITORS: readonly Point[] = CHARACTERS.flatMap((role) => role.monitor ? [role.monitor] : []);

// ---------------------------------------------------------------- people

const ROWS = CHARACTERS.map((role) => ({
  run: ATLAS[`p${role.sprite}-run`]!, idle: ATLAS[`p${role.sprite}-idle_anim`]!, reading: ATLAS[`p${role.sprite}-reading`] ?? null,
}));
/** A dancer turns right, front, left, front. */
const DANCE = [0, 3, 2, 3] as const;

/** Where a character's 16×32 frame comes from in the atlas and where it goes, written into `out` (no allocation). */
export interface SpriteFrame { sx: number; sy: number; x: number; y: number; alpha: number }
export function actorFrame(s: SceneState, a: Actor, out: SpriteFrame): void {
  'worklet';
  const status = sceneStatus(s, a.id);
  const moving = a.path !== null;
  const reads = a.reading || (status === 'trabajando' && !a.away && !a.role.monitor && !a.role.service);
  const rows = ROWS[a.index]!;
  const reading = !moving && reads && rows.reading !== null;
  const r: Rect = moving ? rows.run : reading ? rows.reading! : rows.idle;
  const animate = !s.still && !s.paused && !s.frozen && (moving || status === 'trabajando' || status === 'en_espera' || a.reading);
  const frame = animate ? Math.floor(s.clock / (moving ? s.motion.runFrameMs : s.motion.idleFrameMs) + a.index) % 6 : 0;
  let dir: number = reading ? 2 : a.dir;
  let bob = 0;
  if (!moving && animate && a.pastime === 'baila') {
    const step = Math.floor(s.clock / s.motion.danceStepMs) + a.index;
    dir = DANCE[step % 4]!; bob = step % 2;
  }
  if ((dir * 6 + frame) * 16 + 16 > r[2]) dir = 0;
  out.sx = r[0] + (dir * 6 + frame) * 16; out.sy = r[1];
  out.x = Math.round(a.x - 8); out.y = Math.round(a.y - 29) - sceneHop(s, a.id) - bob;
  out.alpha = a.alpha * (status === 'diseno' ? 0.45 : 1);
}

/** Furniture drawn again over a resting agent (the pouf over its legs, the drum kit), once it is there. */
export function frontProp(a: Actor): { sprite: string; at: Point } | null {
  'worklet';
  if (!a.spot || !a.pastime || a.path) return null;
  return REST_SPOTS[a.spot].front ?? null;
}

// ---------------------------------------------------------------- the still room

export function paintRoom(p: RoomPen): void {
  const W = PLAN_WIDTH;
  const H = PLAN_HEIGHT;
  const R = p.rect;
  const S = p.sprite;
  R(0, 0, W, H, ROOM.outside);
  // ---------------------------------------------------------------- the office
  p.tile('floor', 4, 30, 184, OFFICE_HEIGHT - 30);
  p.tile('tile', 112, 30, 76, 76);
  R(110, 30, 2, 76, ROOM.kitchenEdge);
  R(0, 0, W, 22, ROOM.plaster);
  R(0, 0, W, 2, ROOM.plasterLight);
  R(0, 22, W, 6, ROOM.wainscot);
  R(0, 28, W, 2, ROOM.skirting);
  R(0, 0, 4, H, ROOM.wall);
  R(3, 2, 1, H - 4, ROOM.wallLight);
  R(188, 0, 4, H, ROOM.wall);
  R(188, 2, 1, H - 4, ROOM.wallLight);
  p.rug('rugBlue', 6, 114, 72, 60, 8);
  p.rug('rugGreen', 114, 114, 72, 60, 6);
  p.rug('rugRust', 6, 184, 72, 68, 8);
  p.rug('rugGreen', 114, 184, 72, 64, 6);
  p.rug('rugBlue', 30, 260, 132, 72, 8);
  S('door', 88, 2);
  S('windowSmall', 52, 4);
  S('board', 160, 6);
  S('wallCabinet', 116, 8);
  S('wallCabinet', 134, 8);
  // Furniture behind the people.
  S('library', 6, 22);
  S('books', 40, 28);
  S('plantSmall', 78, 30);
  S('cabinet', 113, 42);
  S('coffee', 120, 32);
  S('sink', 144, 40);
  S('stove', 152, 30);
  S('fridge', 171, 22);
  S('deskLight', 142, 58);
  S('fruit', 150, 62);
  S('cup', 168, 66);
  for (const [x, y] of [[8, 114], [44, 114], [116, 114], [152, 114]] as const) S('deskLight', x, y);
  S('chair', 18, 186);
  S('chair', 50, 186);
  S('desk', 10, 196);
  S('desk', 42, 196);
  S('laptop', 18, 210);
  S('laptop', 50, 210);
  S('cup', 66, 220);
  S('deskLight', 140, 188);
  S('plant', 114, 190);
  S('printer', 172, 226);
  S('sofa', 72, 262);
  S('lamp', 158, 266);
  S('palm', 8, 292);
  S('plant', 164, 298);
  S('roundChair', 45, 314);
  S('roundChair', 133, 314);
  S('coffeeTable', 81, 300);
  // Monitors, off: the lit screen is drawn over them while their owner works (paintLights).
  for (const [x, y] of MONITORS) {
    S('monitorFront', x, y);
    R(x + 2, y + 2, 25, 12, ROOM.screenOff);
    R(x + 3, y + 3, 23, 1, ROOM.screenOffLine);
  }
  // ---------------------------------------------------------------- the game room
  const wy = GAME_WALL_Y;
  const fy = GAME_FLOOR_Y;
  p.tile('floor', 4, fy, 184, H - 4 - fy);
  // Its north wall, with a doorway on the path past the sofa (the floor of the barrio goes through it).
  const door = [GAME_DOOR_X - 8, GAME_DOOR_X + 8] as const;
  for (const [x0, x1] of [[4, door[0] - 2], [door[1] + 2, 188]] as const) {
    R(x0, wy, x1 - x0, 14, ROOM.gameWall);
    R(x0, wy, x1 - x0, 1, ROOM.gameWallLight);
    R(x0, wy + 14, x1 - x0, 5, ROOM.gameWainscot);
    R(x0, wy + 19, x1 - x0, 2, ROOM.gameSkirting);
  }
  p.tile('floor', door[0], wy, 16, fy - wy);
  R(door[0] - 2, wy, 2, fy - wy, ROOM.gameSkirting);
  R(door[1], wy, 2, fy - wy, ROOM.gameSkirting);
  R(0, H - 4, W, 4, ROOM.base);
  p.rug('rugRust', 124, 400, 62, 46, 8);
  // The dance floor, off: dark tiles with a grid (paintFloor lights them).
  const [dx, dy, dw, dh] = DANCE_FLOOR;
  R(dx - 1, dy - 1, dw + 2, dh + 2, ROOM.gameSkirting);
  for (let j = 0; j < dh / 8; j++) for (let i = 0; i < dw / 8; i++) R(dx + i * 8, dy + j * 8, 7, 7, (i + j) % 2 ? ROOM.gameWainscot : ROOM.gameWall);
  S('tvConsole', 8, 337);
  S('speaker', 74, 335);
  S('cueRack', 137, 338);
  S('arcades', 152, 332);
  S('pouf', 13, 373);
  S('pouf', 41, 373);
  S('poolTable', 129, 404);
  S('drums', 8, 413);
  S('mic', 63, 405);
}

// ---------------------------------------------------------------- bubbles

/**
 * Bubble icons, 7×6 pixel maps (several frames for the animated ones). Letters are colours (ICON_INK);
 * a dot is empty. The first seven are the work icons the scene always had.
 */
export const ICONS: Readonly<Record<BubbleIcon, readonly (readonly string[])[]>> = {
  libro: [['.......', 'bbbBbbb', 'bppBppb', 'bppBppb', 'bppBppb', 'bbbBbbb']],
  hoja: [['.wwwww.', '.wwwww.', '.wsssw.', '.wwwww.', '.wsssw.', '.wwwww.']],
  cafe: [['..m....', '...m...', '.wwww..', '.wccww.', '.wwwww.', '.wwww..']],
  listo: [['.......', '.....d.', 'd...d..', '.d.d...', '..d....', '..d....']],
  pregunta: [['..kkk..', '.....k.', '....k..', '...k...', '.......', '...k...']],
  busca: [['.kkk...', 'k...k..', 'k...k..', '.kkk...', '....k..', '.....k.']],
  charla: [
    ['.......', '.......', 's......', '...s..s', '.......', '.......'],
    ['.......', '.......', '...s...', 's.....s', '.......', '.......'],
    ['.......', '.......', '......s', 's..s...', '.......', '.......'],
  ],
  corazon: [['.rr.rr.', 'rrrrrrr', 'rrrrrrr', '.rrrrr.', '..rrr..', '...r...']],
  nota: [
    ['..vvvvv', '..v...v', '..v...v', 'vvv.vvv', 'vvv.vvv', '.......'],
    ['.......', '..vvvvv', '..v...v', '..v...v', 'vvv.vvv', 'vvv.vvv'],
  ],
  exclama: [['...r...', '..rrr..', '..rrr..', '...r...', '.......', '...r...']],
  risa: [['.yyyyy.', 'yykykyy', 'yyyyyyy', 'ykkkkky', 'yykkkyy', '.yyyyy.']],
  estrella: [['...y...', '..yyy..', 'yyyyyyy', '.yyyyy.', '.yy.yy.', 'y.....y']],
  zzz: [
    ['...uuuu', '....u..', '...uuuu', 'uuu....', '.u.....', 'uuu....'],
    ['....uuu', '.....u.', '....uuu', '.uuu...', '..u....', '.uuu...'],
  ],
  idea: [['..yyy..', '.yyyyy.', '.yyyyy.', '..yyy..', '..sss..', '...s...']],
  juego: [['.......', '.sssss.', 'swsssrs', 'wwwsrss', 'swsssss', 'ss...ss']],
  gota: [['...u...', '..uuu..', '.uuuuu.', '.uuwuu.', '.uuuuu.', '..uuu..']],
  pizza: [['ooooooo', '.yryyy.', '.yyyry.', '..ryy..', '..yy...', '...y...']],
};

function iconInk(C: ScenePalette, letter: string): string {
  'worklet';
  switch (letter) {
    case 'k': return C.tinta;
    case 's': return C.tintaSuave;
    case 'p': return C.papel;
    case 'd': return C.hondo;
    case 'w': return ROOM.white;
    case 'b': return ROOM.book;
    case 'B': return ROOM.bookSpine;
    case 'c': return ROOM.coffee;
    case 'm': return ROOM.steam;
    case 'r': return ROOM.red;
    case 'y': return ROOM.yellow;
    case 'o': return ROOM.orange;
    case 'u': return ROOM.blue;
    case 'v': return ROOM.violet;
    default: return ROOM.green;
  }
}

/** A speech bubble whose tail points at (x, y + 12): the bubble is 13×12 and its icon 7×6. */
export function paintBubble(p: Pen, C: ScenePalette, icon: BubbleIcon, x: number, y: number, frame: number): void {
  'worklet';
  p.rect(x - 7, y, 13, 10, C.tinta);
  p.rect(x - 6, y + 1, 11, 8, ROOM.white);
  p.rect(x - 1, y + 10, 3, 2, C.tinta);
  p.rect(x, y + 9, 1, 2, ROOM.white);
  const frames = ICONS[icon];
  const rows = frames[frame % frames.length]!;
  for (let j = 0; j < rows.length; j++) {
    const row = rows[j]!;
    let i = 0;
    while (i < row.length) {
      const letter = row[i]!;
      let k = i + 1;
      while (k < row.length && row[k] === letter) k++;
      if (letter !== '.') p.rect(x - 3 + i, y + 2 + j, k - i, 1, iconInk(C, letter));
      i = k;
    }
  }
}

// ---------------------------------------------------------------- light layers

const DISCO = [ROOM.pink, ROOM.yellow, '#0ff1ce', ROOM.violet] as const;
const BULBS = [ROOM.pink, ROOM.yellow, '#0ff1ce', ROOM.orange, ROOM.violet] as const;
/** How dark a zone gets with its lights off. */
const DARK = 0.62;

function dancing(s: SceneState): number {
  'worklet';
  let n = 0;
  for (const a of s.actors) if (a.pastime === 'baila' && !a.path) n++;
  return n;
}

function animated(s: SceneState): boolean {
  'worklet';
  return !s.still && !s.paused && !s.frozen;
}

/** The dance floor, drawn under the people: lit while someone dances or during a party, faint otherwise. */
export function paintFloor(p: Pen, s: SceneState): void {
  'worklet';
  const game = s.light.juegos ?? 0;
  if (game <= 0.02) return;
  const party = s.partyUntil > s.clock;
  const dancers = dancing(s);
  const beat = animated(s) ? Math.floor(s.clock / s.motion.discoMs) : 0;
  const strength = (party ? 0.95 : dancers ? 0.75 : 0.22) * game;
  const [dx, dy, dw, dh] = DANCE_FLOOR;
  for (let j = 0; j < dh / 8; j++) {
    for (let i = 0; i < dw / 8; i++) {
      const lit = party || dancers ? (i + j + beat) % 3 !== 0 : (i * 3 + j + beat) % 5 === 0;
      if (!lit) continue;
      p.rect(dx + i * 8, dy + j * 8, 7, 7, DISCO[(i + j * 2 + beat) % 4]!, strength);
    }
  }
}

function playing(s: SceneState, pastime: string): boolean {
  'worklet';
  for (const a of s.actors) if (a.pastime === pastime && !a.path) return true;
  return false;
}

function playingAt(s: SceneState, spot: string): boolean {
  'worklet';
  for (const a of s.actors) if (a.spot === spot && a.pastime && !a.path) return true;
  return false;
}

/** Whether a seated role works at its seat now: its screen and its zone's light are on. */
export function atWork(s: SceneState, index: number): boolean {
  'worklet';
  const a = s.actors[index]!;
  if (a.away || a.path || a.at || s.paused) return false;
  return s.statuses[a.id] === 'trabajando' || a.busy || a.duty > s.clock;
}

export function paintLights(p: Pen, s: SceneState, C: ScenePalette): void {
  'worklet';
  const m = s.motion;
  const live = animated(s);
  // The dark over every zone whose lights are off.
  for (const area of LIGHT_AREAS) {
    const level = s.light[area.zone] ?? 1;
    if (level >= 0.99) continue;
    const [x, y, w, h] = area.box;
    p.rect(x, y, w, h, ROOM.night, DARK * (1 - level));
  }
  // The screens of the desks in use.
  for (let i = 0; i < s.actors.length; i++) {
    const a = s.actors[i]!;
    const at = a.role.monitor;
    if (!at || !atWork(s, i)) continue;
    const [x, y] = at;
    p.rect(x - 2, y + 16, MONITOR[2] + 4, 6, C.ofc, 0.18);
    p.rect(x + 2, y + 2, 25, 12, C.claro);
    p.rect(x + 2, y + 2, 25, 2, C.ofc);
    p.rect(x + 4, y + 6, 13, 1, C.hondo);
    p.rect(x + 4, y + 9, 17, 1, ROOM.screenLine);
    p.rect(x + 4, y + 12, 9, 1, ROOM.screenLine);
    if (live && Math.floor(s.clock / 500 + i) % 2) p.rect(x + 4 + (Math.floor(s.clock / 250) % 9), y + 12, 1, 1, C.hondo);
  }
  // The game room's lights follow its own light level.
  const game = s.light.juegos ?? 0;
  if (game > 0.02) {
    const party = s.partyUntil > s.clock;
    const beat = live ? Math.floor(s.clock / (party ? m.bulbMs / 2 : m.bulbMs)) : 0;
    const frame = live ? Math.floor(s.clock / m.screenFrameMs) : 0;
    // String lights along the top of its wall.
    p.rect(4, GAME_WALL_Y + 2, 184, 1, ROOM.gameSkirting);
    for (let i = 0; i < 31; i++) {
      const x = 6 + i * 6;
      if (x >= GAME_DOOR_X - 10 && x <= GAME_DOOR_X + 9) continue;
      const on = party ? (i + beat) % 3 !== 0 : (i + beat) % 7 !== 0;
      p.rect(x, GAME_WALL_Y + 3 + (i % 2), 2, 2, BULBS[(i + (party ? beat : 0)) % 5]!, on ? game : 0.25 * game);
    }
    // The TV: a race while someone plays the console, a soft glow otherwise.
    const tvX = 8 + 26;
    const tvY = 337 + 2;
    const console1 = s.occupied.consola1 !== undefined || s.occupied.consola2 !== undefined;
    if (console1 && playing(s, 'consola')) {
      p.rect(tvX, tvY, 24, 11, '#1d2b55', game);
      p.rect(tvX, tvY + 7, 24, 4, '#2f6b3f', game);
      p.rect(tvX + ((frame * 2) % 24), tvY + 8, 3, 2, ROOM.red, game);
      p.rect(tvX + ((frame * 3 + 11) % 24), tvY + 9, 3, 2, ROOM.yellow, game);
      p.rect(tvX + 10, tvY + 2, 4, 1, ROOM.white, game);
      p.rect(tvX - 4, tvY + 13, 32, 3, '#4c9be8', 0.18 * game);
    }
    // The arcade screens: the game while someone plays, the attract loop otherwise.
    for (const [k, sx] of [[0, 155], [1, 171]] as const) {
      const used = playingAt(s, k === 0 ? 'arcade1' : 'arcade2');
      const y = 345;
      p.rect(sx, y, 10, 6, used ? '#141a33' : '#232a46', game);
      const t = frame + k * 5;
      if (used) {
        p.rect(sx + (t % 9), y + 1 + (t % 4), 1, 1, ROOM.yellow, game);
        p.rect(sx + 1, y + 4, 3 + (t % 5), 1, k ? ROOM.pink : '#0ff1ce', game);
        p.rect(sx + 7 - (t % 6), y + 2, 2, 1, ROOM.red, game);
      } else if (Math.floor(t / 4) % 2) {
        p.rect(sx + 2, y + 2, 6, 2, k ? ROOM.violet : ROOM.orange, 0.8 * game);
      }
    }
    // The speaker's lights beat while the band plays or during a party.
    if (party || playing(s, 'bateria') || playing(s, 'canta') || dancing(s)) {
      const pulse = beat % 2;
      p.rect(78, 345 + pulse, 2, 2, ROOM.pink, game);
      p.rect(100, 350 - pulse, 2, 2, '#0ff1ce', game);
    }
    // The dance floor's glow over the dancers, faint.
    if (party || dancing(s)) {
      const [dx, dy, dw, dh] = DANCE_FLOOR;
      p.rect(dx - 4, dy - 6, dw + 8, dh + 6, DISCO[beat % 4]!, 0.08 * game);
    }
  }
  // The working light over those who work at their seat.
  for (let i = 0; i < s.actors.length; i++) {
    const a = s.actors[i]!;
    const working = a.id === LIBRARIAN_ID ? a.busy : s.statuses[a.id] === 'trabajando';
    if (!working || a.away || a.path || s.paused || s.frozen) continue;
    const on = s.still || Math.floor(s.clock / m.lightMs + i) % 3 !== 0;
    const x = Math.round(a.x + 6);
    const y = Math.round(a.y - 30);
    p.rect(x - 1, y - 1, 4, 4, C.tinta);
    p.rect(x, y, 2, 2, on ? C.ofc : C.hondo);
  }
  // Speech bubbles.
  for (const a of s.actors) {
    const b = a.bubble;
    if (!b || s.clock > b.until || a.alpha <= 0.2) continue;
    const frame = live ? Math.floor(s.clock / m.bubbleFrameMs) : 0;
    paintBubble(p, C, b.icon, Math.round(a.x), Math.round(a.y - 42), frame);
  }
}
