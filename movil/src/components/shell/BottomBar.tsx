// Mobile bottom bar: Oficina and Resultados, the raised capture button in the centre, Personas and the
// Bandeja de entrada (formerly «Tu turno», with its counter; Gustavo, 12/11/2026: the Galería went away and the
// inbox took its place). It floats over the screens (they pad their content with useContentInsets) so the raised
// button stays touchable above the bar.
//
// Motion (MovNavegacion `tab`): one pill slides to the active tab with the `pill` spring, the tapped
// tab's icon pops from 0.92 with the `tabIcon` spring and the phone ticks (`tabChange`). On the three
// top-bar screens no bottom tab is active and the pill hides; it slides from where it was when a
// bottom tab is chosen again. With reduced motion the springs jump.
import type { BottomTabBarProps } from 'expo-router/js-tabs';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View, type LayoutChangeEvent, type LayoutRectangle } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from 'react-native-reanimated';
import { CaptureButton } from '@/capture/CaptureButton';
import { Icon, type IconName } from '@/components/icons';
import { T } from '@/components/ui';
import { Counter } from './TurnBadge';
import { turnLabel, useTurnCount } from './useTurnCount';
import { haptic, navSpring, navValues } from '@/theme/motion';
import { colors, radius, shell } from '@/theme/tokens';

interface Item {
  route: 'index' | 'resultados' | 'personas' | 'tu-turno';
  label: string;
  icon: IconName;
}

export const BOTTOM_LEFT: readonly Item[] = [
  { route: 'index', label: 'Oficina', icon: 'oficina' },
  { route: 'resultados', label: 'Resultados', icon: 'resultados' },
];
export const BOTTOM_RIGHT: readonly Item[] = [
  { route: 'personas', label: 'Personas', icon: 'personas' },
  { route: 'tu-turno', label: 'Bandeja', icon: 'tuTurno' },
];

/** Room the raised capture button needs above the bar (it grows to 72 px while holding). */
const RAISE = shell.captureButtonHolding - shell.captureButton + shell.captureLift;

const PILL = { width: 56, height: 28 } as const;

/** Where the pill sits for a tab centred at `center` (MovNavegacion: `CX[i] − 28`). */
export function pillLeft(center: number): number {
  return center - PILL.width / 2;
}

function Tab({
  item,
  focused,
  onPress,
  onPlace,
  onIcon,
  a11yLabel,
  badge,
}: {
  item: Item;
  focused: boolean;
  /** The accessible name when it says more than the label («Bandeja de entrada, 3 pendientes»). */
  a11yLabel?: string;
  /** Drawn over the icon's top right corner (the Bandeja counter). */
  badge?: ReactNode;
  onPress: () => void;
  onPlace: (route: Item['route'], layout: LayoutRectangle) => void;
  onIcon: (layout: LayoutRectangle) => void;
}) {
  const scale = useSharedValue(1);
  const wasFocused = useRef(focused);
  // Only a change of tab pops the icon (MovNavegacion: `IC[i].sc.set(0.92).to(1, TOK.soft)`).
  useEffect(() => {
    if (focused && !wasFocused.current) {
      scale.set(navValues.tabIconFrom);
      scale.set(withSpring(1, navSpring('tabIcon')));
    }
    wasFocused.current = focused;
  }, [focused, scale]);
  const icon = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  return (
    <Pressable
      testID={`tab-${item.route}`}
      accessibilityRole="tab"
      accessibilityLabel={a11yLabel ?? item.label}
      accessibilityState={{ selected: focused }}
      onPress={onPress}
      onLayout={(event: LayoutChangeEvent) => onPlace(item.route, event.nativeEvent.layout)}
      style={styles.tab}
    >
      <Animated.View testID={`tab-icon-${item.route}`} onLayout={(event: LayoutChangeEvent) => onIcon(event.nativeEvent.layout)} style={[styles.icon, icon]}>
        <Icon name={item.icon} color={focused ? colors.ink : colors.inkSoft} />
        {badge}
      </Animated.View>
      <T variant="etiqueta" color={focused ? colors.ink : colors.inkSoft} numberOfLines={1} style={styles.label}>
        {item.label}
      </T>
    </Pressable>
  );
}

