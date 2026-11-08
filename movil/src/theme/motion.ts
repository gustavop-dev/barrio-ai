// Motion tokens: every duration, spring, easing, gesture threshold and haptic of the app lives here.
// Screens never write a number for motion: they ask this module. Gustavo's motion spec (Claude
// Design) is applied by editing the values below; MOTION.md lists each token and where it is used.
//
// Reduced motion: every config carries `reduceMotion`, so Reanimated honours the OS setting
// («Quitar animaciones» on Android) by jumping straight to the end value. `REDUCE_MOTION` switches
// that for the whole app; `useMotion()` gives components the same decision for what Reanimated does
// not animate by itself (pulses, the hold overlay, the toast slide).
import * as Haptics from 'expo-haptics';
import { SCENE_MOTION } from '@compartido/scene/motion';
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

// ---------------------------------------------------------------- design base (Claude Design, «0ff1ce — Vistas móviles»)
// The motion design in `movil/diseno-movimiento/` runs one engine on every board: `TOK` there is this
// block. Its springs integrate force = −k·(x − target) − c·v with mass 1, exactly Reanimated's model, so
// k is `stiffness` and c is `damping`. Every token below builds on these values.

/** The four durations of the design (ms): `instant` taps, `fast` most tweens, `base` screens and panels, `slow` big reveals. */
export const durations = { instant: 100, fast: 180, base: 260, slow: 400 } as const;

/** Sheets, pushes, navigation, selections and anything that follows the finger (TOK.firm). */
export const FIRM = { damping: 20, stiffness: 260, mass: 1 } as const;
/** Presses, pulses, counters and morphs (TOK.soft). */
export const SOFT = { damping: 14, stiffness: 160, mass: 1 } as const;

/** Past an edge, a drag keeps this fraction of the extra distance (the design's `rubber`). */
export const RUBBER = 0.35;

/** The design's rubber band: free up to `limit`, then resisting. Worklet-safe. */
export function rubberBand(x: number, limit: number): number {
  'worklet';
  if (x <= limit) return x;
  return limit + (x - limit) * RUBBER;
}

// ---------------------------------------------------------------- springs (damping, stiffness, mass)

export interface SpringToken {
  damping: number;
  stiffness: number;
  mass: number;
}

export const springs = {
  /** A swiped card that did not commit goes back to its place. */
  snapBack: FIRM,
  /** The capture button grows to 72 px (and shrinks back) under the finger. */
  captureGrow: SOFT,
  /** The capture button and lock follow the finger while sliding up. */
  captureFollow: FIRM,
  /** Bottom sheets (capture, confirm) rising into place. */
  sheetOpen: FIRM,
  /** Pressed buttons, tab pills and chips scaling back. */
  press: SOFT,
  /** The toast rising from the bottom. */
  toast: FIRM,
  /** Calendario: the week strip or the month settling on the next page after a swipe (or back to its place). */
  pageSnap: FIRM,
  /** An opportunity card lifting under the finger when its drag starts (and settling when dropped). */
  dragLift: { damping: 18, stiffness: 300, mass: 0.8 },
  /** The photo viewer: double-tap zoom, the photo settling back inside its bounds, a drag-to-close that did not close. */
  zoomSettle: { damping: 22, stiffness: 240, mass: 1 },
} as const satisfies Record<string, SpringToken>;

export type SpringName = keyof typeof springs;

// ---------------------------------------------------------------- durations and easings

