// The shell at mobile size: the top bar over every view and the bottom bar with the capture button.
// Tu turno, Notificaciones, Calendario and Ajustes are tabs without a button of their own (the top
// bar opens them); Android back goes through the tab history.
//
// Those four are NOT declared with `href: null`. In Expo Router 58, `href: null` on a js-tabs screen
// becomes `hidden: true`, and a focused hidden tab makes the navigator render nothing and replace the
// route with the first visible tab: the top bar could never open them (the APK of #38). They need no
// hiding anyway: the tab bar is BottomBar, which only draws the four bottom tabs.
//
// Motion (MovNavegacion): the top bar stays while the content changes (tabTransitions.ts); the
// top-bar screens open with the push. When a detail screen is pushed over the tabs, the whole shell
// moves left and darkens with it (push.ts).
import { useNavigation, useRootNavigationState, useRoute } from 'expo-router';
import { Tabs, type TabsScreenOptions } from 'expo-router/js-tabs';
import { useEffect, useRef, type ComponentRef } from 'react';
import { StyleSheet, View, useWindowDimensions } from 'react-native';
import Animated, { useAnimatedStyle } from 'react-native-reanimated';
import { BottomBar } from '@/components/shell/BottomBar';
import { TopBar } from '@/components/shell/TopBar';
import { baseFrame, pushProgress, registerLayer, stackLevel } from '@/components/shell/push';
import { focusedChild, sceneRole, tabMove, tabSceneOptions, useFocusMemory } from '@/components/shell/tabTransitions';
import { useMotion } from '@/theme/motion';
import { colors } from '@/theme/tokens';

/** The tabs in the navigator's order (the side a scene slides from depends on it). */
const ORDER = ['index', 'resultados', 'personas', 'galeria', 'tu-turno', 'notificaciones', 'calendario', 'ajustes'] as const;

export default function TabsLayout() {
  const navigation = useNavigation();
  const route = useRoute();
  const level = stackLevel(navigation.getState(), route.key);
  const covered = pushProgress(level + 1);
  const { reduced } = useMotion();
  const { width } = useWindowDimensions();
  const root = useRef<ComponentRef<typeof View>>(null);
  // The focused tab, from the root state of this very render: the navigator below receives the same
  // state in the same pass, so each scene's part in the change is right before its animation starts.
  const focus = useFocusMemory(focusedChild(useRootNavigationState(), route.key));

  useEffect(() => registerLayer(level, root.current), [level]);

  const shift = useAnimatedStyle(() => ({ transform: [{ translateX: baseFrame(covered.value, width, reduced).translateX }] }), [covered, width, reduced]);
  const dim = useAnimatedStyle(() => ({ opacity: baseFrame(covered.value, width, reduced).dim }), [covered, width, reduced]);

  const screenOptions = ({ route: tab }: { route: { name: string } }): TabsScreenOptions => {
    const { role, side } = sceneRole(focus, tab.name, ORDER);
    return {
      headerShown: false,
      sceneStyle: { backgroundColor: colors.paper },
      ...tabSceneOptions(tabMove(focus.previous, focus.current ?? tab.name), role, side, width, reduced),
    };
  };

  return (
    <Animated.View testID="shell-tabs" style={[styles.root, shift]}>
      <View ref={root} collapsable={false} pointerEvents="none" style={styles.fill} />
      <TopBar />
      <View style={styles.scenes}>
        <Tabs backBehavior="history" tabBar={(props) => <BottomBar {...props} />} screenOptions={screenOptions}>
          <Tabs.Screen name="index" options={{ title: 'Oficina' }} />
          <Tabs.Screen name="resultados" options={{ title: 'Resultados' }} />
          <Tabs.Screen name="personas" options={{ title: 'Personas' }} />
          <Tabs.Screen name="galeria" options={{ title: 'Galería' }} />
          {/* The top bar's four: real tabs, without `href: null` (see the note at the top). */}
          <Tabs.Screen name="tu-turno" options={{ title: 'Tu turno' }} />
          <Tabs.Screen name="notificaciones" options={{ title: 'Notificaciones' }} />
          <Tabs.Screen name="calendario" options={{ title: 'Calendario' }} />
          <Tabs.Screen name="ajustes" options={{ title: 'Ajustes' }} />
        </Tabs>
      </View>
      <Animated.View pointerEvents="none" style={[styles.fill, styles.dim, dim]} />
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.paper },
  fill: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0 },
  scenes: { flex: 1 },
  dim: { backgroundColor: colors.ink, opacity: 0 },
});
