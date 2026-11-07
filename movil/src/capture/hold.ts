// The press-and-hold rules of the capture button, apart from the gesture so they can be tested:
// slide up past lockDistance to lock, left past discardDistance to discard (motion.ts gestures.capture).
import { gestures } from '@/theme/motion';

export type HoldDecision = 'none' | 'lock' | 'discard';

/** What a finger at (dx, dy) from the press point means while recording. Up wins over left. */
export function holdDecision(dx: number, dy: number): HoldDecision {
  'worklet';
  if (dy < -gestures.capture.lockDistance) return 'lock';
  if (dx < -gestures.capture.discardDistance) return 'discard';
  return 'none';
}

/** How far the button and the lock follow the finger up (0 to -maxLift). */
export function holdLift(dy: number): number {
  'worklet';
  return Math.max(Math.min(0, dy), -gestures.capture.maxLift);
}

/** A hold released sooner than minHoldMs (from the press) records nothing: it counts as a tap. */
export function isTooShort(pressedAt: number, releasedAt: number): boolean {
  return releasedAt - pressedAt < gestures.capture.minHoldMs;
}
