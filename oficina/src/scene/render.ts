// Draws the vertical office plan with the LimeZu atlas, ported from the design (Oficina.dc.html).
// Always daylight. The paused darkening is a DOM layer over the canvas, not part of the drawing.

import { lookFor } from './activity';
import { ATLAS, type AtlasImage } from './atlas';
import type { Actor, BubbleIcon, OfficeEngine } from './engine';
import { PLAN_HEIGHT, PLAN_WIDTH } from './plan';
import { LIBRARIAN_ID, LIBRARY, SPRITES_WITHOUT_READING, TEAMS, type CharacterId, type ZoneId } from './roles';

/** Brand colours used on the canvas; read from the tokens (see `readPalette`). */
export interface Palette {
  tinta: string;
  tintaSuave: string;
  papel: string;
  ofc: string;
  hondo: string;
  claro: string;
  postit: string;
}

export const DEFAULT_PALETTE: Palette = {
  tinta: '#1e1e2b',
  tintaSuave: '#565972',
  papel: '#f7f6f0',
  ofc: '#0ff1ce',
  hondo: '#00715e',
  claro: '#d2fbf3',
  postit: '#f8d47d',
};

/** The palette from the CSS tokens, falling back to the manual's values. */
export function readPalette(element: Element | null = typeof document !== 'undefined' ? document.documentElement : null): Palette {
  if (!element || typeof getComputedStyle !== 'function') return DEFAULT_PALETTE;
  const style = getComputedStyle(element);
  const token = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback;
  return {
    tinta: token('--color-tinta', DEFAULT_PALETTE.tinta),
    tintaSuave: token('--color-tinta-suave', DEFAULT_PALETTE.tintaSuave),
    papel: token('--color-papel', DEFAULT_PALETTE.papel),
    ofc: token('--color-0ff1ce', DEFAULT_PALETTE.ofc),
    hondo: token('--color-0ff1ce-hondo', DEFAULT_PALETTE.hondo),
    claro: token('--color-0ff1ce-claro', DEFAULT_PALETTE.claro),
    postit: token('--color-post-it', DEFAULT_PALETTE.postit),
  };
}

export interface DrawOptions {
  /** Device pixels per logical pixel (integer). */
  scale: number;
  selectedRole: CharacterId | null;
  selectedZone: ZoneId | null;
  palette?: Palette;
}

// Pixel-art colours of the room itself (walls, floor edges, the monitor off, bubble icons).
const ROOM = {
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
};

