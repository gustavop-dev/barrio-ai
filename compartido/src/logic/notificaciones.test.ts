// The dropdown of Notificaciones: which API filter each view asks for and which groups each section keeps.
import { notificacionesFixture, notificationFixture } from '../fixtures/turno';
import { filterNotificationGroups, groupNotifications, notificationFilterOf, notificationSection } from './notificaciones';

const NOW = new Date('2026-11-11T17:00:00Z').getTime();
const DAY = 86_400_000;

function groups() {
  const data = notificacionesFixture({
    items: [
      notificationFixture({ id: 'hoy', at: new Date(NOW - 3_600_000).toISOString() }),
      notificationFixture({ id: 'ayer', at: new Date(NOW - DAY).toISOString() }),
      notificationFixture({ id: 'antes', at: new Date(NOW - 3 * DAY).toISOString() }),
      notificationFixture({ id: 'sin-fecha', at: '' }),
    ],
  });
  return groupNotifications(data, 'todas', NOW);
}

const ids = (list: ReturnType<typeof groups>) => list.flatMap((group) => group.items.map((item) => item.id));

describe('Notificaciones · secciones del filtro', () => {
  it('only «Sin leer» filters on the server', () => {
    expect(notificationFilterOf('sin_leer')).toBe('sin_leer');
    for (const view of ['todas', 'proximo', 'hoy', 'ayer', 'anteriores'] as const) expect(notificationFilterOf(view)).toBe('todas');
  });

  it('names the section of each group', () => {
    expect(groups().map(notificationSection)).toEqual(['proximo', 'hoy', 'ayer', 'anteriores', 'anteriores']);
  });

  it('keeps every group for Todas and Sin leer, and only its section otherwise', () => {
    const all = groups();
    expect(filterNotificationGroups(all, 'todas')).toBe(all);
    expect(filterNotificationGroups(all, 'sin_leer')).toBe(all);
    expect(ids(filterNotificationGroups(all, 'proximo'))).toEqual(['piece_scheduled:p2']);
    expect(ids(filterNotificationGroups(all, 'hoy'))).toEqual(['hoy']);
    expect(ids(filterNotificationGroups(all, 'ayer'))).toEqual(['ayer']);
    expect(ids(filterNotificationGroups(all, 'anteriores'))).toEqual(['antes', 'sin-fecha']);
  });
});
