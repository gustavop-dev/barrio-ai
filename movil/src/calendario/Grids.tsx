// The calendar at phone size (Calendario.dc.html): the week as a 7-day strip and the month as a compact
// grid, both with one dot per visible layer with important events. Tapping a day selects it (its panel sits
// under the calendar). The page shows a period; the selected day may be in another one, and then no cell of
// this page is selected (today keeps its mark).
//
// Motion (MovCalendario): each grid is drawn in three layers so the selection can slide between days: the
// days' boxes, the dark selection (Selection.tsx) and the days' text on top. When the view switches, the
// week fades in, or the month comes in row by row (boxes and text of a row together); the weekday initials
// of the month are there at once, as in the board.
import type { CalendarGasp, CalendarLayer, CalendarioDay } from '@compartido/api/types';
import { dayInitial, dayNumber, longDayTitle, monthGrid, monthOf, weekDays, WEEKDAY_INITIALS } from '@compartido/logic/dates';
import { dayDots, LAYER_LABEL } from '@compartido/logic/events';
import { useState } from 'react';
import { Pressable, StyleSheet, View, type LayoutChangeEvent, type ViewStyle } from 'react-native';
import Animated from 'react-native-reanimated';
import { T } from '@/components/ui';
import { calendarLayout } from '@/theme/motion';
import { colors, layers as LAYER_COLOR, radius, space } from '@/theme/tokens';
import { SelectionPill, useDayRects, type PillHandle } from './Selection';

export interface GridProps {
  /** A day (AAAA-MM-DD) of the page's week or month. */
  fecha: string;
  /** The selected day: only a page with its cell shows the selection. */
  selected: string;
  today: string;
  byDate: ReadonlyMap<string, CalendarioDay>;
  visible: ReadonlySet<CalendarLayer>;
  onSelect: (day: string) => void;
  /** No data yet: days without dots. */
  loading?: boolean;
  /** A page beside the current one (being swiped in), or the view that is leaving: no selection. */
  preview?: boolean;
  /** The sliding selection. Without it (or before it is placed) the selected day paints its own dark box. */
  pill?: PillHandle;
  /** The view has just switched to this one: the week fades in, the month enters row by row. */
  enter?: boolean;
}

const WEEK_GAP = space[1];
const MONTH_GAP = 2;
const DAY_HINT = 'Muestra el día debajo del calendario';

