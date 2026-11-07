// Mobile bottom bar: Oficina and Resultados, the raised capture button in the centre, Personas and
// Galería. It floats over the screens (they pad their content with useContentInsets) so the raised
// button stays touchable above the bar.
import type { BottomTabBarProps } from 'expo-router/js-tabs';
import { Pressable, StyleSheet, View } from 'react-native';
import Animated, { useAnimatedStyle, withSpring } from 'react-native-reanimated';
import { CaptureButton } from '@/capture/CaptureButton';
import { Icon, type IconName } from '@/components/icons';
import { T } from '@/components/ui';
import { haptic, spring } from '@/theme/motion';
import { colors, radius, shell } from '@/theme/tokens';

interface Item {
  route: 'index' | 'resultados' | 'personas' | 'galeria';
  label: string;
  icon: IconName;
}

export const BOTTOM_LEFT: readonly Item[] = [
  { route: 'index', label: 'Oficina', icon: 'oficina' },
  { route: 'resultados', label: 'Resultados', icon: 'resultados' },
];
export const BOTTOM_RIGHT: readonly Item[] = [
  { route: 'personas', label: 'Personas', icon: 'personas' },
  { route: 'galeria', label: 'Galería', icon: 'galeria' },
];

/** Room the raised capture button needs above the bar (it grows to 72 px while holding). */
const RAISE = shell.captureButtonHolding - shell.captureButton + shell.captureLift;

function Tab({ item, focused, onPress }: { item: Item; focused: boolean; onPress: () => void }) {
  const pill = useAnimatedStyle(() => ({ transform: [{ scale: withSpring(focused ? 1 : 0.92, spring('press')) }] }), [focused]);
  return (
    <Pressable
      testID={`tab-${item.route}`}
      accessibilityRole="tab"
      accessibilityLabel={item.label}
      accessibilityState={{ selected: focused }}
      onPress={onPress}
      style={styles.tab}
    >
      <Animated.View style={[styles.pill, focused ? styles.pillOn : null, pill]}>
        <Icon name={item.icon} color={focused ? colors.ink : colors.inkSoft} />
      </Animated.View>
      <T variant="etiqueta" color={focused ? colors.ink : colors.inkSoft} numberOfLines={1} style={styles.label}>
        {item.label}
      </T>
    </Pressable>
  );
}

export function BottomBar({ state, navigateToTab, insets }: BottomTabBarProps) {
  const focusedName = state.routes[state.index]?.name;
  const go = (item: Item) => {
    const route = state.routes.find((r) => r.name === item.route);
    if (!route) return;
    if (route.name !== focusedName) haptic('tabChange');
    navigateToTab(route.key);
  };
  const render = (item: Item) => <Tab key={item.route} item={item} focused={focusedName === item.route} onPress={() => go(item)} />;
  return (
    <View pointerEvents="box-none" style={[styles.root, { height: shell.tabBarHeight + insets.bottom + RAISE }]} accessibilityRole="tablist" accessibilityLabel="Secciones">
      <View style={[styles.bar, { height: shell.tabBarHeight + insets.bottom, paddingBottom: insets.bottom }]}>
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
  pill: { width: 56, height: 28, borderRadius: radius.pill, alignItems: 'center', justifyContent: 'center' },
  pillOn: { backgroundColor: colors.brandLight },
  label: { letterSpacing: 0, textTransform: 'none', fontSize: 12, lineHeight: 16 },
});
