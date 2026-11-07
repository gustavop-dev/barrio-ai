// Motion tokens: every duration, spring, easing, gesture threshold and haptic of the app lives here.
// Screens never write a number for motion: they ask this module. Gustavo's motion spec (Claude
// Design) is applied by editing the values below; MOTION.md lists each token and where it is used.
//
// Reduced motion: every config carries `reduceMotion`, so Reanimated honours the OS setting
// («Quitar animaciones» on Android) by jumping straight to the end value. `REDUCE_MOTION` switches
// that for the whole app; `useMotion()` gives components the same decision for what Reanimated does
// not animate by itself (pulses, the hold overlay, the toast slide).
import * as Haptics from 'expo-haptics';
import { Easing, FadeIn, FadeInDown, FadeOut, LinearTransition, ReduceMotion, useReducedMotion, type WithSpringConfig, type WithTimingConfig } from 'react-native-reanimated';

// ---------------------------------------------------------------- reduced motion

export type ReduceMotionChoice = 'system' | 'always' | 'never';

/** 'system' follows the OS; 'always' removes every animation; 'never' animates even with the OS setting on. */
export const REDUCE_MOTION = 'system' as ReduceMotionChoice;

const REDUCE: Record<ReduceMotionChoice, ReduceMotion> = {
  system: ReduceMotion.System,
  always: ReduceMotion.Always,
  never: ReduceMotion.Never,
};

// ---------------------------------------------------------------- springs (damping, stiffness, mass)

export interface SpringToken {
  damping: number;
  stiffness: number;
  mass: number;
}

export const springs = {
  /** A swiped card that did not commit goes back to its place. */
  snapBack: { damping: 20, stiffness: 260, mass: 1 },
  /** The capture button grows to 72 px (and shrinks back) under the finger. */
  captureGrow: { damping: 15, stiffness: 320, mass: 0.7 },
  /** The capture button and lock follow the finger while sliding up. */
  captureFollow: { damping: 24, stiffness: 420, mass: 0.6 },
  /** Bottom sheets (capture, confirm) rising into place. */
  sheetOpen: { damping: 24, stiffness: 260, mass: 1 },
  /** Pressed buttons, tab pills and chips scaling back. */
  press: { damping: 18, stiffness: 420, mass: 0.6 },
  /** The toast rising from the bottom. */
  toast: { damping: 20, stiffness: 260, mass: 0.9 },
} as const satisfies Record<string, SpringToken>;

export type SpringName = keyof typeof springs;

// ---------------------------------------------------------------- durations and easings

export const easings = {
  /** Most UI moves: quick start, soft landing. */
  standard: Easing.bezier(0.2, 0, 0, 1),
  /** Things arriving (fade in, sheet backdrop). */
  enter: Easing.out(Easing.cubic),
  /** Things leaving (card out after a swipe, sheet down). */
  exit: Easing.in(Easing.cubic),
  /** Breathing loops (recording dot, pulsing ball, skeleton). */
  pulse: Easing.inOut(Easing.sin),
} as const;

export type EasingName = keyof typeof easings;

export interface TimingToken {
  /** Milliseconds. */
  duration: number;
  easing: EasingName;
}

export const timings = {
  /** Press feedback on buttons and chips. */
  press: { duration: 90, easing: 'standard' },
  /** A swiped card flying off screen once committed. */
  swipeExit: { duration: 200, easing: 'exit' },
  /** A card leaving the list (answered, done, postponed) and the gap closing. */
  listExit: { duration: 220, easing: 'exit' },
  /** A card entering the list. */
  listEnter: { duration: 240, easing: 'enter' },
  /** Fold open/close («Pospuestas», «Hecho recientemente»). */
  fold: { duration: 200, easing: 'standard' },
  /** Sheet and modal backdrop fading in or out. */
  backdrop: { duration: 180, easing: 'enter' },
  /** Bottom sheet leaving. */
  sheetClose: { duration: 200, easing: 'exit' },
  /** Toast leaving. */
  toastOut: { duration: 160, easing: 'exit' },
  /** The hold overlay (lock, strip) appearing over the bar. */
  holdOverlay: { duration: 140, easing: 'enter' },
  /** Red recording dot: one blink (in + out). */
  recordDot: { duration: 1000, easing: 'pulse' },
  /** Locked recording: one heartbeat of the brand ball. */
  recordPulse: { duration: 1400, easing: 'pulse' },
  /** Skeleton shimmer: one cycle. */
  skeleton: { duration: 1100, easing: 'pulse' },
  /** Screen transitions of the stack (detail views). */
  screen: { duration: 260, easing: 'standard' },
} as const satisfies Record<string, TimingToken>;

export type TimingName = keyof typeof timings;

/** The idle character of empty states: one frame of its 6-frame loop (1.2 s per loop, as in the PWA). */
export const spriteFrameMs = 200;

/** How long a toast stays: 5 s with «Deshacer»/«Recuperar» (the reversible-action window), 4 s otherwise. */
export const toastDurations = { withUndo: 5000, plain: 4000 } as const;

// ---------------------------------------------------------------- gestures

