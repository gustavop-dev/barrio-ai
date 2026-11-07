// Nonmodal sheet: the scene above it remains interactive. Drag only the handle, leaving content scroll
// native. Two snap points, accessible expand/collapse actions, Android back and an explicit close.
import { useCallback, useEffect, type ReactNode } from 'react';
import { BackHandler, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import { GestureDetector, usePanGesture } from 'react-native-gesture-handler';
import Animated, { runOnJS, useAnimatedStyle, useSharedValue, withSpring, withTiming } from 'react-native-reanimated';
import { gestures, officeGestures, spring, timing } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';
import { Button } from './Button';

export interface SnapSheetProps {
  label: string; onClose: () => void; children: ReactNode;
  bottom: number; availableHeight?: number; testID?: string;
}
export function SnapSheet({ label, onClose, children, bottom, availableHeight, testID }: SnapSheetProps) {
  const window = useWindowDimensions();
  const room = (availableHeight ?? window.height) - bottom;
  const half = room * officeGestures.sheetHalf;
  const full = room * officeGestures.sheetFull;
  const height = useSharedValue(0);
  const start = useSharedValue(half);
  const snap = spring('sheetOpen');
  const close = timing('sheetClose');
  const dismiss = useCallback(() => {
    height.set(withTiming(0, close, (finished) => { if (finished) runOnJS(onClose)(); }));
  }, [height, close, onClose]);
  useEffect(() => { height.set(withSpring(half, spring('sheetOpen'))); }, [half, height]);
  useEffect(() => {
    const listener = BackHandler.addEventListener('hardwareBackPress', () => { dismiss(); return true; });
    return () => listener.remove();
  }, [dismiss]);
  const drag = usePanGesture({
    testID: 'snap-sheet-drag', minDistance: officeGestures.sheetActivation,
    onActivate: () => { 'worklet'; start.value = height.value; },
    onUpdate: (event) => { 'worklet'; height.set(Math.max(0, Math.min(full, start.value - event.translationY))); },
    onDeactivate: (event) => {
      'worklet';
      if (!event.canceled && (height.value < half - gestures.sheet.dismissDistance || event.velocityY > gestures.sheet.dismissVelocity)) runOnJS(dismiss)();
      else height.set(withSpring(height.value > (half + full) / 2 ? full : half, snap));
    },
  });
  const animated = useAnimatedStyle(() => ({ height: height.value }));
  return <Animated.View testID={testID} accessibilityLabel={label} style={[styles.sheet, { bottom }, animated]}>
    <GestureDetector gesture={drag}>
      <View style={styles.grip} accessibilityRole="adjustable" accessibilityLabel="Altura del panel" accessibilityHint="Desliza para ampliar o cerrar"
        accessibilityActions={[{ name: 'increment', label: 'Ampliar' }, { name: 'decrement', label: 'Media pantalla' }]}
        onAccessibilityAction={({ nativeEvent }) => height.set(withSpring(nativeEvent.actionName === 'increment' ? full : half, snap))}>
        <View style={styles.handle} />
      </View>
    </GestureDetector>
    <View style={styles.close}><Button accessibilityLabel="Cerrar" onPress={dismiss}>Cerrar</Button></View>
    <ScrollView key={label} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">{children}</ScrollView>
  </Animated.View>;
}
const styles = StyleSheet.create({
  sheet: { position: 'absolute', left: 0, right: 0, backgroundColor: colors.surface, borderTopWidth: 1, borderColor: colors.line,
    borderTopLeftRadius: radius.sheet, borderTopRightRadius: radius.sheet, overflow: 'hidden', elevation: 4 },
  grip: { height: 56, marginRight: 100, justifyContent: 'center', alignItems: 'center' },
  handle: { width: 40, height: 4, backgroundColor: colors.inkSoft, borderRadius: radius.pill },
  close: { position: 'absolute', top: space[1], right: space[2] },
  content: { padding: space[4], gap: space[3], paddingBottom: space[6] },
});
