// Tu turno: only what Gustavo alone can resolve, grouped Urgente → Importante → Cuando puedas, the
// expired ones in a neutral tone, then the folds («Pospuestas», «Hecho recientemente», «Cómo se
// ordena»), and the «Lo que el equipo sabe de ti» tab. Pull to refresh; `ancla` scrolls to a card.
//
// Motion (MovTuTurno, see exits.ts): a resolved card leaves step by step and the list closes the gap
// with an item layout animation; the group counters and «Pospuestas» roll once it is gone.
import { useTuTurno } from '@compartido/api/hooks';
import type { TuTurno, TurnoCard as TurnoCardData, TurnoRecent } from '@compartido/api/types';
import { agoText, dayAndTime, doneTodaySentence, longDate, toAgent, turnoAnchor } from '@compartido/logic/turno';
import { router, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { FlatList, RefreshControl, ScrollView, StyleSheet, View, type ListViewToken } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withDelay, withTiming } from 'react-native-reanimated';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { Badge, Button, EmptyText, ErrorRetry, Fold, IdleLibrarian, PageHeader, Skeleton, T, TabBar, pageContent } from '@/components/ui';
import { timing, timingWith, turnoLayout, turnoMotion, turnoTimings, useMotion } from '@/theme/motion';
import { colors, space } from '@/theme/tokens';
import { ExitRow } from './ExitRow';
import { buildRows, pendingView, summaryOf, TurnoExitsContext, usePublishHeld, useTurnoExits, type Row } from './exits';
import { PostponedFold } from './PostponedFold';
import { RollingNumber } from './RollingNumber';
import { Sabe } from './Sabe';
import { TurnoCard } from './TurnoCard';
import { SEEN_VIEWABILITY, useSeenCards } from './useSeenCards';

export { buildRows, pendingView };

type Tab = 'pendiente' | 'sabe';

const TABS = [
  { value: 'pendiente', label: 'Pendiente' },
  { value: 'sabe', label: 'Lo que el equipo sabe de ti' },
] as const;

/** Cards that were Nueva when they first showed keep «NUEVA» for the whole visit. */
function useFreshIds(cards: readonly TurnoCardData[]): ReadonlySet<string> {
  const [fresh, setFresh] = useState<ReadonlySet<string>>(() => new Set());
  const added = cards.filter((card) => card.state === 'nueva' && !fresh.has(card.id)).map((card) => card.id);
  if (added.length) setFresh((current) => new Set([...current, ...added]));
  return fresh;
}

/**
 * A row fading in as it joins the list (`timings.listEnter`). A shared value, not Reanimated `entering`: a row mounted
 * right after a sheet's Modal closed stayed at opacity 0, invisible to Gustavo and to the QA (the folds, run
 * 42466144199; the same pattern as the Galería tiles in 05-captura-envios). With reduced motion it is visible at once.
 */
function RowIn({ children, style, delay = 0, duration }: { children: ReactNode; style?: object; delay?: number; duration?: number }) {
  const { reduced } = useMotion();
  const shown = useSharedValue(reduced ? 1 : 0);
  useEffect(() => {
    const fade = withTiming(1, duration ? timingWith(duration, 'enter') : timing('listEnter'));
    shown.set(delay ? withDelay(delay, fade) : fade);
  }, [shown, delay, duration]);
  const fade = useAnimatedStyle(() => ({ opacity: shown.value }));
  return <Animated.View style={[style, fade]}>{children}</Animated.View>;
}

/** A group's label (the Section look): «URGENTE · 1», its number rolling when a card stops counting. */
function GroupLabel({ name, count, intro }: { name: string; count: number; intro?: string }) {
  return (
    <View style={styles.section}>
      <View accessible accessibilityRole="header" accessibilityLabel={`${name} · ${count}`} style={styles.labelRow}>
        <T variant="etiqueta" soft>
          {name} ·{' '}
        </T>
        <RollingNumber value={String(count)} variant="etiqueta" soft />
      </View>
      {intro ? (
        <T variant="detalle" soft>
          {intro}
        </T>
      ) : null}
    </View>
  );
}

function FoldRow({ title, sub, badge }: { title: string; sub: string; badge: string }) {
  return (
    <View style={styles.foldRow}>
      <View style={styles.foldText}>
        <T>{title}</T>
        {sub ? (
          <T variant="detalle" soft>
            {sub}
          </T>
        ) : null}
      </View>
      <Badge tone="muted">{badge}</Badge>
    </View>
  );
}

function postponedTitle(card: TurnoCardData): string {
  if (card.question) return `Responde ${toAgent(card.agent_label)}: ${card.question.question}`;
  return card.title;
}

function postponedSub(card: TurnoCardData): string {
  const back = longDate(card.question?.postponed_until);
  return back ? `Vuelve el ${back} · no cuenta en el contador` : 'No cuenta en el contador';
}

