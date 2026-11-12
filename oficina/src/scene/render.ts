// Draws the vertical office plan with the LimeZu atlas. The room, its lights and the bubbles are the shared art
// (compartido/src/scene/art.ts, also drawn by the native app); this file supplies the 2D canvas pen and adds the
// people, the selection and the capture envelope. The paused darkening is a DOM layer over the canvas.

import {
  DEFAULT_PALETTE as SCENE_PALETTE, ROOM, actorFrame, frontProp, paintFloor, paintLights, paintRoom,
  type RoomPen, type ScenePalette, type SpriteFrame,
} from '../../../compartido/src/scene/art';
import { sceneBracketLength, selectScene } from '../../../compartido/src/scene/runtime';
import { ATLAS, type AtlasImage } from './atlas';
import type { Actor, OfficeEngine } from './engine';
import { PLAN_HEIGHT, PLAN_WIDTH } from './plan';
import { LIBRARIAN_ID, LIBRARY, TEAMS, type CharacterId, type ZoneId } from './roles';

/** Brand colours used on the canvas; read from the tokens (see `readPalette`). */
export type Palette = ScenePalette;

export const DEFAULT_PALETTE: Palette = SCENE_PALETTE;

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

/** The 2D canvas as the shared art's pen. */
function canvasPen(ctx: CanvasRenderingContext2D, image: AtlasImage): RoomPen {
  const rect = (x: number, y: number, w: number, h: number, color: string, alpha = 1) => {
    if (alpha <= 0) return;
    ctx.globalAlpha = alpha;
    ctx.fillStyle = color;
    ctx.fillRect(x, y, w, h);
    ctx.globalAlpha = 1;
  };
  const sprite = (name: string, x: number, y: number) => {
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
      for (let yy = y; yy < y + h; yy += r[3]) for (let xx = x; xx < x + w; xx += r[2]) sprite(name, xx, yy);
    });
  };
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
  return { rect, sprite, tile, rug };
}

export function drawScene(ctx: CanvasRenderingContext2D, atlas: AtlasImage | null, engine: OfficeEngine, options: DrawOptions): void {
  selectScene(engine.state, options.selectedRole, options.selectedZone);
  const s = engine.state;
  const C = options.palette ?? DEFAULT_PALETTE;

  ctx.setTransform(options.scale, 0, 0, options.scale, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.globalAlpha = 1;
  ctx.fillStyle = ROOM.outside;
  ctx.fillRect(0, 0, PLAN_WIDTH, PLAN_HEIGHT);
  if (!atlas) return;
  const image = atlas;
  const pen = canvasPen(ctx, image);
  const R = pen.rect;

  paintRoom(pen);
  paintFloor(pen, s);

  // ---------------------------------------------------------------- people
  const chairFor = (a: Actor) => {
    const [x, y] = a.role.home;
    if (a.role.chair === 'north') pen.sprite('chairNorth', x - 11, y - 6);
    if (a.role.chair === 'gold') pen.sprite('chairNorthGold', x - 11, y - 6);
  };
  const frontChair = (a: Actor) => a.role.chair === 'north' || a.role.chair === 'gold';
  const frame: SpriteFrame = { sx: 0, sy: 0, x: 0, y: 0, alpha: 1 };
  const person = (a: Actor) => {
    actorFrame(s, a, frame);
    ctx.save();
    ctx.globalAlpha = frame.alpha;
    ctx.drawImage(image, frame.sx, frame.sy, 16, 32, frame.x, frame.y, 16, 32);
    ctx.restore();
  };

  const sorted = [...engine.actors].sort((a, b) => a.y - b.y);
  for (const a of sorted) if (a.away && frontChair(a)) chairFor(a);
  for (const a of sorted) {
    person(a);
    if (!a.away && frontChair(a)) chairFor(a);
    const prop = frontProp(a);
    if (prop) pen.sprite(prop.sprite, prop.at[0], prop.at[1]);
    // The librarian stands behind the counter.
    if (a.id === LIBRARIAN_ID) pen.sprite('book', 28, 70);
  }

  // ---------------------------------------------------------------- lights, bubbles, selection
  paintLights(pen, s, C);

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
    const L = sceneBracketLength(s);
    for (const [cx, cy, dx, dy] of [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]] as const) {
      R(Math.min(cx, cx + dx * L), dy > 0 ? cy : cy - 2, L, 3, C.tinta);
      R(dx > 0 ? cx : cx - 2, Math.min(cy, cy + dy * L), 3, L, C.tinta);
      R(Math.min(cx, cx + dx * L) + (dx > 0 ? 1 : 0), dy > 0 ? cy + 1 : cy - 1, L - 1, 1, C.postit);
      R(dx > 0 ? cx + 1 : cx - 1, Math.min(cy, cy + dy * L) + (dy > 0 ? 1 : 0), 1, L - 1, C.postit);
    }
  };

  const mail = s.mail;
  if (mail && !s.still) {
    const x = Math.round(mail.x - 5), y = Math.round(mail.y - 4);
    R(x, y, 11, 8, C.tinta); R(x + 1, y + 1, 9, 6, ROOM.white);
    R(x + 1, y + 1, 1, 1, C.tinta); R(x + 2, y + 2, 1, 1, C.tinta);
    R(x + 3, y + 3, 1, 1, C.tinta); R(x + 4, y + 4, 3, 1, C.tinta);
    R(x + 7, y + 3, 1, 1, C.tinta); R(x + 8, y + 2, 1, 1, C.tinta);
    R(x + 9, y + 1, 1, 1, C.tinta); R(x + 4, y + 5, 3, 1, C.ofc);
  }
  const zone = options.selectedZone;
  if (zone) {
    const box = zone === 'biblioteca' ? LIBRARY.box : TEAMS.find((t) => t.id === zone)?.box;
    if (box) brackets(box);
  }
  if (options.selectedRole) pointer(engine.byId[options.selectedRole]);
}
