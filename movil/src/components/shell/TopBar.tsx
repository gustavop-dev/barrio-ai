// Mobile top bar: the 0ff1ce signature (or «‹ Volver» on detail views) and the four accesses:
// Tu turno (counter, alerta when critical), Notificaciones (dot), Calendario, Ajustes.
// Under it, the global pause banner and the offline strip.
//
// Motion (MovTuTurno, MovNotificaciones): the Tu turno counter rolls to its new number and pops
// (`badge`, SOFT) when it changes; when a notification arrives the bell sways and its dot pops in
// from nothing (`dot`, SOFT), and the dot closes (FIRM) once everything is read.
import { useOverview } from '@compartido/api/hooks';
import { turnoAnchor } from '@compartido/logic/turno';
import NetInfo from '@react-native-community/netinfo';
import { router, usePathname, type Href } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Image, Pressable, StyleSheet, View } from 'react-native';
import Animated, { runOnJS, useAnimatedStyle, useSharedValue, withSequence, withSpring, withTiming } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Icon, type IconName } from '@/components/icons';
import { T } from '@/components/ui';
import { reportUnread, useLiveNotifications } from '@/notificaciones/arrival';
import { notifMotion, notifSpring, notifTiming, turnoMotion, turnoSpring, useMotion } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import { RollingNumber } from '@/turno/RollingNumber';
import FIRMA from '../../../assets/brand/firma-horizontal.png';
import { notificationsLabel, turnLabel, useTurnCount } from './useTurnCount';

interface Access {
  path: '/tu-turno' | '/notificaciones' | '/calendario' | '/ajustes';
  label: string;
  icon: IconName;
}

export const TOP_NAV: readonly Access[] = [
  { path: '/tu-turno', label: 'Tu turno', icon: 'tuTurno' },
  { path: '/notificaciones', label: 'Notificaciones', icon: 'notificaciones' },
  { path: '/calendario', label: 'Calendario', icon: 'calendario' },
  { path: '/ajustes', label: 'Ajustes', icon: 'ajustes' },
];

/**
 * Calls `onChange` when a value of GET /tu-turno changes. Its first answer is not a change: `onFirst`
 * gets it instead (and the value a top bar finds when it mounts).
 */
function useChange<V>(value: V, loaded: boolean, onChange: (before: V, now: V) => void, onFirst?: (now: V) => void) {
  const previous = useRef<{ value: V } | null>(null);
  const handlers = useRef({ onChange, onFirst });
  useEffect(() => {
    handlers.current = { onChange, onFirst };
  });
  useEffect(() => {
    if (!loaded) return;
    const before = previous.current;
    previous.current = { value };
    if (!before) handlers.current.onFirst?.(value);
    else if (before.value !== value) handlers.current.onChange(before.value, value);
  }, [value, loaded]);
}

/** Tu turno's counter (MovTuTurno `badge`): a new number rolls in and the badge pops back from badgePop. */
function Counter({ count, critical, loaded }: { count: number; critical: boolean; loaded: boolean }) {
  const scale = useSharedValue(1);
  useChange(count, loaded, () => {
    scale.set(turnoMotion.badgePop);
    scale.set(withSpring(1, turnoSpring('badge')));
  });
  const pop = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  if (count <= 0) return null;
  return (
    <Animated.View style={[styles.counter, critical ? styles.counterCritical : null, pop]} testID="turn-counter">
      <RollingNumber value={count > 99 ? '99+' : String(count)} variant="etiqueta" color={critical ? colors.onAlert : colors.paper} style={styles.counterText} />
    </Animated.View>
  );
}

/**
 * The bell and its dot (MovNotificaciones). An arrival sways the bell through `bellSway` (each step
 * eased out, from a pivot near its top) and pops the dot in from 0; reading everything closes the dot,
 * which leaves the tree once it is shut. With reduced motion the bell stays still and the dot just shows.
 */
