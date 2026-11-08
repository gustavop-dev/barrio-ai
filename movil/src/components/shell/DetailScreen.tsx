// A detail view above the tabs (pieza, persona): the top bar with «‹ {back}» and the push of
// MovNavegacion. It slides in from the right with the `push` spring while the tabs move left and
// darken (push.ts); «‹», Android back and any navigation away run the same spring back before the
// route goes. A drag from the left edge follows the finger and, on release, settles with the board's
// projection (navGestures). With reduced motion it appears and goes at once (board: «menos movimiento»).
import { router, useNavigation, usePreventRemove, useRootNavigationState, useRoute } from 'expo-router';
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ComponentRef, type ReactNode } from 'react';
import { StyleSheet, View, useWindowDimensions } from 'react-native';
import { GestureDetector, usePanGesture } from 'react-native-gesture-handler';
import Animated, { cancelAnimation, runOnJS, useAnimatedStyle, useSharedValue, withSpring } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { navGestures, navSpring, useMotion } from '@/theme/motion';
import { colors, shell } from '@/theme/tokens';
import { FlightProvider, useFlightHost } from './flight';
import { baseFrame, canGrab, dragProgress, edgeRelease, panelFrame, pushProgress, registerLayer, stackLevel, stackOf } from './push';
import { TopBar } from './TopBar';

/** The hairline on the panel's left edge, seen while it slides. */
const EDGE_LINE = 1;

/** Actions that leave nothing underneath to reveal: the route goes at once. */
const WITHOUT_PUSH = new Set(['REPLACE', 'RESET']);

export function DetailScreen({ back, fallback, children }: { back: string; fallback: '/calendario' | '/personas'; children: ReactNode }) {
  const navigation = useNavigation();
  const route = useRoute();
  // From the root state of this render: getState() would not have this screen yet on its first render
  // (level 0: the tabs would not move, and this panel would take the tabs' layer).
  const level = stackLevel(stackOf(useRootNavigationState(), route.key) ?? navigation.getState(), route.key);
  const progress = pushProgress(level);
  const covered = pushProgress(level + 1);
  const { reduced } = useMotion();
  const { width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const headerBottom = insets.top + shell.topBarHeight;
  const panel = useRef<ComponentRef<typeof View>>(null);
  const flight = useFlightHost({ level, panel, reduced, headerBottom });
  const { flyBack } = flight;
  const exiting = useSharedValue(false);
  const dragging = useSharedValue(false);
  const grabbedAt = useSharedValue(0);
  const released = useRef(false);
  const [guarded, setGuarded] = useState(true);
  const offscreen = width + EDGE_LINE;

  // In from the right; whatever happens, the screen underneath is left in place.
  useLayoutEffect(() => {
    progress.set(0);
    progress.set(withSpring(1, navSpring('push')));
    return () => {
      cancelAnimation(progress);
      progress.set(0);
    };
  }, [progress]);

  useEffect(() => registerLayer(level, panel.current), [level]);

  const goBack = useCallback(() => (router.canGoBack() ? router.back() : router.replace(fallback)), [fallback]);

  /** The push back, then `after` (the navigation that was waiting). */
  const leave = useCallback(
    (after: () => void) => {
      exiting.set(true);
      flyBack(0);
      progress.set(
        withSpring(0, navSpring('push'), (finished) => {
          if (finished) runOnJS(after)();
        }),
      );
    },
    [exiting, flyBack, progress],
  );

  // Every way out («‹», Android back, a link to a tab) waits for the push back, then goes on.
  usePreventRemove(guarded, ({ data, repeat }) => {
    const go = () => {
      released.current = true;
      setGuarded(false);
      repeat();
    };
    if (released.current || WITHOUT_PUSH.has(data.action.type)) {
      go();
      return;
    }
    if (exiting.get()) return;
    leave(go);
  });

  /** After a drag that let go: the spring already runs; the copies fly from where the card is. */
  const dragBack = useCallback(
    (offsetX: number) => {
      exiting.set(true);
      flyBack(offsetX);
    },
    [exiting, flyBack],
  );
  const settleBack = useCallback(() => {
    released.current = true;
    goBack();
  }, [goBack]);

  const config = navSpring('push');
  const edge = usePanGesture({
    testID: 'detail-edge',
    // The board grabs on touch (pointerdown on the strip).
    minDistance: 0,
    onActivate: () => {
      'worklet';
      if (exiting.value || !canGrab(progress.value)) return;
      cancelAnimation(progress);
      grabbedAt.set(progress.value);
      dragging.set(true);
    },
    onUpdate: (event) => {
      'worklet';
      if (!dragging.value) return;
      progress.set(dragProgress(grabbedAt.value, event.translationX, width));
    },
    onDeactivate: (event) => {
      'worklet';
      if (!dragging.value) return;
      dragging.set(false);
      if (edgeRelease(progress.value, event.velocityX) === 1) {
        progress.set(withSpring(1, config));
        return;
      }
      runOnJS(dragBack)((1 - progress.value) * offscreen);
      progress.set(
        withSpring(0, config, (finished) => {
          if (finished) runOnJS(settleBack)();
        }),
      );
    },
  });

  const panelStyle = useAnimatedStyle(() => {
    const frame = panelFrame(progress.value, covered.value, width, offscreen, reduced);
    return { opacity: frame.opacity, transform: [{ translateX: frame.translateX }] };
  }, [progress, covered, width, offscreen, reduced]);
  const dimStyle = useAnimatedStyle(() => ({ opacity: baseFrame(covered.value, width, reduced).dim }), [covered, width, reduced]);

  return (
    <View style={styles.fill} pointerEvents="box-none">
      <Animated.View testID="detail-panel" style={[styles.panel, panelStyle]}>
        <View ref={panel} collapsable={false} pointerEvents="none" style={styles.fill} />
        <View style={styles.line} pointerEvents="none" />
        <FlightProvider value={flight.context}>
          <TopBar back={{ label: back, onPress: goBack }} />
          {children}
        </FlightProvider>
        <GestureDetector gesture={edge}>
          <View
            testID="detail-edge-zone"
            accessible={false}
            importantForAccessibility="no-hide-descendants"
            style={[styles.edge, { top: headerBottom, width: navGestures.edgeWidth }]}
          />
        </GestureDetector>
        <Animated.View pointerEvents="none" style={[styles.dim, dimStyle]} />
      </Animated.View>
      {flight.ghost}
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0 },
  panel: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, backgroundColor: colors.paper },
  line: { position: 'absolute', top: 0, bottom: 0, left: -EDGE_LINE, width: EDGE_LINE, backgroundColor: colors.line },
  edge: { position: 'absolute', left: 0, bottom: 0 },
  dim: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, backgroundColor: colors.ink, opacity: 0 },
});
