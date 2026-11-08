// The aguamarina capture button in the centre of the bottom bar (Captura.dc.html), moving as in
// MovCaptura:
// - a short tap opens the sheet without recording, and the button turns into the sheet's audio ball;
// - holding (gestures.capture.holdDelayMs) grows it to 1.2 on SOFT and records («HÁPTICO · MEDIO»):
//   the strip rises with the time and the lock appears above it;
// - the button follows 60 % of the finger. Sliding up dims the screen and fills the lock; at the lock
//   point the shackle drops («ÉXITO») and the recording carries on in the sheet;
// - sliding left opens the trash; at the discard point the button falls into it («AVISO»), the trash
//   closes, the button pops back and the toast offers «Recuperar»;
// - releasing without locking ends it and opens the sheet with the audio ready (never sent alone);
// - after «Guardar» the button pulses.
// The finger is followed on the UI thread; the microphone is asked for only after explaining why (in the sheet).
import { mmss } from '@compartido/logic/audio';
import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState, StyleSheet, View, useWindowDimensions } from 'react-native';
import { GestureDetector, useExclusiveGestures, usePanGesture, useTapGesture } from 'react-native-gesture-handler';
import Animated, { runOnJS, useAnimatedStyle, useSharedValue, withSequence, withSpring, withTiming, type SharedValue } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Icon } from '@/components/icons';
import { T, useToast } from '@/components/ui';
import { captureMotion, durations, gestures, haptic, spring, springWith, timingWith } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import { lerp } from './choreo';
import { LockGlyph, TrashGlyph } from './glyphs';
import { discardProgress, holdDecision, holdFollow, isTooShort, lockProgress } from './hold';
import { useRecorder, useRecorderLive, type MicState } from './recorder';
import { markCaptureUsed, openCaptureSheet, useCaptureSentCount, useCaptureSheet, useCaptureUsed } from './store';
import type { CaptureOrigin } from './types';
import { Wave } from './Wave';

export const CAPTURE_LABEL = 'Capturar: mantén oprimido para grabar audio, o toca para foto o nota';

/** The gesture's phase, shared with the UI thread. */
const IDLE = 0;
const RECORDING = 1;
const HANDLED = 2;

/** MovCaptura's overlay, from the bar's top edge: the lock (56 × 92) 86 above it, the trash (48) 10 above it and 22 from the screen's left edge. */
const LOCK = { width: 56, height: 92, above: 86 } as const;
const TRASH = { size: 48, left: 22, above: 10 } as const;
/** The trash's centre from the button's centre, vertically (the button's centre is captureButton/2 − captureLift under the bar's top). */
const TRASH_DY = -(TRASH.above + TRASH.size / 2) - (shell.captureButton / 2 - shell.captureLift);
/** The button at rest, for a tap. */
const AT_REST: CaptureOrigin = { lift: 0, scale: 1 };

interface HoldValues {
  phase: SharedValue<number>;
  dy: SharedValue<number>;
  dx: SharedValue<number>;
  bar: SharedValue<number>;
  lockOn: SharedValue<number>;
  shut: SharedValue<number>;
  trashOn: SharedValue<number>;
  drop: SharedValue<number>;
  canceling: SharedValue<number>;
}