export function BottomBar({ state, navigateToTab, insets }: BottomTabBarProps) {
  const focusedName = state.routes[state.index]?.name;
  const turn = useTurnCount();
  const centers = useRef<Partial<Record<string, number>>>({});
  const placed = useRef(false);
  const pillX = useSharedValue(0);
  const pillOn = useSharedValue(0);
  const [pillTop, setPillTop] = useState(0);

  /** Puts the pill under the active tab: at once the first time, then sliding from where it was. */
  const placePill = useCallback(
    (name: string | undefined) => {
      const center = name ? centers.current[name] : undefined;
      if (center === undefined) {
        pillOn.set(0);
        return;
      }
      if (placed.current) pillX.set(withSpring(pillLeft(center), navSpring('pill')));
      else pillX.set(pillLeft(center));
      placed.current = true;
      pillOn.set(1);
    },
    [pillOn, pillX],
  );

  useEffect(() => placePill(focusedName), [focusedName, placePill]);

  const onPlace = useCallback(
    (route: Item['route'], layout: LayoutRectangle) => {
      const first = centers.current[route] === undefined;
      centers.current[route] = layout.x + layout.width / 2;
      if (first && route === focusedName) placePill(route);
    },
    [focusedName, placePill],
  );
  const onIcon = useCallback((layout: LayoutRectangle) => setPillTop(layout.y), []);

  const pill = useAnimatedStyle(() => ({ opacity: pillOn.value, transform: [{ translateX: pillX.value }] }));

  const go = (item: Item) => {
    const route = state.routes.find((r) => r.name === item.route);
    if (!route) return;
    if (route.name !== focusedName) haptic('tabChange');
    navigateToTab(route.key);
  };
  const render = (item: Item) => (
    <Tab
      key={item.route}
      item={item}
      focused={focusedName === item.route}
      onPress={() => go(item)}
      onPlace={onPlace}
      onIcon={onIcon}
      a11yLabel={item.route === 'tu-turno' ? turnLabel(turn) : undefined}
      badge={item.route === 'tu-turno' ? <Counter count={turn.count} critical={turn.critical} loaded={turn.loaded} style={styles.counter} /> : undefined}
    />
  );
  return (
    <View pointerEvents="box-none" style={[styles.root, { height: shell.tabBarHeight + insets.bottom + RAISE }]} accessibilityRole="tablist" accessibilityLabel="Secciones">
      <View style={[styles.bar, { height: shell.tabBarHeight + insets.bottom, paddingBottom: insets.bottom }]}>
        <Animated.View testID="tab-pill" pointerEvents="none" accessible={false} importantForAccessibility="no" style={[styles.pill, { top: pillTop }, pill]} />
        {BOTTOM_LEFT.map(render)}
        <CaptureButton />
        {BOTTOM_RIGHT.map(render)}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { position: 'absolute', left: 0, right: 0, bottom: 0, justifyContent: 'flex-end' },
  bar: { flexDirection: 'row', alignItems: 'flex-start', backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.line },
  tab: { flex: 1, height: shell.tabBarHeight, alignItems: 'center', justifyContent: 'center', gap: 2 },
  icon: { width: PILL.width, height: PILL.height, alignItems: 'center', justifyContent: 'center' },
  pill: { position: 'absolute', left: 0, width: PILL.width, height: PILL.height, borderRadius: radius.pill, backgroundColor: colors.brandLight },
  label: { letterSpacing: 0, textTransform: 'none', fontSize: 12, lineHeight: 16 },
  // Over the icon's top right corner: the icon is centred in the 56-wide pill box.
  counter: { top: -6, right: 4 },
});
