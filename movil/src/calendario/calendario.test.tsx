// The calendar's pieces apart from the screen: deep links (and the PWA's legacy paths), the route
// params, the paging threshold and the Lista grouping.
import { item } from '@compartido/fixtures/calendario';
import { openLink } from '@/navigation';
import { routeForUrl } from '@/push/routes';
import { gestures } from '@/theme/motion';
import { groupRows } from './ListView';
import { pageDirection } from './Pager';
import { readCalendarParams } from './params';

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
    expect(expoRouter.router.push).toHaveBeenLastCalledWith({ pathname: '/calendario', params: { vista: 'lista' } });
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
