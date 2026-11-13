// The calendar's pieces apart from the screen: deep links (and the PWA's legacy paths), the route
// params, the period on screen apart from the selected day, the paging threshold and the Lista grouping.
import { item } from '@compartido/fixtures/calendario';
import type { Vista } from '@compartido/logic/events';
import { act, renderHook } from '@testing-library/react-native';
import { openLink } from '@/navigation';
import { routeForUrl } from '@/push/routes';
import { gestures } from '@/theme/motion';
import { groupRows } from './ListView';
import { pageDirection } from './Pager';
import { readCalendarParams } from './params';
import { inPeriod, rangeOf, shifted, useVisiblePeriod } from './period';

const expoRouter = jest.requireMock('expo-router') as { router: Record<string, jest.Mock> };

describe('deep links of the calendar and the piece', () => {
  it('maps the calendar, its params and the piece detail', () => {
    expect(routeForUrl('/calendario')).toEqual({ pathname: '/calendario', params: {} });
    expect(routeForUrl('/calendario?vista=mes&fecha=2026-11-20')).toEqual({ pathname: '/calendario', params: { vista: 'mes', fecha: '2026-11-20' } });
    expect(routeForUrl('/calendario?fecha=2026-11-06&capas=tuyo,red')).toEqual({ pathname: '/calendario', params: { fecha: '2026-11-06', capas: 'tuyo,red' } });
    expect(routeForUrl('/calendario/pieza/p-9')).toEqual({ pathname: '/calendario/pieza/p-9', params: {} });
  });

  it('maps the legacy paths the PWA redirects (App.tsx)', () => {
    expect(routeForUrl('/contenido/p-9')).toEqual({ pathname: '/calendario/pieza/p-9', params: {} });
    expect(routeForUrl('/editorial/p-9')).toEqual({ pathname: '/calendario/pieza/p-9', params: {} });
    expect(routeForUrl('/editorial/p%209?x=1')).toEqual({ pathname: '/calendario/pieza/p%209', params: {} });
    expect(routeForUrl('/contenido')).toEqual({ pathname: '/calendario', params: {} });
    expect(routeForUrl('/editorial/')).toEqual({ pathname: '/calendario', params: {} });
    expect(routeForUrl('/maquina')).toEqual({ pathname: '/calendario', params: {} });
    expect(routeForUrl('/acciones')).toEqual({ pathname: '/calendario', params: {} });
    expect(routeForUrl('/acciones?state=uncertain')).toEqual({ pathname: '/tu-turno', params: {} });
  });

  it('opens them in the app', () => {
    openLink('/editorial/p-9');
    expect(expoRouter.router.push).toHaveBeenLastCalledWith({ pathname: '/calendario/pieza/p-9', params: {} });
    openLink('/calendario?vista=lista');
    expect(expoRouter.router.navigate).toHaveBeenLastCalledWith({ pathname: '/calendario', params: { vista: 'lista' } });
  });
});

describe('route params', () => {
  it('reads valid params and falls back on the defaults', () => {
    expect(readCalendarParams({})).toEqual({ vista: 'semana', fecha: null, capas: null, tipo: 'todo', noSalio: false });
    const read = readCalendarParams({ vista: 'mes', fecha: '2026-11-20', capas: 'red,nada,tuyo', tipo: 'reacciones', no_salio: '1' });
    expect(read).toMatchObject({ vista: 'mes', fecha: '2026-11-20', tipo: 'reacciones', noSalio: true });
    expect([...read.capas!]).toEqual(['red', 'tuyo']);
    expect(readCalendarParams({ vista: 'año', fecha: '2026-02-30', tipo: 'otro', no_salio: 'si' })).toMatchObject({ vista: 'semana', fecha: null, tipo: 'todo', noSalio: false });
    expect(readCalendarParams({ capas: '' }).capas).toBeNull();
  });
});

describe('the period on screen', () => {
  it('knows the days each page has: the week, or the month’s grid with its neighbours’ days', () => {
    expect(rangeOf('semana', '2026-11-07')).toEqual(['2026-11-02', '2026-11-08']);
    expect(rangeOf('mes', '2026-11-07')).toEqual(['2026-10-26', '2026-12-06']);
    expect(shifted('semana', '2026-11-07', 1)).toBe('2026-11-14');
    expect(shifted('mes', '2026-11-07', -1)).toBe('2026-10-07');
    expect(inPeriod('semana', '2026-11-14', '2026-11-09')).toBe(true);
    expect(inPeriod('semana', '2026-11-14', '2026-11-07')).toBe(false);
    expect(inPeriod('mes', '2026-12-15', '2026-11-30')).toBe(true);
    expect(inPeriod('mes', '2026-12-15', '2026-11-07')).toBe(false);
  });

  it('turns without moving the selection, keeps a tapped day’s period and follows a day out of it or a new view', async () => {
    const { result, rerender } = await renderHook((props: { vista: Vista; selected: string }) => useVisiblePeriod(props.vista, props.selected), {
      initialProps: { vista: 'semana', selected: '2026-11-07' },
    });
    expect(result.current.anchor).toBe('2026-11-07');

    // A swipe: the next week is on screen, the selection has not moved.
    await act(async () => result.current.setAnchor('2026-11-14'));
    expect(result.current.anchor).toBe('2026-11-14');
    // A tap on a day of that week: the week stays.
    await rerender({ vista: 'semana', selected: '2026-11-12' });
    expect(result.current.anchor).toBe('2026-11-14');
    // A link to a day of another week: its week comes with it.
    await rerender({ vista: 'semana', selected: '2026-11-25' });
    expect(result.current.anchor).toBe('2026-11-25');

    // Semana → Mes opens on the selected day's month; the leaving week keeps the period it showed.
    await act(async () => result.current.setAnchor('2026-12-02'));
    await rerender({ vista: 'mes', selected: '2026-11-25' });
    expect(result.current.anchor).toBe('2026-11-25');
    expect(result.current.before).toBe('2026-12-02');
  });
});

describe('thresholds', () => {
  it('turns the page past the commit fraction or with a flick', () => {
    const width = 400;
    const commit = width * gestures.pager.commitFraction;
    expect(pageDirection(-commit, 0, width)).toBe(1);
    expect(pageDirection(commit, 0, width)).toBe(-1);
    expect(pageDirection(-commit + 1, 0, width)).toBe(0);
    expect(pageDirection(-20, -gestures.pager.commitVelocity, width)).toBe(1);
    expect(pageDirection(20, -gestures.pager.commitVelocity, width)).toBe(0);
    expect(pageDirection(-300, 0, 0)).toBe(0);
  });
});

describe('Lista', () => {
  it('groups the items by day, in the order they come (newest first)', () => {
    const rows = groupRows(
      [item({ id: 'a', date: '2026-11-07' }), item({ id: 'b', date: '2026-11-07' }), item({ id: 'c', date: '2026-11-06' }), item({ id: 'd', date: '', at: '2026-11-05T14:00:00Z' })],
      'America/Bogota',
    );
    expect(rows.map((row) => (row.kind === 'day' ? `día ${row.date}` : row.item.id))).toEqual(['día 2026-11-07', 'a', 'b', 'día 2026-11-06', 'c', 'día 2026-11-05', 'd']);
  });
});
