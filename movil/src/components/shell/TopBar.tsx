// Mobile top bar: the 0ff1ce signature (or «‹ Volver» on detail views) and the four accesses:
// Tu turno (counter, alerta when critical), Notificaciones (dot), Calendario, Ajustes.
// Under it, the global pause banner and the offline strip.
import { useOverview } from '@compartido/api/hooks';
import { turnoAnchor } from '@compartido/logic/turno';
import NetInfo from '@react-native-community/netinfo';
import { router, usePathname } from 'expo-router';
import { useEffect, useState } from 'react';
import { Image, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Icon, type IconName } from '@/components/icons';
import { T } from '@/components/ui';
import { colors, radius, shell, space } from '@/theme/tokens';
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

function Counter({ count, critical }: { count: number; critical: boolean }) {
  if (count <= 0) return null;
  return (
    <View style={[styles.counter, critical ? styles.counterCritical : null]} testID="turn-counter">
      <T variant="etiqueta" color={critical ? colors.onAlert : colors.paper} style={styles.counterText}>
        {count > 99 ? '99+' : String(count)}
      </T>
    </View>
  );
}

export function PauseBanner() {
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
      onPress={() => router.push(control?.paused ? { pathname: '/ajustes', params: { ancla: 'maquina' } } : { pathname: '/tu-turno', params: { ancla: turnoAnchor(`account_paused:${account?.id ?? ''}`) } })}
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
  return (
    <View style={styles.wrap}>
      <View style={[styles.bar, { paddingTop: insets.top, height: shell.topBarHeight + insets.top }]}>
        {back ? (
          <Pressable accessibilityRole="button" onPress={back.onPress} style={styles.back}>
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
                onPress={() => router.navigate(item.path)}
                style={[styles.icon, current ? styles.iconCurrent : null]}
              >
                <Icon name={item.icon} color={current ? colors.ink : colors.inkSoft} />
                {item.path === '/tu-turno' ? <Counter count={turn.count} critical={turn.critical} /> : null}
                {item.path === '/notificaciones' && turn.unread > 0 ? <View style={styles.dot} testID="unread-dot" /> : null}
              </Pressable>
            );
          })}
        </View>
      </View>
      <PauseBanner />
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
  pause: { flexDirection: 'row', alignItems: 'center', gap: space[3], paddingVertical: 10, paddingHorizontal: space[4], backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.alert },
  pauseIcon: { width: 32, height: 32, borderRadius: radius.pill, backgroundColor: colors.alert, alignItems: 'center', justifyContent: 'center' },
  pauseText: { flex: 1 },
  offline: { paddingVertical: 6, paddingHorizontal: space[4], backgroundColor: colors.ink },
});