export const gestures = {
  swipe: {
    /** Horizontal travel before a card starts following the finger (points). */
    activeOffsetX: 14,
    /** Vertical travel that hands the touch to the list scroll instead (points). */
    failOffsetY: 12,
    /** Travel that commits the action when the finger lifts (fraction of the card width). */
    commitFraction: 0.33,
    /** Or a flick this fast in the action's direction (points per second). */
    commitVelocity: 900,
    /** Resistance past the commit point and on a side without an action (0 = rigid, 1 = free). */
    overdragResistance: 0.35,
    /** The action's icon grows to full size at this fraction of the commit distance. */
    revealFraction: 0.6,
  },
  capture: {
    /** Hold this long before recording starts (shorter is a tap that opens the sheet). */
    holdDelayMs: 220,
    /** A hold released sooner than this (from the press) records nothing: it counts as a tap. */
    minHoldMs: 600,
    /** Slide up this far to lock the recording. */
    lockDistance: 64,
    /** Slide left this far to discard it. */
    discardDistance: 110,
    /** The button and the lock follow the finger up to this height. */
    maxLift: 60,
  },
  sheet: {
    /** Drag a sheet down this far to close it. */
    dismissDistance: 120,
    /** Or flick it down this fast. */
    dismissVelocity: 1000,
  },
} as const;

// ---------------------------------------------------------------- haptics

export type HapticKind =
  | { type: 'selection' }
  | { type: 'impact'; style: 'light' | 'medium' | 'heavy' | 'soft' | 'rigid' }
  | { type: 'notification'; style: 'success' | 'warning' | 'error' };

/** One entry per interaction. null: no vibration. */
export const haptics = {
  /** A swiped card crosses the commit point (and again if it goes back). */
  swipeThreshold: { type: 'selection' },
  /** A swipe commits its action. */
  swipeCommit: { type: 'impact', style: 'medium' },
  /** The capture hold starts recording. */
  captureStart: { type: 'impact', style: 'medium' },
  /** Sliding up locks the recording. */
  captureLock: { type: 'impact', style: 'light' },
  /** Sliding left discards it. */
  captureDiscard: { type: 'notification', style: 'warning' },
  /** The capture went to the team. */
  captureSent: { type: 'notification', style: 'success' },
  /** A card action or answer succeeded. */
  actionSuccess: { type: 'notification', style: 'success' },
  /** An action failed. */
  actionError: { type: 'notification', style: 'error' },
  /** Switching tabs in the bottom bar. */
  tabChange: { type: 'selection' },
  /** Toggling a chip or option. */
  toggle: null,
} as const satisfies Record<string, HapticKind | null>;

export type HapticEvent = keyof typeof haptics;

/** Turns every vibration off (for example while testing on a desk). */
export const HAPTICS_ENABLED = true;

const IMPACT = {
  light: Haptics.ImpactFeedbackStyle.Light,
  medium: Haptics.ImpactFeedbackStyle.Medium,
  heavy: Haptics.ImpactFeedbackStyle.Heavy,
  soft: Haptics.ImpactFeedbackStyle.Soft,
  rigid: Haptics.ImpactFeedbackStyle.Rigid,
} as const;

const NOTIFICATION = {
  success: Haptics.NotificationFeedbackType.Success,
  warning: Haptics.NotificationFeedbackType.Warning,
  error: Haptics.NotificationFeedbackType.Error,
} as const;

/** Plays the haptic mapped to an interaction. Never throws (devices without a vibrator ignore it). */
export function haptic(event: HapticEvent): void {
  const kind: HapticKind | null = haptics[event];
  if (!HAPTICS_ENABLED || !kind) return;
  const run =
    kind.type === 'selection'
      ? Haptics.selectionAsync()
      : kind.type === 'impact'
        ? Haptics.impactAsync(IMPACT[kind.style])
        : Haptics.notificationAsync(NOTIFICATION[kind.style]);
  run.catch(() => undefined);
}

// ---------------------------------------------------------------- configs for Reanimated

/** withSpring config of a named spring, honouring reduced motion. */
export function spring(name: SpringName): WithSpringConfig {
  return { ...springs[name], reduceMotion: REDUCE[REDUCE_MOTION] };
}

/** withTiming config of a named timing, honouring reduced motion. */
export function timing(name: TimingName): WithTimingConfig {
  const token = timings[name];
  return { duration: token.duration, easing: easings[token.easing], reduceMotion: REDUCE[REDUCE_MOTION] };
}

/** True when animations should be skipped: the app switch, or the OS setting under 'system'. */
export function shouldReduceMotion(osReduced: boolean): boolean {
  if (REDUCE_MOTION === 'always') return true;
  if (REDUCE_MOTION === 'never') return false;
  return osReduced;
}

/** For components: whether to run loops and decorative motion right now. */
export function useMotion(): { reduced: boolean } {
  const osReduced = useReducedMotion();
  return { reduced: shouldReduceMotion(osReduced) };
}

// ---------------------------------------------------------------- layout animations (enter, exit, move)

const reduce = () => REDUCE[REDUCE_MOTION];

/** Builders for Reanimated `entering`, `exiting` and `layout` props, from the tokens above. */
export const layout = {
  /** Toast rising from the bottom. */
  toastIn: () =>
    FadeInDown.springify().damping(springs.toast.damping).stiffness(springs.toast.stiffness).mass(springs.toast.mass).reduceMotion(reduce()),
  toastOut: () => FadeOut.duration(timings.toastOut.duration).reduceMotion(reduce()),
  /** A card entering or leaving a list, and the rest closing the gap. */
  listEnter: () => FadeIn.duration(timings.listEnter.duration).reduceMotion(reduce()),
  listExit: () => FadeOut.duration(timings.listExit.duration).reduceMotion(reduce()),
  listMove: () => LinearTransition.duration(timings.listExit.duration).reduceMotion(reduce()),
  /** Fold content opening or closing. */
  foldIn: () => FadeIn.duration(timings.fold.duration).reduceMotion(reduce()),
  foldOut: () => FadeOut.duration(timings.fold.duration).reduceMotion(reduce()),
  /** The hold overlay of the capture button. */
  overlayIn: () => FadeIn.duration(timings.holdOverlay.duration).reduceMotion(reduce()),
  overlayOut: () => FadeOut.duration(timings.holdOverlay.duration).reduceMotion(reduce()),
};