function Bell({ color, unread, loaded }: { color: string; unread: number; loaded: boolean }) {
  const { reduced } = useMotion();
  const angle = useSharedValue(0);
  const dot = useSharedValue(unread > 0 ? 1 : 0);
  const [closing, setClosing] = useState(false);
  const [shown, setShown] = useState(unread);
  if (shown !== unread) {
    setShown(unread);
    setClosing(unread === 0 && shown > 0 && !reduced);
  }

  useEffect(() => {
    if (loaded) reportUnread(unread);
  }, [unread, loaded]);

  useChange(
    unread,
    loaded,
    (before, now) => {
      if (now > before) {
        dot.set(0);
        dot.set(withSpring(1, notifSpring('dotIn')));
        if (!reduced) angle.set(withSequence(...notifMotion.bellSway.map((step) => withTiming(step, notifTiming('bellStep')))));
      } else if (now === 0) {
        dot.set(
          withSpring(0, notifSpring('dotOut'), (finished) => {
            if (finished) runOnJS(setClosing)(false);
          }),
        );
      }
    },
    // What GET /tu-turno said first: the dot is just there.
    (now) => dot.set(now > 0 ? 1 : 0),
  );

  const sway = useAnimatedStyle(() => ({ transform: [{ rotate: `${angle.value}deg` }] }));
  const pulse = useAnimatedStyle(() => ({ transform: [{ scale: Math.max(0, dot.value) }] }));
  return (
    <>
      <Animated.View style={[styles.bell, sway]} testID="bell">
        <Icon name="notificaciones" color={color} />
      </Animated.View>
      {unread > 0 || closing ? <Animated.View style={[styles.dot, pulse]} testID={unread > 0 ? 'unread-dot' : 'unread-dot-closing'} /> : null}
    </>
  );
}

/** Opens a screen of the tabs from the top bar (see `TopBar`). */
type Open = (href: Href) => void;

const pushHref: Open = (href) => router.push(href);

export function PauseBanner({ open = pushHref }: { open?: Open }) {
  const overview = useOverview();
  const control = overview.data?.control;
  const account = overview.data?.accounts?.find((a) => a.paused);
  if (!control?.paused && !account) return null;
  const title = control?.paused ? 'Máquina en pausa' : 'La cuenta de LinkedIn está en pausa';
  const detail = control?.paused ? [control.reason, control.source === 'env' ? 'fijada en el entorno' : ''].filter(Boolean) : account?.paused_reason ? [account.paused_reason] : [];
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLiveRegion="polite"
      onPress={() => open(control?.paused ? { pathname: '/ajustes', params: { ancla: 'maquina' } } : { pathname: '/tu-turno', params: { ancla: turnoAnchor(`account_paused:${account?.id ?? ''}`) } })}
      style={styles.pause}
    >
      <View style={styles.pauseIcon}>
        <Icon name="pausa" size={20} color={colors.onAlert} />
      </View>
      <T variant="detalle" style={styles.pauseText} numberOfLines={2}>
        <T variant="detalle">{title}</T>
        {detail.map((part) => ` · ${part}`).join('')}
      </T>
      <Icon name="chevronRight" size={20} color={colors.inkSoft} />
    </Pressable>
  );
}

export function OfflineStrip() {
  const [online, setOnline] = useState(true);
  useEffect(() => NetInfo.addEventListener((state) => setOnline(state.isConnected !== false)), []);
  if (online) return null;
  return (
    <View style={styles.offline} accessibilityLiveRegion="polite">
      <T variant="detalle" color={colors.paper}>
        Sin conexión. Mostrando lo último que cargó.
      </T>
    </View>
  );
}

