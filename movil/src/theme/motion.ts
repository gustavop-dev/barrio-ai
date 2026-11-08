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

/** How long «Copiado» stays on a copy button before it says «Copiar» again (MovMicro: 1,5 s). */
export const copiedLabelMs = 1500;

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
  /** Sliding up locks the recording (MovCaptura: «HÁPTICO · ÉXITO»). */
  captureLock: { type: 'notification', style: 'success' },
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
  /** Flipping a switch row (Ajustes, the photo sheet) (MovMicro: «HÁPTICO · SELECCIÓN»). */
  switchToggle: { type: 'selection' },
  /** The photos reached the gallery. */
  uploadDone: { type: 'notification', style: 'success' },
  officePick: { type: 'selection' },
  /** MovHojas: a sheet settles on a new snap point, opening included («HÁPTICO · LEVE»). */
  sheetSnap: { type: 'impact', style: 'light' },
  /** MovMicro: a filter chip is chosen or let go («HÁPTICO · SELECCIÓN»). */
  chipToggle: { type: 'selection' },
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

// ---------------------------------------------------------------- Captura, hojas y microinteracciones
// Boards MovCaptura, MovHojas and MovMicro (diseno-movimiento/tableros): every value here is the
// board's own, named after what it moves. (This block keeps its own imports so the shared header
// above stays untouched by each motion area.)
import { Keyframe, type EntryExitAnimationFunction } from 'react-native-reanimated';

/** withSpring config of any spring token (not only the named `springs`), honouring reduced motion. */
export function springWith(token: SpringToken): WithSpringConfig {
  return { ...token, reduceMotion: REDUCE[REDUCE_MOTION] };
}

/** withTiming config from one of the design's durations and a curve, honouring reduced motion. */
export function timingWith(duration: number, easing: EasingName): WithTimingConfig {
  return { duration, easing: easings[easing], reduceMotion: REDUCE[REDUCE_MOTION] };
}

/**
 * A linear clock that always runs, also with reduced motion: the boards' timelines (`tl`) keep their
 * length and their «menos movimiento» branch picks simpler visuals instead.
 */
export function timelineWith(duration: number): WithTimingConfig {
  return { duration, easing: Easing.linear, reduceMotion: ReduceMotion.Never };
}

/** MovHojas: bottom sheets (Sheet, SnapSheet, ConfirmSheet). The sheet's position springs on `springs.sheetOpen` (FIRM). */
export const sheetMotion = {
  /**
   * The open snap points of a SnapSheet as fractions of the room above it (SNAPS = [0, 0.5, 0.9]).
   * The half one is `officeGestures.sheetHalf`, the share the Oficina leaves to its scene.
   */
  snaps: [officeGestures.sheetHalf, 0.9] as const,
  /** On release the sheet is projected along its velocity for this long (s): `proj = p + v · 0.15`. */
  projectionS: 0.15,
  /** A projection under this fraction of the lowest snap closes the sheet (0.25 of the screen with the 0.5 snap). */
  closeBelow: 0.5,
  /** MovCaptura: a closed sheet rests this far past its own height, so no edge peeks (`SH + 20`, px). */
  closedGap: 20,
  /** Native: the handle takes the drag after this travel, so taps on the header still work (points). */
  activation: 8,
} as const;

