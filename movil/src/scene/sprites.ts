import { ATLAS } from '@compartido/scene/atlas';
import { actorFrame, frontProp } from '@compartido/scene/art';
import type { SceneState } from '@compartido/scene/runtime';
import { CHARACTERS, LIBRARIAN_ID } from '@compartido/scene/roles';

interface SpriteSlot { x: number; y: number; sx: number; sy: number; w: number; h: number; alpha: number }
export interface SpriteBuffer { order: number[]; slots: SpriteSlot[] }
export const SPRITE_SLOTS = CHARACTERS.length * 3;
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
function put(slot: SpriteSlot, name: string, x: number, y: number) {
  'worklet';
  const r = ATLAS[name]!;
  slot.sx = r[0]; slot.sy = r[1]; slot.w = r[2]; slot.h = r[3]; slot.x = x; slot.y = y; slot.alpha = 1;
}
/**
 * In-place depth ordering and sprite selection; no arrays or objects created per frame. Each character has three
 * slots: its chair behind it while it is away, itself, and what goes in front of it (its chair while seated, the
 * librarian's counter, the pouf or the drum kit of its pastime).
 */
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
    actorFrame(s, a, slot);
    slot.w = 16; slot.h = 32;
    const front = b.slots[n + i * 2 + 1]!;
    chair(front, s, a.index, false);
    if (a.id === LIBRARIAN_ID) put(front, 'book', 28, 70);
    const prop = frontProp(a);
    if (prop) put(front, prop.sprite, prop.at[0], prop.at[1]);
  }
}