export function TopBar({ back }: { back?: { label: string; onPress: () => void } | null }) {
  const insets = useSafeAreaInsets();
  const pathname = usePathname();
  const turn = useTurnCount();
  useLiveNotifications();
  // On a detail view (`back`) the tabs are under it in the (app) stack: dismissTo goes back down to
  // them (the detail runs its push back first) and focuses the tab, keeping the tab history. A
  // navigate from there would push a second shell over the detail: in Expo Router 58 a stack's
  // NAVIGATE only reuses the route on top.
  const open: Open = back ? (href) => router.dismissTo(href) : (href) => router.navigate(href);
  return (
    <View style={styles.wrap}>
      <View style={[styles.bar, { paddingTop: insets.top, height: shell.topBarHeight + insets.top }]}>
        {back ? (
          <Pressable accessibilityRole="button" onPress={back.onPress} style={styles.back} testID="top-volver">
            <Icon name="chevronLeft" size={20} />
            <T>{back.label}</T>
          </Pressable>
        ) : (
          <Pressable accessibilityRole="link" accessibilityLabel="0ff1ce, ir a la Oficina" onPress={() => router.navigate('/')} style={styles.brand}>
            <Image source={FIRMA} style={styles.firma} resizeMode="contain" />
          </Pressable>
        )}
        <View style={styles.nav} accessibilityRole="toolbar" accessibilityLabel="Accesos">
          {TOP_NAV.map((item) => {
            const current = pathname === item.path || pathname.startsWith(`${item.path}/`);
            const label = item.path === '/tu-turno' ? turnLabel(turn) : item.path === '/notificaciones' ? notificationsLabel(turn.unread) : item.label;
            return (
              <Pressable
                key={item.path}
                testID={`top-${item.path.slice(1)}`}
                accessibilityRole="link"
                accessibilityLabel={label}
                accessibilityState={{ selected: current }}
                onPress={() => open(item.path)}
                style={[styles.icon, current ? styles.iconCurrent : null]}
              >
                {item.path === '/notificaciones' ? (
                  <Bell color={current ? colors.ink : colors.inkSoft} unread={turn.unread} loaded={turn.loaded} />
                ) : (
                  <Icon name={item.icon} color={current ? colors.ink : colors.inkSoft} />
                )}
                {item.path === '/tu-turno' ? <Counter count={turn.count} critical={turn.critical} loaded={turn.loaded} /> : null}
              </Pressable>
            );
          })}
        </View>
      </View>
      <PauseBanner open={back ? open : undefined} />
      <OfflineStrip />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { backgroundColor: colors.surface },
  bar: { paddingLeft: space[3], paddingRight: space[1], flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.line },
  brand: { minHeight: shell.touch, justifyContent: 'center' },
  firma: { width: 92, height: 28 },
  back: { minHeight: shell.touch, flexDirection: 'row', alignItems: 'center', gap: space[1], paddingRight: space[2] },
  nav: { flexDirection: 'row', alignItems: 'center' },
  icon: { width: shell.touch, height: shell.touch, alignItems: 'center', justifyContent: 'center', borderRadius: radius.pill },
  iconCurrent: { backgroundColor: colors.brandLight },
  counter: { position: 'absolute', top: 4, right: 2, minWidth: 18, height: 18, paddingHorizontal: 5, borderRadius: radius.pill, backgroundColor: colors.ink, alignItems: 'center', justifyContent: 'center' },
  counterCritical: { backgroundColor: colors.alert },
  counterText: { letterSpacing: 0, lineHeight: 18 },
  dot: { position: 'absolute', top: 9, right: 10, width: 9, height: 9, borderRadius: radius.pill, backgroundColor: colors.brand, borderWidth: 1.5, borderColor: colors.ink },
  bell: { transformOrigin: `${notifMotion.bellPivot.x * 100}% ${notifMotion.bellPivot.y * 100}%` },
  pause: { flexDirection: 'row', alignItems: 'center', gap: space[3], paddingVertical: 10, paddingHorizontal: space[4], backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.alert },
  pauseIcon: { width: 32, height: 32, borderRadius: radius.pill, backgroundColor: colors.alert, alignItems: 'center', justifyContent: 'center' },
  pauseText: { flex: 1 },
  offline: { paddingVertical: 6, paddingHorizontal: space[4], backgroundColor: colors.ink },
});
