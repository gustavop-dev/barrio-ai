// What the team did (GET /api/v1/actividad): one row per item, the queued actions with Vetar, the
// type chips and «Mostrar lo que no salió», and «Ver todo lo del día» with «Cargar más». In the day panel the rows
// are compact: one line with «…» that a tap unfolds in place (TimelineItem's `compact`, OneLine).
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
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Switch, View, type StyleProp, type ViewStyle } from 'react-native';
import { Button, ErrorRetry, FilterChip, Fold, Skeleton, T } from '@/components/ui';
import { colors, layers, shell, space } from '@/theme/tokens';
import { TimelineItem } from './TimelineItem';
import { ApproveButton, VetoButton } from './Veto';

/**
 * A row's text, each line in one line with «…»; a tap shows it whole and another folds it again. For rows whose
 * buttons stay beside or under the text (the queue) and for the expected invitations.
 */
export function OneLine({ title, sub, style }: { title: string; sub?: string | null; style?: StyleProp<ViewStyle> }) {
  const [open, setOpen] = useState(false);
  const lines = open ? undefined : 1;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ expanded: open }}
      accessibilityHint={open ? 'Pliega el texto' : 'Muestra el texto completo'}
      onPress={() => setOpen((value) => !value)}
      style={[styles.oneLine, style]}
    >
      <T numberOfLines={lines}>{title}</T>
      {sub ? (
        <T variant="detalle" soft numberOfLines={lines}>
          {sub}
        </T>
      ) : null}
    </Pressable>
  );
}

/** One activity item: the post excerpt, the full comment and «Por qué» folded. Compact (the day panel): one line that a
 * tap unfolds with all of it. */
export function ActivityRow({ item, timeZone, compact = false }: { item: ActivityItem; timeZone: string; compact?: boolean }) {
  const layer = itemLayer(item);
  const link = itemLink(item);
  // A reply on his own post shows the comment it answers; a comment or reaction elsewhere, the post.
  const excerptText = item.target?.kind === 'comment' ? item.target.comment_excerpt : item.target?.post_excerpt;
  const writes = item.capability === 'INT-03' || item.capability === 'INT-04';
  const expandable = (writes || item.capability === 'INT-02') && Boolean(excerptText || item.text || item.rationale);
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
      compact={compact}
      expandLabel={item.capability === 'INT-04' ? 'Ver la respuesta' : item.capability === 'INT-03' ? 'Ver el comentario' : 'Ver el post'}
    >
      {expandable ? (
        <>
          {excerptText ? (
            <T variant="detalle" soft numberOfLines={2}>
              {excerptText}
            </T>
          ) : null}
          {writes && item.text ? <T>{item.text}</T> : null}
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
 * that waits for Gustavo's approval (`approval` mode) also has «Aprobar». Compact (the day panel): the sentence and when
 * it goes out take one line each until a tap on them; the buttons stay. */
export function QueuedRow({
  item,
  today,
  timeZone,
  windowOpen,
  compact = false,
}: {
  item: QueuedItem;
  today: string;
  timeZone: string;
  windowOpen: boolean | undefined;
  compact?: boolean;
}) {
  const sentence = queuedSentence(item);
  const awaiting = Boolean(item.awaiting_approval && item.payload_hash);
  const when = awaiting ? awaitingSentence(item.expires_at, { today, timeZone }) : queuedWhen(item.expected_at, { today, timeZone, windowOpen });
  const textStyle = awaiting ? styles.rowTextStacked : styles.rowText;
  return (
    <View style={awaiting ? styles.rowStacked : styles.row} testID={`en-cola-${item.id}`} collapsable={false}>
      {compact ? (
        <OneLine title={sentence} sub={when} style={textStyle} />
      ) : (
        <View style={textStyle}>
          <T>{sentence}</T>
          <T variant="detalle" soft>
            {when}
          </T>
        </View>
      )}
      {/* Waiting for approval, the two buttons go under the text: beside it they squeezed it into a narrow column. */}
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
            <ActivityRow key={item.id} item={item} timeZone={timeZone} compact />
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
  rowStacked: { gap: space[2], paddingVertical: 10, borderTopWidth: 1, borderTopColor: colors.line },
  rowTextStacked: { gap: 2 },
  oneLine: { gap: 2, minHeight: shell.touch, justifyContent: 'center' },
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: space[3], minHeight: shell.touch },
});
