// Nonmodal sheet (MovHojas, backdrop off): the scene above it remains interactive. Drag only the
// handle, leaving content scroll native. Its position `p` (a fraction of the room above `bottom`) opens
// at the half snap on FIRM, follows the handle with a rubber band past the full snap, and on release is
// projected along its velocity to the nearest snap, or closes («HÁPTICO · LEVE» on each new snap).
// Accessible expand/collapse actions, Android back and an explicit close.
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { BackHandler, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import { GestureDetector, usePanGesture } from 'react-native-gesture-handler';
import Animated, { cancelAnimation, runOnJS, useAnimatedReaction, useAnimatedStyle, useSharedValue, withSpring } from 'react-native-reanimated';
import { haptic, officeGestures, rubberBand, sheetMotion, spring } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';
import { Button } from './Button';
import { settleSnap } from './Sheet';

export interface SnapSheetProps {
  label: string; onClose: () => void; children: ReactNode;
  bottom: number; availableHeight?: number; testID?: string;
}
export function SnapSheet({ label, onClose, children, bottom, availableHeight, testID }: SnapSheetProps) {
  const window = useWindowDimensions();
  const room = (availableHeight ?? window.height) - bottom;
  const [half, full] = sheetMotion.snaps;
  const p = useSharedValue(0);
  const span = useSharedValue(room);
  const snap = useSharedValue(0);
  const start = useSharedValue(0);
  const from = useSharedValue(0);
  const closing = useSharedValue(false);
  // The snap it rests on: the content gets the hidden part as bottom padding, so all of it can be reached.
  const [resting, setResting] = useState<number>(half);
  const closed = useRef(false);
  const latestClose = useRef(onClose);
  const firm = spring('sheetOpen');

  useEffect(() => {
    latestClose.current = onClose;
  }, [onClose]);
  useEffect(() => {
    span.set(room);
  }, [room, span]);

  const go = useCallback(
    (target: number) => {
      if (closing.get()) return;
      if (target !== snap.get() && target > 0) haptic('sheetSnap');
      snap.set(target);
      setResting(target);
      p.set(withSpring(target, spring('sheetOpen')));
    },
    [closing, snap, p],
  );

  const dismiss = useCallback(() => {
    if (closing.get()) return;
    closing.set(true);
    p.set(withSpring(0, spring('sheetOpen')));
  }, [closing, p]);

  const finish = useCallback(() => {
    if (closed.current) return;
    closed.current = true;
    latestClose.current();
  }, []);

  // Closing is FIRM too; the sheet is gone the moment p reaches 0.
  useAnimatedReaction(
    () => closing.value && p.value <= 0,
    (gone, was) => {
      if (gone && !was) runOnJS(finish)();
    },
  );

  // Opening: to the half snap (already the resting one), and it is a snap.
  const opened = useRef(false);
  useEffect(() => {
    if (opened.current) return;
    opened.current = true;
    haptic('sheetSnap');
    snap.set(half);
    p.set(withSpring(half, spring('sheetOpen')));
  }, [half, snap, p]);

  useEffect(() => {
    const listener = BackHandler.addEventListener('hardwareBackPress', () => { dismiss(); return true; });
    return () => listener.remove();
  }, [dismiss]);

  const drag = usePanGesture({
    testID: 'snap-sheet-drag', minDistance: officeGestures.sheetActivation,
    onActivate: (event) => {
      'worklet';
      if (closing.value) return;
      cancelAnimation(p);
      start.set(p.value);
      from.set(event.translationY);
    },
    onUpdate: (event) => {
      'worklet';
      if (closing.value) return;
      const raw = start.value - (event.translationY - from.value) / span.value;
      p.set(Math.max(0, rubberBand(raw, full)));
    },
    onDeactivate: (event) => {
      'worklet';
      if (closing.value) return;
      const target = event.canceled ? snap.value : settleSnap(p.value, -event.velocityY / span.value, sheetMotion.snaps);
      if (target === 0) {
        runOnJS(dismiss)();
        return;
      }
      if (target !== snap.value) runOnJS(haptic)('sheetSnap');
      snap.set(target);
      p.set(withSpring(target, firm));
      runOnJS(setResting)(target);
    },
  });
  const animated = useAnimatedStyle(() => ({ transform: [{ translateY: span.value * Math.max(0, 1 - Math.max(0, p.value)) }] }));
  return <Animated.View testID={testID} accessibilityLabel={label} style={[styles.sheet, { bottom, height: room }, animated]}>
    <GestureDetector gesture={drag}>
      <View style={styles.grip} accessibilityRole="adjustable" accessibilityLabel="Altura del panel" accessibilityHint="Desliza para ampliar o cerrar"
        accessibilityActions={[{ name: 'increment', label: 'Ampliar' }, { name: 'decrement', label: 'Media pantalla' }]}
        onAccessibilityAction={({ nativeEvent }) => go(nativeEvent.actionName === 'increment' ? full : half)}>
        <View style={styles.handle} />
      </View>
    </GestureDetector>
    <View style={styles.close}><Button accessibilityLabel="Cerrar" onPress={dismiss}>Cerrar</Button></View>
    <ScrollView key={label} contentContainerStyle={[styles.content, { paddingBottom: space[6] + room * (1 - resting) }]} keyboardShouldPersistTaps="handled">{children}</ScrollView>
  </Animated.View>;
}
const styles = StyleSheet.create({
  sheet: { position: 'absolute', left: 0, right: 0, backgroundColor: colors.surface, borderTopWidth: 1, borderColor: colors.line,
    borderTopLeftRadius: radius.sheet, borderTopRightRadius: radius.sheet, overflow: 'hidden', elevation: 4 },
  grip: { height: 56, marginRight: 100, justifyContent: 'center', alignItems: 'center' },
  handle: { width: 40, height: 4, backgroundColor: colors.inkSoft, borderRadius: radius.pill },
  close: { position: 'absolute', top: space[1], right: space[2] },
  content: { padding: space[4], gap: space[3] },
});
