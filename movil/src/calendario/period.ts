// The period on screen (the week or the month) apart from the selected day. The selected day lives in the route
// (`fecha`, so a link selects a day); the period is the screen's own state, a day inside the week or month shown.
// Swiping moves only the period, and tapping a day moves only the selection, which is always on screen when tapped.
// The period follows the selection when it lands outside it (a link to another week) and when the view changes:
// Semana ↔ Mes opens on the selected day's week or month, so the selection travels to its cell.
import { addDays, addMonths, monthGrid, weekDays } from '@compartido/logic/dates';
import type { Vista } from '@compartido/logic/events';
import { useCallback, useState } from 'react';

/** The days a view asks for: the week, or the Monday-to-Sunday grid of the month. */
export function rangeOf(vista: Vista, fecha: string): [string, string] {
  const days = vista === 'mes' ? monthGrid(fecha) : weekDays(fecha);
  return [days[0]!, days[days.length - 1]!];
}

/** The same view one week or one month away. */
export function shifted(vista: Vista, fecha: string, direction: number): string {
  return vista === 'mes' ? addMonths(fecha, direction) : addDays(fecha, 7 * direction);
}

/** Whether `day` has a cell in the page of `anchor`: its week, or its month's grid (with the neighbours' days). */
export function inPeriod(vista: Vista, anchor: string, day: string): boolean {
  const [from, to] = rangeOf(vista, anchor);
  return day >= from && day <= to;
}

interface PeriodMemory {
  vista: Vista;
  selected: string;
  anchor: string;
  /** The period of the view that just left, for its fading grid. */
  before: string;
}

export interface VisiblePeriod {
  /** A day of the week or month on screen. */
  anchor: string;
  /** The period the previous view showed (the leaving grid of Semana ↔ Mes). */
  before: string;
  /** Turns the period (a swipe): the selected day stays. */
  setAnchor: (anchor: string) => void;
}

export function useVisiblePeriod(vista: Vista, selected: string): VisiblePeriod {
  const [memory, setMemory] = useState<PeriodMemory>({ vista, selected, anchor: selected, before: selected });
  let current = memory;
  if (memory.vista !== vista || memory.selected !== selected) {
    const keep = memory.vista === vista && inPeriod(vista, memory.anchor, selected);
    current = { vista, selected, anchor: keep ? memory.anchor : selected, before: memory.vista !== vista ? memory.anchor : memory.before };
    setMemory(current);
  }
  const setAnchor = useCallback((anchor: string) => setMemory((value) => ({ ...value, anchor })), []);
  return { anchor: current.anchor, before: current.before, setAnchor };
}
