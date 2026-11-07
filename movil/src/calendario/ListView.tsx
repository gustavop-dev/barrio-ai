// Vista Lista: «Próximo» on top (the scheduled piece with its countdown and Vetar, the queue), then
// every day newest first (Hoy, Ayer, «Jueves 5 de noviembre») with everything that happened, in a
// virtualized list with the type chips, «Mostrar lo que no salió» and «Cargar más».
import { useActividad } from '@compartido/api/hooks';
import type { Actividad, ActividadTipo, ActivityItem, CalendarLayer, UpcomingPiece } from '@compartido/api/types';
import { dayOf, relativeDay } from '@compartido/logic/dates';
import { pieceStatus } from '@compartido/logic/editorial';
import { formatTime } from '@compartido/logic/format';
import { firstLines, pieceMeta, pieceWhen, stageShort } from '@compartido/logic/piece';
import type { ReactElement } from 'react';
import { useMemo } from 'react';
import { FlatList, Pressable, RefreshControl, StyleSheet, View } from 'react-native';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { Badge, Button, Card, EmptyState, ErrorRetry, Section, Skeleton, T, pageContent } from '@/components/ui';
import { openLink } from '@/navigation';
import { colors, shell, space } from '@/theme/tokens';
import { ActivityRow, NoSalioSwitch, QueuedRow, TypeChips, visibleItems } from './ActivityList';
import { piecePath } from './go';
import { PlanNextButton, VetoButton } from './Veto';

function TextLink({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="link" onPress={onPress} style={styles.textLink}>
      <T color={colors.brandDeep}>{label}</T>
    </Pressable>
  );
}

function UpcomingPieceCard({ piece, today, timeZone, now }: { piece: UpcomingPiece; today: string; timeZone: string; now: number }) {
  const badge = pieceStatus(piece.status);
  const when = pieceWhen(piece.status, piece.scheduled_for, { today, timeZone, now });
  const meta = pieceMeta(piece);
  return (
    <Card>
      <View style={styles.pieceHead}>
        <Badge tone={badge.tone}>{badge.label}</Badge>
        <T variant="detalle" soft>
          {when}
        </T>
      </View>
      <T variant="subtitulo">{piece.thesis || 'El equipo prepara la pieza'}</T>
      {piece.excerpt ? <T soft>{firstLines(piece.excerpt)}</T> : null}
      {piece.status === 'preparing' ? (
        <T variant="detalle" soft>
          {`Etapa: ${stageShort(piece.stage)}`}
        </T>
      ) : null}
      {meta ? (
        <T variant="detalle" soft>
          {meta}
        </T>
      ) : null}
      {piece.vetoable && piece.action ? (
        <VetoButton block accessibilityHint={piece.thesis ?? undefined} target={{ actionId: piece.action.id, kind: 'pieza', when: `a las ${formatTime(piece.scheduled_for, timeZone)}` }} />
      ) : null}
      <TextLink label="Ver cómo se escribió" onPress={() => openLink(piecePath(piece.piece_id))} />
    </Card>
  );
}

/** «Próximo»: the scheduled piece with its countdown and Vetar, the next ones and the actions waiting their turn. */
export function Proximo({
  upcoming,
  loading,
  error,
  onRetry,
  today,
  timeZone,
  windowOpen,
  now,
}: {
  upcoming: Actividad['upcoming'] | undefined;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
  today: string;
  timeZone: string;
  windowOpen: boolean | undefined;
  now: number;
}) {
  const [first, ...later] = upcoming?.pieces ?? [];
  const queued = upcoming?.queued ?? [];
  return (
    <Section label="Próximo">
      {loading ? <Skeleton variant="card" label="Cargando lo próximo…" /> : null}
      <ErrorRetry error={error} onRetry={onRetry} />
      {upcoming ? (
        first ? (
          <UpcomingPieceCard piece={first} today={today} timeZone={timeZone} now={now} />
        ) : (
          <Card tone="dashed">
            <T>No hay pieza programada para los próximos días.</T>
            <PlanNextButton block />
          </Card>
        )
      ) : null}
      {later.length ? (
        <View accessibilityLabel="Después">
          {later.map((piece) => (
            <Pressable key={piece.piece_id} accessibilityRole="link" onPress={() => openLink(piecePath(piece.piece_id))} style={styles.row}>
              <T color={colors.brandDeep}>{piece.thesis || 'Pieza en preparación'}</T>
              <T variant="detalle" soft>
                {`${relativeDay(dayOf(piece.scheduled_for, timeZone) ?? piece.slot_date, today)} a las ${formatTime(piece.scheduled_for, timeZone)} · ${pieceStatus(piece.status).label}`}
              </T>
            </Pressable>
          ))}
        </View>
      ) : null}
      {queued.length ? (
        <Card compact>
          <T variant="etiqueta" soft accessibilityRole="header">
            En cola
          </T>
          <View>
            {queued.map((item) => (
              <QueuedRow key={item.id} item={item} today={today} timeZone={timeZone} windowOpen={windowOpen} />
            ))}
          </View>
        </Card>
      ) : null}
    </Section>
  );
}