/** MovCaptura: the capture button, its hold overlay and the capture sheet. */
export const captureMotion = {
  /** The button grows to this scale while holding (72 px over 60), on `springs.captureGrow` (SOFT). */
  holdScale: 1.2,
  /** The button follows 60 % of the finger up and left (`dy · 0.6`); it goes back on `springs.captureFollow` (FIRM). */
  follow: 0.6,
  /** The lock rises this far while it appears (`12 · (1 − lockOn)`, px). */
  lockRise: 12,
  /** The lock follows the button up at this ratio (`dy · 0.35`). */
  lockFollow: 0.35,
  /** The lock's opacity before the finger moves; it reaches 1 at the lock point (`0.55 + 0.45 · dragP`). */
  lockRestOpacity: 0.55,
  /** The lock's scale before the finger moves; 1 at the lock point or once it shuts (`0.85 + 0.15 · …`). */
  lockRestScale: 0.85,
  /** The shackle drops this far when the recording locks (px)… */
  shackleDrop: 3,
  /** …in this long (ms, EASE_OUT). */
  shackleMs: 120,
  /** The recording strip slides up from this far below (its height, px). */
  barRise: 56,
  /** At the discard point the strip keeps 40 % of its opacity (`1 − cancelP · 0.6`). */
  barCancelFade: 0.6,
  /** The trash circle shows up once the finger has gone this share of the way left. */
  trashShowAt: 0.05,
  /** The trash circle's scale as it appears (`0.8 + 0.2 · trashOn`). */
  trashRestScale: 0.8,
  /** The trash lid opens this far at the discard point (`−28 · cancelP`, degrees). */
  lidOpenDeg: -28,
  /** The discarded button falls into the trash shrinking to this scale (fast, EASE_IN). */
  dropScale: 0.2,
  /** After the fall the trash waits this long before closing (`fast + 220`, ms). */
  trashLingerMs: 220,
  /** Sliding up to lock dims the screen up to half the backdrop (`dragP · 0.5`). */
  holdDim: 0.5,
  /** Sheet open: the button turns into the sheet's audio ball on this spring… */
  morph: SOFT,
  /** …and hands over to the ball in the sheet once within 0.2 % of its end, at rest (native: the sheet's ball scrolls and drags with it). */
  dockWithin: 0.002,
  /** The ball beats with the voice: scale 1 + 0.08 · level. */
  ballBeat: 0.08,
  /** Paused, the ball rests at this scale. */
  ballPausedScale: 0.96,
  /** The ring around the live ball: 4 px plus 18 px · level… */
  ringBase: 4,
  ringLevel: 18,
  /** …at 35 % opacity, fading by half with the level (`0.35 · (1 − level · 0.5)`). */
  ringOpacity: 0.35,
  ringFade: 0.5,
  /** The voice level follows the microphone at this rate per 60 Hz frame (`level += (target − level) · 0.25`)… */
  levelFollow: 0.25,
  /** …and falls back to silence at this one when nothing records. */
  levelRelease: 0.2,
  /** The wave takes a new bar this often (ms). */
  levelEveryMs: 90,
  /** Paused, the time blinks every 500 ms down to 35 %. */
  pausedBlinkMs: 500,
  pausedBlinkOpacity: 0.35,
  /** Icons on the ball crossfade turning 90° (fast, EASE_OUT); pause grows from 0.8, play from 0.6. */
  iconTurnDeg: 90,
  pauseFrom: 0.8,
  playFrom: 0.6,
  /** After «Guardar», the button pulses from this scale back to 1… */
  sentPulse: 1.18,
  /** …on this spring. */
  pulse: SOFT,
  /** A new photo pops in: scale 0.6 → 1.06 at 60 % of `durations.base` → 1, EASE_OUT. */
  thumbFrom: 0.6,
  thumbOvershoot: 1.06,
  thumbPeakAt: 60,
} as const;

/** MovCaptura: the timelines of «Descartar» and «Guardar» in the sheet. Points are fractions of `ms`. */
export const captureTimeline = {
  discard: {
    ms: 780,
    /** The recording's controls fade out. */
    fade: [0, 0.2],
    /** The bin pops in with a 10 % bump. */
    binPop: [0, 0.2],
    binBump: 0.1,
    /** The bin sits this far below the ball's centre (px). */
    binBelow: 116,
    /** The lid opens, then closes after the ball drops in (degrees). */
    lidOpen: [0.05, 0.2],
    lidClose: [0.55, 0.66],
    lidDeg: -35,
    /** The ball flies into the bin (EASE_IN) along an arc 60 px right and 40 px up, shrinking to 22 px, ending 34 px above the bin's centre. */
    fly: [0.22, 0.55],
    arcX: 60,
    arcY: -40,
    mouth: 34,
    shrinkTo: 22,
    /** «HÁPTICO · AVISO»: the ball drops in, and is gone a moment later. */
    dropAt: 0.55,
    ballOffAt: 0.56,
    /** The bin shakes ±4 px, two times… */
    shake: [0.66, 0.82],
    shakePx: 4,
    shakeHalfTurns: 4,
    /** …and goes, shrinking by 20 %. */
    out: [0.82, 1],
    outShrink: 0.2,
  },
  send: {
    ms: 1000,
    /** The sheet's content fades out. */
    fade: [0, 0.16],
    /** The audio ball shrinks to 45 % (EASE_OUT), then into the envelope; reduced motion: it shrinks over 0–0.4. */
    ballShrink: [0, 0.18],
    ballShrinkTo: 0.45,
    ballGone: [0.18, 0.36],
    ballOff: 0.4,
    /** The envelope pops in (EASE_OUT) and its flap closes (EASE_OUT). */
    envelopeIn: [0.02, 0.2],
    flapClose: [0.3, 0.42],
    /** «HÁPTICO · ÉXITO»: sealed. */
    sealAt: 0.42,
    /** The sheet goes down. */
    closeAt: 0.45,
    /** The envelope flies off to the top right (EASE_IN): control and end points from where it sealed (px), shrinking to 60 % and turning −18°. */
    fly: [0.45, 1],
    flyControlX: 145,
    flyControlY: -64,
    flyEndX: 255,
    flyEndY: -324,
    flyScale: 0.6,
    flyTurnDeg: -18,
    /** Reduced motion: the envelope stays and fades. */
    envelopeFade: [0.6, 1],
    /** Each photo flies into the envelope (EASE_IN), 40 ms after the one before, shrinking by 80 %; reduced motion: 0–0.3. */
    thumbs: [0.05, 0.28],
    thumbStagger: 0.04,
    thumbShrink: 0.8,
    thumbsReduced: [0, 0.3],
  },
} as const;

