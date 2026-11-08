// Horizontal paging for the week strip and the month («Deslizar la tira cambia de semana»): the page
// follows the finger with the previous and next pages beside it, and past gestures.pager.commitFraction
// (or a flick) it turns with the pageSnap spring; otherwise it springs back. The header arrows animate
// the same way through the ref, and screen readers get «anterior» and «siguiente» actions.
//
// Pages are keyed by an absolute index and placed at index × width, so when the parent moves its date
// the page that slid in keeps its place: nothing jumps between the spring and the new render.
//
// The frame's height is MovCalendario's `h`: the parent keeps it (so it carries from the week to the
// month) and the frame eases to the current page's height, clipping what is still outside it.
import { useCallback, useEffect, useImperativeHandle, useRef, useState, type ReactNode, type Ref } from 'react';
import { StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import { GestureDetector, usePanGesture } from 'react-native-gesture-handler';
import Animated, { runOnJS, useAnimatedStyle, useSharedValue, withSpring, withTiming, type SharedValue } from 'react-native-reanimated';
import { calendarTiming, gestures, haptic, spring, useMotion } from '@/theme/motion';

// Built on the JS thread: spring()/timing() are not worklets, and calling them inside a gesture worklet crashes the
// app on the UI runtime («Tried to synchronously call a Remote Function»).
const PAGE_SNAP = spring('pageSnap');

export type PageOffset = -1 | 0 | 1;

export interface PagerHandle {
  /** Turns the page with the same spring as a swipe. */
  go: (direction: 1 | -1) => void;
}

/** Whether a released drag turns the page, and which way (1: next, -1: previous). Pure, so it can be tested. */
export function pageDirection(translationX: number, velocityX: number, width: number): 1 | -1 | 0 {
  'worklet';
  const { commitFraction, commitVelocity } = gestures.pager;
  if (width <= 0) return 0;
  if (translationX <= -width * commitFraction || (velocityX <= -commitVelocity && translationX < 0)) return 1;
  if (translationX >= width * commitFraction || (velocityX >= commitVelocity && translationX > 0)) return -1;
  return 0;
}

export interface PagerProps {
  renderPage: (offset: PageOffset) => ReactNode;
  /** The page turned: move the date by one week or month. */
  onShift: (direction: 1 | -1) => void;
  previousLabel: string;
  nextLabel: string;
  testID?: string;
  ref?: Ref<PagerHandle>;
  /** The frame's height (−1: not measured yet, so the frame takes its page's height at once). */
  height?: SharedValue<number>;
}

export function Pager({ renderPage, onShift, previousLabel, nextLabel, testID, ref, height }: PagerProps) {
  const { reduced } = useMotion();
  const [width, setWidth] = useState(0);
  const [index, setIndex] = useState(0);
  /** index × width, also on the UI thread. */
  const base = useSharedValue(0);
  /** What the strip shows: base minus the finger's travel. */
  const offset = useSharedValue(0);

  useEffect(() => {
    base.set(index * width);
    offset.set(index * width);
    // Only when the width changes (rotation): turns keep base and offset in step themselves.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [width]);

  const commit = useCallback(
    (direction: 1 | -1) => {
      setIndex((current) => current + direction);
      onShift(direction);
    },
    [onShift],
  );

  const swiped = useCallback(
    (direction: 1 | -1) => {
      haptic('pageChange');
      commit(direction);
    },
    [commit],
  );

  const go = useCallback(
    (direction: 1 | -1) => {
      const target = base.get() + direction * width;
      base.set(target);
      offset.set(withSpring(target, PAGE_SNAP));
      commit(direction);
    },
    [base, offset, width, commit],
  );

  useImperativeHandle(ref, () => ({ go }), [go]);

  const pan = usePanGesture({
    testID: testID ? `${testID}-swipe` : undefined,
    activeOffsetX: [-gestures.pager.activeOffsetX, gestures.pager.activeOffsetX],
    failOffsetY: [-gestures.pager.failOffsetY, gestures.pager.failOffsetY],
    onUpdate: (event) => {
      'worklet';
      offset.set(base.value - event.translationX);
    },
    onDeactivate: (event) => {
      'worklet';
      const direction = pageDirection(event.translationX, event.velocityX, width);
      const target = base.value + direction * width;
      base.set(target);
      offset.set(withSpring(target, PAGE_SNAP));
      if (direction !== 0) runOnJS(swiped)(direction);
    },
  });

  // Every page's height: a page that slides in may not lay out again, so the frame follows it from here.
  const heights = useRef(new Map<number, number>());
  const follow = useCallback(
    (next: number) => {
      if (!height) return;
      height.set(reduced || height.get() < 0 ? next : withTiming(next, calendarTiming('height')));
    },
    [height, reduced],
  );
  const measure = (key: number) => (event: LayoutChangeEvent) => {
    const next = event.nativeEvent.layout.height;
    heights.current.set(key, next);
    if (key === index) follow(next);
  };
  useEffect(() => {
    const next = heights.current.get(index);
    if (next !== undefined) follow(next);
  }, [index, follow]);

  const strip = useAnimatedStyle(() => ({ transform: [{ translateX: -offset.value }] }));
  const frame = useAnimatedStyle(() => (height && height.value >= 0 ? { height: height.value } : {}));
  const pages: { key: number; offset: PageOffset }[] = width ? [-1, 0, 1].map((step) => ({ key: index + step, offset: step as PageOffset })) : [{ key: index, offset: 0 }];
  // The strip's own box spans its three pages (from the previous one): a page laid out outside its parent's box is
  // drawn, but Android does not count it as on screen, so after a swipe TalkBack (and the QA flows) lost the days of the
  // week that slid in. A page's place on screen stays index × width − offset whatever `first` is.
  const first = index - 1;

  return (
    <Animated.View
      style={[styles.frame, frame]}
      onLayout={(event: LayoutChangeEvent) => setWidth(Math.round(event.nativeEvent.layout.width))}
      accessibilityActions={[
        { name: 'previous', label: previousLabel },
        { name: 'next', label: nextLabel },
      ]}
      onAccessibilityAction={(event) => {
        if (event.nativeEvent.actionName === 'previous') go(-1);
        if (event.nativeEvent.actionName === 'next') go(1);
      }}
      testID={testID}
    >
      <GestureDetector gesture={pan}>
        <Animated.View style={[strip, width ? { left: first * width, width: 3 * width } : null]}>
          {pages.map((page) =>
            page.offset === 0 ? (
              <View key={page.key} style={[styles.current, { left: (page.key - first) * width }, width ? { width } : null]} onLayout={measure(page.key)}>
                {renderPage(0)}
              </View>
            ) : (
              <View
                key={page.key}
                style={[styles.side, { left: (page.key - first) * width, width }]}
                onLayout={measure(page.key)}
                accessibilityElementsHidden
                importantForAccessibility="no-hide-descendants"
                pointerEvents="none"
              >
                {renderPage(page.offset)}
              </View>
            ),
          )}
        </Animated.View>
      </GestureDetector>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  frame: { overflow: 'hidden' },
  current: { position: 'relative' },
  side: { position: 'absolute', top: 0 },
});
