// The selected day as one dark piece that slides (MovCalendario's `px`, `py`, `pw`, `ph`): tapping a day
// springs it to the new cell, and switching Semana ↔ Mes makes it travel from the week cell to its cell
// in the month. The screen keeps the four values, so they carry from one view (and one page) to the next;
// each grid draws the piece over the days' boxes and under their text, and tells it where the selected
// day sits. Coordinates are the page's: the week strip and the month share the same origin.
// A page without the selected day draws no piece. When a swipe brings the selected day back (or a tap
// selects a day on a page that had none), the piece appears on it at once instead of travelling.
import { useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { StyleSheet, type LayoutChangeEvent } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withSpring, type SharedValue } from 'react-native-reanimated';
import { calendarChoreography, calendarSpring } from '@/theme/motion';
import { colors, radius } from '@/theme/tokens';

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface PillHandle {
  x: SharedValue<number>;
  y: SharedValue<number>;
  w: SharedValue<number>;
  h: SharedValue<number>;
  /** The piece is on screen: the selected day stops painting its own dark box. */
  placed: boolean;
  /** Springs the piece to a cell, or jumps there (`travel` false, the first time, and with reduced motion). */
  moveTo: (rect: Rect, travel?: boolean) => void;
  /** Forgets the piece (the calendar left for Lista): the next grid places it without travelling. */
  reset: () => void;
}

/** The screen's selection: four springs that outlive the week strip, the month and their pages. */
export function usePill(reduced: boolean): PillHandle {
  const x = useSharedValue(0);
  const y = useSharedValue(0);
  const w = useSharedValue(0);
  const h = useSharedValue(0);
  const [placed, setPlaced] = useState(false);
  /** Where the piece was last sent: sending it there again leaves a spring on its way alone. */
  const target = useRef<Rect | null>(null);

  const moveTo = useCallback(
    (rect: Rect, travel = true) => {
      const last = target.current;
      if (placed && last && last.x === rect.x && last.y === rect.y && last.w === rect.w && last.h === rect.h) return;
      target.current = rect;
      const jump = reduced || !placed || !travel;
      const config = calendarSpring('daySelect');
      for (const [value, to] of [
        [x, rect.x],
        [y, rect.y],
        [w, rect.w],
        [h, rect.h],
      ] as const) {
        value.set(jump ? to : withSpring(to, config));
      }
      if (!placed) setPlaced(true);
    },
    [reduced, placed, x, y, w, h],
  );

  const reset = useCallback(() => {
    w.set(0);
    h.set(0);
    target.current = null;
    setPlaced(false);
  }, [w, h]);

  return useMemo(() => ({ x, y, w, h, placed, moveTo, reset }), [x, y, w, h, placed, moveTo, reset]);
}

/** The radius of the piece at height `height`: a week day's above `pillTallAt`, a month cell's below. Worklet. */
export function pillRadius(height: number): number {
  'worklet';
  return height > calendarChoreography.pillTallAt ? radius.md : radius.sm;
}

/** The dark piece, inside a grid whose top sits `originY` below the page's. */
export function SelectionPill({ pill, originY = 0 }: { pill: PillHandle; originY?: number }) {
  const { x, y, w, h } = pill;
  const style = useAnimatedStyle(
    () => ({
      width: w.value,
      height: h.value,
      borderRadius: pillRadius(h.value),
      transform: [{ translateX: x.value }, { translateY: y.value - originY }],
    }),
    [originY],
  );
  return <Animated.View testID="seleccion-dia" pointerEvents="none" style={[styles.pill, style]} />;
}

/**
 * Where each day sits, from the cells' own layout, and the piece sent to the selected one whenever the
 * selection or its layout changes. Month cells sit in rows: their row's offset is added. Without `pill`
 * (a page beside the current one, or without the selected day) nothing is drawn. The piece travels when
 * the selection moves on this page, or when the view has just switched (`travel`); otherwise it jumps.
 */
export function useDayRects(pill: PillHandle | undefined, selected: string, originY = 0, travel = false) {
  const cells = useRef(new Map<string, { rect: Rect; row: number | null }>());
  const rows = useRef(new Map<number, number>());
  /** The day this page last put the piece on, since it last showed it (null: not yet). */
  const placedOn = useRef<string | null>(null);

  const place = useCallback(() => {
    if (!pill) return;
    const cell = cells.current.get(selected);
    if (!cell) return;
    const rowY = cell.row === null ? 0 : rows.current.get(cell.row);
    if (rowY === undefined) return;
    const moved = placedOn.current !== null && placedOn.current !== selected;
    placedOn.current = selected;
    pill.moveTo({ x: cell.rect.x, y: originY + rowY + cell.rect.y, w: cell.rect.w, h: cell.rect.h }, travel || moved);
  }, [pill, selected, originY, travel]);

  useLayoutEffect(() => {
    if (!pill) {
      placedOn.current = null;
      return;
    }
    place();
  }, [pill, place]);

  const onCell = useCallback(
    (day: string, row: number | null = null) =>
      (event: LayoutChangeEvent) => {
        const { x, y, width, height } = event.nativeEvent.layout;
        cells.current.set(day, { rect: { x, y, w: width, h: height }, row });
        if (day === selected) place();
      },
    [selected, place],
  );

  const onRow = useCallback(
    (row: number) => (event: LayoutChangeEvent) => {
      rows.current.set(row, event.nativeEvent.layout.y);
      if (cells.current.get(selected)?.row === row) place();
    },
    [selected, place],
  );

  return { onCell, onRow };
}

const styles = StyleSheet.create({
  pill: { position: 'absolute', left: 0, top: 0, backgroundColor: colors.ink },
});
