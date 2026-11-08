// MovCalendario in the app: the selection sliding to the tapped day and travelling into the month, the day
// panel entering from the side the date moved to, Semana ↔ Mes (the leaving view, the rows entering) and the
// Vista selection; each with its tokens and its reduced-motion path.
import { act, fireEvent, render, screen } from '@testing-library/react-native';
import * as Haptics from 'expo-haptics';
import { useState } from 'react';
import { StyleSheet, Text, type StyleProp, type ViewStyle } from 'react-native';
import { Segmented } from '@/components/ui';
import * as motion from '@/theme/motion';
import { calendarChoreography, calendarLayout, calendarSpring, calendarTiming, durations, easings, FIRM } from '@/theme/motion';
import { radius } from '@/theme/tokens';
import { DaySwap, directionOf, useDaySwap } from './DaySwap';
import { MonthDots, WeekStrip } from './Grids';
import { pillRadius, usePill } from './Selection';
import { LeavingView, useViewSwitch } from './ViewSwitch';
import type { Vista } from '@compartido/logic/events';

const WEEK = ['2026-11-02', '2026-11-03', '2026-11-04', '2026-11-05', '2026-11-06', '2026-11-07', '2026-11-08'];
/** Week cells 48 pt wide with the 4 pt gap: day i starts at 52 × i. */
const STEP = 52;