/** «Sábado 7 de noviembre, hoy, post de crecimiento, Publicaciones, Red». */
export function dayLabel(day: string, today: string, layers: CalendarLayer[], gasp?: CalendarGasp | null): string {
  const parts = [longDayTitle(day)];
  if (day === today) parts.push('hoy');
  if (gasp) parts.push(`post de ${gasp.label.toLowerCase()}`);
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

interface Look {
  /** The box under the day: selected (only while there is no sliding selection), today, outside the month. */
  box: ViewStyle | null;
  color: string;
}

function look(day: string, { selected, today, preview, pill }: Pick<GridProps, 'selected' | 'today' | 'preview' | 'pill'>, outside = false): Look {
  const isSelected = day === selected && !preview;
  const color = isSelected ? colors.paper : outside && day !== today ? colors.inkSoft : colors.ink;
  if (isSelected && !pill?.placed) return { box: styles.selected, color };
  if (day === today) return { box: styles.today, color };
  if (outside) return { box: styles.outside, color };
  return { box: null, color };
}

/** The week: initial, number and dots of each day. */
export function WeekStrip({ fecha, selected, today, byDate, visible, onSelect, loading, preview, pill, enter }: GridProps) {
  const days = weekDays(fecha);
  const selection = preview || !days.includes(selected) ? undefined : pill;
  const rects = useDayRects(selection, selected, 0, enter);
  const entering = enter ? calendarLayout.weekIn : undefined;
  return (
    <View style={loading ? styles.loading : null}>
      <Animated.View entering={entering?.()} style={[StyleSheet.absoluteFill, styles.week]} pointerEvents="none">
        {days.map((day) => (
          <View key={day} style={[styles.weekBox, look(day, { selected, today, preview, pill }).box]} />
        ))}
      </Animated.View>
      {selection ? <SelectionPill pill={selection} /> : null}
      <Animated.View entering={entering?.()} style={styles.week} accessibilityLabel={preview ? undefined : 'Semana'}>
        {days.map((day) => {
          const layers = loading ? [] : dayDots(byDate.get(day), visible);
          const gasp = byDate.get(day)?.gasp;
          const { color } = look(day, { selected, today, preview, pill });
          return (
            <Pressable
              key={day}
              testID={preview ? undefined : `dia-${day}`}
              accessibilityRole="button"
              accessibilityLabel={dayLabel(day, today, layers, gasp)}
              accessibilityHint={DAY_HINT}
              accessibilityState={{ selected: day === selected && !preview }}
              onPress={() => onSelect(day)}
              onLayout={rects.onCell(day)}
              style={styles.weekDay}
            >
              <T variant="detalle" color={color} style={styles.initial}>
                {dayInitial(day)}
              </T>
              <T color={color}>{String(dayNumber(day))}</T>
              <Dots layers={layers} size={6} />
              {gasp ? (
                // The GASP type of the day: one letter, the label is in the accessibility label and the day panel.
                <T variant="detalle" color={color} style={styles.gasp} testID={preview ? undefined : `tipo-${day}`} importantForAccessibility="no">
                  {gasp.type}
                </T>
              ) : null}
            </Pressable>
          );
        })}
      </Animated.View>
    </View>
  );
}

/** The month: a compact grid with only dots (Monday first). */
export function MonthDots({ fecha, selected, today, byDate, visible, onSelect, loading, preview, pill, enter }: GridProps) {
  const month = monthOf(fecha);
  const days = monthGrid(fecha);
  const weeks = Array.from({ length: days.length / 7 }, (_, row) => days.slice(row * 7, row * 7 + 7));
  // The grid sits under the weekday initials: the selection lives in page coordinates, so it needs the offset.
  const [gridY, setGridY] = useState<number | null>(null);
  const selection = preview || gridY === null || !days.includes(selected) ? undefined : pill;
  const rects = useDayRects(selection, selected, gridY ?? 0, enter);
  const rowEntering = (row: number) => (enter ? calendarLayout.monthRowIn(row) : undefined);
  return (
    <View style={styles.month}>
      <View style={styles.weekdays} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
        {WEEKDAY_INITIALS.map((initial) => (
          <T key={initial} variant="etiqueta" soft center style={styles.weekdayCell}>
            {initial}
          </T>
        ))}
      </View>
      <View
        testID={preview ? undefined : 'rejilla-mes'}
        style={loading ? styles.loading : null}
        onLayout={(event: LayoutChangeEvent) => setGridY(event.nativeEvent.layout.y)}
      >
        <View style={[StyleSheet.absoluteFill, styles.monthGrid]} pointerEvents="none">
          {weeks.map((week, row) => (
            <Animated.View key={week[0]} entering={rowEntering(row)} style={styles.monthBoxRow}>
              {week.map((day) => {
                const outside = monthOf(day) !== month;
                return <View key={day} style={[styles.monthBox, outside ? null : styles.inMonth, look(day, { selected, today, preview, pill }, outside).box]} />;
              })}
            </Animated.View>
          ))}
        </View>
        {selection ? <SelectionPill pill={selection} originY={gridY ?? 0} /> : null}
        <View style={styles.monthGrid} accessibilityLabel={preview ? undefined : 'Días del mes'}>
          {weeks.map((week, row) => (
            <Animated.View
              key={week[0]}
              testID={preview ? undefined : `fila-${row}`}
              entering={rowEntering(row)}
              style={styles.monthRow}
              onLayout={rects.onRow(row)}
            >
              {week.map((day) => {
                const outside = monthOf(day) !== month;
                const layers = loading ? [] : dayDots(byDate.get(day), visible);
                const { color } = look(day, { selected, today, preview, pill }, outside);
                return (
                  <Pressable
                    key={day}
                    testID={preview ? undefined : `dia-${day}`}
                    accessibilityRole="button"
                    accessibilityLabel={dayLabel(day, today, layers)}
                    accessibilityHint={DAY_HINT}
                    accessibilityState={{ selected: day === selected && !preview }}
                    onPress={() => onSelect(day)}
                    onLayout={rects.onCell(day, row)}
                    style={styles.monthDay}
                  >
                    <T variant="detalle" color={color}>
                      {String(dayNumber(day))}
                    </T>
                    <Dots layers={layers} size={6} />
                  </Pressable>
                );
              })}
            </Animated.View>
          ))}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  week: { flexDirection: 'row', gap: WEEK_GAP },
  // The box and the text of a day share their size: the box layer stretches to the text layer's height.
  weekBox: { flex: 1, borderRadius: radius.md, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  weekDay: {
    flex: 1,
    minHeight: 72,
    paddingVertical: 6,
    alignItems: 'center',
    gap: space[1],
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  initial: { fontSize: 12, lineHeight: 16 },
  gasp: { fontSize: 11, lineHeight: 14, letterSpacing: 0.5 },
  selected: { borderColor: colors.ink, backgroundColor: colors.ink },
  today: { borderColor: colors.brandDeep, backgroundColor: colors.surface },
  outside: { backgroundColor: 'transparent' },
  loading: { opacity: 0.6 },
  dots: { flexDirection: 'row', gap: 3, alignItems: 'center' },
  dot: { borderRadius: radius.pill, borderWidth: 1, borderColor: colors.ink },
  month: { gap: space[1] },
  weekdays: { flexDirection: 'row', gap: MONTH_GAP },
  weekdayCell: { flex: 1 },
  monthGrid: { gap: MONTH_GAP },
  monthBoxRow: { flex: 1, flexDirection: 'row', gap: MONTH_GAP },
  monthBox: { flex: 1, borderRadius: radius.sm, borderWidth: 1, borderColor: 'transparent' },
  monthRow: { flexDirection: 'row', gap: MONTH_GAP },
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
