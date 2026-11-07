// Bottom sheet (capture sheet, confirmations): a Modal with the tinta backdrop, rising on the
// sheetOpen spring, closed by the backdrop, the Android back button, or dragging the handle down
// (gestures.sheet). Inside a Modal Android starts a new root, so it brings its GestureHandlerRootView.
import { useCallback, useEffect, useRef, type ReactNode } from 'react';
import { KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import { GestureDetector, GestureHandlerRootView, usePanGesture } from 'react-native-gesture-handler';
import Animated, { runOnJS, useAnimatedStyle, useSharedValue, withSpring, withTiming } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { gestures, spring, timing } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';

export interface SheetProps {
  /** Accessible name of the sheet. */
  label: string;
  onClose: () => void;
  children: ReactNode;
  /** Header that stays put above the scrolling content (handle included by the sheet). */
  header?: ReactNode;
  /** While another dialog is on top: the back button and the backdrop do nothing. */
  suspended?: boolean;
  /** Asked before closing from the backdrop, the back button or a drag; false keeps the sheet (the caller asks first). */
  canClose?: () => boolean;
  testID?: string;
}

export function Sheet({ label, onClose, children, header, suspended, canClose, testID }: SheetProps) {
  const { height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const offset = useSharedValue(height);
  const backdrop = useSharedValue(0);
  const closing = useRef(false);

  useEffect(() => {
    offset.set(withSpring(0, spring('sheetOpen')));
    backdrop.set(withTiming(1, timing('backdrop')));
  }, [offset, backdrop]);

  const dismiss = useCallback(() => {
    if (closing.current) return;
    closing.current = true;
    backdrop.set(withTiming(0, timing('backdrop')));
    offset.set(
      withTiming(height, timing('sheetClose'), (finished) => {
        if (finished) runOnJS(onClose)();
      }),
    );
  }, [backdrop, offset, height, onClose]);

  const requestClose = useCallback(() => {
    if (!suspended && (canClose?.() ?? true)) dismiss();
  }, [suspended, canClose, dismiss]);

  /** End of a drag on the handle: close past the threshold (unless another dialog is on top), or go back up. */
  const release = useCallback(
    (wantsClose: boolean) => {
      if (wantsClose && !suspended && (canClose?.() ?? true)) dismiss();
      else offset.set(withSpring(0, spring('sheetOpen')));
    },
    [suspended, canClose, dismiss, offset],
  );

  const drag = usePanGesture({
    activeOffsetY: 8,
    onUpdate: (event) => {
      'worklet';
      offset.set(Math.max(0, event.translationY));
    },
    onDeactivate: (event) => {
      'worklet';
      runOnJS(release)(event.translationY > gestures.sheet.dismissDistance || event.velocityY > gestures.sheet.dismissVelocity);
    },
  });

  const panel = useAnimatedStyle(() => ({ transform: [{ translateY: offset.value }] }));
  const shade = useAnimatedStyle(() => ({ opacity: backdrop.value }));

  return (
    <Modal transparent visible animationType="none" statusBarTranslucent navigationBarTranslucent onRequestClose={requestClose}>
      <GestureHandlerRootView style={styles.root}>
        <Animated.View style={[StyleSheet.absoluteFill, styles.backdrop, shade]}>
          <Pressable style={StyleSheet.absoluteFill} accessibilityLabel="Cerrar" accessibilityRole="button" onPress={requestClose} />
        </Animated.View>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.avoid} pointerEvents="box-none">
          <Animated.View
            testID={testID}
            accessibilityViewIsModal
            accessibilityLabel={label}
            style={[styles.sheet, { maxHeight: height * 0.94, paddingBottom: space[4] + insets.bottom }, panel]}
          >
            <GestureDetector gesture={drag}>
              <View style={styles.grab}>
                <View style={styles.handle} />
                {header}
              </View>
            </GestureDetector>
            <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
              {children}
            </ScrollView>
          </Animated.View>
        </KeyboardAvoidingView>
      </GestureHandlerRootView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  backdrop: { backgroundColor: colors.backdrop },
  avoid: { flex: 1, justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.sheet,
    borderTopRightRadius: radius.sheet,
    paddingHorizontal: space[4],
    paddingTop: space[3],
  },
  grab: { gap: space[2], paddingBottom: space[2] },
  handle: { alignSelf: 'center', width: 40, height: 4, borderRadius: radius.pill, backgroundColor: colors.line },
  content: { gap: 14, paddingBottom: space[2] },
});
