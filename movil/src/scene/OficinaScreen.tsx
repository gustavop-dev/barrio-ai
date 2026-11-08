import { useCallback, useEffect, useMemo, useRef, useState, type ComponentRef } from 'react';
import { FlatList, Pressable, RefreshControl, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import { runOnUI } from 'react-native-reanimated';
import { GestureDetector, useNativeGesture } from 'react-native-gesture-handler';
import { useOfficeQueries, feedUnavailable } from '@compartido/api/oficinaQueries';
import { REFRESH } from '@compartido/api/hooks';
import { statusesFrom, type SceneStatus } from '@compartido/scene/activity';
import { nowLine } from '@compartido/scene/presentation';
import { narrateSceneSelection, selectScene } from '@compartido/scene/runtime';
import { PLAN_HEIGHT, sceneScale } from '@compartido/scene/plan';
import { CHARACTER_BY_ID, LIBRARIAN_ID, TEAMS, teamById, type CharacterId, type TeamId } from '@compartido/scene/roles';
import type { PanelData } from '@compartido/scene/panels';
import { timeAgo } from '@compartido/logic/format';
import { Button, ErrorRetry, Note, SnapSheet, T } from '@/components/ui';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { useCaptureSheet } from '@/capture/store';
import { haptic, officeGestures, sheetMotion, useMotion } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import { OfficeCanvas, type ScenePick } from './OfficeCanvas';
import { RolePanel, TeamPanel } from './OfficePanels';
import { useOfficeLifecycle } from './useOfficeLifecycle';
import { useOfficeScene } from './useOfficeScene';
import { OfficeNarration } from './OfficeNarration';

type Selection = { kind: 'team'; id: TeamId } | { kind: 'role'; id: CharacterId };
const TEAMS_AND_LIBRARY = [...TEAMS.map((t) => ({ id: t.id, name: t.name })), { id: 'biblioteca' as const, name: 'Biblioteca' }];
export function OficinaScreen() {
  const active = useOfficeLifecycle();
  const pageScroll = useNativeGesture();
  const { reduced } = useMotion();
  const { activity, overview, events } = useOfficeQueries(active);
  const live = Boolean(activity.data) && !activity.isError;
  const statuses = useMemo(() => statusesFrom(live ? activity.data : null), [live, activity.data]);
  const paused = Boolean(overview.data?.control?.paused);
  // Overview must be known before playing: a missing machine state must not look like a running one.
  const canPlay = live && Boolean(overview.data) && !overview.isError;
  // The scene pauses while something covers it: the capture sheet (a modal) or a panel dragged to full height.
  const captureOpen = useCaptureSheet().open;
  const [panelSnap, setPanelSnap] = useState(0);
  const [selection, setSelection] = useState<Selection | null>(null);
  const covered = captureOpen || (selection !== null && panelSnap >= sheetMotion.snaps[1]);
  const { scene, snapshot } = useOfficeScene({ active, live: canPlay, paused, reduced, statuses, page: events.data, covered });
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => setNow(Date.now()), REFRESH.scene);
    return () => clearInterval(timer);
  }, [active]);
  const window = useWindowDimensions();
  const insets = useContentInsets();
  const [height, setHeight] = useState(window.height - shell.topBarHeight);
  const scale = Math.round(sceneScale(window.width, height - insets.bottom) * window.scale) / window.scale;
  const sceneHeight = Math.min(PLAN_HEIGHT * scale, Math.max(240, height - insets.bottom - 100));
  const scroll = useRef<ComponentRef<typeof ScrollView>>(null);
  const select = useCallback((next: Selection) => {
    haptic('officePick'); scroll.current?.scrollTo({ y: 0, animated: !reduced }); setSelection(next);
    runOnUI(() => {
      scene.modify((s) => {
        const role = next.kind === 'role' ? next.id : null;
        selectScene(s, role, role ? CHARACTER_BY_ID[role].team : next.id as TeamId);
        if (role) { s.wallTime = Date.now(); narrateSceneSelection(s, role); }
        return s;
      });
    })();
  }, [reduced, scene]);
  const clearSelection = () => {
    setSelection(null);
    runOnUI(() => { scene.modify((s) => { selectScene(s, null, null); return s; }); })();
  };
  const onPick = useCallback((pick: ScenePick) => {
    select(pick.kind === 'role' ? pick : pick.id === 'biblioteca' ? { kind: 'role', id: LIBRARIAN_ID } : { kind: 'team', id: pick.id });
  }, [select]);
  const statusOf = (id: CharacterId): SceneStatus => id === LIBRARIAN_ID
    ? Object.values(statuses).some((s) => s !== 'desconocido') ? snapshot.librarianBusy ? 'trabajando' : 'en_espera' : 'desconocido'
    : statuses[id];
  const data: PanelData = { statusOf, activity: live ? activity.data : undefined, snapshot, now };
  const line = nowLine({ loading: activity.isPending, unavailable: activity.isError, paused, entry: snapshot.now, statuses, activity: activity.data, now });
  const selectedRole = selection?.kind === 'role' ? selection.id : null;
  const selectedZone = selection?.kind === 'team' ? selection.id : selectedRole ? CHARACTER_BY_ID[selectedRole].team : null;
  const label = selection ? selection.kind === 'team' ? teamById(selection.id).name : CHARACTER_BY_ID[selection.id].name : '';
  const [refreshing, setRefreshing] = useState(false);
  const refresh = async () => {
    if (!active) return;
    setRefreshing(true);
    try { await Promise.all([activity.refetch(), overview.refetch(), events.refetch()]); }
    finally { setRefreshing(false); }
  };
  return <View testID="screen-oficina" style={styles.root} onLayout={(e) => setHeight(e.nativeEvent.layout.height)}>
    <GestureDetector gesture={pageScroll}>
    <ScrollView ref={scroll} contentContainerStyle={{ paddingBottom: insets.bottom }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={colors.brandDeep} />}>
      <View>
        <OfficeCanvas scrollGesture={pageScroll} scene={scene} width={window.width} height={sceneHeight} visibleHeight={selection ? Math.min(sceneHeight, (height - insets.bottom + space[10]) * (1 - officeGestures.sheetHalf)) : sceneHeight} scale={scale} selectedRole={selectedRole} selectedZone={selectedZone} statuses={statuses} onPick={onPick} />
        {paused ? <View testID="oficina-pausa" pointerEvents="none" style={[StyleSheet.absoluteFill, styles.paused]} /> : null}
        <OfficeNarration line={line} revision={snapshot.now?.key ?? 0} reduced={reduced} />
      </View>
      <View style={styles.below}>
        <View style={styles.legend}>
          {(['Trabajando', 'En espera', 'En diseño'] as const).map((text, i) => <View key={text} style={styles.legendItem}><View style={[styles.dot, { backgroundColor: [colors.brand, colors.spriteBlue, colors.line][i] }]} /><T variant="detalle" soft>{text}</T></View>)}
        </View>
        <T variant="detalle" soft>{live ? `Actividad real · ${timeAgo(activity.data?.updated_at, now)}` : activity.isPending ? 'Leyendo actividad…' : 'Actividad no disponible'}</T>
        {activity.isError ? <Note tone="error" title="No se pudo leer la actividad." actions={<Button onPress={() => void activity.refetch()}>Reintentar</Button>}>Mientras tanto los personajes quedan quietos: la oficina no simula trabajo.</Note> : null}
        <ErrorRetry error={overview.error} title="No se pudo leer el estado de la máquina." onRetry={() => void overview.refetch()} />
        {feedUnavailable(events.error) ? <Note title="Aún no disponible">El registro de eventos no está disponible. Se muestra la actividad real de cada rol.</Note> : <ErrorRetry error={events.error} title="No se pudieron leer los eventos." onRetry={() => void events.refetch()} />}
      </View>
      <FlatList horizontal data={TEAMS_AND_LIBRARY} keyExtractor={(item) => item.id} accessibilityLabel="Equipos" testID="team-strip" showsHorizontalScrollIndicator={false} contentContainerStyle={styles.teams}
        renderItem={({ item }) => {
          const selected = item.id === 'biblioteca' ? selectedRole === LIBRARIAN_ID : selection?.kind === 'team' && selection.id === item.id;
          return <Pressable accessibilityRole="button" accessibilityLabel={item.name} accessibilityState={{ selected }} testID={`team-chip-${item.id}`} style={[styles.chip, selected && styles.chipOn]}
            onPress={() => select(item.id === 'biblioteca' ? { kind: 'role', id: LIBRARIAN_ID } : { kind: 'team', id: item.id })}>
            <T variant="detalle" color={selected ? colors.paper : colors.ink}>{item.name}</T>
          </Pressable>;
        }} />
      <T variant="detalle" soft style={styles.credit}>Arte: LimeZu — Modern Interiors</T>
    </ScrollView>
    </GestureDetector>
    {selection ? <SnapSheet label={label} testID="office-panel" bottom={insets.bottom - space[10]} availableHeight={height} onClose={clearSelection} onRest={setPanelSnap}>
      {selection.kind === 'team' ? <TeamPanel team={selection.id} data={data} onRole={(id) => select({ kind: 'role', id })} /> : <RolePanel id={selection.id} data={data} onTeam={(id) => select({ kind: 'team', id })} />}
    </SnapSheet> : null}
  </View>;
}
const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.paper },
  paused: { backgroundColor: colors.backdrop },
  below: { padding: space[4], gap: space[2] },
  legend: { flexDirection: 'row', flexWrap: 'wrap', gap: space[3] },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: space[1] },
  dot: { width: 10, height: 10, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.ink },
  teams: { gap: space[2], paddingHorizontal: space[4] },
  chip: { minHeight: 48, paddingHorizontal: space[3], justifyContent: 'center', backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.inkSoft, borderRadius: radius.pill },
  chipOn: { backgroundColor: colors.ink },
  credit: { padding: space[4] },
});