export const easings = {
  /** Most UI moves: quick start, soft landing. */
  standard: Easing.bezier(0.2, 0, 0, 1),
  /** Things arriving: fast start, settles (the design's EASE_OUT). */
  enter: Easing.bezier(0.2, 0, 0, 1),
  /** Things leaving: soft start, gone fast (the design's EASE_IN). */
  exit: Easing.bezier(0.3, 0, 1, 1),
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
  press: { duration: durations.instant, easing: 'standard' },
  /** A swiped card flying off screen once committed. */
  swipeExit: { duration: durations.fast, easing: 'exit' },
  /** A card leaving the list (answered, done, postponed) and the gap closing. */
  listExit: { duration: durations.fast, easing: 'exit' },
  /** A card entering the list. */
  listEnter: { duration: durations.base, easing: 'enter' },
  /** Fold open/close («Pospuestas», «Hecho recientemente»). */
  fold: { duration: durations.fast, easing: 'standard' },
  /** Sheet and modal backdrop fading in or out. */
  backdrop: { duration: durations.fast, easing: 'enter' },
  /** Bottom sheet leaving. */
  sheetClose: { duration: durations.fast, easing: 'exit' },
  /** Toast leaving. */
  toastOut: { duration: durations.fast, easing: 'exit' },
  /** The hold overlay (lock, strip) appearing over the bar. */
  holdOverlay: { duration: durations.instant, easing: 'enter' },
  /** Red recording dot: one blink (in + out). */
  recordDot: { duration: 1000, easing: 'pulse' },
  /** Locked recording: one heartbeat of the brand ball. */
  recordPulse: { duration: 1400, easing: 'pulse' },
  /** Skeleton shimmer: one cycle. */
  skeleton: { duration: 1100, easing: 'pulse' },
  /** Screen transitions of the stack (detail views). */
  screen: { duration: durations.base, easing: 'enter' },
  /** The full-screen photo viewer fading in and out. */
  viewerFade: { duration: durations.fast, easing: 'enter' },
  /** An upload progress bar moving to its new value. */
  progress: { duration: durations.base, easing: 'standard' },
  officeNowIn: { duration: durations.base, easing: 'enter' },
  officeNowOut: { duration: durations.fast, easing: 'exit' },
} as const satisfies Record<string, TimingToken>;

export type TimingName = keyof typeof timings;

/** The idle character of empty states: one frame of its 6-frame loop (1.2 s per loop, as in the PWA). */
export const spriteFrameMs = 200;

/** How long a toast stays: 5 s with «Deshacer»/«Recuperar» (the reversible-action window), 4 s otherwise. */
export const toastDurations = { withUndo: 5000, plain: 4000 } as const;

/** How long «Copiado» stays on a copy button before it says «Copiar» again. */
export const copiedLabelMs = 2000;

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
  pager: {
    /** Horizontal travel before the week strip or the month follows the finger (points). */
    activeOffsetX: 16,
    /** Vertical travel that leaves the touch to the page scroll instead (points). */
    failOffsetY: 14,
    /** Travel that turns the page when the finger lifts (fraction of the width). */
    commitFraction: 0.25,
    /** Or a flick this fast (points per second). */
    commitVelocity: 700,
  },
  drag: {
    /** Hold an opportunity card this long before it lifts and follows the finger (ms). */
    longPressMs: 400,
    /** Scale of the lifted card. */
    liftScale: 1.03,
    /** Distance from the top or bottom edge of the list where a dragged card scrolls it (points). */
    autoScrollEdge: 80,
    /** Speed of that scroll (points per second). */
    autoScrollSpeed: 700,
  },
  zoom: {
    /** Pinch-zoom limit of the photo viewer (1 = fitted to the screen). */
    maxScale: 4,
    /** Where a double tap zooms to (and a second double tap goes back to 1). */
    doubleTapScale: 2.5,
    /** Longest gap between the two taps of a double tap (ms). */
    doubleTapMaxDelayMs: 250,
  },
  viewer: {
    /** Vertical travel before the unzoomed photo follows the finger down to close (points). */
    activeOffsetY: 16,
    /** Horizontal travel that hands the touch to the pager instead (points). */
    failOffsetX: 14,
    /** Drag the photo down this far to close the viewer. */
    dismissDistance: 140,
    /** Or flick it down this fast. */
    dismissVelocity: 1000,
    /** How much the photo fades (0–1) by the time the drag reaches dismissDistance. */
    dragFade: 0.4,
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
  /** Calendario: a swipe turns the week or the month. */
  pageChange: { type: 'selection' },
  /** The text went to the clipboard. */
  copied: { type: 'notification', style: 'success' },
  /** An opportunity card lifts after the long press. */
  dragStart: { type: 'impact', style: 'medium' },
  /** The dragged card moves over another stage. */
  dragOver: { type: 'selection' },
  /** The card is dropped on a new stage. */
  dragDrop: { type: 'impact', style: 'light' },
  /** Flipping a switch row (Ajustes, the photo sheet). */
  switchToggle: null,
  /** The photos reached the gallery. */
  uploadDone: { type: 'notification', style: 'success' },
  officePick: { type: 'selection' },
  /** MovTuTurno: «Más tarde» sends a card to «Pospuestas» (LEVE). A card resolved with its button plays `actionSuccess` (ÉXITO). */
  turnoLater: { type: 'impact', style: 'light' },
  /** MovNotificaciones: a new notification arrives while the app is open; the bell sways (LEVE). */
  notificationArrive: { type: 'impact', style: 'light' },
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
  /** The full-screen photo viewer of the Galería. */
  viewerIn: () => FadeIn.duration(timings.viewerFade.duration).reduceMotion(reduce()),
  viewerOut: () => FadeOut.duration(timings.viewerFade.duration).reduceMotion(reduce()),
};

