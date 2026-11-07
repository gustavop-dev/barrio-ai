// Tu turno: only what Gustavo alone can resolve, grouped Urgente → Importante → Cuando puedas, the
// expired ones in a neutral tone, then the folds («Pospuestas», «Hecho recientemente», «Cómo se
// ordena»), and the «Lo que el equipo sabe de ti» tab. Pull to refresh; `ancla` scrolls to a card.
import { useTuTurno } from '@compartido/api/hooks';
import type { TuTurno, TurnoCard as TurnoCardData, TurnoPriority, TurnoRecent } from '@compartido/api/types';
import {
  activeCards,
  agoText,
  dayAndTime,
  doneTodaySentence,
  groupByPriority,
  longDate,
  PRIORITY_LABEL,
  prioritySummary,
  splitLater,
  toAgent,
  turnoAnchor,
} from '@compartido/logic/turno';
import { router, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FlatList, RefreshControl, ScrollView, StyleSheet, View, type ListViewToken } from 'react-native';
import Animated from 'react-native-reanimated';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { Badge, Button, EmptyState, EmptyText, ErrorRetry, Fold, PageHeader, Section, Skeleton, T, TabBar, pageContent } from '@/components/ui';
import { layout } from '@/theme/motion';
import { colors, space } from '@/theme/tokens';
import { Sabe } from './Sabe';
import { TurnoCard } from './TurnoCard';
import { SEEN_VIEWABILITY, useSeenCards } from './useSeenCards';

type Tab = 'pendiente' | 'sabe';

const TABS = [
  { value: 'pendiente', label: 'Pendiente' },
  { value: 'sabe', label: 'Lo que el equipo sabe de ti' },
] as const;

/** The derived parts of GET /tu-turno that the list and its header share. */
export function pendingView(data: TuTurno | undefined) {
  const cards = data ? activeCards(data) : [];
  const groups = groupByPriority(cards);
  const { postponed, expired } = splitLater(data?.later);
  return { cards, groups, postponed, expired, recent: data?.recent ?? [] };
}

type Row =
  | { key: string; kind: 'label'; label: string; intro?: string }
  | { key: string; kind: 'card'; card: TurnoCardData; priority: TurnoPriority | null };

const QUESTION_INTRO = 'Lo que respondas pasa a la memoria confirmada: así el equipo puede contar experiencias reales.';

export function buildRows(view: ReturnType<typeof pendingView>): Row[] {
  const rows: Row[] = [];
  for (const group of view.groups) {
    rows.push({
      key: `label-${group.priority}`,
      kind: 'label',
      label: `${PRIORITY_LABEL[group.priority]} · ${group.cards.length}`,
      intro: group.priority === 'cuando_puedas' && group.cards.some((card) => card.question) ? QUESTION_INTRO : undefined,
    });
    for (const card of group.cards) rows.push({ key: card.id, kind: 'card', card, priority: group.priority });
  }
  if (view.expired.length) {
    rows.push({ key: 'label-caducadas', kind: 'label', label: `Ya no es urgente · ${view.expired.length}` });
    for (const card of view.expired) rows.push({ key: `caducada-${card.id}`, kind: 'card', card, priority: null });
  }
  return rows;
}

/** Cards that were Nueva when they first showed keep «NUEVA» for the whole visit. */
function useFreshIds(cards: readonly TurnoCardData[]): ReadonlySet<string> {
  const [fresh, setFresh] = useState<ReadonlySet<string>>(() => new Set());
  const added = cards.filter((card) => card.state === 'nueva' && !fresh.has(card.id)).map((card) => card.id);
  if (added.length) setFresh((current) => new Set([...current, ...added]));
  return fresh;
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

function Folds({ postponed, recent }: { postponed: TurnoCardData[]; recent: TurnoRecent[] }) {
  return (
    <View style={styles.folds}>
      {postponed.length ? (
        <Fold summary={`Pospuestas · ${postponed.length}`}>
          {postponed.map((card) => (
            <FoldRow key={card.id} title={postponedTitle(card)} sub={postponedSub(card)} badge="Pospuesta" />
          ))}
        </Fold>
      ) : null}
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

function NothingPending({ data }: { data: TuTurno }) {
  const sentence = doneTodaySentence(data.summary?.done_today);
  const next = data.summary?.next_piece;
  return (
    <EmptyState
      title="Nada depende de ti hoy"
      action={
        <Button variant="ghost" onPress={() => router.navigate('/calendario')}>
          Ver el Calendario
        </Button>
      }
    >
      {sentence ? <EmptyText>{sentence}</EmptyText> : null}
      {next ? <EmptyText>La próxima pieza sale {dayAndTime(next.scheduled_for)}.</EmptyText> : null}
    </EmptyState>
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
  const view = useMemo(() => pendingView(turno.data), [turno.data]);
  const rows = useMemo(() => buildRows(view), [view]);
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
      <PageHeader title="Tu turno" subtitle={view.groups.length ? prioritySummary(view.groups) : null} />
      <TabBar<Tab> label="Tu turno" tabs={TABS} value={tab} onChange={setTab} />
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

  const nothing = view.groups.length === 0;
  const quiet = nothing && !view.postponed.length && !view.recent.length;

  return (
    <FlatList
      ref={list}
      testID="turno-list"
      style={styles.screen}
      contentContainerStyle={[pageContent, styles.gapCards, { paddingBottom: bottom }]}
      data={turno.data ? rows : []}
      keyExtractor={(row) => row.key}
      keyboardShouldPersistTaps="handled"
      ListHeaderComponent={header}
      ListEmptyComponent={
        turno.isPending ? (
          <Skeleton variant="card" count={3} label="Cargando lo que depende de ti…" />
        ) : !turno.data ? (
          <ErrorRetry error={turno.error} onRetry={() => void turno.refetch()} />
        ) : nothing ? (
          <NothingPending data={turno.data} />
        ) : undefined
      }
      ListFooterComponent={turno.data && !quiet ? <Folds postponed={view.postponed} recent={view.recent} /> : undefined}
      renderItem={({ item }) =>
        item.kind === 'label' ? (
          <Animated.View entering={layout.listEnter()} style={styles.label}>
            <Section label={item.label} intro={item.intro} />
          </Animated.View>
        ) : (
          <Animated.View entering={layout.listEnter()} exiting={layout.listExit()} layout={layout.listMove()}>
            <TurnoCard card={item.card} priority={item.priority} isNew={item.priority !== null && (item.card.state === 'nueva' || fresh.has(item.card.id))} />
          </Animated.View>
        )
      }
      viewabilityConfig={SEEN_VIEWABILITY}
      onViewableItemsChanged={onViewable}
      onScrollToIndexFailed={({ index, averageItemLength }) => {
        list.current?.scrollToOffset({ offset: index * averageItemLength, animated: false });
        setTimeout(() => list.current?.scrollToIndex({ index, viewPosition: 0, animated: true }), 120);
      }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={colors.brandDeep} colors={[colors.brandDeep]} />}
    />
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  header: { gap: space[4], marginBottom: space[2] },
  gapSmall: { gap: space[3] },
  gapCards: { gap: space[3] },
  label: { marginTop: space[3] },
  folds: { marginTop: space[6] },
  foldRow: { flexDirection: 'row', alignItems: 'flex-start', gap: space[2], paddingVertical: 10, borderTopWidth: 1, borderTopColor: colors.line },
  foldText: { flex: 1, gap: 2 },
});
