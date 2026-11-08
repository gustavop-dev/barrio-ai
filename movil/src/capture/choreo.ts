// Worklet maths of the capture's choreographies (MovCaptura's `clamp`, `lerp`, `seg` and `qbez`), and
// the voice level that drives the recording ball.
import { useEffect } from 'react';
import { useFrameCallback, useSharedValue, type SharedValue } from 'react-native-reanimated';
import { captureMotion } from '@/theme/motion';

export function clamp01(value: number): number {
  'worklet';
  return Math.min(1, Math.max(0, value));
}

export function lerp(from: number, to: number, t: number): number {
  'worklet';
  return from + (to - from) * t;
}

/** How far `t` is through the segment `range` of a timeline (0–1). */
export function seg(t: number, range: readonly [number, number]): number {
  'worklet';
  return clamp01((t - range[0]) / (range[1] - range[0]));
}

/** A quadratic Bézier from `from` through `control` to `to`. */
export function qbez(from: number, control: number, to: number, t: number): number {
  'worklet';
  return (1 - t) * (1 - t) * from + 2 * (1 - t) * t * control + t * t * to;
}

/** The board's rates are per frame at 60 Hz; this turns them into rates for any frame length. */
const BOARD_FRAME_MS = 1000 / 60;

/**
 * The voice level (0–1) on the UI thread: it follows the microphone at `levelFollow` per board frame
 * while `live`, and falls back to silence at `levelRelease` otherwise. Off with reduced motion.
 */
export function useVoiceLevel(target: number, live: boolean, reduced: boolean): SharedValue<number> {
  const goal = useSharedValue(0);
  const on = useSharedValue(false);
  const level = useSharedValue(0);
  useEffect(() => {
    goal.set(live ? target : 0);
    on.set(live);
  }, [target, live, goal, on]);
  const frame = useFrameCallback((info) => {
    'worklet';
    const elapsed = info.timeSincePreviousFrame ?? BOARD_FRAME_MS;
    const rate = on.value ? captureMotion.levelFollow : captureMotion.levelRelease;
    const step = 1 - Math.pow(1 - rate, elapsed / BOARD_FRAME_MS);
    level.value += (goal.value - level.value) * step;
  }, false);
  useEffect(() => {
    frame.setActive(!reduced);
  }, [frame, reduced]);
  return level;
}