// Oficina: choreography is shared with the PWA; all native overrides belong here.
export const officeMotion = { ...SCENE_MOTION };
export const officeFrames = { stepMs: 16, maxDeltaMs: 64, reportFrames: 300, slowFrameMs: 1000 / 60 } as const;
export const officeGestures = {
  minZoom: 1, maxZoom: 3, panDistance: 8, tapDistance: 10, tapDurationMs: 250, doubleTapMs: 280,
  touchTarget: 48, sheetActivation: 8, sheetHalf: 0.5, sheetFull: 0.88,
} as const;
export const officeLayout = {
  nowIn: () => FadeIn.duration(timings.officeNowIn.duration).reduceMotion(reduce()),
  nowOut: () => FadeOut.duration(timings.officeNowOut.duration).reduceMotion(reduce()),
};

// ---------------------------------------------------------------- Tu turno and Notificaciones (MovTuTurno, MovNotificaciones)
// Gustavo's phase 2 boards. Tu turno: a card resolved with its button shows a check, holds it, then
// collapses while the list closes the gap; only then do the counters roll (each group's, the top bar
// badge). «Más tarde» first slides the card toward «Pospuestas». A swiped card has already left under
// the finger and goes through the same gap and counters. Notificaciones: a new one opens its space at
// the top, the bell sways and its dot pulses; «Marcar todo como leído» turns «Nueva» off in a cascade.
import { withDelay, withTiming, type EntryAnimationsValues, type ExitAnimationsValues, type LayoutAnimation } from 'react-native-reanimated';

/** MovTuTurno: the board's numbers and distances. */
export const turnoMotion = {
  /** MovTuTurno: the check of the resolved button grows from this scale. */
  checkFrom: 0.6,
  /** MovTuTurno: a resolved card shows its check this long before it collapses (ms). */
  doneHoldMs: 220,
  /** MovTuTurno: «Más tarde» moves the card this far right and down while it fades (pt). */
  laterShift: { x: 40, y: 6 },
  /** MovTuTurno: a counter that changes rolls: the old number rises this far and the new one comes from as far below (pt). */
  rollDistance: 8,
  /** MovTuTurno: the top bar badge pops to this scale and springs back with SOFT. */
  badgePop: 1.25,
  /** MovTuTurno: a group label left at 0 collapses this long after its last card is counted out (ms). */
  labelDelayMs: durations.base,
  /** MovTuTurno: «Nada depende de ti hoy» fades in this long after the last card is counted out (ms). */
  emptyDelayMs: durations.base + 80,
  /** MovTuTurno: the librarian of the empty state rises from this far below as it fades in (pt). */
  emptyRise: 8,
  /** MovTuTurno: the «Pospuestas» row flashes 0ff1ce-claro for this long, up and down along a sine (ms, linear). */
  postponedFlashMs: 420,
} as const;

