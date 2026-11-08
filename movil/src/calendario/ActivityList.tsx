// What the team did (GET /api/v1/actividad): one row per item, the queued actions with Vetar, the
// type chips and «Mostrar lo que no salió», and «Ver todo lo del día» with «Cargar más».
import { useActividad } from '@compartido/api/hooks';
import type { ActividadTipo, ActivityItem, CalendarLayer, QueuedItem } from '@compartido/api/types';
import {
  awaitingSentence,
  isNetworkCapability,
  itemLayer,
  itemLink,
  itemSentence,
  itemSub,
  queuedSentence,
  queuedWhen,
  stateBadge,
  TIPOS,
} from '@compartido/logic/events';
import { formatTime } from '@compartido/logic/format';
import { ScrollView, StyleSheet, Switch, View } from 'react-native';
import { Button, ErrorRetry, FilterChip, Fold, Skeleton, T } from '@/components/ui';
import { colors, layers, shell, space } from '@/theme/tokens';
import { TimelineItem } from './TimelineItem';
import { ApproveButton, VetoButton } from './Veto';

/** One activity item: the post excerpt, the full comment and «Por qué» folded. */
export function ActivityRow({ item, timeZone }: { item: ActivityItem; timeZone: string }) {
  const layer = itemLayer(item);
  const link = itemLink(item);
  const excerptText = item.target?.post_excerpt;
  const expandable = (item.capability === 'INT-03' || item.capability === 'INT-02') && Boolean(excerptText || item.text || item.rationale);
  return (
    <TimelineItem
      testID={`actividad-${item.id}`}
      color={layer ? layers[layer] : colors.inkSoft}
      time={formatTime(item.at, timeZone)}
      title={itemSentence(item)}
      sub={itemSub(item)}
      badge={stateBadge(item)}
      agent={item.agent}
      to={link?.to}
      linkLabel={link?.label}
      externalUrl={item.url}
      expandLabel={item.capability === 'INT-03' ? 'Ver el comentario' : 'Ver el post'}
    >
      {expandable ? (
        <>
          {excerptText ? (
            <T variant="detalle" soft numberOfLines={2}>
              {excerptText}
            </T>
          ) : null}
          {item.capability === 'INT-03' && item.text ? <T>{item.text}</T> : null}
          {item.rationale ? (
            <Fold summary="Por qué">
              <T variant="detalle">{item.rationale}</T>
            </Fold>
          ) : null}
        </>
      ) : null}
    </TimelineItem>
  );
}

/** An approved action waiting for the window or the spacing, with its Vetar (a network action discards the person); one
 * that waits for Gustavo's approval (`approval` mode) also has «Aprobar». */
export function QueuedRow({ item, today, timeZone, windowOpen }: { item: QueuedItem; today: string; timeZone: string; windowOpen: boolean | undefined }) {
  const sentence = queuedSentence(item);
  const awaiting = Boolean(item.awaiting_approval && item.payload_hash);
  return (
    <View style={styles.row} testID={`en-cola-${item.id}`}>
      <View style={styles.rowText}>
        <T>{sentence}</T>
        <T variant="detalle" soft>
          {awaiting ? awaitingSentence(item.expires_at, { today, timeZone }) : queuedWhen(item.expected_at, { today, timeZone, windowOpen })}
        </T>
      </View>
      <View style={styles.rowActions}>
        {awaiting ? <ApproveButton size="small" actionId={item.id} expectedHash={item.payload_hash!} accessibilityHint={sentence} /> : null}
        <VetoButton
          size="small"
          accessibilityHint={sentence}
          target={{ actionId: item.id, kind: 'accion', network: isNetworkCapability(item.capability), person: item.target?.name }}
        />
      </View>
    </View>
  );
}

/** Type chips (Todo · Publicaciones · Comentarios · Reacciones · Red). */
export function TypeChips({ tipo, onTipo }: { tipo: ActividadTipo; onTipo: (tipo: ActividadTipo) => void }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips} accessibilityLabel="Filtrar por tipo">
      {TIPOS.map((option) => (
        <FilterChip key={option.value} pressed={tipo === option.value} onPress={() => onTipo(option.value)}>
          {option.label}
        </FilterChip>
      ))}
    </ScrollView>
  );
}

/** «Mostrar lo que no salió», off by default. */
export function NoSalioSwitch({ value, onChange }: { value: boolean; onChange: (value: boolean) => void }) {
  return (
    <View style={styles.switchRow}>
      <View style={styles.rowText}>
        <T>Mostrar lo que no salió</T>
        <T variant="detalle" soft>
          Vetadas, descartadas, caducadas y sustituidas. Las fallidas y las inciertas se ven siempre.
        </T>
      </View>
      <Switch
        accessibilityLabel="Mostrar lo que no salió"
        value={value}
        onValueChange={onChange}
        trackColor={{ false: colors.line, true: colors.brandDeep }}
        thumbColor={colors.surface}
        testID="no-salio"
      />
    </View>
  );
}

/** Items of the visible layers only (an important item of a hidden layer goes away with it). */
export function visibleItems(items: readonly ActivityItem[], visible?: ReadonlySet<CalendarLayer>): ActivityItem[] {
  return items.filter((item) => {
    const layer = itemLayer(item);
    return !layer || !visible || visible.has(layer);
  });
}

/** «Ver todo lo del día»: the day's whole timeline, with the type chips, the switch and «Cargar más». */
export function DayActivity({
  date,
  tipo,
  onTipo,
  noSalio,
  onNoSalio,
  timeZone,
}: {
  date: string;
  tipo: ActividadTipo;
  onTipo: (tipo: ActividadTipo) => void;
  noSalio: boolean;
  onNoSalio: (value: boolean) => void;
  timeZone: string;
}) {
  const query = useActividad({ tipo, desde: date, hasta: date, noSalio });
  const items = query.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <View style={styles.activity}>
      <TypeChips tipo={tipo} onTipo={onTipo} />
      <NoSalioSwitch value={noSalio} onChange={onNoSalio} />
      {query.isPending ? <Skeleton variant="row" count={3} label="Cargando la actividad…" /> : null}
      <ErrorRetry error={query.isError ? query.error : null} onRetry={() => void query.refetch()} />
      {query.isSuccess && !items.length ? <T soft>Nada registrado ese día con este filtro.</T> : null}
      {items.length ? (
        <View accessibilityLabel="Todo lo del día">
          {items.map((item) => (
            <ActivityRow key={item.id} item={item} timeZone={timeZone} />
          ))}
        </View>
      ) : null}
      {query.hasNextPage ? (
        <Button block loading={query.isFetchingNextPage} loadingLabel="Cargando…" onPress={() => void query.fetchNextPage()}>
          Cargar más
        </Button>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  activity: { gap: space[3] },
  chips: { gap: space[2] },
  row: { flexDirection: 'row', alignItems: 'center', gap: space[3], paddingVertical: 10, borderTopWidth: 1, borderTopColor: colors.line },
  rowText: { flex: 1, gap: 2 },
  rowActions: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: space[3], minHeight: shell.touch },
});