/** Everything around the held button: the dim, the strip with the time, the lock and the trash. */
function HoldOverlay({ values, holding, slotX, screenWidth, screenHeight, bottomInset }: { values: HoldValues; holding: boolean; slotX: number; screenWidth: number; screenHeight: number; bottomInset: number }) {
  const live = useRecorderLive();
  const { phase, dy, dx, bar, lockOn, shut, trashOn, drop, canceling } = values;
  const fullWidth = { left: -slotX, width: screenWidth };
  const dim = useAnimatedStyle(() => ({ opacity: phase.value === RECORDING ? lockProgress(dy.value) * captureMotion.holdDim : 0 }));
  const strip = useAnimatedStyle(() => ({
    opacity: bar.value * (1 - discardProgress(dx.value) * captureMotion.barCancelFade),
    transform: [{ translateY: (1 - bar.value) * captureMotion.barRise }],
  }));
  const lock = useAnimatedStyle(() => {
    const dragP = lockProgress(dy.value);
    return {
      opacity: lockOn.value * (captureMotion.lockRestOpacity + (1 - captureMotion.lockRestOpacity) * dragP) * (1 - discardProgress(dx.value)),
      transform: [
        { translateY: captureMotion.lockRise * (1 - lockOn.value) + dy.value * captureMotion.lockFollow },
        { scale: captureMotion.lockRestScale + (1 - captureMotion.lockRestScale) * Math.max(dragP, shut.value) },
      ],
    };
  });
  const hint = useAnimatedStyle(() => ({ opacity: lockOn.value * (1 - discardProgress(dx.value)) }));
  const shackle = useAnimatedStyle(() => ({ transform: [{ translateY: shut.value * captureMotion.shackleDrop }] }));
  const arrow = useAnimatedStyle(() => ({ opacity: 1 - lockProgress(dy.value) }));
  const trash = useAnimatedStyle(() => ({
    opacity: trashOn.value,
    transform: [{ scale: captureMotion.trashRestScale + (1 - captureMotion.trashRestScale) * trashOn.value }],
  }));
  const lid = useAnimatedStyle(() => {
    const open = Math.min(1, Math.max(0, discardProgress(dx.value) + (canceling.value ? 1 - drop.value : 0)));
    return { transform: [{ rotate: `${captureMotion.lidOpenDeg * open}deg` }] };
  });
  // Positions are from the bar's top edge (the slot's top).
  return (
    <View
      pointerEvents="none"
      style={styles.overlay}
      // Always there for its exit; screen readers only hear it while holding.
      importantForAccessibility={holding ? 'auto' : 'no-hide-descendants'}
      accessibilityElementsHidden={!holding}
    >
      <Animated.View style={[styles.dim, fullWidth, { bottom: -bottomInset, height: screenHeight }, dim]} />
      <Animated.View
        style={[styles.holdBar, fullWidth, { bottom: shell.tabBarHeight }, strip]}
        accessibilityLiveRegion="polite"
        accessibilityLabel="Grabando audio. Suelta para terminar, desliza hacia arriba para bloquear o hacia la izquierda para descartar."
      >
        <View style={styles.dot} />
        <T style={styles.time}>{mmss(live.elapsed)}</T>
        <Wave levels={live.levels} tone="suave" />
        <T variant="detalle" soft>
          ‹ Desliza para cancelar
        </T>
      </Animated.View>
      <Animated.View style={[styles.lockHint, fullWidth, { bottom: shell.tabBarHeight + 62 }, hint]}>
        <T variant="detalle" style={styles.lockHintText}>
          Desliza hacia arriba para bloquear
        </T>
      </Animated.View>
      <Animated.View style={[styles.lock, { bottom: shell.tabBarHeight + LOCK.above }, lock]}>
        <LockGlyph shackle={shackle} />
        <Animated.View style={arrow}>
          <Icon name="chevronUp" size={18} />
        </Animated.View>
      </Animated.View>
      <Animated.View style={[styles.trash, { left: TRASH.left - slotX, bottom: shell.tabBarHeight + TRASH.above }, trash]}>
        <TrashGlyph lid={lid} />
      </Animated.View>
    </View>
  );
}