beforeEach(() => {
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

async function advance(ms: number) {
  await act(async () => {
    jest.advanceTimersByTime(ms);
  });
}

/** What Reanimated has applied to an animated view under Jest (its `jestAnimatedStyle`), over its static style. */
function animated(element: { props: Record<string, unknown> }): Record<string, unknown> {
  const style = StyleSheet.flatten(element.props.style as StyleProp<ViewStyle>) ?? {};
  const live = (element.props.jestAnimatedStyle as { value?: Record<string, unknown> } | undefined)?.value ?? {};
  return { ...style, ...live };
}

function translate(element: { props: Record<string, unknown> }): { x: number; y: number } {
  const transform = animated(element).transform as { translateX?: number; translateY?: number }[];
  return { x: transform[0]!.translateX!, y: transform[1]!.translateY! };
}

function Calendar({ vista = 'semana', fecha, reduced = false }: { vista?: 'semana' | 'mes'; fecha: string; reduced?: boolean }) {
  const pill = usePill(reduced);
  const props = { fecha, today: '2026-11-07', byDate: new Map(), visible: new Set<never>(), onSelect: () => undefined, pill };
  return vista === 'mes' ? <MonthDots key="mes" {...props} /> : <WeekStrip key="semana" {...props} />;
}

/** No layout pass under Jest: each week day reports where it sits. */
async function layOutWeek() {
  for (const [index, day] of WEEK.entries()) {
    await fireEvent(screen.getByTestId(`dia-${day}`), 'layout', { nativeEvent: { layout: { x: index * STEP, y: 0, width: 48, height: 72 } } });
  }
}

describe('MovCalendario · the selection', () => {
  it('springs (FIRM) and rounds like the board', () => {
    expect(calendarSpring('daySelect')).toMatchObject(FIRM);
    expect(pillRadius(72)).toBe(radius.md);
    expect(pillRadius(calendarChoreography.pillTallAt)).toBe(radius.sm);
    expect(pillRadius(52)).toBe(radius.sm);
  });

  it('sits on the selected day at once, then slides to the tapped one', async () => {
    const view = await render(<Calendar fecha="2026-11-07" />);
    await layOutWeek();
    // Under Jest, Reanimated applies a value on the next frame.
    await advance(16);
    const pill = screen.getByTestId('seleccion-dia');
    expect(animated(pill)).toMatchObject({ width: 48, height: 72, borderRadius: radius.md });
    expect(translate(pill)).toEqual({ x: 5 * STEP, y: 0 });

    await view.rerender(<Calendar fecha="2026-11-03" />);
    // The tapped day reads as selected at once; the piece is on its way.
    expect(screen.getByTestId('dia-2026-11-03').props.accessibilityState).toMatchObject({ selected: true });
    await advance(32);
    const moving = translate(pill).x;
    expect(moving).toBeLessThan(5 * STEP);
    expect(moving).toBeGreaterThan(STEP);
    await advance(1200);
    expect(translate(pill)).toEqual({ x: STEP, y: 0 });
  });

  it('travels from the week cell to its cell in the month, and takes the month cell’s size', async () => {
    const view = await render(<Calendar fecha="2026-11-07" />);
    await layOutWeek();
    await view.rerender(<Calendar vista="mes" fecha="2026-11-07" />);
    // The grid sits 20 pt under the weekday initials; 7 November is row 1, column 5 (the grid starts on 26 October).
    await fireEvent(screen.getByTestId('rejilla-mes'), 'layout', { nativeEvent: { layout: { x: 0, y: 20, width: 358, height: 322 } } });
    await fireEvent(screen.getByTestId('fila-1'), 'layout', { nativeEvent: { layout: { x: 0, y: 54, width: 358, height: 52 } } });
    await fireEvent(screen.getByTestId('dia-2026-11-07'), 'layout', { nativeEvent: { layout: { x: 250, y: 0, width: 48, height: 52 } } });
    const pill = screen.getByTestId('seleccion-dia');
    // It starts where the week left it (in the grid's coordinates, 20 pt higher)…
    expect(translate(pill)).toEqual({ x: 5 * STEP, y: -20 });
    await advance(1200);
    // …and lands on the month cell, with the month cell's radius.
    expect(translate(pill)).toEqual({ x: 250, y: 54 });
    expect(animated(pill)).toMatchObject({ width: 48, height: 52, borderRadius: radius.sm });
  });

  it('jumps with reduced motion', async () => {
    const view = await render(<Calendar fecha="2026-11-07" reduced />);
    await layOutWeek();
    await view.rerender(<Calendar fecha="2026-11-02" reduced />);
    await advance(16);
    expect(translate(screen.getByTestId('seleccion-dia'))).toEqual({ x: 0, y: 0 });
  });
});

function Panel({ date, reduced = false }: { date: string; reduced?: boolean }) {
  const swap = useDaySwap(date, reduced);
  return <DaySwap date={date} swap={swap} render={(day, leaving) => <Text>{leaving ? `sale ${day}` : day}</Text>} />;
}

const hidden = { includeHiddenElements: true };

describe('MovCalendario · the day panel', () => {
  it('uses the board’s timings', () => {
    expect(calendarTiming('panelOut')).toMatchObject({ duration: 120, easing: easings.exit });
    expect(calendarTiming('panelIn')).toMatchObject({ duration: durations.fast, easing: easings.enter });
    expect(calendarChoreography).toMatchObject({ panelShift: 12, panelRise: 8, panelInDelayMs: 60 });
    expect(directionOf('2026-11-07', '2026-11-08')).toBe(1);
    expect(directionOf('2026-11-07', '2026-10-31')).toBe(-1);
  });

  it('appears without moving, then each new day enters from the side the date moved to', async () => {
    const view = await render(<Panel date="2026-11-07" />);
    expect(animated(screen.getByTestId('panel-entrante'))).toMatchObject({ opacity: 1 });
    expect(translate(screen.getByTestId('panel-entrante'))).toEqual({ x: 0, y: 0 });

    await view.rerender(<Panel date="2026-11-09" />);
    const entering = screen.getByTestId('panel-entrante');
    const leaving = screen.getByTestId('panel-saliente', hidden);
    // The old panel stays laid over the new one, out of reach of screen readers.
    expect(screen.queryByText('sale 2026-11-07')).toBeNull();
    expect(screen.getByText('sale 2026-11-07', hidden)).toBeTruthy();
    expect(animated(entering)).toMatchObject({ opacity: 0 });
    expect(translate(entering)).toEqual({ x: 12, y: 8 });

    await advance(40);
    // The new one waits 60 ms; the old one is already leaving to the left.
    expect(animated(entering)).toMatchObject({ opacity: 0 });
    expect(translate(leaving).x).toBeLessThan(0);

    await advance(400);
    expect(animated(entering)).toMatchObject({ opacity: 1 });
    expect(translate(entering)).toEqual({ x: 0, y: 0 });
    expect(screen.queryByTestId('panel-saliente', hidden)).toBeNull();

    await view.rerender(<Panel date="2026-11-03" />);
    expect(translate(screen.getByTestId('panel-entrante'))).toEqual({ x: -12, y: 8 });
    await advance(48);
    expect(translate(screen.getByTestId('panel-saliente', hidden)).x).toBeGreaterThan(0);
  });

  it('just changes with reduced motion', async () => {
    const view = await render(<Panel date="2026-11-07" reduced />);
    await view.rerender(<Panel date="2026-11-09" reduced />);
    expect(screen.queryByTestId('panel-saliente', hidden)).toBeNull();
    expect(animated(screen.getByTestId('panel-entrante'))).toMatchObject({ opacity: 1 });
    expect(translate(screen.getByTestId('panel-entrante'))).toEqual({ x: 0, y: 0 });
  });
});

function Views({ vista, reduced = false }: { vista: Vista; reduced?: boolean }) {
  const view = useViewSwitch(vista, reduced);
  return view.from ? (
    <LeavingView key={view.from} onDone={view.done}>
      <Text>{view.from}</Text>
    </LeavingView>
  ) : null;
}

describe('MovCalendario · Semana ↔ Mes', () => {
  it('uses the board’s timings, delays and staggers', () => {
    expect(calendarTiming('viewOut')).toMatchObject({ duration: 120, easing: easings.exit });
    expect(calendarTiming('height')).toMatchObject({ duration: durations.base, easing: easings.enter });
    const week = calendarLayout.weekIn();
    expect(week.getDuration()).toBe(durations.fast);
    expect(week.getDelay()).toBe(80);
    const thirdRow = calendarLayout.monthRowIn(2);
    expect(thirdRow.getDuration()).toBe(durations.fast);
    expect(thirdRow.getDelay()).toBe(60 + 2 * 30);
    expect(thirdRow.initialValues).toEqual({ transform: [{ translateY: -6 }] });
  });

  it('keeps the leaving view under the new one while it fades out, only between Semana and Mes', async () => {
    const view = await render(<Views vista="semana" />);
    expect(screen.queryByTestId('vista-saliente', hidden)).toBeNull();

    await view.rerender(<Views vista="mes" />);
    const leaving = screen.getByTestId('vista-saliente', hidden);
    expect(screen.getByText('semana', hidden)).toBeTruthy();
    expect(animated(leaving)).toMatchObject({ opacity: 1 });
    await advance(64);
    const opacity = Number(animated(leaving).opacity);
    expect(opacity).toBeGreaterThan(0);
    expect(opacity).toBeLessThan(1);
    await advance(200);
    expect(screen.queryByTestId('vista-saliente', hidden)).toBeNull();

    await view.rerender(<Views vista="lista" />);
    expect(screen.queryByTestId('vista-saliente', hidden)).toBeNull();
    await view.rerender(<Views vista="semana" />);
    expect(screen.queryByTestId('vista-saliente', hidden)).toBeNull();
  });

  it('switches at once with reduced motion', async () => {
    const view = await render(<Views vista="semana" reduced />);
    await view.rerender(<Views vista="mes" reduced />);
    expect(screen.queryByTestId('vista-saliente', hidden)).toBeNull();
  });
});

const VISTA_OPTIONS = [
  { value: 'mes', label: 'Mes' },
  { value: 'semana', label: 'Semana' },
  { value: 'lista', label: 'Lista' },
] as const;

function VistaControl() {
  const [value, setValue] = useState<'mes' | 'semana' | 'lista'>('semana');
  return <Segmented label="Vista" testID="vista" options={VISTA_OPTIONS} value={value} onChange={setValue} />;
}

/** A 316 pt track: 4 pt of padding and gaps leave three options of 100 pt. */
async function layOutTrack() {
  await fireEvent(screen.getByTestId('vista'), 'layout', { nativeEvent: { layout: { x: 0, y: 0, width: 316, height: 48 } } });
}

describe('MovCalendario · the Vista selection (seg)', () => {
  it('slides with FIRM to the chosen option', async () => {
    expect(calendarSpring('segment')).toMatchObject(FIRM);
    await render(<VistaControl />);
    await layOutTrack();
    const selection = screen.getByTestId('vista-seleccion');
    expect(animated(selection)).toMatchObject({ width: 100 });
    expect(animated(selection).transform).toEqual([{ translateX: 104 }]);

    await fireEvent.press(screen.getByRole('tab', { name: 'Mes' }));
    expect(Haptics.selectionAsync).toHaveBeenCalled();
    expect(screen.getByRole('tab', { name: 'Mes' })).toBeSelected();
    await advance(32);
    const moving = (animated(selection).transform as { translateX: number }[])[0]!.translateX;
    expect(moving).toBeGreaterThan(0);
    expect(moving).toBeLessThan(104);
    await advance(1200);
    expect(animated(selection).transform).toEqual([{ translateX: 0 }]);
  });

  it('jumps with reduced motion', async () => {
    jest.spyOn(motion, 'useMotion').mockReturnValue({ reduced: true });
    await render(<VistaControl />);
    await layOutTrack();
    await fireEvent.press(screen.getByRole('tab', { name: 'Lista' }));
    await advance(16);
    expect(animated(screen.getByTestId('vista-seleccion')).transform).toEqual([{ translateX: 208 }]);
  });
});
