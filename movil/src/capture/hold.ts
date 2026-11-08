// The press-and-hold rules of the capture button, apart from the gesture so they can be tested
// (MovCaptura): the finger slides up lockDistance to lock, left discardDistance to discard
// (motion.ts gestures.capture); the button follows 60 % of it (captureMotion.follow).
import { captureMotion, gestures } from '@/theme/motion';

export type HoldDecision = 'none' | 'lock' | 'discard';

/** What a finger at (dx, dy) from the press point means while recording. Up wins over left. */
export function holdDecision(dx: number, dy: number): HoldDecision {
  'worklet';
  if (-dy >= gestures.capture.lockDistance) return 'lock';
  if (-dx >= gestures.capture.discardDistance) return 'discard';
  return 'none';
}

/** How far the button follows the finger, only up or left (`min(0, d) · 0.6`). */
export function holdFollow(distance: number): number {
  'worklet';
  return Math.min(0, distance) * captureMotion.follow;
}

/** How far along the way to the lock (`dragP`) the button is, from its followed lift (0–1). */
export function lockProgress(lift: number): number {
  'worklet';
  return Math.min(1, Math.max(0, -lift / (gestures.capture.lockDistance * captureMotion.follow)));
}

/** How far along the way to the discard (`cancelP`) the button is, from its followed shift (0–1). */
export function discardProgress(shift: number): number {
  'worklet';
  return Math.min(1, Math.max(0, -shift / (gestures.capture.discardDistance * captureMotion.follow)));
}

/** A hold released sooner than minHoldMs (from the press) records nothing: it counts as a tap. */
export function isTooShort(pressedAt: number, releasedAt: number): boolean {
  return releasedAt - pressedAt < gestures.capture.minHoldMs;
}