export function CaptureButton() {
  const toast = useToast();
  const recorder = useRecorder();
  const used = useCaptureUsed();
  const sheet = useCaptureSheet();
  const sentCount = useCaptureSentCount();
  const insets = useSafeAreaInsets();
  const [holding, setHolding] = useState(false);
  const { width: screenWidth, height: screenHeight } = useWindowDimensions();
  const [slot, setSlot] = useState({ x: 0, width: 0 });
  const phase = useSharedValue(IDLE);
  const press = useSharedValue(1);
  const dy = useSharedValue(0);
  const dx = useSharedValue(0);
  const bar = useSharedValue(0);
  const lockOn = useSharedValue(0);
  const shut = useSharedValue(0);
  const trashOn = useSharedValue(0);
  const drop = useSharedValue(0);
  const canceling = useSharedValue(0);
  const pulse = useSharedValue(1);
  const hidden = useSharedValue(0);
  const pressedAt = useSharedValue(0);
  const trashDX = useSharedValue(0);
  const mic = useRef<MicState>('explain');
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  // Keep the permission known before the first hold (and after a trip to the system settings).
  useEffect(() => {
    const refresh = () => {
      recorder
        .micState()
        .then((state) => {
          mic.current = state;
        })
        .catch(() => undefined);
    };
    refresh();
    const subscription = AppState.addEventListener('change', (status) => status === 'active' && refresh());
    return () => subscription.remove();
  }, [recorder]);

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach(clearTimeout);
  }, []);

  // The trash's centre from the button's centre, horizontally (the button is in the middle of its slot).
  useEffect(() => {
    trashDX.set(TRASH.left + TRASH.size / 2 - (slot.x + slot.width / 2));
  }, [slot, trashDX]);

  // While the sheet it turned into is open the button is gone; it is back when the sheet closes.
  useEffect(() => {
    if (!sheet.open) hidden.set(0);
  }, [sheet.open, hidden]);

  // «Guardar»: the button pulses from 1.18 back to 1 (SOFT).
  const seenSent = useRef(sentCount);
  useEffect(() => {
    if (sentCount === seenSent.current) return;
    seenSent.current = sentCount;
    pulse.set(withSequence(withTiming(captureMotion.sentPulse, { duration: 0 }), withSpring(1, springWith(captureMotion.pulse))));
  }, [sentCount, pulse]);

  /** Where the button is now, for the ball that takes its place. */
  const origin = useCallback((): CaptureOrigin => ({ lift: dy.get(), scale: press.get() }), [dy, press]);

  /** The hold ends into the sheet: strip, lock and trash go (fast, EASE_IN), the button goes back on FIRM. */
  const settle = useCallback(() => {
    setHolding(false);
    const out = timingWith(durations.fast, 'exit');
    bar.set(withTiming(0, out));
    lockOn.set(withTiming(0, out));
    trashOn.set(withTiming(0, out));
    dy.set(withSpring(0, spring('captureFollow')));
    dx.set(withSpring(0, spring('captureFollow')));
    press.set(withSpring(1, spring('captureFollow')));
  }, [bar, lockOn, trashOn, dy, dx, press]);

  const beginHold = useCallback(() => {
    markCaptureUsed();
    if (mic.current !== 'granted') {
      // Explain before the system asks, or say why there is no audio.
      phase.set(HANDLED);
      openCaptureSheet(undefined, { mic: mic.current === 'denied' ? 'denied' : 'explain' });
      return;
    }
    phase.set(RECORDING);
    haptic('captureStart');
    setHolding(true);
    shut.set(0);
    const enter = timingWith(durations.fast, 'enter');
    press.set(withSpring(captureMotion.holdScale, spring('captureGrow')));
    bar.set(withTiming(1, enter));
    lockOn.set(withTiming(1, enter));
    void recorder.start().then((started) => {
      if (started || phase.get() !== RECORDING) return;
      phase.set(HANDLED);
      settle();
      openCaptureSheet(undefined, { mic: 'error' });
    });
  }, [recorder, settle, phase, shut, press, bar, lockOn]);

  /** Slid up: the shackle drops and the recording carries on in the sheet. */
  const lockNow = useCallback(() => {
    haptic('captureLock');
    shut.set(withTiming(1, timingWith(captureMotion.shackleMs, 'enter')));
    const from = origin();
    settle();
    hidden.set(1);
    openCaptureSheet(undefined, { recording: true, from });
  }, [origin, settle, shut, hidden]);

  /** Slid left: the button falls into the trash, which closes; then the button pops back and the toast offers «Recuperar». */
  const discardNow = useCallback(() => {
    haptic('captureDiscard');
    const out = timingWith(durations.fast, 'exit');
    canceling.set(1);
    drop.set(withTiming(1, out));
    bar.set(withTiming(0, out));
    lockOn.set(withTiming(0, out));
    const recovered = recorder.discard();
    timers.current.push(
      setTimeout(() => {
        trashOn.set(withTiming(0, timingWith(durations.fast, 'enter')));
        dx.set(0);
        dy.set(0);
        drop.set(0);
        canceling.set(0);
        shut.set(0);
        press.set(withSequence(withTiming(0, { duration: 0 }), withSpring(1, spring('captureGrow'))));
        setHolding(false);
        void recovered.then((audio) => {
          toast.show('Grabación descartada.', audio ? { undo: () => openCaptureSheet(undefined, { audio }), undoLabel: 'Recuperar' } : {});
        });
      }, durations.fast + captureMotion.trashLingerMs),
    );
  }, [recorder, toast, canceling, drop, bar, lockOn, trashOn, dx, dy, shut, press]);

  const release = useCallback(() => {
    if (phase.get() !== RECORDING) return;
    phase.set(IDLE);
    const from = origin();
    const tooShort = isTooShort(pressedAt.get(), Date.now());
    settle();
    hidden.set(1);
    if (tooShort) {
      void recorder.discard();
      openCaptureSheet(undefined, { from });
      return;
    }
    void recorder.stop().then((audio) => {
      openCaptureSheet(undefined, audio ? { audio, from } : recorder.failed ? { mic: 'error' } : { from });
    });
  }, [recorder, settle, origin, phase, pressedAt, hidden]);

  const tap = useTapGesture({
    maxDuration: gestures.capture.holdDelayMs,
    runOnJS: true,
    testID: 'capture-tap',
    onActivate: () => {
      markCaptureUsed();
      hidden.set(1);
      openCaptureSheet(undefined, { from: AT_REST });
    },
  });

  const hold = usePanGesture({
    activateAfterLongPress: gestures.capture.holdDelayMs,
    testID: 'capture-hold',
    onBegin: () => {
      'worklet';
      pressedAt.value = Date.now();
    },
    onActivate: () => {
      'worklet';
      runOnJS(beginHold)();
    },
    onUpdate: (event) => {
      'worklet';
      if (phase.value !== RECORDING) return;
      dy.value = holdFollow(event.translationY);
      dx.value = holdFollow(event.translationX);
      const cancelP = discardProgress(dx.value);
      if (cancelP > captureMotion.trashShowAt) trashOn.value = Math.max(trashOn.value, cancelP);
      const decision = holdDecision(event.translationX, event.translationY);
      if (decision === 'none') return;
      phase.value = HANDLED;
      if (decision === 'lock') runOnJS(lockNow)();
      else runOnJS(discardNow)();
    },
    onDeactivate: () => {
      'worklet';
      runOnJS(release)();
    },
    onFinalize: () => {
      'worklet';
      if (phase.value === HANDLED) phase.value = IDLE;
    },
  });

  const gesture = useExclusiveGestures(hold, tap);

  const button = useAnimatedStyle(() => {
    const falling = canceling.value === 1;
    const d = drop.value;
    return {
      opacity: hidden.value ? 0 : falling ? 1 - d : 1,
      transform: [
        { translateX: falling ? lerp(dx.value, trashDX.value, d) : dx.value },
        { translateY: falling ? lerp(dy.value, TRASH_DY, d) : dy.value },
        { scale: falling ? lerp(press.value, captureMotion.dropScale, d) : press.value * pulse.value },
      ],
    };
  });

  return (
    <View style={styles.slot} onLayout={(event) => setSlot({ x: event.nativeEvent.layout.x, width: event.nativeEvent.layout.width })}>
      {!used && !holding ? (
        <View style={styles.hint} pointerEvents="none">
          <T variant="detalle" color={colors.paper} center>
            Mantén oprimido para grabar. Toca para foto o nota.
          </T>
        </View>
      ) : null}
      <HoldOverlay
        values={{ phase, dy, dx, bar, lockOn, shut, trashOn, drop, canceling }}
        holding={holding}
        slotX={slot.x}
        screenWidth={screenWidth}
        screenHeight={screenHeight}
        bottomInset={insets.bottom}
      />
      <GestureDetector gesture={gesture}>
        <Animated.View
          testID="capture-button"
          accessible
          accessibilityRole="button"
          accessibilityLabel={CAPTURE_LABEL}
          accessibilityActions={[
            { name: 'activate', label: 'Abrir la hoja de captura' },
            { name: 'longpress', label: 'Grabar un audio' },
          ]}
          onAccessibilityAction={(event) => {
            markCaptureUsed();
            if (event.nativeEvent.actionName === 'longpress') openCaptureSheet(undefined, { mic: mic.current === 'granted' ? undefined : mic.current === 'denied' ? 'denied' : 'explain' });
            else openCaptureSheet();
          }}
          style={[styles.button, button]}
        >
          <Icon name="microfono" size={26} color={colors.onBrand} />
        </Animated.View>
      </GestureDetector>
    </View>
  );
}