export function drawScene(ctx: CanvasRenderingContext2D, atlas: AtlasImage | null, engine: OfficeEngine, options: DrawOptions): void {
  const C = options.palette ?? DEFAULT_PALETTE;
  const clock = engine.clock;
  const still = engine.isStill;
  const paused = engine.isPaused;

  ctx.setTransform(options.scale, 0, 0, options.scale, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.globalAlpha = 1;

  const R = (x: number, y: number, w: number, h: number, color: string) => {
    ctx.fillStyle = color;
    ctx.fillRect(x, y, w, h);
  };

  R(0, 0, PLAN_WIDTH, PLAN_HEIGHT, ROOM.outside);
  if (!atlas) return;
  const image = atlas;

  const S = (name: string, x: number, y: number) => {
    const r = ATLAS[name];
    if (r) ctx.drawImage(image, r[0], r[1], r[2], r[3], Math.round(x), Math.round(y), r[2], r[3]);
  };
  const clip = (x: number, y: number, w: number, h: number, paint: () => void) => {
    ctx.save();
    ctx.beginPath();
    ctx.rect(x, y, w, h);
    ctx.clip();
    paint();
    ctx.restore();
  };
  const tile = (name: string, x: number, y: number, w: number, h: number) => {
    const r = ATLAS[name];
    if (!r) return;
    clip(x, y, w, h, () => {
      for (let yy = y; yy < y + h; yy += r[3]) for (let xx = x; xx < x + w; xx += r[2]) S(name, xx, yy);
    });
  };
  // Rug in nine parts: fixed corners, repeated edges and centre, never scaled.
  const rug = (name: string, x: number, y: number, w: number, h: number, k: number) => {
    const r = ATLAS[name];
    if (!r) return;
    const [sx, sy, rw, rh] = r;
    const part = (px: number, py: number, pw: number, ph: number, dx: number, dy: number, dw: number, dh: number) =>
      clip(dx, dy, dw, dh, () => {
        for (let yy = dy; yy < dy + dh; yy += ph) for (let xx = dx; xx < dx + dw; xx += pw) ctx.drawImage(image, sx + px, sy + py, pw, ph, xx, yy, pw, ph);
      });
    const mw = rw - 2 * k;
    const mh = rh - 2 * k;
    part(0, 0, k, k, x, y, k, k);
    part(rw - k, 0, k, k, x + w - k, y, k, k);
    part(0, rh - k, k, k, x, y + h - k, k, k);
    part(rw - k, rh - k, k, k, x + w - k, y + h - k, k, k);
    part(k, 0, 1, k, x + k, y, w - 2 * k, k);
    part(k, rh - k, 1, k, x + k, y + h - k, w - 2 * k, k);
    part(0, k, k, 1, x, y + k, k, h - 2 * k);
    part(rw - k, k, k, 1, x + w - k, y + k, k, h - 2 * k);
    part(k + Math.floor(mw / 2), k + Math.floor(mh / 2), 1, 1, x + k, y + k, w - 2 * k, h - 2 * k);
  };
  // Monitors light up in 0ff1ce only while their owner is really working at the desk.
  const monitor = (x: number, y: number, lit: boolean) => {
    S('monitorFront', x, y);
    if (!lit) {
      R(x + 2, y + 2, 25, 12, ROOM.screenOff);
      R(x + 3, y + 3, 23, 1, ROOM.screenOffLine);
      return;
    }
    R(x + 2, y + 2, 25, 12, C.claro);
    R(x + 2, y + 2, 25, 2, C.ofc);
    R(x + 4, y + 6, 13, 1, C.hondo);
    R(x + 4, y + 9, 17, 1, ROOM.screenLine);
    R(x + 4, y + 12, 9, 1, ROOM.screenLine);
  };

  // ---------------------------------------------------------------- room
  const W = PLAN_WIDTH;
  const H = PLAN_HEIGHT;
  tile('floor', 4, 30, 184, 302);
  tile('tile', 112, 30, 76, 76);
  R(110, 30, 2, 76, ROOM.kitchenEdge);
  R(0, 0, W, 22, ROOM.plaster);
  R(0, 0, W, 2, ROOM.plasterLight);
  R(0, 22, W, 6, ROOM.wainscot);
  R(0, 28, W, 2, ROOM.skirting);
  R(0, 0, 4, H, ROOM.wall);
  R(3, 2, 1, H - 4, ROOM.wallLight);
  R(188, 0, 4, H, ROOM.wall);
  R(188, 2, 1, H - 4, ROOM.wallLight);
  R(0, H - 4, W, 4, ROOM.base);
  rug('rugBlue', 6, 114, 72, 60, 8);
  rug('rugGreen', 114, 114, 72, 60, 6);
  rug('rugRust', 6, 184, 72, 68, 8);
  rug('rugGreen', 114, 184, 72, 64, 6);
  rug('rugBlue', 30, 260, 132, 72, 8);
  S('door', 88, 2);
  S('windowSmall', 52, 4);
  S('board', 160, 6);
  S('wallCabinet', 116, 8);
  S('wallCabinet', 134, 8);

  // ---------------------------------------------------------------- furniture behind the people
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
  for (const a of engine.actors) {
    if (a.role.monitor) monitor(a.role.monitor[0], a.role.monitor[1], !paused && engine.statusOf(a.id) === 'trabajando' && !a.away);
  }

  // ---------------------------------------------------------------- people
  const chairFor = (a: Actor) => {
    const [x, y] = a.role.home;
    if (a.role.chair === 'north') S('chairNorth', x - 11, y - 6);
    if (a.role.chair === 'gold') S('chairNorthGold', x - 11, y - 6);
  };
  const frontChair = (a: Actor) => a.role.chair === 'north' || a.role.chair === 'gold';

  const person = (a: Actor) => {
    const status = engine.statusOf(a.id);
    const look = lookFor(status);
    const moving = a.path !== null;
    const sprite = a.role.sprite;
    const canRead = !SPRITES_WITHOUT_READING.has(sprite) && Boolean(ATLAS[`p${sprite}-reading`]);
    // Working at a table without a monitor (writers, readers, Relaciones) reads; desk workers face the screen.
    const readsAtSeat = status === 'trabajando' && !a.away && !a.role.monitor && !a.role.service;
    const anim = moving ? 'run' : canRead && (a.reading || readsAtSeat) ? 'reading' : 'idle_anim';
    const r = ATLAS[`p${sprite}-${anim}`] ?? ATLAS[`p${sprite}-idle_anim`];
    if (!r) return;
    const animate = !still && (moving || look.animated || a.reading);
    const frame = animate ? Math.floor(clock / (moving ? 110 : 220) + a.index) % 6 : 0;
    let dir: number = anim === 'reading' ? 2 : a.dir;
    if ((dir * 6 + frame) * 16 + 16 > r[2]) dir = 0;
    ctx.save();
    ctx.globalAlpha = a.alpha * (look.dimmed ? 0.45 : 1);
    ctx.drawImage(image, r[0] + (dir * 6 + frame) * 16, r[1], 16, 32, Math.round(a.x - 8), Math.round(a.y - 29), 16, 32);
    ctx.restore();
  };

  const sorted = [...engine.actors].sort((a, b) => a.y - b.y);
  for (const a of sorted) if (a.away && frontChair(a)) chairFor(a);
  for (const a of sorted) {
    person(a);
    if (!a.away && frontChair(a)) chairFor(a);
    // The librarian stands behind the counter.
    if (a.id === LIBRARIAN_ID) S('book', 28, 70);
  }

  // ---------------------------------------------------------------- lights, bubbles, selection
  const light = (a: Actor) => {
    if (engine.statusOf(a.id) !== 'trabajando' || a.away || paused) return;
    const on = still || Math.floor(clock / 700 + a.index) % 3 !== 0;
    const x = Math.round(a.x + 6);
    const y = Math.round(a.y - 30);
    R(x - 1, y - 1, 4, 4, C.tinta);
    R(x, y, 2, 2, on ? C.ofc : C.hondo);
  };

  const icon = (kind: BubbleIcon, x: number, y: number) => {
    const t = C.tinta;
    if (kind === 'libro') {
      R(x, y + 1, 7, 5, ROOM.book);
      R(x + 1, y + 2, 5, 3, C.papel);
      R(x + 3, y + 1, 1, 5, ROOM.bookSpine);
    } else if (kind === 'hoja') {
      R(x + 1, y, 5, 6, ROOM.white);
      R(x + 2, y + 2, 3, 1, C.tintaSuave);
      R(x + 2, y + 4, 3, 1, C.tintaSuave);
    } else if (kind === 'cafe') {
      R(x + 1, y + 2, 4, 4, ROOM.white);
      R(x + 5, y + 3, 1, 2, ROOM.white);
      R(x + 2, y + 3, 2, 1, ROOM.coffee);
      R(x + 2, y, 1, 1, ROOM.steam);
      R(x + 3, y + 1, 1, 1, ROOM.steam);
    } else if (kind === 'listo') {
      for (const [dx, dy] of [[5, 1], [4, 2], [3, 3], [2, 4], [1, 3], [0, 2], [2, 5]] as const) R(x + dx, y + dy, 1, 1, C.hondo);
    } else if (kind === 'pregunta') {
      R(x + 2, y, 3, 1, t);
      R(x + 5, y + 1, 1, 1, t);
      R(x + 4, y + 2, 1, 1, t);
      R(x + 3, y + 3, 1, 1, t);
      R(x + 3, y + 5, 1, 1, t);
    } else if (kind === 'busca') {
      R(x + 1, y, 3, 1, t);
      R(x, y + 1, 1, 2, t);
      R(x + 4, y + 1, 1, 2, t);
      R(x + 1, y + 3, 3, 1, t);
      R(x + 4, y + 4, 1, 1, t);
      R(x + 5, y + 5, 1, 1, t);
    } else {
      const f = Math.floor(clock / 300) % 3;
      for (let d = 0; d < 3; d++) R(x + d * 3, y + 3 - (f === d && !still ? 1 : 0), 1, 1, C.tintaSuave);
    }
  };
  const bubble = (a: Actor) => {
    const b = a.bubble;
    if (!b || clock > b.until) return;
    const x = Math.round(a.x);
    const y = Math.round(a.y - 42);
    R(x - 7, y, 13, 10, C.tinta);
    R(x - 6, y + 1, 11, 8, ROOM.white);
    R(x - 1, y + 10, 3, 2, C.tinta);
    R(x, y + 9, 1, 2, ROOM.white);
    icon(b.icon, x - 3, y + 2);
  };
  const pointer = (a: Actor) => {
    const x = Math.round(a.x);
    const y = Math.round(a.y - 46 - (a.bubble ? 12 : 0));
    R(x - 4, y, 9, 1, C.tinta);
    R(x - 3, y + 1, 7, 1, C.tinta);
    R(x - 2, y + 2, 5, 1, C.tinta);
    R(x - 1, y + 3, 3, 1, C.tinta);
    R(x, y + 4, 1, 1, C.tinta);
    R(x - 3, y, 7, 1, C.postit);
    R(x - 2, y + 1, 5, 1, C.postit);
    R(x - 1, y + 2, 3, 1, C.postit);
    R(x, y + 3, 1, 1, C.postit);
  };
  const brackets = (box: readonly number[]) => {
    const x = box[0]! + 1;
    const y = box[1]! + 1;
    const w = box[2]! - 2;
    const h = box[3]! - 2;
    const L = 7;
    for (const [cx, cy, dx, dy] of [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]] as const) {
      R(Math.min(cx, cx + dx * L), dy > 0 ? cy : cy - 2, L, 3, C.tinta);
      R(dx > 0 ? cx : cx - 2, Math.min(cy, cy + dy * L), 3, L, C.tinta);
      R(Math.min(cx, cx + dx * L) + (dx > 0 ? 1 : 0), dy > 0 ? cy + 1 : cy - 1, L - 1, 1, C.postit);
      R(dx > 0 ? cx + 1 : cx - 1, Math.min(cy, cy + dy * L) + (dy > 0 ? 1 : 0), 1, L - 1, C.postit);
    }
  };

  for (const a of engine.actors) light(a);
  for (const a of engine.actors) bubble(a);
  const zone = options.selectedZone;
  if (zone) {
    const box = zone === 'biblioteca' ? LIBRARY.box : TEAMS.find((t) => t.id === zone)?.box;
    if (box) brackets(box);
  }
  if (options.selectedRole) pointer(engine.byId[options.selectedRole]);
}
