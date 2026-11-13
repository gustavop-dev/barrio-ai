// «Panel del día»: the selected day (Hoy, Pasado or Programado) under the calendar, top to bottom: its
// publication, «Lo importante del día», «Programado», «De tu Bandeja» (what was Gustavo's; the Bandeja has its own
// tab, so it no longer leads here) and, last, the day's summary with «Ver todo lo del día» folded. The rows are
// compact: one line with «…» that a tap unfolds in place, and another folds again. Sections other than the
// publication and «Lo importante» show only when they have something, as in the PWA's DayPanel.
import { usePiece } from '@compartido/api/hooks';
import type { Actividad, ActividadTipo, CalendarEvent, CalendarLayer, CalendarioDay } from '@compartido/api/types';
import { dayOf, daysBetween, longDayTitle } from '@compartido/logic/dates';
import { pieceStatus, vetoable } from '@compartido/logic/editorial';
import {
  chronological,
  dayKind,
  eventBadge,
  eventLink,
  eventSentence,
  eventSub,
  eventTime,
  FAR_FUTURE_DAYS,
  importantEvents,
  leadText,
  pieceIdFromLink,
  piecesOfDay,
  summaryParts,
  type DayKind,
} from '@compartido/logic/events';
import { formatTime } from '@compartido/logic/format';
import { firstLines, isOnItsWay, pieceMeta, pieceWhen, publishedAt, resultLine } from '@compartido/logic/piece';
import { useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Animated, { useAnimatedStyle, withTiming } from 'react-native-reanimated';
import { Icon } from '@/components/icons';
import { Badge, Button, Card, EmptyState, EmptyText, ErrorRetry, FoldIn, Skeleton, T } from '@/components/ui';
import { timing } from '@/theme/motion';
import { openLink } from '@/navigation';
import { colors, layers as LAYER_COLOR, radius, shell, space } from '@/theme/tokens';
import { DayActivity, OneLine, QueuedRow } from './ActivityList';
import { piecePath } from './go';
import { PIECE_PREVIEW_LINES, PieceHead, PieceOpener } from './PieceOpener';
import { TimelineItem } from './TimelineItem';
import { PlanNextButton, VetoButton } from './Veto';

// Built on the JS thread: timing() is not a worklet, and calling it inside a style worklet crashes the app on the UI
// runtime («Tried to synchronously call a Remote Function»).
const FOLD = timing('fold');

export interface DayPanelProps {
  date: string;
  day: CalendarioDay | undefined;
  today: string;
  timeZone: string;
  leadHours: number | undefined;
  visible: ReadonlySet<CalendarLayer>;
  /** Calendar data still loading for this day. */
  loading: boolean;
  /** The calendar failed and this day has no data: the panel says so instead of drawing an empty day. */
  failed?: boolean;
  upcoming: Actividad['upcoming'] | undefined;
  windowOpen: boolean | undefined;
  now: number;
  testID?: string;
}

const KIND_BADGE: Record<DayKind, { label: string; tone: 'ink' | 'muted' | 'info' }> = {
  hoy: { label: 'Hoy', tone: 'ink' },
  pasado: { label: 'Pasado', tone: 'muted' },
  programado: { label: 'Programado', tone: 'info' },
};

/** «Sábado 7 de noviembre» with Hoy, Pasado or Programado: also says which day it is when another week is on screen. */
function DayHeading({ date, today }: { date: string; today: string }) {
  const badge = KIND_BADGE[dayKind(date, today)];
  return (
    <View style={styles.heading}>
      <T variant="subtitulo" accessibilityRole="header" style={styles.headingText}>
        {longDayTitle(date)}
      </T>
      <Badge tone={badge.tone}>{badge.label}</Badge>
    </View>
  );
}

function Block({ label, children, testID }: { label: string; children: ReactNode; testID?: string }) {
  return (
    <View style={styles.block} testID={testID} accessibilityLabel={label} collapsable={false}>
      <T variant="etiqueta" soft accessibilityRole="header">
        {label}
      </T>
      {children}
    </View>
  );
}

function Gap({ children }: { children: ReactNode }) {
  return <View style={styles.gap}>{children}</View>;
}

function TextLink({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="link" onPress={onPress} style={styles.textLink}>
      <T color={colors.brandDeep}>{label}</T>
    </Pressable>
  );
}

/** The day's piece: state, hour, thesis and first lines (clamped), result and Vetar. Tapping it opens the piece. */
function DayPiece({ event, today, timeZone, now }: { event: CalendarEvent; today: string; timeZone: string; now: number }) {
  const pieceId = pieceIdFromLink(event.link) ?? '';
  const query = usePiece(pieceId);
  const piece = query.data;
  const status = piece?.status ?? event.state ?? event.kind.replace(/^piece_/, '');
  const to = pieceId ? piecePath(pieceId) : null;

  // The piece could not be loaded: say so (with «Reintentar») rather than fall back to the bare thesis without
  // its «Vetar».
  if (query.isError && !piece) {
    return (
      <Card>
        <T variant="subtitulo">{event.title}</T>
        <ErrorRetry error={query.error} onRetry={() => void query.refetch()} title="No se pudo cargar la pieza" />
      </Card>
    );
  }

  if (status === 'skipped') {
    const reason = event.skip_reason || piece?.brief?.skip_reason || piece?.note;
    return (
      <Gap>
        <T soft numberOfLines={3}>{`Sin publicación.${reason ? ` El director decidió no publicar: ${reason}` : ''}`}</T>
        {to ? <TextLink label="Ver cómo se decidió" onPress={() => openLink(to)} /> : null}
      </Gap>
    );
  }

  const badge = pieceStatus(status);
  const thesis = piece?.thesis ?? (event.title !== 'Publicación del día' ? event.title : null);
  const lines = firstLines(piece?.final_text);
  const meta = piece ? pieceMeta(piece) : '';
  const result = piece ? resultLine(piece, { today, timeZone }) : null;
  const when = pieceWhen(status, piece?.scheduled_for ?? event.at, { today, timeZone, now, published: piece ? publishedAt(piece) : null });
  return (
    <Card>
      <PieceOpener to={to} testID="pieza-del-dia">
        <PieceHead badge={badge} when={when} opens={Boolean(to)} />
        <T variant="subtitulo" numberOfLines={PIECE_PREVIEW_LINES}>
          {thesis ?? 'El equipo prepara la pieza del día'}
        </T>
        {lines ? (
          <T soft numberOfLines={PIECE_PREVIEW_LINES}>
            {lines}
          </T>
        ) : null}
        {meta ? (
          <T variant="detalle" soft numberOfLines={1}>
            {meta}
          </T>
        ) : null}
        {result ? <T variant="detalle">{result}</T> : null}
      </PieceOpener>
      {query.isPending && pieceId ? <Skeleton variant="row" label="Cargando la pieza…" /> : null}
      {piece?.action && vetoable(piece.action) ? (
        <VetoButton block accessibilityHint={thesis ?? undefined} target={{ actionId: piece.action.id, kind: 'pieza', when: `a las ${formatTime(piece.scheduled_for, timeZone)}` }} />
      ) : null}
    </Card>
  );
}

/** «1 post · 6 comentarios…»: each part opens «Ver todo lo del día» filtered by its type. The «·» closes the part before
 * it, so a wrapped line never starts with one (backlog #15). */
function Summary({ day, onPick }: { day: CalendarioDay | undefined; onPick: (tipo: ActividadTipo) => void }) {
  const parts = summaryParts(day);
  if (!parts.length) return <T soft>Sin actividad registrada.</T>;
  return (
    <View style={styles.summary}>
      {parts.map((part, index) => (
        <View key={part.key} style={styles.summaryItem}>
          <Pressable accessibilityRole="button" onPress={() => onPick(part.tipo)} style={styles.summaryPart} hitSlop={{ top: 8, bottom: 8 }}>
            <T soft style={styles.underline}>
              {part.text}
            </T>
          </Pressable>
          {index < parts.length - 1 ? (
            <T soft importantForAccessibility="no">
              ·
            </T>
          ) : null}
        </View>
      ))}
    </View>
  );
}

/** «Ver todo lo del día», folded: opened by its summary row or by a part of the day's summary. */
function AllOfDay({ open, onToggle, children }: { open: boolean; onToggle: () => void; children: ReactNode }) {
  const chevron = useAnimatedStyle(() => ({ transform: [{ rotate: withTiming(open ? '180deg' : '0deg', FOLD) }] }), [open]);
  return (
    <View style={styles.all}>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={onToggle} style={styles.allSummary}>
        <T color={colors.brandDeep}>Ver todo lo del día</T>
        <Animated.View style={chevron}>
          <Icon name="chevronDown" size={20} color={colors.brandDeep} />
        </Animated.View>
      </Pressable>
      {open ? (
        <FoldIn>{children}</FoldIn>
      ) : null}
    </View>
  );
}

export function DayPanel({ date, day, today, timeZone, leadHours, visible, loading, failed = false, upcoming, windowOpen, now, testID = 'panel-dia' }: DayPanelProps) {
  const [allOpen, setAllOpen] = useState(false);
  const [tipo, setTipo] = useState<ActividadTipo>('todo');
  const [noSalio, setNoSalio] = useState(false);
  const kind = dayKind(date, today);
  const heading = <DayHeading date={date} today={today} />;

  if (daysBetween(today, date) > FAR_FUTURE_DAYS) {
    return (
      <View style={styles.panel} testID={testID} collapsable={false}>
        {heading}
        <EmptyState title="Todavía no hay nada programado tan lejos.">
          <EmptyText>{`El equipo prepara cada pieza ${leadText(leadHours)} antes de su hora.`}</EmptyText>
        </EmptyState>
      </View>
    );
  }

  if (failed && !day) {
    return (
      <View style={styles.panel} testID={testID} collapsable={false}>
        {heading}
        <T soft>No se pudo cargar este día.</T>
      </View>
    );
  }

  if (loading) {
    return (
      <View style={styles.panel} testID={testID} collapsable={false}>
        {heading}
        <Skeleton variant="card" label="Cargando el día…" />
        <Skeleton variant="row" count={2} label="Cargando los eventos…" />
      </View>
    );
  }

  const tuyo = visible.has('tuyo') ? chronological((day?.events ?? []).filter((event) => event.layer === 'tuyo')) : [];
  const pieces = piecesOfDay(day);
  const queued = kind === 'pasado' ? [] : (upcoming?.queued ?? []).filter((item) => (dayOf(item.expected_at, timeZone) ?? today) === date);
  const expected = kind === 'pasado' ? [] : (day?.events ?? []).filter((event) => event.kind === 'invite_expected');
  const important = chronological(importantEvents(day, visible));
  const noUpcoming = upcoming !== undefined && !upcoming.pieces.some((p) => isOnItsWay(p.status));

  const pick = (value: ActividadTipo) => {
    setTipo(value);
    setAllOpen(true);
  };

  return (
    <View style={styles.panel} testID={testID} collapsable={false}>
      {heading}

      <Block label={pieces.length > 1 ? 'Publicaciones del día' : 'Publicación del día'} testID="bloque-publicacion">
        {pieces.length ? (
          <View style={styles.pieces}>
            {pieces.map((piece) => (
              <DayPiece key={piece.id} event={piece} today={today} timeZone={timeZone} now={now} />
            ))}
          </View>
        ) : (
          <Gap>
            <T soft>{kind === 'pasado' ? 'Sin publicación.' : `Hueco libre. El equipo prepara cada pieza ${leadText(leadHours)} antes de su hora.`}</T>
            {kind !== 'pasado' && noUpcoming ? (
              <>
                <T variant="detalle" soft>
                  No hay pieza programada para los próximos días.
                </T>
                <PlanNextButton block />
              </>
            ) : null}
          </Gap>
        )}
      </Block>

      <Block label="Lo importante del día" testID="bloque-importante">
        {important.length ? (
          <View>
            {important.map((event) => (
              <TimelineItem
                key={event.id}
                compact
                testID={`evento-${event.id}`}
                color={LAYER_COLOR[event.layer]}
                time={eventTime(event, timeZone)}
                title={eventSentence(event)}
                sub={eventSub(event)}
                badge={eventBadge(event)}
                agent={(event as CalendarEvent & { agent?: string }).agent ?? null}
                to={eventLink(event)}
                linkLabel={event.kind === 'action_uncertain' ? 'Resuélvela en la Bandeja' : 'Abrir'}
              />
            ))}
          </View>
        ) : (
          <T variant="detalle" soft>
            Nada importante en las capas visibles.
          </T>
        )}
      </Block>

      {queued.length || expected.length ? (
        <Block label="Programado" testID="bloque-programado">
          <View>
            {queued.map((item) => (
              <QueuedRow key={item.id} item={item} today={today} timeZone={timeZone} windowOpen={windowOpen} compact />
            ))}
            {expected.map((event) => (
              <View key={event.id} style={styles.row} testID={`prevista-${event.id}`} collapsable={false}>
                <OneLine
                  style={styles.rowText}
                  title={`Invitaciones previstas: ${event.people?.length ?? 0} ${event.people?.length === 1 ? 'persona' : 'personas'}`}
                  sub={eventSub(event)}
                />
              </View>
            ))}
          </View>
        </Block>
      ) : null}

      {tuyo.length ? (
        <Block label="De tu Bandeja" testID="bloque-bandeja">
          <View>
            {tuyo.map((event) => {
              const resolved = event.kind === 'resolved';
              return (
                <TimelineItem
                  key={event.id}
                  compact
                  testID={`bandeja-${event.id}`}
                  color={LAYER_COLOR.tuyo}
                  time={eventTime(event, timeZone)}
                  title={resolved ? eventSentence(event) : event.title}
                  sub={event.at && !resolved ? `Plazo: ${formatTime(event.at, timeZone)}` : null}
                  aside={
                    resolved ? (
                      <View style={styles.done} accessibilityLabel="Hecho">
                        <T variant="detalle" color={colors.brandDeep}>
                          Hecho
                        </T>
                        <Icon name="check" size={16} color={colors.brandDeep} />
                      </View>
                    ) : null
                  }
                />
              );
            })}
          </View>
          {tuyo.some((event) => event.kind !== 'resolved') ? (
            <Button block onPress={() => openLink('/tu-turno')}>
              Ir a la Bandeja
            </Button>
          ) : null}
        </Block>
      ) : null}

      {kind !== 'programado' ? (
        <View style={styles.block} testID="bloque-todo" collapsable={false}>
          <Summary day={day} onPick={pick} />
          <AllOfDay open={allOpen} onToggle={() => setAllOpen((value) => !value)}>
            <DayActivity date={date} tipo={tipo} onTipo={setTipo} noSalio={noSalio} onNoSalio={setNoSalio} timeZone={timeZone} />
          </AllOfDay>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  panel: { gap: 20 },
  heading: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space[2] },
  headingText: { flexShrink: 1 },
  block: { gap: space[2] },
  pieces: { gap: space[3] },
  gap: { gap: space[2], paddingVertical: space[3], paddingHorizontal: space[4], borderWidth: 1, borderStyle: 'dashed', borderColor: colors.inkSoft, borderRadius: radius.md },
  textLink: { minHeight: shell.touch, justifyContent: 'center', alignSelf: 'flex-start' },
  summary: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center' },
  summaryItem: { flexDirection: 'row', alignItems: 'center', gap: 6, marginRight: 6 },
  summaryPart: { minHeight: 32, justifyContent: 'center' },
  underline: { textDecorationLine: 'underline' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: space[1], borderTopWidth: 1, borderTopColor: colors.line },
  rowText: { flex: 1 },
  done: { flexDirection: 'row', alignItems: 'center', gap: space[1] },
  all: { borderTopWidth: 1, borderTopColor: colors.line },
  allSummary: { minHeight: 48, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
});
