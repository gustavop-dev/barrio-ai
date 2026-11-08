// The push of MovNavegacion: a detail screen slides in from the right over the screen underneath,
// which moves left by 30 % and darkens 8 %; «‹», Android back and a drag from the left edge send it
// back with the same FIRM spring.
//
// The (app) stack shows detail screens as transparent modals without a native animation, so the
// screen underneath stays drawn and the push runs here, on the UI thread. Each screen of that stack
// has a level (its index): the detail at level L drives `pushProgress(L)` (0 off screen, 1 in place)
// and the screen at level L − 1 reads it to move and darken.
import { makeMutable, type SharedValue } from 'react-native-reanimated';
import { navGestures, navValues } from '@/theme/motion';

/** Levels with their own progress; deeper pushes share the last one (the app never stacks that many). */
const LEVELS = 8;
const MS_PER_S = 1000;

const progress: SharedValue<number>[] = Array.from({ length: LEVELS }, () => makeMutable(0));
const layers = new Map<number, unknown>();

const clampLevel = (level: number) => Math.max(0, Math.min(LEVELS - 1, level));

/** Push progress of the screen at `level` of the (app) stack: 0 off screen to the right, 1 in place. */
export function pushProgress(level: number): SharedValue<number> {
  return progress[clampLevel(level)]!;
}

/** Index of a route in its stack (0 when the state is not known yet). */
export function stackLevel(state: { routes: readonly { key: string }[] } | undefined, key: string): number {
  const index = state?.routes.findIndex((route) => route.key === key) ?? -1;
  return index < 0 ? 0 : index;
}

interface StackNode {
  routes?: readonly { key?: string; state?: StackNode }[];
}

/**
 * The state of the navigator that holds the route `key`, searched from the root navigation state
 * (useRootNavigationState). Screens take their level from it: during render, `navigation.getState()`
 * still returns the previous render's state, where a screen pushed just now is not there yet.
 */
export function stackOf(root: unknown, key: string): { routes: readonly { key: string }[] } | undefined {
  const node = root as StackNode | null | undefined;
  const routes = node?.routes ?? [];
  if (routes.some((route) => route.key === key)) return node as { routes: readonly { key: string }[] };
  for (const route of routes) {
    const found = stackOf(route.state, key);
    if (found) return found;
  }
  return undefined;
}

/** The root view of the screen at `level`, so a flight can measure a row against its resting place. */
export function registerLayer(level: number, node: unknown): () => void {
  layers.set(level, node);
  return () => {
    if (layers.get(level) === node) layers.delete(level);
  };
}

export function layerAt(level: number): unknown {
  return layers.get(level) ?? null;
}

function clamp(value: number, min: number, max: number): number {
  'worklet';
  return Math.min(max, Math.max(min, value));
}

/** The edge drag: the detail follows the finger, from where it was grabbed (MovNavegacion `edgeMove`). */
export function dragProgress(from: number, translationX: number, width: number): number {
  'worklet';
  return clamp(from - translationX / Math.max(1, width), 0, 1);
}

/**
 * Where a released edge drag settles (MovNavegacion `edgeUp`): the progress is projected with the
 * finger's speed; below `stayOpen` the detail goes back (0), otherwise it stays (1).
 */
export function edgeRelease(current: number, velocityX: number): 0 | 1 {
  'worklet';
  const projected = current - (velocityX / MS_PER_S) * navGestures.velocityProjection;
  return projected < navGestures.stayOpen ? 0 : 1;
}

/** Whether the strip may grab the detail (it is at least half in). */
export function canGrab(current: number): boolean {
  'worklet';
  return current >= navGestures.grabFrom;
}

/**
 * The pushed screen at `p` (its own progress) while `covered` (the progress of a screen pushed over
 * it): it slides in from beyond the right edge and, when covered, moves left. With reduced motion it
 * only fades, as in the board's «menos movimiento».
 */
export function panelFrame(p: number, covered: number, width: number, offscreen: number, reduced: boolean): { translateX: number; opacity: number } {
  'worklet';
  if (reduced) return { translateX: 0, opacity: p };
  return { translateX: (1 - p) * offscreen - navValues.pushParallax * width * covered, opacity: 1 };
}

/** The screen underneath a push at `covered`: it moves left (not with reduced motion) and darkens. */
export function baseFrame(covered: number, width: number, reduced: boolean): { translateX: number; dim: number } {
  'worklet';
  return { translateX: reduced ? 0 : -navValues.pushParallax * width * covered, dim: navValues.pushDim * covered };
}