/** MovTuTurno: the board's tweens. */
export const turnoTimings = {
  /** MovTuTurno: the check grows in the resolved button. */
  check: { duration: durations.fast, easing: 'enter' },
  /** MovTuTurno: «Más tarde» slides the card away and fades it. */
  laterSlide: { duration: durations.base, easing: 'exit' },
  /** MovTuTurno: a card (or an empty group label) collapses; the rest of the list closes the gap at the same pace. */
  collapse: { duration: durations.base, easing: 'exit' },
  /** MovTuTurno: the old number of a counter leaves upward. */
  rollOut: { duration: 90, easing: 'exit' },
  /** MovTuTurno: then the new number comes in from below. */
  rollIn: { duration: 90, easing: 'enter' },
  /** MovTuTurno: «Nada depende de ti hoy» fades in. */
  emptyIn: { duration: durations.base, easing: 'enter' },
} as const satisfies Record<string, TimingToken>;

/** MovTuTurno: the top bar badge springs back from its pop (`badge`, SOFT). */
export const turnoSprings = { badge: SOFT } as const satisfies Record<string, SpringToken>;

/** MovNotificaciones: the board's numbers, angles and distances. */
export const notifMotion = {
  /** MovNotificaciones: a new notification drops into its space from this far above (pt). */
  arriveDrop: 8,
  /** MovNotificaciones: the bell sways through these angles (degrees, one equal step each) and rests on the last. */
  bellSway: [12, -9, 6, -3, 0],
  /** MovNotificaciones: the whole sway (ms); each step eases out. */
  bellSwayMs: 600,
  /** MovNotificaciones: the bell hangs from this point of its 24-unit icon: the centre, 3 units from the top. */
  bellPivot: { x: 0.5, y: 3 / 24 },
  /** MovNotificaciones: «Marcar todo como leído» turns each «Nueva» off this long after the one before (ms). */
  readStaggerMs: 30,
  /** MovNotificaciones: the «Nueva» label shrinks to this scale as it fades. */
  readChipTo: 0.7,
} as const;

/** MovNotificaciones: the board's tweens. */
export const notifTimings = {
  /** MovNotificaciones: a new notification opens its space and fades in; the list moves down at the same pace. */
  arrive: { duration: durations.base, easing: 'enter' },
  /** MovNotificaciones: one step of the bell's sway. */
  bellStep: { duration: notifMotion.bellSwayMs / notifMotion.bellSway.length, easing: 'enter' },
  /** MovNotificaciones: a «Nueva» label and its row highlight turn off. */
  readOff: { duration: durations.fast, easing: 'exit' },
} as const satisfies Record<string, TimingToken>;

/** MovNotificaciones: the bell's dot pops in from 0 when one arrives (SOFT) and closes when all are read (FIRM). */
export const notifSprings = { dotIn: SOFT, dotOut: FIRM } as const satisfies Record<string, SpringToken>;

function timingOf(token: TimingToken): WithTimingConfig {
  return { duration: token.duration, easing: easings[token.easing], reduceMotion: REDUCE[REDUCE_MOTION] };
}

function springOf(token: SpringToken): WithSpringConfig {
  return { ...token, reduceMotion: REDUCE[REDUCE_MOTION] };
}

/** withTiming config of a Tu turno tween, honouring reduced motion. */
export function turnoTiming(name: keyof typeof turnoTimings): WithTimingConfig {
  return timingOf(turnoTimings[name]);
}

/** withTiming config of the «Pospuestas» flash: linear, the sine is applied to its progress. */
export function postponedFlashTiming(): WithTimingConfig {
  return { duration: turnoMotion.postponedFlashMs, easing: Easing.linear, reduceMotion: REDUCE[REDUCE_MOTION] };
}

/** withSpring config of a Tu turno spring, honouring reduced motion. */
export function turnoSpring(name: keyof typeof turnoSprings): WithSpringConfig {
  return springOf(turnoSprings[name]);
}

/** withTiming config of a Notificaciones tween, honouring reduced motion. */
export function notifTiming(name: keyof typeof notifTimings): WithTimingConfig {
  return timingOf(notifTimings[name]);
}

/** withSpring config of a Notificaciones spring, honouring reduced motion. */
export function notifSpring(name: keyof typeof notifSprings): WithSpringConfig {
  return springOf(notifSprings[name]);
}

/** Layout animations of MovTuTurno: `entering`, `exiting` and the list's `itemLayoutAnimation`. Their configs are
 * built here on the JS thread and captured by the worklets, which run on the UI thread. */
