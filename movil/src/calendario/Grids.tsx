// The calendar at phone size (Calendario.dc.html): the week as a 7-day strip and the month as a compact
// grid, both with one dot per visible layer with important events. Tapping a day opens it.
import type { CalendarLayer, CalendarioDay } from '@compartido/api/types';
import { dayInitial, dayNumber, longDayTitle, monthGrid, monthOf, weekDays, WEEKDAY_INITIALS } from '@compartido/logic/dates';
import { dayDots, LAYER_LABEL } from '@compartido/logic/events';
import { Pressable, StyleSheet, View } from 'react-native';
import { T } from '@/components/ui';
import { colors, layers as LAYER_COLOR, radius, space } from '@/theme/tokens';

export interface GridProps {
  /** The selected day (AAAA-MM-DD); also the page's week or month. */
  fecha: string;
  today: string;
  byDate: ReadonlyMap<string, CalendarioDay>;
  visible: ReadonlySet<CalendarLayer>;
  onSelect: (day: string) => void;
  /** No data yet: days without dots. */
  loading?: boolean;
  /** A page beside the current one (being swiped in): no selection. */
  preview?: boolean;
}

/** «Sábado 7 de noviembre, hoy, Publicaciones, Red». */
export function dayLabel(day: string, today: string, layers: CalendarLayer[]): string {
  const parts = [longDayTitle(day)];
  if (day === today) parts.push('hoy');
  if (layers.length) parts.push(layers.map((layer) => LAYER_LABEL[layer]).join(', '));
  return parts.join(', ');
}

function Dots({ layers, size }: { layers: CalendarLayer[]; size: number }) {
  return (
    <View style={[styles.dots, { minHeight: size + 2 }]}>
      {layers.map((layer) => (
        <View key={layer} style={[styles.dot, { width: size, height: size, backgroundColor: LAYER_COLOR[layer] }]} />
      ))}
    </View>
  );
}

function tone(day: string, { fecha, today, preview }: Pick<GridProps, 'fecha' | 'today' | 'preview'>, outside = false) {
  if (day === fecha && !preview) return { box: styles.selected, color: colors.paper };
  if (day === today) return { box: styles.today, color: colors.ink };
  if (outside) return { box: styles.outside, color: colors.inkSoft };
  return { box: null, color: colors.ink };
}

/** The week: initial, number and dots of each day. */
export function WeekStrip({ fecha, today, byDate, visible, onSelect, loading, preview }: GridProps) {
  return (
    <View style={[styles.week, loading ? styles.loading : null]} accessibilityLabel={preview ? undefined : 'Semana'}>
      {weekDays(fecha).map((day) => {
        const layers = loading ? [] : dayDots(byDate.get(day), visible);
        const look = tone(day, { fecha, today, preview });
        return (
          <Pressable
            key={day}
            testID={preview ? undefined : `dia-${day}`}
            accessibilityRole="button"
            accessibilityLabel={dayLabel(day, today, layers)}
            accessibilityHint="Abre el detalle del día"
            accessibilityState={{ selected: day === fecha && !preview }}
            onPress={() => onSelect(day)}
            style={[styles.weekDay, look.box]}
          >
            <T variant="detalle" color={look.color} style={styles.initial}>
              {dayInitial(day)}
            </T>
            <T color={look.color}>{String(dayNumber(day))}</T>
            <Dots layers={layers} size={6} />
          </Pressable>
        );
      })}
    </View>
  );
}

/** The month: a compact grid with only dots (Monday first). */
export function MonthDots({ fecha, today, byDate, visible, onSelect, loading, preview }: GridProps) {
  const month = monthOf(fecha);
  const days = monthGrid(fecha);
  const weeks = Array.from({ length: days.length / 7 }, (_, row) => days.slice(row * 7, row * 7 + 7));
  return (
    <View style={styles.month}>
      <View style={styles.weekdays} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
        {WEEKDAY_INITIALS.map((initial) => (
          <T key={initial} variant="etiqueta" soft center style={styles.weekdayCell}>
            {initial}
          </T>
        ))}
      </View>
      <View style={[styles.monthGrid, loading ? styles.loading : null]} accessibilityLabel={preview ? undefined : 'Días del mes'}>
        {weeks.map((week) => (
          <View key={week[0]} style={styles.monthRow}>
            {week.map((day) => {
              const outside = monthOf(day) !== month;
              const layers = loading ? [] : dayDots(byDate.get(day), visible);
              const look = tone(day, { fecha, today, preview }, outside);
              return (
                <Pressable
                  key={day}
                  testID={preview ? undefined : `dia-${day}`}
                  accessibilityRole="button"
                  accessibilityLabel={dayLabel(day, today, layers)}
                  accessibilityHint="Abre el detalle del día"
                  accessibilityState={{ selected: day === fecha && !preview }}
                  onPress={() => onSelect(day)}
                  style={[styles.monthDay, outside ? null : styles.inMonth, look.box]}
                >
                  <T variant="detalle" color={look.color}>
                    {String(dayNumber(day))}
                  </T>
                  <Dots layers={layers} size={6} />
                </Pressable>
              );
            })}
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  week: { flexDirection: 'row', gap: space[1] },
  weekDay: {
    flex: 1,
    minHeight: 72,
    paddingVertical: 6,
    alignItems: 'center',
    gap: space[1],
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  initial: { fontSize: 12, lineHeight: 16 },
  selected: { borderColor: colors.ink, backgroundColor: colors.ink },
  today: { borderColor: colors.brandDeep, backgroundColor: colors.surface },
  outside: { backgroundColor: 'transparent' },
  loading: { opacity: 0.6 },
  dots: { flexDirection: 'row', gap: 3, alignItems: 'center' },
  dot: { borderRadius: radius.pill, borderWidth: 1, borderColor: colors.ink },
  month: { gap: space[1] },
  weekdays: { flexDirection: 'row', gap: 2 },
  weekdayCell: { flex: 1 },
  monthGrid: { gap: 2 },
  monthRow: { flexDirection: 'row', gap: 2 },
  monthDay: {
    flex: 1,
    minHeight: 52,
    paddingVertical: space[1],
    alignItems: 'center',
    gap: space[1],
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  inMonth: { backgroundColor: colors.surface },
});
