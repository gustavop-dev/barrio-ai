// MovResultados in the app: the figures count up from 0 the first time (600 ms) and from the old value to the
// new one afterwards (TOK.slow), on the UI thread and ending on the exact figure; the bars grow in a cascade;
// «sin dato» never counts; reduced motion shows everything at once.
import { kpi } from '@compartido/fixtures/resultados';
import { formatKpiValue, type KpiUnit } from '@compartido/logic/resultados';
import { act, render, screen } from '@testing-library/react-native';
import { getAnimatedStyle } from 'react-native-reanimated';
import { renderApp } from '@/test/render';
import * as motion from '@/theme/motion';
import { durations, easings, resultsChoreography, resultsTiming } from '@/theme/motion';
import { KpiTile } from './charts';
import { countDecimals, CountUp, formatCount, GrowBar } from './CountUp';

const hidden = { includeHiddenElements: true };

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

/** What the counting figure shows right now. */
function figure(testID = 'cifra'): string {
  const input = screen.getByTestId(`${testID}-cifra`, hidden) as unknown as { props: { jestAnimatedProps: { value: { text: string } } } };
  return input.props.jestAnimatedProps.value.text;
}

describe('MovResultados · tokens', () => {
  it('counts and grows with the board’s timings', () => {
    expect(resultsTiming('countFirst')).toMatchObject({ duration: 600, easing: easings.enter });
    expect(resultsTiming('count')).toMatchObject({ duration: durations.slow, easing: easings.enter });
    expect(resultsTiming('bar')).toMatchObject({ duration: durations.base, easing: easings.enter });
    expect(resultsChoreography).toEqual({ barFirstDelayMs: 120, barStaggerMs: 40 });
  });

  it('writes a figure on its way exactly as the screen writes the final one', () => {
    const cases: [number, KpiUnit][] = [
      [0, 'number'],
      [7, 'number'],
      [1520, 'number'],
      [1234567, 'number'],
      [3.45, 'number'],
      [999.96, 'number'],
      [41, 'percent'],
      [3.5, 'percent'],
      [3.1, 'usd'],
      [61.2, 'usd'],
      [12345.678, 'usd'],
    ];
    for (const [value, unit] of cases) expect(formatCount(value, unit, countDecimals(value, unit))).toBe(formatKpiValue(value, unit));
    // An integer figure counts in integers, like the board.
    expect(formatCount(923.4, 'number', countDecimals(1520, 'number'))).toBe('923');
  });
});

describe('MovResultados · the figures', () => {
  it('count up from 0 the first time, in 600 ms, and screen readers hear only the final figure', async () => {
    await render(<CountUp value={1520} text="1.520" testID="cifra" />);
    expect(screen.getByLabelText('1.520')).toBeOnTheScreen();
    expect(figure()).toBe('0');
    await advance(400);
    // Still counting at 400 ms: the first count lasts 600.
    const midway = Number(figure().replace('.', ''));
    expect(midway).toBeGreaterThan(0);
    expect(midway).toBeLessThan(1520);
    await advance(300);
    expect(figure()).toBe('1.520');
  });

  it('count from the old value to the new one on a change, in TOK.slow', async () => {
    const view = await render(<CountUp value={1520} text="1.520" testID="cifra" />);
    await advance(700);
    await view.rerender(<CountUp value={1290} text="1.290" testID="cifra" />);
    expect(screen.getByLabelText('1.290')).toBeOnTheScreen();
    await advance(200);
    const midway = Number(figure().replace('.', ''));
    expect(midway).toBeGreaterThan(1290);
    expect(midway).toBeLessThan(1520);
    await advance(250);
    expect(figure()).toBe('1.290');
  });

  it('show the final figure at once with reduced motion', async () => {
    jest.spyOn(motion, 'useMotion').mockReturnValue({ reduced: true });
    await render(<CountUp value={41} text="41 %" unit="percent" testID="cifra" />);
    await advance(16);
    expect(figure()).toBe('41 %');
  });

  it('never count «sin dato»: the tile keeps its dash', async () => {
    await renderApp(<KpiTile label="Seguidores" kpi={kpi(null)} />);
    expect(screen.getByLabelText('Sin dato')).toBeOnTheScreen();
    expect(screen.queryByTestId('kpi-cifra-Seguidores', hidden)).toBeNull();
    expect(screen.queryByText('0')).toBeNull();
  });
});

describe('MovResultados · the bars', () => {
  it('grow in a cascade: 120 ms plus 40 ms per bar the first time, 40 ms per bar afterwards', async () => {
    const view = await render(<GrowBar width={60} color="#647e99" index={2} />);
    const bar = screen.getByTestId('barra');
    expect(bar).toHaveAnimatedStyle({ width: '0%' });
    await advance(150);
    // Bar 2 waits 120 + 2 × 40 = 200 ms.
    expect(bar).toHaveAnimatedStyle({ width: '0%' });
    await advance(400);
    expect(bar).toHaveAnimatedStyle({ width: '60%' });

    await view.rerender(<GrowBar width={30} color="#647e99" index={2} />);
    await advance(48);
    // Now it waits only 2 × 40 = 80 ms.
    expect(bar).toHaveAnimatedStyle({ width: '60%' });
    await advance(400);
    expect(bar).toHaveAnimatedStyle({ width: '30%' });
  });

  it('are at their length at once with reduced motion', async () => {
    jest.spyOn(motion, 'useMotion').mockReturnValue({ reduced: true });
    await render(<GrowBar width={45} color="#647e99" index={3} />);
    await advance(16);
    expect(getAnimatedStyle(screen.getByTestId('barra')).width).toBe('45%');
  });
});
