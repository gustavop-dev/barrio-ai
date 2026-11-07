// Bottom sheet with two snap points, for content you browse (the calendar's day panel): it opens at
// half height, the handle and the header drag it between half and full (or down to close), a tap on
// the handle switches them, and «Cerrar», the backdrop and Android back close it. Heights, thresholds
// and the spring come from motion.ts (gestures.snapSheet, springs.sheetSnap).
//
// It is a Modal, so it stays over whatever comes next: content that navigates, or that shows a toast
// (the toast lives under the Modal), closes the sheet first through `useSnapSheet()`.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import { GestureDetector, GestureHandlerRootView, usePanGesture } from 'react-native-gesture-handler';
import Animated, { runOnJS, useAnimatedStyle, useSharedValue, withSpring, withTiming } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Icon } from '@/components/icons';
import { gestures, haptic, spring, timing } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';

export type SnapPoint = 'half' | 'full';

export interface SnapSheetControls {
  /** Slides the sheet down, then calls onClose. */
  dismiss: () => void;
  /** Closes it at once: before navigating, so the Modal does not stay over the next screen. */
  close: () => void;
}

const SnapSheetContext = createContext<SnapSheetControls | null>(null);

/** The enclosing snap sheet, or null outside one. */
export function useSnapSheet(): SnapSheetControls | null {
  return useContext(SnapSheetContext);
}

/** translateY of each snap point for a window height: the panel is as tall as the full point. */
export function snapOffsets(windowHeight: number): { panel: number; full: number; half: number; closed: number } {
  const panel = Math.round(windowHeight * gestures.snapSheet.full);
  return { panel, full: 0, half: Math.max(0, panel - Math.round(windowHeight * gestures.snapSheet.half)), closed: panel };
}

/** Where a released drag goes: a flick moves one point (or closes from half); otherwise the nearest point, or closed well below half. */
export function snapTarget(position: number, velocity: number, offsets: { half: number }): SnapPoint | 'closed' {
  const { flickVelocity, dismissDistance } = gestures.snapSheet;
  if (velocity <= -flickVelocity) return 'full';
  if (velocity >= flickVelocity) return position < offsets.half ? 'half' : 'closed';
  if (position > offsets.half + dismissDistance) return 'closed';
  return position < offsets.half / 2 ? 'full' : 'half';
}

export interface SnapSheetProps {
  /** Accessible name of the sheet. */
  label: string;
  onClose: () => void;
  children: ReactNode;
  /** Stays above the scrolling content and drags the sheet like the handle. */
  header?: ReactNode;
  initialSnap?: SnapPoint;
  testID?: string;
}

export function SnapSheet({ label, onClose, children, header, initialSnap = 'half', testID }: SnapSheetProps) {
  const { height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const offsets = useMemo(() => snapOffsets(height), [height]);
  const offset = useSharedValue(offsets.closed);
  const start = useSharedValue(0);
  const backdrop = useSharedValue(0);
  const [snap, setSnap] = useState<SnapPoint>(initialSnap);
  const current = useRef<SnapPoint>(initialSnap);
  const closing = useRef(false);

  const moveTo = useCallback(
    (point: SnapPoint) => {
      if (current.current !== point) haptic('sheetSnap');
      current.current = point;
      setSnap(point);
      offset.set(withSpring(offsets[point], spring('sheetSnap')));
    },
    [offset, offsets],
  );

  useEffect(() => {
    offset.set(withSpring(offsets[initialSnap], spring('sheetOpen')));
    backdrop.set(withTiming(1, timing('backdrop')));
    // Only on opening: later snaps go through moveTo.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const dismiss = useCallback(() => {
    if (closing.current) return;
    closing.current = true;
    backdrop.set(withTiming(0, timing('backdrop')));
    offset.set(
      withTiming(offsets.closed, timing('sheetClose'), (finished) => {
        if (finished) runOnJS(onClose)();
      }),
    );
  }, [backdrop, offset, offsets.closed, onClose]);

  const close = useCallback(() => {
    if (closing.current) return;
    closing.current = true;
    onClose();
  }, [onClose]);

  const release = useCallback(
    (position: number, velocity: number) => {
      const target = snapTarget(position, velocity, offsets);
      if (target === 'closed') dismiss();
      else moveTo(target);
    },
    [offsets, dismiss, moveTo],
  );

  const drag = usePanGesture({
    testID: testID ? `${testID}-drag` : undefined,
    activeOffsetY: [-8, 8],
    onActivate: () => {
      'worklet';
      start.set(offset.value);
    },
    onUpdate: (event) => {
      'worklet';
      offset.set(Math.min(offsets.closed, Math.max(offsets.full, start.value + event.translationY)));
    },
    onDeactivate: (event) => {
      'worklet';
      runOnJS(release)(start.value + event.translationY, event.velocityY);
    },
  });

  const panel = useAnimatedStyle(() => ({ transform: [{ translateY: offset.value }] }));
  const shade = useAnimatedStyle(() => ({ opacity: backdrop.value }));
  const controls = useMemo(() => ({ dismiss, close }), [dismiss, close]);

  return (
    <Modal transparent visible animationType="none" statusBarTranslucent navigationBarTranslucent onRequestClose={dismiss}>
      <GestureHandlerRootView style={styles.root}>
        <Animated.View style={[StyleSheet.absoluteFill, styles.backdrop, shade]}>
          <Pressable style={StyleSheet.absoluteFill} accessibilityLabel="Cerrar" accessibilityRole="button" onPress={dismiss} />
        </Animated.View>
        <Animated.View testID={testID} accessibilityViewIsModal accessibilityLabel={label} style={[styles.sheet, { height: offsets.panel }, panel]}>
          <GestureDetector gesture={drag}>
            <View style={styles.grab}>
              <View style={styles.bar}>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={snap === 'half' ? 'Expandir el panel' : 'Reducir el panel'}
                  onPress={() => moveTo(snap === 'half' ? 'full' : 'half')}
                  style={styles.handleArea}
                  testID={testID ? `${testID}-handle` : undefined}
                >
                  <View style={styles.handle} />
                </Pressable>
                <Pressable accessibilityRole="button" accessibilityLabel="Cerrar" onPress={dismiss} style={styles.close} hitSlop={4}>
                  <Icon name="cerrar" size={20} color={colors.inkSoft} />
                </Pressable>
              </View>
              {header}
            </View>
          </GestureDetector>
          <SnapSheetContext.Provider value={controls}>
            <ScrollView
              style={styles.scroll}
              keyboardShouldPersistTaps="handled"
              contentContainerStyle={[styles.content, { paddingBottom: (snap === 'half' ? offsets.half : 0) + insets.bottom + space[6] }]}
              showsVerticalScrollIndicator={false}
            >
              {children}
            </ScrollView>
          </SnapSheetContext.Provider>
        </Animated.View>
      </GestureHandlerRootView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  backdrop: { backgroundColor: colors.backdrop },
  sheet: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.sheet,
    borderTopRightRadius: radius.sheet,
    paddingHorizontal: space[4],
  },
  grab: { paddingBottom: space[2], gap: space[2] },
  bar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center' },
  handleArea: { flex: 1, minHeight: shell.touch, alignItems: 'center', justifyContent: 'center', marginLeft: shell.touch },
  handle: { width: 40, height: 4, borderRadius: radius.pill, backgroundColor: colors.line },
  close: { width: shell.touch, height: shell.touch, alignItems: 'center', justifyContent: 'center' },
  scroll: { flex: 1 },
  content: { gap: space[6] },
});