function recentSorted(recent: readonly TurnoRecent[]): TurnoRecent[] {
  return [...recent].sort((a, b) => (b.at ?? '').localeCompare(a.at ?? ''));
}

interface FoldsProps {
  postponedCount: number;
  postponed: TurnoCardData[];
  recent: TurnoRecent[];
  flash: number;
}

function Folds({ postponedCount, postponed, recent, flash }: FoldsProps) {
  return (
    <View style={styles.folds}>
      <PostponedFold count={postponedCount} flash={flash}>
        {postponed.map((card) => (
          <FoldRow key={card.id} title={postponedTitle(card)} sub={postponedSub(card)} badge="Pospuesta" />
        ))}
      </PostponedFold>
      {recent.length ? (
        <Fold summary={`Hecho recientemente · ${recent.length}`}>
          {recentSorted(recent).map((item) => (
            <FoldRow key={`${item.kind}:${item.id}:${item.at}`} title={item.title} sub={agoText(item.at)} badge={item.how} />
          ))}
        </Fold>
      ) : null}
      <Fold summary="Cómo se ordena lo que depende de ti">
        <T variant="detalle">Urgente: algo se rompe o se queda bloqueado si no actúas. Pone el contador en rojo.</T>
        <T variant="detalle">Importante: tiene plazo en menos de 48 h, alguien espera tu respuesta o algo caduca en unos días.</T>
        <T variant="detalle">Cuando puedas: preguntas y tareas sin prisa. Si su plazo se acerca, suben solas a Importante.</T>
        <T variant="detalle" soft>
          Lo pospuesto sale del contador hasta su fecha. Lo informativo no entra aquí: va a Notificaciones.
        </T>
      </Fold>
    </View>
  );
}

/** «Nada depende de ti hoy» (the EmptyState look). After the last card it fades in late and its librarian rises (MovTuTurno). */
function NothingPending({ data, afterExit, reduced }: { data: TuTurno; afterExit: boolean; reduced: boolean }) {
  const sentence = doneTodaySentence(data.summary?.done_today);
  const next = data.summary?.next_piece;
  return (
    <RowIn
      style={styles.empty}
      delay={afterExit && !reduced ? turnoMotion.emptyDelayMs : 0}
      duration={afterExit ? turnoTimings.emptyIn.duration : undefined}
    >
      <View testID="turno-empty" style={styles.emptyInner}>
        <IdleLibrarian />
      <T variant="subtitulo" center accessibilityRole="header">
        Nada depende de ti hoy
      </T>
      {sentence || next ? (
        <View style={styles.emptyText}>
          {sentence ? <EmptyText>{sentence}</EmptyText> : null}
          {next ? <EmptyText>La próxima pieza sale {dayAndTime(next.scheduled_for)}.</EmptyText> : null}
        </View>
      ) : null}
      <View>
        <Button variant="ghost" onPress={() => router.navigate('/calendario')}>
          Ver el Calendario
        </Button>
      </View>
      </View>
    </RowIn>
  );
}