type Row = { key: string; kind: 'day'; date: string } | { key: string; kind: 'item'; item: ActivityItem };

/** Days in the order the backend sends the items (newest first), each with its label row. */
export function groupRows(items: readonly ActivityItem[], timeZone: string): Row[] {
  const rows: Row[] = [];
  let current: string | null = null;
  for (const item of items) {
    const date = item.date || dayOf(item.at, timeZone) || '';
    if (date !== current) {
      current = date;
      rows.push({ key: `dia-${date}`, kind: 'day', date });
    }
    rows.push({ key: item.id, kind: 'item', item });
  }
  return rows;
}

export interface ListViewProps {
  /** The screen's title, view switch and layer chips, scrolled with the list. */
  header: ReactElement;
  upcoming: Actividad['upcoming'] | undefined;
  upcomingLoading: boolean;
  upcomingError: unknown;
  onRetryUpcoming: () => void;
  tipo: ActividadTipo;
  onTipo: (tipo: ActividadTipo) => void;
  noSalio: boolean;
  onNoSalio: (value: boolean) => void;
  today: string;
  timeZone: string;
  visible: ReadonlySet<CalendarLayer>;
  windowOpen: boolean | undefined;
  now: number;
  refreshing: boolean;
  onRefresh: () => void;
}

export function ListView(props: ListViewProps) {
  const { bottom } = useContentInsets();
  const query = useActividad({ tipo: props.tipo, noSalio: props.noSalio });
  const items = useMemo(() => visibleItems(query.data?.pages.flatMap((page) => page.items) ?? [], props.visible), [query.data, props.visible]);
  const rows = useMemo(() => groupRows(items, props.timeZone), [items, props.timeZone]);

  const header = (
    <View style={styles.header}>
      {props.header}
      <Proximo
        upcoming={props.upcoming}
        loading={props.upcomingLoading}
        error={props.upcomingError}
        onRetry={props.onRetryUpcoming}
        today={props.today}
        timeZone={props.timeZone}
        windowOpen={props.windowOpen}
        now={props.now}
      />
      <View style={styles.filters}>
        <T variant="etiqueta" soft accessibilityRole="header">
          Lo que pasó
        </T>
        <TypeChips tipo={props.tipo} onTipo={props.onTipo} />
        <NoSalioSwitch value={props.noSalio} onChange={props.onNoSalio} />
        {query.isPending ? <Skeleton variant="row" count={3} label="Cargando la actividad…" /> : null}
        <ErrorRetry error={query.isError ? query.error : null} onRetry={() => void query.refetch()} />
        {query.isSuccess && !items.length ? <EmptyState title="No hay nada registrado con este filtro." /> : null}
      </View>
    </View>
  );

  return (
    <FlatList
      testID="calendario-lista"
      style={styles.list}
      contentContainerStyle={[pageContent, styles.content, { paddingBottom: bottom }]}
      data={rows}
      keyExtractor={(row) => row.key}
      ListHeaderComponent={header}
      renderItem={({ item: row }) =>
        row.kind === 'day' ? (
          <T variant="etiqueta" soft accessibilityRole="header" style={styles.dayLabel}>
            {row.date ? relativeDay(row.date, props.today) : 'Sin fecha'}
          </T>
        ) : (
          <ActivityRow item={row.item} timeZone={props.timeZone} />
        )
      }
      ListFooterComponent={
        query.hasNextPage ? (
          <Button block loading={query.isFetchingNextPage} loadingLabel="Cargando…" onPress={() => void query.fetchNextPage()} style={styles.more}>
            Cargar más
          </Button>
        ) : undefined
      }
      refreshControl={<RefreshControl refreshing={props.refreshing} onRefresh={props.onRefresh} tintColor={colors.brandDeep} colors={[colors.brandDeep]} />}
    />
  );
}

const styles = StyleSheet.create({
  list: { flex: 1, backgroundColor: colors.paper },
  content: { gap: 0 },
  header: { gap: 20, marginBottom: space[2] },
  filters: { gap: space[3] },
  pieceHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: space[2] },
  textLink: { minHeight: shell.touch, justifyContent: 'center', alignSelf: 'flex-start' },
  row: { gap: 2, paddingVertical: 10, minHeight: shell.touch, borderTopWidth: 1, borderTopColor: colors.line },
  dayLabel: { marginTop: space[4], marginBottom: space[1] },
  more: { marginTop: space[4] },
});
