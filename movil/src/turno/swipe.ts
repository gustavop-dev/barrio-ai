// The swipe rules of a Tu turno card, as worklets (they run on the UI thread while dragging) and
// plain functions for tests. Thresholds come from motion.ts gestures.swipe.
import { gestures } from '@/theme/motion';

export type SwipeSide = 'right' | 'left';

export interface SwipeSides {
  right: boolean;
  left: boolean;
}

/** Where the card is drawn for a finger at translationX: free up to the commit point, then resisting; a side without an action barely moves. */
export function dragOffset(translationX: number, width: number, sides: SwipeSides): number {
  'worklet';
  const { commitFraction, overdragResistance } = gestures.swipe;
  const allowed = translationX > 0 ? sides.right : sides.left;
  const distance = Math.abs(translationX);
  const sign = translationX < 0 ? -1 : 1;
  if (!allowed) return sign * Math.min(distance * overdragResistance * 0.3, 24);
  const commit = width * commitFraction;
  if (distance <= commit) return translationX;
  return sign * (commit + (distance - commit) * overdragResistance);
}

/** Past the commit point (for the threshold haptic and the reveal). */
export function pastCommit(translationX: number, width: number): boolean {
  'worklet';
  return Math.abs(translationX) >= width * gestures.swipe.commitFraction;
}

/** The side that commits when the finger lifts: past the commit point, or a fast flick that way. */
export function commitSide(translationX: number, velocityX: number, width: number, sides: SwipeSides): SwipeSide | null {
  'worklet';
  const { commitVelocity, activeOffsetX } = gestures.swipe;
  const far = pastCommit(translationX, width);
  if (translationX > 0 && sides.right && (far || (velocityX >= commitVelocity && translationX > activeOffsetX))) return 'right';
  if (translationX < 0 && sides.left && (far || (velocityX <= -commitVelocity && translationX < -activeOffsetX))) return 'left';
  return null;
}

/** 0 → 1 as the finger approaches the commit point: the action's icon grows with it. */
export function revealProgress(translationX: number, width: number): number {
  'worklet';
  const full = width * gestures.swipe.commitFraction * gestures.swipe.revealFraction;
  return Math.min(1, Math.abs(translationX) / Math.max(1, full));
}