export function TuTurnoScreen() {
  const params = useLocalSearchParams<{ tab?: string; ancla?: string }>();
  // The tab the link asked for, until Gustavo picks another one (a new link resets it).
  const linked: Tab = params.tab === 'sabe' ? 'sabe' : 'pendiente';
  const [choice, setChoice] = useState<{ link: Tab; tab: Tab } | null>(null);
  const tab = choice && choice.link === linked ? choice.tab : linked;
  const setTab = (next: Tab) => setChoice({ link: linked, tab: next });
  const turno = useTuTurno();
  const { bottom } = useContentInsets();
  const { reduced } = useMotion();
  const view = useMemo(() => pendingView(turno.data), [turno.data]);
  const live = useMemo(() => buildRows(view), [view]);
  const exits = useTurnoExits(live, reduced);
  const rows = exits.rows;
  usePublishHeld(exits.state, turno.data);
  const fresh = useFreshIds(view.cards);
  const markSeen = useSeenCards();
  const list = useRef<FlatList<Row>>(null);
  const scrolledTo = useRef('');
  const [refreshing, setRefreshing] = useState(false);

  // Scroll to /tu-turno#turno-<id> once the cards are there.
  useEffect(() => {
    const anchor = params.ancla;
    if (!anchor || tab !== 'pendiente' || !turno.data || scrolledTo.current === anchor) return;
    const index = rows.findIndex((row) => row.kind === 'card' && turnoAnchor(row.card.id) === anchor);
    if (index < 0) return;
    scrolledTo.current = anchor;
    requestAnimationFrame(() => list.current?.scrollToIndex({ index, viewPosition: 0, animated: true }));
  }, [params.ancla, rows, tab, turno.data]);

  // Stable (FlatList refuses a new onViewableItemsChanged): markSeen never changes.
  const onViewable = useCallback(
    ({ viewableItems }: { viewableItems: ListViewToken[] }) => {
      const ids = viewableItems.flatMap(({ item }) => {
        const row = item as Row | undefined;
        return row?.kind === 'card' && row.card.state === 'nueva' ? [row.card.id] : [];
      });
      if (ids.length) markSeen(ids);
    },
    [markSeen],
  );

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await turno.refetch();
    } finally {
      setRefreshing(false);
    }
  }, [turno]);

  const header = (
    <View style={styles.header}>
      <PageHeader title="Bandeja de entrada" subtitle={summaryOf(rows)} />
      <TabBar<Tab> label="Bandeja de entrada" tabs={TABS} value={tab} onChange={setTab} />
      {tab === 'pendiente' && turno.error && turno.data ? <ErrorRetry error={turno.error} onRetry={() => void turno.refetch()} title="No se pudo actualizar" /> : null}
    </View>
  );

  if (tab === 'sabe') {
    return (
      <ScrollView style={styles.screen} contentContainerStyle={[pageContent, styles.gapSmall, { paddingBottom: bottom }]} keyboardShouldPersistTaps="handled">
        {header}
        <Sabe />
      </ScrollView>
    );
  }

  const renderRow = ({ item }: { item: Row }) => {
    switch (item.kind) {
      case 'label':
        return (
          <Animated.View exiting={reduced ? undefined : turnoLayout.collapse()} style={[styles.label, styles.clip]}>
            <RowIn>
              <GroupLabel name={item.name} count={item.count} intro={item.intro} />
            </RowIn>
          </Animated.View>
        );
      case 'card': {
        const exit = exits.state.exits[item.card.id];
        return (
          <ExitRow exit={exit}>
            <TurnoCard card={item.card} priority={item.priority} exit={exit} isNew={item.priority !== null && (item.card.state === 'nueva' || fresh.has(item.card.id))} />
          </ExitRow>
        );
      }
      case 'empty':
        return turno.data ? <NothingPending data={turno.data} afterExit={exits.state.emptyAfterExit} reduced={reduced} /> : null;
      case 'folds':
        return (
          <RowIn>
            <Folds postponedCount={item.postponed} postponed={view.postponed} recent={view.recent} flash={exits.state.flash} />
          </RowIn>
        );
    }
  };

  return (
    <TurnoExitsContext value={exits.api}>
      <Animated.FlatList
        ref={list}
        testID="turno-list"
        style={styles.screen}
        contentContainerStyle={[pageContent, styles.gapCards, { paddingBottom: bottom }]}
        data={turno.data ? rows : []}
        keyExtractor={(row: Row) => row.key}
        keyboardShouldPersistTaps="handled"
        // With reduced motion nothing animates in or moves: the rows mounted later (the folds after the first
        // batch, a group counter that changes) were left invisible on Android with the system animations off.
        itemLayoutAnimation={reduced ? undefined : turnoLayout.listMove()}
        // A short list: keep every row attached, so a row scrolled back into view is never left blank.
        removeClippedSubviews={false}
        ListHeaderComponent={header}
        ListEmptyComponent={
          turno.isPending ? (
            <Skeleton variant="card" count={3} label="Cargando lo que depende de ti…" />
          ) : !turno.data ? (
            <ErrorRetry error={turno.error} onRetry={() => void turno.refetch()} />
          ) : undefined
        }
        renderItem={renderRow}
        viewabilityConfig={SEEN_VIEWABILITY}
        onViewableItemsChanged={onViewable}
        onScrollToIndexFailed={({ index, averageItemLength }: { index: number; averageItemLength: number }) => {
          list.current?.scrollToOffset({ offset: index * averageItemLength, animated: false });
          setTimeout(() => list.current?.scrollToIndex({ index, viewPosition: 0, animated: true }), 120);
        }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={colors.brandDeep} colors={[colors.brandDeep]} />}
      />
    </TurnoExitsContext>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  header: { gap: space[4], marginBottom: space[2] },
  gapSmall: { gap: space[3] },
  gapCards: { gap: space[3] },
  label: { marginTop: space[3] },
  clip: { overflow: 'hidden' },
  section: { gap: space[3] },
  labelRow: { flexDirection: 'row', alignItems: 'center' },
  folds: { marginTop: space[6] },
  foldRow: { flexDirection: 'row', alignItems: 'flex-start', gap: space[2], paddingVertical: 10, borderTopWidth: 1, borderTopColor: colors.line },
  foldText: { flex: 1, gap: 2 },
  empty: { paddingVertical: space[6] },
  emptyInner: { gap: space[3], alignItems: 'center' },
  emptyText: { gap: space[2], maxWidth: 340 },
});
