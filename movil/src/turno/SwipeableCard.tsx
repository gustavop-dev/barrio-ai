// A Tu turno card that can be swiped: right for its primary action (done), left for «Más tarde».
// The card follows the finger on the UI thread; past the commit point a selection tick plays, and
// on release it either flies off (the action runs) or springs back. Screen readers get the same two
// actions as accessibility actions. MovTuTurno: once the action is confirmed, the list closes the gap
// behind the card that flew off, exactly as for a card resolved with its button (exits.ts).
import { useState, type ReactNode } from 'react';
import { StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import { GestureDetector, usePanGesture } from 'react-native-gesture-handler';
import Animated, { interpolate, runOnJS, useAnimatedStyle, useSharedValue, withSpring, withTiming } from 'react-native-reanimated';
import { Icon } from '@/components/icons';
import { T } from '@/components/ui';
import { gestures, haptic, spring, timing } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';
import { commitSide, dragOffset, pastCommit, revealProgress, type SwipeSide } from './swipe';

// Built on the JS thread: spring()/timing() are not worklets, and calling them inside a gesture worklet crashes the
// app on the UI runtime («Tried to synchronously call a Remote Function»).
const SNAP_BACK = spring('snapBack');
const SWIPE_EXIT = timing('swipeExit');

export interface SwipeableCardProps {
  children: ReactNode;
  /** Label of the right swipe (the primary action), or null when there is none. */
  rightLabel: string | null;
  /** Label of the left swipe («Más tarde»), or null. */
  leftLabel: string | null;
  /**
   * Runs the swipe. Resolves true when the card leaves the list (it stays off screen), false to bring it
   * back. `flown`: the finger took the card off screen (false for the screen reader's actions).
   */
  onSwipe: (side: SwipeSide, flown: boolean) => Promise<boolean>;
  testID?: string;
}

export function SwipeableCard({ children, rightLabel, leftLabel, onSwipe, testID }: SwipeableCardProps) {
  const [width, setWidth] = useState(360);
  const x = useSharedValue(0);
  const armed = useSharedValue(false);
  const sides = { right: Boolean(rightLabel), left: Boolean(leftLabel) };
  const enabled = sides.right || sides.left;

  const settle = (gone: boolean) => {
    if (!gone) x.set(withSpring(0, SNAP_BACK));
  };

  const commit = (side: SwipeSide) => {
    haptic('swipeCommit');
    void onSwipe(side, true).then(settle, () => settle(false));
  };

  const tick = () => haptic('swipeThreshold');

  const pan = usePanGesture({
    enabled,
    testID: testID ? `${testID}-swipe` : undefined,
    activeOffsetX: [-gestures.swipe.activeOffsetX, gestures.swipe.activeOffsetX],
    failOffsetY: [-gestures.swipe.failOffsetY, gestures.swipe.failOffsetY],
    onUpdate: (event) => {
      'worklet';
      x.set(dragOffset(event.translationX, width, sides));
      const past = pastCommit(event.translationX, width) && (event.translationX > 0 ? sides.right : sides.left);
      if (past !== armed.value) {
        armed.set(past);
        runOnJS(tick)();
      }
    },
    onDeactivate: (event) => {
      'worklet';
      armed.set(false);
      const side = commitSide(event.translationX, event.velocityX, width, sides);
      if (!side) {
        x.set(withSpring(0, SNAP_BACK));
        return;
      }
      x.set(withTiming(side === 'right' ? width * 1.1 : -width * 1.1, SWIPE_EXIT));
      runOnJS(commit)(side);
    },
  });

  const card = useAnimatedStyle(() => ({ transform: [{ translateX: x.value }] }));
  const rightReveal = useAnimatedStyle(() => ({
    opacity: x.value > 0 ? 1 : 0,
    transform: [{ scale: interpolate(revealProgress(x.value, width), [0, 1], [0.6, 1]) }],
  }));
  const leftReveal = useAnimatedStyle(() => ({
    opacity: x.value < 0 ? 1 : 0,
    transform: [{ scale: interpolate(revealProgress(x.value, width), [0, 1], [0.6, 1]) }],
  }));

  const actions = [
    ...(rightLabel ? [{ name: 'swipeRight', label: rightLabel }] : []),
    ...(leftLabel ? [{ name: 'swipeLeft', label: leftLabel }] : []),
  ];

  return (
    <View
      testID={testID}
      onLayout={(event: LayoutChangeEvent) => setWidth(event.nativeEvent.layout.width)}
      accessibilityActions={actions}
      onAccessibilityAction={(event) => {
        if (event.nativeEvent.actionName === 'swipeRight' && rightLabel) void onSwipe('right', false);
        if (event.nativeEvent.actionName === 'swipeLeft' && leftLabel) void onSwipe('left', false);
      }}
    >
      {enabled ? (
        <View style={styles.under} pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          {rightLabel ? (
            <Animated.View style={[styles.side, styles.right, rightReveal]}>
              <Icon name="check" size={22} color={colors.brandDeep} />
              <T variant="detalle" color={colors.brandDeep} numberOfLines={2} style={styles.sideText}>
                {rightLabel}
              </T>
            </Animated.View>
          ) : null}
          {leftLabel ? (
            <Animated.View style={[styles.side, styles.left, leftReveal]}>
              <T variant="detalle" numberOfLines={2} style={[styles.sideText, styles.leftText]}>
                {leftLabel}
              </T>
              <Icon name="reloj" size={22} />
            </Animated.View>
          ) : null}
        </View>
      ) : null}
      <GestureDetector gesture={pan}>
        <Animated.View style={card}>{children}</Animated.View>
      </GestureDetector>
    </View>
  );
}

const styles = StyleSheet.create({
  under: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, borderRadius: radius.md, overflow: 'hidden' },
  side: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, flexDirection: 'row', alignItems: 'center', gap: space[2], paddingHorizontal: space[6] },
  right: { backgroundColor: colors.brandLight, justifyContent: 'flex-start' },
  left: { backgroundColor: colors.postIt, justifyContent: 'flex-end' },
  sideText: { maxWidth: 160 },
  leftText: { textAlign: 'right' },
});
