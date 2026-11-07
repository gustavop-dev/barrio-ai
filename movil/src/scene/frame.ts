import { stepScene, type SceneState } from '@compartido/scene/runtime';
import { officeFrames } from '@/theme/motion';

export interface FrameClock { remainder: number }
/** Bound catch-up after a stall; never advance hidden/background time. */
export function advanceFrame(scene: SceneState, clock: FrameClock, delta: number | null, active: boolean) {
  'worklet';
  if (!active || scene.paused || scene.frozen || scene.still || delta === null) { clock.remainder = 0; return; }
  clock.remainder += Math.max(0, Math.min(delta, officeFrames.maxDeltaMs));
  while (clock.remainder >= officeFrames.stepMs) {
    stepScene(scene, officeFrames.stepMs);
    clock.remainder -= officeFrames.stepMs;
  }
}
