// The aguamarina capture button in the centre of the bottom bar (Captura.dc.html), press and hold:
// - a short tap opens the sheet without recording;
// - holding (gestures.capture.holdDelayMs) grows the button to 72 px and records, with the red dot,
//   the time, the wave and the lock;
// - sliding up locks the recording: it carries on in the sheet, on the pulsing ball;
// - sliding left discards it, with «Recuperar» in the toast;
// - releasing without locking ends it and opens the sheet with the audio ready (never sent alone).
// The microphone is asked for only after explaining why (in the sheet).
import { mmss } from '@compartido/logic/audio';
import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState, StyleSheet, View, useWindowDimensions } from 'react-native';
import { GestureDetector, useExclusiveGestures, usePanGesture, useTapGesture } from 'react-native-gesture-handler';
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from 'react-native-reanimated';
import { Icon } from '@/components/icons';
import { T, useToast } from '@/components/ui';
import { gestures, haptic, layout, spring } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import { holdDecision, holdLift, isTooShort } from './hold';
import { Pulse } from './Pulse';
import { useRecorder, useRecorderLive, type MicState } from './recorder';
import { markCaptureUsed, openCaptureSheet, useCaptureUsed } from './store';
import { Wave } from './Wave';

export const CAPTURE_LABEL = 'Capturar: mantén oprimido para grabar audio, o toca para foto o nota';

type HoldMode = 'idle' | 'recording' | 'handled';

/** Where the bar's centre slot starts, so the overlay can span the whole screen width. */
interface SlotFrame {
  x: number;
  screenWidth: number;
}

function HoldOverlay({ lift, frame }: { lift: ReturnType<typeof useSharedValue<number>>; frame: SlotFrame }) {
  const live = useRecorderLive();
  const lock = useAnimatedStyle(() => ({ transform: [{ translateY: lift.value }] }));
  const fullWidth = { left: -frame.x, width: frame.screenWidth };
  // Positions are from the bar's top edge: the strip sits on it, the lock and its hint above.
  return (
    <Animated.View entering={layout.overlayIn()} exiting={layout.overlayOut()} pointerEvents="none" style={styles.overlay}>
      <Animated.View style={[styles.lock, { bottom: shell.tabBarHeight + 86 }, lock]}>
        <Icon name="candado" size={22} />
        <Icon name="chevronUp" size={18} />
      </Animated.View>
      <View style={[styles.lockHint, fullWidth, { bottom: shell.tabBarHeight + 62 }]}>
        <T variant="detalle" style={styles.lockHintText}>
          Desliza hacia arriba para bloquear
        </T>
      </View>
      <View
        style={[styles.holdBar, fullWidth, { bottom: shell.tabBarHeight }]}
        accessibilityLiveRegion="polite"
        accessibilityLabel="Grabando audio. Suelta para terminar, desliza hacia arriba para bloquear o hacia la izquierda para descartar."
      >
        <Pulse kind="recordDot" style={styles.dot} />
        <T style={styles.time}>{mmss(live.elapsed)}</T>
        <Wave levels={live.levels} tone="suave" />
        <T variant="detalle" soft>
          ‹ Desliza para cancelar
        </T>
      </View>
    </Animated.View>
  );
}

