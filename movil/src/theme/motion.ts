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
import { Easing, FadeIn, FadeInDown, FadeOut, LinearTransition, ReduceMotion, useReducedMotion, withDelay, withTiming, type WithSpringConfig, type WithTimingConfig } from 'react-native-reanimated';

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
  /** MovOficina: new narration enters after the previous one starts leaving. */
  officeNowIn: { duration: durations.fast, easing: 'enter' },
  officeNowOut: { duration: 120, easing: 'exit' },
  officeNowRetire: { duration: durations.fast, easing: 'exit' },
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
/** MovOficina: shared interpreter values, in logical pixels and milliseconds. */
export const officeMotion = {
  ...SCENE_MOTION,
  ambientEvery: 11000,
  hopPx: 2, hopSettlePx: 1, hopStepMs: 90, hopEndMs: durations.fast,
  bracketPx: 7, bracketMs: 120,
  mailX: 98, mailStartY: -6, mailLandingY: 68, mailAcceleration: 0.9, mailStepMs: 16,
  captureQuestionMs: 700, captureSheetMs: 1600, capturePickupMs: 500, captureHandoffMs: 1800,
  captureFreePollMs: 300,
};
/** MovOficina: caption text swaps independently from the box's automatic retirement. */
export const officeNarration = { enterY: 6, exitY: -4, retireY: -6, enterDelayMs: 60, holdMs: 3500 } as const;
export const officeFrames = { stepMs: 16, maxDeltaMs: 60, reportFrames: 300, slowFrameMs: 1000 / 60 } as const;
export const officeGestures = {
  minZoom: 1, maxZoom: 3, panDistance: 8, tapDistance: 10, tapDurationMs: 250, doubleTapMs: 280,
  touchTarget: 48, sheetActivation: 8, sheetHalf: 0.5, sheetFull: 0.88,
} as const;
export const officeLayout = {
  /** MovOficina: text layers overlap; the new one starts at 60 ms. */
  nowIn: () => {
    const config = timing('officeNowIn'); const reduced = reduce();
    return () => {
      'worklet';
      return { initialValues: { opacity: 0, transform: [{ translateY: officeNarration.enterY }] },
        animations: { opacity: withDelay(officeNarration.enterDelayMs, withTiming(1, config), reduced),
          transform: [{ translateY: withDelay(officeNarration.enterDelayMs, withTiming(0, config), reduced) }] } };
    };
  },
  nowOut: () => {
    const config = timing('officeNowOut');
    return () => {
      'worklet';
      return { initialValues: { opacity: 1, transform: [{ translateY: 0 }] },
        animations: { opacity: withTiming(0, config), transform: [{ translateY: withTiming(officeNarration.exitY, config) }] } };
    };
  },
};

// ---------------------------------------------------------------- navigation, entrance and detail (MovNavegacion, MovEntrada, MovDetalle)
// The bottom bar, the push of detail screens (and of the top-bar screens), the login entrance and the
// shared element from a list row into a person card. MOTION.md › «Navegación, Entrada y Detalle».

/** Springs of the navigation boards (TOK.firm and TOK.soft). */
export const navSprings = {
  /** MovNavegacion: the active pill slides to the tapped tab. */
  pill: FIRM,
  /** MovNavegacion: the tapped tab's icon pops from `navValues.tabIconFrom` back to 1. */
  tabIcon: SOFT,
  /** MovNavegacion: a detail screen (and a top-bar screen) pushed in and back, also after the edge drag. */
  push: FIRM,
  /** MovDetalle: the portrait and the name flying between the list row and the person card. */
  flight: FIRM,
} as const satisfies Record<string, SpringToken>;

export type NavSpringName = keyof typeof navSprings;

export const navTimings = {
  /** MovNavegacion: the new tab's content fades in and rises (TOK.fast, EASE_OUT). */
  tabIn: { duration: durations.fast, easing: 'enter' },
  /** MovNavegacion: the old tab's content fades out in 60 % of TOK.fast (EASE_IN). */
  tabOut: { duration: durations.fast * 0.6, easing: 'exit' },
  /** MovDetalle: each block of the person card enters (TOK.fast, EASE_OUT). */
  cardBlock: { duration: durations.fast, easing: 'enter' },
  /** MovEntrada: the login form and the tagline leave (TOK.fast, EASE_IN). */
  entradaFormOut: { duration: durations.fast, easing: 'exit' },
  /** MovEntrada: the login fades into the Oficina (TOK.base, EASE_OUT). With reduced motion it is the whole entrance. */
  entradaFade: { duration: durations.base, easing: 'enter' },
  /** MovEntrada: the door leaf and the integer zoom jump instead of tweening (crisp pixels). */
  entradaCut: { duration: 0, easing: 'standard' },
} as const satisfies Record<string, TimingToken>;