const styles = StyleSheet.create({
  // Above the tabs beside it, so the overlay spans the whole bar.
  slot: { flex: 1, height: shell.tabBarHeight, alignItems: 'center', justifyContent: 'flex-start', overflow: 'visible', zIndex: 1 },
  overlay: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, alignItems: 'center' },
  dim: { position: 'absolute', backgroundColor: colors.backdrop },
  button: {
    width: shell.captureButton,
    height: shell.captureButton,
    marginTop: -shell.captureLift,
    borderRadius: radius.pill,
    borderWidth: 4,
    borderColor: colors.surface,
    backgroundColor: colors.brand,
    alignItems: 'center',
    justifyContent: 'center',
  },
  hint: {
    position: 'absolute',
    bottom: shell.tabBarHeight + 32,
    width: 260,
    paddingVertical: 10,
    paddingHorizontal: space[3],
    borderRadius: radius.md,
    backgroundColor: colors.ink,
  },
  lock: {
    position: 'absolute',
    alignSelf: 'center',
    width: LOCK.width,
    height: LOCK.height,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    gap: space[1],
  },
  lockHint: { position: 'absolute', left: 0, right: 0, alignItems: 'center' },
  lockHintText: { paddingHorizontal: 10, paddingVertical: 2, borderRadius: radius.pill, backgroundColor: colors.surface, overflow: 'hidden' },
  trash: {
    position: 'absolute',
    width: TRASH.size,
    height: TRASH.size,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.alert,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  holdBar: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: 56,
    paddingHorizontal: space[4],
    flexDirection: 'row',
    alignItems: 'center',
    gap: space[3],
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  dot: { width: 12, height: 12, borderRadius: radius.pill, backgroundColor: colors.alert },
  time: { width: 44, fontVariant: ['tabular-nums'] },
});