/** MovMicro: buttons, the switch, chips, «Copiar» and loading. */
export const microMotion = {
  /** A pressed button gives way to 0.97 on a stiff spring (k 900, c 60)… */
  pressDown: { damping: 60, stiffness: 900, mass: 1 },
  pressedScale: 0.97,
  /** …and comes back on FIRM. */
  pressUp: FIRM,
  /** The switch knob slides on FIRM; the track and the knob's border change colour halfway through a fast EASE_OUT. */
  switchKnob: FIRM,
  switchColorAt: 0.5,
  /** A chosen chip's check slides in from 6 px to the left (fast; EASE_OUT on, EASE_IN off). */
  chipCheckShift: 6,
  /** «Copiado»: the copy icon turns 90° away while the check turns in from −90° and grows from 0.6 (fast, EASE_OUT). */
  copyTurnDeg: 90,
  copyCheckFrom: 0.6,
  /** Loading blocks breathe between 55 % and 100 % every 1.2 s, each 0.4 rad behind the one before… */
  skeletonPeriodMs: 1200,
  skeletonLow: 0.55,
  skeletonLag: 0.4,
  /** …and stay at 70 % with reduced motion. */
  skeletonStill: 0.7,
  /** MovCaptura: the toast rises this far while it fades in (fast, EASE_OUT) and sinks back fading out (fast, EASE_IN). */
  toastRise: 12,
} as const;

/** The design's curves as plain functions, for worklets that place things along a timeline (EASE_OUT, EASE_IN). */
export const curves = { enter: easings.enter.factory(), exit: easings.exit.factory() } as const;

/** `entering`/`exiting` builders for this block. */
export const microLayout = {
  /** The toast fading in while it rises 12 px (fast, EASE_OUT). */
  toastIn: (): EntryExitAnimationFunction => {
    const config = timingWith(durations.fast, 'enter');
    return () => {
      'worklet';
      return {
        initialValues: { opacity: 0, transform: [{ translateY: microMotion.toastRise }] },
        animations: { opacity: withTiming(1, config), transform: [{ translateY: withTiming(0, config) }] },
      };
    };
  },
  /** The toast fading out while it sinks 12 px (fast, EASE_IN). */
  toastOut: (): EntryExitAnimationFunction => {
    const config = timingWith(durations.fast, 'exit');
    return () => {
      'worklet';
      return {
        initialValues: { opacity: 1, transform: [{ translateY: 0 }] },
        animations: { opacity: withTiming(0, config), transform: [{ translateY: withTiming(microMotion.toastRise, config) }] },
      };
    };
  },
  /** A photo added to the capture pops in (MovCaptura `.entra`). */
  thumbIn: () =>
    new Keyframe({
      0: { opacity: 0, transform: [{ scale: captureMotion.thumbFrom }] },
      [captureMotion.thumbPeakAt]: { opacity: 1, transform: [{ scale: captureMotion.thumbOvershoot }], easing: easings.enter },
      100: { opacity: 1, transform: [{ scale: 1 }], easing: easings.enter },
    })
      .duration(durations.base)
      .reduceMotion(reduce()),
};

// ---------------------------------------------------------------- Tu turno and Notificaciones (MovTuTurno, MovNotificaciones)
// Gustavo's phase 2 boards. Tu turno: a card resolved with its button shows a check, holds it, then
// collapses while the list closes the gap; only then do the counters roll (each group's, the top bar
// badge). «Más tarde» first slides the card toward «Pospuestas». A swiped card has already left under
// the finger and goes through the same gap and counters. Notificaciones: a new one opens its space at
// the top, the bell sways and its dot pulses; «Marcar todo como leído» turns «Nueva» off in a cascade.
import { type EntryAnimationsValues, type ExitAnimationsValues, type LayoutAnimation } from 'react-native-reanimated';  // withDelay/withTiming: top import

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