export type NavTimingName = keyof typeof navTimings;

export const navValues = {
  /** MovNavegacion: the tapped tab's icon starts at this scale. */
  tabIconFrom: 0.92,
  /** MovNavegacion: the new tab's content rises from this many points below. */
  tabRise: 8,
  /** MovNavegacion: the screen underneath a push moves left by this fraction of the width, */
  pushParallax: 0.3,
  /** and darkens with tinta at this opacity. */
  pushDim: 0.08,
  /** MovDetalle: each block of the person card rises from this many points below, */
  cardBlockRise: 8,
  /** the first one this long (ms) after the push starts, */
  cardBlockDelayMs: 120,
  /** and each next one this much later (ms). */
  cardBlockStepMs: 30,
} as const;

export const navGestures = {
  /** MovNavegacion: width of the strip at the left edge of a detail screen that drags it back (points). */
  edgeWidth: 24,
  /** On release the detail stays when its projected progress is at least this (0 gone, 1 in place); below, it goes back. */
  stayOpen: 0.6,
  /** The release projection: progress taken off per point/ms of rightward speed (the board's `vx · 0.25`). */
  velocityProjection: 0.25,
  /** The strip only grabs a detail that is at least this far in. */
  grabFrom: 0.5,
} as const;

/** MovEntrada: after the server says yes, the pixel door opens and the picture zooms in integer steps (ms). */
export const entrada = {
  /** The door leaf folds on its hinge to this width at once, */
  leafHalf: 0.5,
  /** and to this one `leafStepMs` later. */
  leafOpen: 0.125,
  leafStepMs: 80,
  /** The picture jumps to `zoom2` here, */
  zoom2Ms: 160,
  zoom2: 2,
  /** and to `zoom3` here. */
  zoom3Ms: 310,
  zoom3: 3,
  /** The form and the tagline start leaving here (navTimings.entradaFormOut), */
  formOutMs: 160,
  /** the form dropping this many points. */
  formDrop: 16,
  /** The login starts fading into the Oficina here (navTimings.entradaFade). */
  fadeMs: 460,
} as const;

/** Control points of `easings.enter` and `easings.exit`, for React Native's Animated (the tab scenes). */
export const BEZIER = { enter: [0.2, 0, 0, 1], exit: [0.3, 0, 1, 1] } as const;

/** withSpring config of a navigation spring, honouring reduced motion. */
export function navSpring(name: NavSpringName): WithSpringConfig {
  return { ...navSprings[name], reduceMotion: REDUCE[REDUCE_MOTION] };
}

/** withTiming config of a navigation timing, honouring reduced motion. */
export function navTiming(name: NavTimingName): WithTimingConfig {
  const token = navTimings[name];
  return { duration: token.duration, easing: easings[token.easing], reduceMotion: REDUCE[REDUCE_MOTION] };
}

/**
 * An opacity-only fade that still plays when the phone asks for less motion: the boards' «menos
 * movimiento» crossfades (MovEntrada). REDUCE_MOTION 'always' still removes it.
 */
export function crossfade(name: NavTimingName): WithTimingConfig {
  const token = navTimings[name];
  return { duration: token.duration, easing: easings[token.easing], reduceMotion: REDUCE_MOTION === 'always' ? ReduceMotion.Always : ReduceMotion.Never };
}

export const navLayout = {
  /** MovDetalle: block `step` of the person card fades in and rises, staggered after the push. */
  cardBlock: (step: number) =>
    FadeInDown.duration(navTimings.cardBlock.duration)
      .easing(easings.enter)
      .delay(navValues.cardBlockDelayMs + step * navValues.cardBlockStepMs)
      .withInitialValues({ opacity: 0, transform: [{ translateY: navValues.cardBlockRise }] })
      .reduceMotion(reduce()),
};
