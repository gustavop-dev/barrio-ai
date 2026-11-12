import { createScene, ingestScene, selectScene, setSceneStill } from '@compartido/scene/runtime';
import { officeFrames } from '@/theme/motion';
import { advanceFrame } from './frame';
import { createSpriteBuffer, updateSprites } from './sprites';
import { clampPan, zoomAt } from './viewport';
import { routeForUrl } from '@/push/routes';

it('advances identical fixed steps at different display rates and bounds a long stall', () => {
  const a = createScene(), b = createScene(), ca = { remainder: 0 }, cb = { remainder: 0 };
  for (let i = 0; i < 120; i++) advanceFrame(a, ca, 8, true);
  for (let i = 0; i < 60; i++) advanceFrame(b, cb, 16, true);
  expect(a.clock).toBe(b.clock);
  const before = a.clock; advanceFrame(a, ca, 20000, true);
  expect(a.clock - before).toBe(Math.floor(officeFrames.maxDeltaMs / officeFrames.stepMs) * officeFrames.stepMs);
  expect(ca.remainder).toBe(officeFrames.maxDeltaMs % officeFrames.stepMs);
});
it('freezes a walker for blur, background, machine pause and unavailable activity without catching up', () => {
  const s = createScene(), c = { remainder: 0 };
  ingestScene(s, [{ id: 1, ts: '2026-11-07T15:00:00Z', tipo: 'publicacion', rol: 'operador_cuenta', destino: '', detalle: '' }]);
  advanceFrame(s, c, 16, true);
  const clock = s.clock, actors = JSON.stringify(s.actors);
  advanceFrame(s, c, 20000, false);
  s.paused = true; advanceFrame(s, c, 32, true);
  s.paused = false; s.frozen = true; advanceFrame(s, c, 32, true);
  expect(s.clock).toBe(clock); expect(JSON.stringify(s.actors)).toBe(actors);
  s.frozen = false; advanceFrame(s, c, null, true); advanceFrame(s, c, 16, true);
  expect(s.clock).toBe(clock + 16);
});
it('reduced motion returns everyone home and only narrates the next events', () => {
  const s = createScene(), c = { remainder: 0 };
  const event = { id: 1, ts: '2026-11-07T15:00:00Z', tipo: 'publicacion', rol: 'operador_cuenta', destino: '', detalle: '' };
  ingestScene(s, [event]); advanceFrame(s, c, 16, true); setSceneStill(s, true);
  ingestScene(s, [{ ...event, id: 2 }]); const clock = s.clock; advanceFrame(s, c, 32, true);
  expect(s.clock).toBe(clock); expect(s.now?.key).toBe(2);
  expect(s.actors.every((a) => a.x === a.role.home[0] && a.y === a.role.home[1] && !a.path)).toBe(true);
});
it('reuses sprite buffers, sorts walkers by depth and fades design roles', () => {
  const s = createScene(); s.statuses.perfil = 'diseno';
  const b = createSpriteBuffer(), slots = [...b.slots], order = b.order;
  updateSprites(s, b); s.actors[1]!.y = 330; updateSprites(s, b);
  expect(b.order).toBe(order); expect(b.order[b.order.length - 1]).toBe(1);
  b.slots.forEach((slot, i) => expect(slot).toBe(slots[i]));
  expect(b.slots.some((slot) => slot.alpha === 0.45)).toBe(true);
});
it('clamps pan, keeps the pinch focal point stable and snaps to whole physical pixels', () => {
  const v = { x: 0, y: 0, scale: 2 };
  zoomAt(v, 3.1, 100, 200, 384, 500, 2, 2);
  expect(v.scale * 2 % 1).toBe(0);
  expect((100 - v.x) / v.scale).toBe(50);
  expect((200 - v.y) / v.scale).toBe(100);
  zoomAt(v, 200, 100, 200, 384, 500, 2, 2); expect(v.scale).toBe(6);
  expect(clampPan(-900, 384, 500)).toBe(-116); expect(clampPan(90, 384, 500)).toBe(0);
});
it('keeps the opening scale that fills the width, and never zooms out below it', () => {
  const base = 390 / 192, v = { x: 0, y: 0, scale: base };
  zoomAt(v, base * 1.01, 195, 300, 390, 700, base, 2);
  expect(v.scale).toBe(base);
  expect(v.x).toBe(0);
  zoomAt(v, base * 0.5, 195, 300, 390, 700, base, 2);
  expect(v.scale).toBe(base);
  zoomAt(v, base * 2, 195, 300, 390, 700, base, 2);
  expect(v.scale).toBe(4);
  expect(clampPan(-10, 390, 192 * base)).toBe(0);
});
it('opens the home path and legacy knowledge redirect in Oficina', () => {
  expect(routeForUrl('/')).toEqual({ pathname: '/', params: {} });
  expect(routeForUrl('/conocimiento')).toEqual({ pathname: '/', params: {} });
});

it('moves only the selected sprite in whole logical pixels, without shifting its hit target or furniture', () => {
  const s = createScene(), b = createSpriteBuffer();
  updateSprites(s, b);
  const before = b.slots.map((slot) => ({ ...slot }));
  selectScene(s, 'perfil', 'estrategia'); updateSprites(s, b);
  const changes = b.slots.filter((slot, i) => slot.y !== before[i]!.y);
  expect(changes).toHaveLength(1);
  expect(changes[0]!.y).toBe(166 - 29 - s.motion.hopPx);
  expect(s.actors.find((a) => a.id === 'perfil')!.y).toBe(166);
  s.clock = s.motion.hopStepMs; updateSprites(s, b);
  expect(changes[0]!.y).toBe(166 - 29 - s.motion.hopSettlePx);
  setSceneStill(s, true); updateSprites(s, b);
  expect(changes[0]!.y).toBe(166 - 29);
});
