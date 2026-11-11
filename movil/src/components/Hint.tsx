// Usage hints («cómo usar la app») are temporary: each one leaves by itself after `visibleMs` and a sideways swipe
// (or the screen reader's «Quitar el aviso») removes it. A hint with `persistId` never comes back once swiped (one
// SecureStore flag per hint, read once per launch); one without it calls `onDismiss`, so its owner decides.
import * as SecureStore from 'expo-secure-store';
import { useEffect, useState, useSyncExternalStore, type ReactNode } from 'react';
import type { StyleProp, ViewStyle } from 'react-native';
import { GestureDetector, usePanGesture } from 'react-native-gesture-handler';
import Animated, { runOnJS, useAnimatedStyle, useSharedValue, withSpring, withTiming } from 'react-native-reanimated';
import { captureMotion, gestures, spring, timing, useMotion } from '@/theme/motion';

// Built on the JS thread: spring()/timing() are not worklets (SwipeableCard does the same).
const SNAP_BACK = spring('snapBack');
const SWIPE_EXIT = timing('swipeExit');
const FADE = timing('swipeExit');
/** How long the swipe or the fade plays before the hint unmounts (ms). */
const LEAVE_MS = 220;

const PREFIX = 'oficina.aviso.';
const dismissed = new Map<string, boolean>();
const loading = new Set<string>();
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((listener) => listener());
const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};

async function load(id: string) {
  if (dismissed.has(id) || loading.has(id)) return;
  loading.add(id);
  let value: boolean;
  try {
    value = (await SecureStore.getItemAsync(PREFIX + id)) === '1';
  } catch {
    value = false;
  }
  loading.delete(id);
  if (!dismissed.has(id)) dismissed.set(id, value);
  emit();
}

/** Removes a hint for good (also for its next mounts and launches). */
export function dismissHint(id: string) {
  dismissed.set(id, true);
  SecureStore.setItemAsync(PREFIX + id, '1').catch(() => undefined);
  emit();
}

/** True while unknown, so a hint never flashes before its flag loads. */
export function useHintDismissed(id: string | undefined): boolean {
  useEffect(() => {
    if (id) void load(id);
  }, [id]);
  return useSyncExternalStore(subscribe, () => (id ? (dismissed.get(id) ?? true) : false), () => true);
}

/** For tests: forget what was read or swiped in this process. */
export function resetHintsForTests() {
  dismissed.clear();
  loading.clear();
}

export interface DismissibleHintProps {
  children: ReactNode;
  /** Remembers the swipe for good under this id; without it, `onDismiss` owns that. */
  persistId?: string;
  onDismiss?: () => void;
  /** How long it stays before leaving by itself (it shows again on the next visit). */
  visibleMs?: number;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

export function DismissibleHint({ children, persistId, onDismiss, visibleMs = captureMotion.hintMs, style, testID }: DismissibleHintProps) {
  const { reduced } = useMotion();
  const gone = useHintDismissed(persistId);
  const [up, setUp] = useState(true);
  const [width, setWidth] = useState(320);
  const x = useSharedValue(0);
  const opacity = useSharedValue(1);

  useEffect(() => {
    if (gone || !up) return;
    const timer = setTimeout(() => {
      if (reduced) return setUp(false);
      opacity.set(withTiming(0, FADE));
      setTimeout(() => setUp(false), LEAVE_MS);
    }, visibleMs);
    return () => clearTimeout(timer);
  }, [gone, up, visibleMs, reduced, opacity]);

  const dismiss = () => {
    if (persistId) dismissHint(persistId);
    onDismiss?.();
    if (reduced) setUp(false);
    else setTimeout(() => setUp(false), LEAVE_MS);
  };

  const pan = usePanGesture({
    testID: testID ? `${testID}-swipe` : undefined,
    activeOffsetX: [-gestures.swipe.activeOffsetX, gestures.swipe.activeOffsetX],
    failOffsetY: [-gestures.swipe.failOffsetY, gestures.swipe.failOffsetY],
    onUpdate: (event) => {
      'worklet';
      x.set(event.translationX);
    },
    onDeactivate: (event) => {
      'worklet';
      const out = Math.abs(event.translationX) > width * gestures.swipe.commitFraction || Math.abs(event.velocityX) > gestures.swipe.commitVelocity;
      if (!out) {
        x.set(withSpring(0, SNAP_BACK));
        return;
      }
      const side = (event.translationX || event.velocityX) < 0 ? -1 : 1;
      x.set(withTiming(side * width * 1.2, SWIPE_EXIT));
      runOnJS(dismiss)();
    },
  });

  const moving = useAnimatedStyle(() => ({
    opacity: opacity.value * Math.max(0, 1 - Math.abs(x.value) / Math.max(1, width)),
    transform: [{ translateX: x.value }],
  }));

  if (gone || !up) return null;
  return (
    <GestureDetector gesture={pan}>
      <Animated.View
        testID={testID}
        style={[style, moving]}
        onLayout={(event) => setWidth(event.nativeEvent.layout.width)}
        accessibilityHint="Desliza a un lado para quitarlo"
        accessibilityActions={[{ name: 'dismiss', label: 'Quitar el aviso' }]}
        onAccessibilityAction={(event) => {
          if (event.nativeEvent.actionName === 'dismiss') dismiss();
        }}
      >
        {children}
      </Animated.View>
    </GestureDetector>
  );
}