export function CaptureButton() {
  const toast = useToast();
  const recorder = useRecorder();
  const used = useCaptureUsed();
  const [holding, setHolding] = useState(false);
  const { width: screenWidth } = useWindowDimensions();
  const [slotX, setSlotX] = useState(0);
  const size = useSharedValue<number>(shell.captureButton);
  const lift = useSharedValue(0);
  const mode = useRef<HoldMode>('idle');
  const pressedAt = useRef(0);
  const mic = useRef<MicState>('explain');

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

  const settle = useCallback(() => {
    setHolding(false);
    size.set(withSpring(shell.captureButton, spring('captureGrow')));
    lift.set(withSpring(0, spring('captureFollow')));
  }, [size, lift]);

  const beginHold = useCallback(() => {
    markCaptureUsed();
    if (mic.current !== 'granted') {
      // Explain before the system asks, or say why there is no audio.
      mode.current = 'handled';
      openCaptureSheet(undefined, { mic: mic.current === 'denied' ? 'denied' : 'explain' });
      return;
    }
    mode.current = 'recording';
    haptic('captureStart');
    setHolding(true);
    size.set(withSpring(shell.captureButtonHolding, spring('captureGrow')));
    void recorder.start().then((started) => {
      if (started || mode.current !== 'recording') return;
      mode.current = 'handled';
      settle();
      openCaptureSheet(undefined, { mic: 'error' });
    });
  }, [recorder, settle, size]);

  const move = useCallback(
    (dx: number, dy: number) => {
      if (mode.current !== 'recording') return;
      const decision = holdDecision(dx, dy);
      if (decision === 'lock') {
        mode.current = 'handled';
        haptic('captureLock');
        settle();
        openCaptureSheet(undefined, { recording: true });
        return;
      }
      if (decision === 'discard') {
        mode.current = 'handled';
        haptic('captureDiscard');
        settle();
        void recorder.discard().then((audio) => {
          toast.show('Grabación descartada.', audio ? { undo: () => openCaptureSheet(undefined, { audio }), undoLabel: 'Recuperar' } : {});
        });
        return;
      }
      lift.set(withSpring(holdLift(dy), spring('captureFollow')));
    },
    [lift, recorder, settle, toast],
  );

  const release = useCallback(() => {
    const was = mode.current;
    mode.current = 'idle';
    if (was !== 'recording') return;
    settle();
    if (isTooShort(pressedAt.current, Date.now())) {
      void recorder.discard();
      openCaptureSheet();
      return;
    }
    void recorder.stop().then((audio) => {
      openCaptureSheet(undefined, audio ? { audio } : recorder.failed ? { mic: 'error' } : {});
    });
  }, [recorder, settle]);

  const tap = useTapGesture({
    maxDuration: gestures.capture.holdDelayMs,
    runOnJS: true,
    testID: 'capture-tap',
    onActivate: () => {
      markCaptureUsed();
      openCaptureSheet();
    },
  });

  const hold = usePanGesture({
    activateAfterLongPress: gestures.capture.holdDelayMs,
    runOnJS: true,
    testID: 'capture-hold',
    onBegin: () => {
      pressedAt.current = Date.now();
    },
    onActivate: () => beginHold(),
    onUpdate: (event) => move(event.translationX, event.translationY),
    onDeactivate: () => release(),
    onFinalize: () => {
      if (mode.current === 'handled') mode.current = 'idle';
    },
  });

  const gesture = useExclusiveGestures(hold, tap);

  const button = useAnimatedStyle(() => ({
    width: size.value,
    height: size.value,
    // The bottom edge stays put while it grows (60 px at -22, 72 px at -34).
    marginTop: shell.captureButton - shell.captureLift - size.value,
    transform: [{ translateY: lift.value }],
  }));

  return (
    <View style={styles.slot} onLayout={(event) => setSlotX(event.nativeEvent.layout.x)}>
      {!used && !holding ? (
        <View style={styles.hint} pointerEvents="none">
          <T variant="detalle" color={colors.paper} center>
            Mantén oprimido para grabar. Toca para foto o nota.
          </T>
        </View>
      ) : null}
      {holding ? <HoldOverlay lift={lift} frame={{ x: slotX, screenWidth }} /> : null}
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
          <Icon name="microfono" size={holding ? 30 : 26} color={colors.onBrand} />
        </Animated.View>
      </GestureDetector>
    </View>
  );
}

const styles = StyleSheet.create({
  slot: { flex: 1, height: shell.tabBarHeight, alignItems: 'center', justifyContent: 'flex-start', overflow: 'visible' },
  overlay: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, alignItems: 'center' },
  button: {
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
    width: 64,
    paddingVertical: space[3],
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    alignItems: 'center',
    gap: 6,
  },
  lockHint: { position: 'absolute', left: 0, right: 0, alignItems: 'center' },
  lockHintText: { paddingHorizontal: 10, paddingVertical: 2, borderRadius: radius.pill, backgroundColor: colors.surface, overflow: 'hidden' },
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
