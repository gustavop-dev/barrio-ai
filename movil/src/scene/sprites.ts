import { ATLAS } from '@compartido/scene/atlas';
import { sceneHop, sceneStatus, type SceneState } from '@compartido/scene/runtime';
import { CHARACTERS, LIBRARIAN_ID } from '@compartido/scene/roles';

interface SpriteSlot { x: number; y: number; sx: number; sy: number; w: number; h: number; alpha: number }
export interface SpriteBuffer { order: number[]; slots: SpriteSlot[] }
export const SPRITE_SLOTS = CHARACTERS.length * 3;
const SPRITE_ROWS = CHARACTERS.map((a) => ({
  run: ATLAS[`p${a.sprite}-run`]!, idle: ATLAS[`p${a.sprite}-idle_anim`]!, reading: ATLAS[`p${a.sprite}-reading`],
}));
export function createSpriteBuffer(): SpriteBuffer {
  return { order: CHARACTERS.map((_, i) => i), slots: Array.from({ length: SPRITE_SLOTS }, () => ({ x: 0, y: 0, sx: 0, sy: 0, w: 1, h: 1, alpha: 0 })) };
}
function chair(slot: SpriteSlot, s: SceneState, index: number, away: boolean) {
  'worklet';
  const a = s.actors[index]!;
  const r = a.role.chair === 'north' ? ATLAS.chairNorth : a.role.chair === 'gold' ? ATLAS.chairNorthGold : null;
  slot.alpha = r && a.away === away ? 1 : 0;
  if (r) { slot.sx = r[0]; slot.sy = r[1]; slot.w = r[2]; slot.h = r[3]; slot.x = a.role.home[0] - 11; slot.y = a.role.home[1] - 6; }
}
/** In-place depth ordering and sprite selection; no arrays or objects created per frame. */
export function updateSprites(s: SceneState, b: SpriteBuffer) {
  'worklet';
  const n = s.actors.length;
  for (let i = 1; i < n; i++) {
    const index = b.order[i]!; let j = i - 1;
    while (j >= 0 && s.actors[b.order[j]!]!.y > s.actors[index]!.y) { b.order[j + 1] = b.order[j]!; j--; }
    b.order[j + 1] = index;
  }
  for (let i = 0; i < n; i++) {
    chair(b.slots[i]!, s, i, true);
    const a = s.actors[b.order[i]!]!;
    const slot = b.slots[n + i * 2]!;
    const status = sceneStatus(s, a.id);
    const moving = a.path !== null;
    const reads = a.reading || (status === 'trabajando' && !a.away && !a.role.monitor && !a.role.service);
    const rows = SPRITE_ROWS[a.index]!;
    const reading = !moving && reads && Boolean(rows.reading);
    const r = moving ? rows.run : reading ? rows.reading! : rows.idle;
    const animate = !s.still && !s.paused && !s.frozen && (moving || status === 'trabajando' || status === 'en_espera' || a.reading);
    const frame = animate ? Math.floor(s.clock / (moving ? s.motion.runFrameMs : s.motion.idleFrameMs) + a.index) % 6 : 0;
    let dir = reading ? 2 : a.dir;
    if ((dir * 6 + frame) * 16 + 16 > r[2]) dir = 0;
    slot.sx = r[0] + (dir * 6 + frame) * 16; slot.sy = r[1]; slot.w = 16; slot.h = 32;
    slot.x = Math.round(a.x - 8); slot.y = Math.round(a.y - 29) - sceneHop(s, a.id); slot.alpha = a.alpha * (status === 'diseno' ? 0.45 : 1);
    const front = b.slots[n + i * 2 + 1]!;
    chair(front, s, a.index, false);
    if (a.id === LIBRARIAN_ID) {
      const book = ATLAS.book!;
      front.sx = book[0]; front.sy = book[1]; front.w = book[2]; front.h = book[3]; front.x = 28; front.y = 70; front.alpha = 1;
    }
  }
}