export const turnoLayout = {
  /** A resolved card or an empty group label collapses (its height closes) and fades: the board's `collapse`. Clip the row. */
  collapse: () => {
    const config = timingOf(turnoTimings.collapse);
    return (values: ExitAnimationsValues): LayoutAnimation => {
      'worklet';
      return {
        initialValues: { height: values.currentHeight, opacity: 1 },
        animations: { height: withTiming(0, config), opacity: withTiming(0, config) },
      };
    };
  },
  /** A card that already slid away invisible («Más tarde»): only its space closes. */
  collapseSpace: () => {
    const config = timingOf(turnoTimings.collapse);
    return (values: ExitAnimationsValues): LayoutAnimation => {
      'worklet';
      return { initialValues: { height: values.currentHeight }, animations: { height: withTiming(0, config) } };
    };
  },
  /** The rest of the list closes the gap at the pace of the collapse. */
  listMove: () => LinearTransition.duration(turnoTimings.collapse.duration).easing(easings.exit).reduceMotion(reduce()),
  /** «Nada depende de ti hoy» after the last card: it fades in once the gap has closed. */
  emptyIn: () => {
    const config = timingOf(turnoTimings.emptyIn);
    const delay = turnoMotion.emptyDelayMs;
    const rm = reduce();
    return (): LayoutAnimation => {
      'worklet';
      return { initialValues: { opacity: 0 }, animations: { opacity: withDelay(delay, withTiming(1, config), rm) } };
    };
  },
  /** …and its librarian rises into place with it. */
  emptyPortraitIn: () => {
    const config = timingOf(turnoTimings.emptyIn);
    const delay = turnoMotion.emptyDelayMs;
    const rise = turnoMotion.emptyRise;
    const rm = reduce();
    return (): LayoutAnimation => {
      'worklet';
      return {
        initialValues: { transform: [{ translateY: rise }] },
        animations: { transform: [{ translateY: withDelay(delay, withTiming(0, config), rm) }] },
      };
    };
  },
  /** A counter's old number leaves upward. */
  rollOut: () => {
    const config = timingOf(turnoTimings.rollOut);
    const distance = turnoMotion.rollDistance;
    return (): LayoutAnimation => {
      'worklet';
      return {
        initialValues: { opacity: 1, transform: [{ translateY: 0 }] },
        animations: { opacity: withTiming(0, config), transform: [{ translateY: withTiming(-distance, config) }] },
      };
    };
  },
  /** …then the new one comes in from below, once the old one is gone. */
  rollIn: () => {
    const config = timingOf(turnoTimings.rollIn);
    const delay = turnoTimings.rollOut.duration;
    const distance = turnoMotion.rollDistance;
    const rm = reduce();
    return (): LayoutAnimation => {
      'worklet';
      return {
        initialValues: { opacity: 0, transform: [{ translateY: distance }] },
        animations: { opacity: withDelay(delay, withTiming(1, config), rm), transform: [{ translateY: withDelay(delay, withTiming(0, config), rm) }] },
      };
    };
  },
};

/** Layout animations of MovNotificaciones (configs built on the JS thread, as above). */
export const notifLayout = {
  /** A new notification opens its space (clip the row) and fades in. */
  arrive: () => {
    const config = timingOf(notifTimings.arrive);
    return (values: EntryAnimationsValues): LayoutAnimation => {
      'worklet';
      return {
        initialValues: { height: 0, opacity: 0 },
        animations: { height: withTiming(values.targetHeight, config), opacity: withTiming(1, config) },
      };
    };
  },
  /** …while its content drops into place from above. */
  arriveContent: () => {
    const config = timingOf(notifTimings.arrive);
    const drop = notifMotion.arriveDrop;
    return (): LayoutAnimation => {
      'worklet';
      return { initialValues: { transform: [{ translateY: -drop }] }, animations: { transform: [{ translateY: withTiming(0, config) }] } };
    };
  },
  /** The rest of the list moves down at the same pace. */
  listMove: () => LinearTransition.duration(notifTimings.arrive.duration).easing(easings.enter).reduceMotion(reduce()),
};
