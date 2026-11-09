// MovNotificaciones in the app: a notification that arrives while the screen is open enters at the top
// with the board's motion; «Marcar todo como leído» turns «Nueva» off in a cascade, top to bottom; the
// bell of every top bar sways and its dot pops in (one LEVE for all of them), and the dot closes once
// everything is read; a push received with the app open refreshes the bell.
import type { Notificaciones } from '@compartido/api/notificaciones';
import { keys } from '@compartido/api/queryClient';
import { notificacionesFixture, notificationFixture, turnoFixture } from '@compartido/fixtures/turno';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import * as Haptics from 'expo-haptics';
import * as Notifications from 'expo-notifications';
import '@/api/transport';
import { TopBar } from '@/components/shell/TopBar';
import { renderApp } from '@/test/render';
import { fakeServer } from '@/test/server';
import { notifMotion, notifTimings } from '@/theme/motion';
import { NotificacionesScreen } from './NotificacionesScreen';

const OVERVIEW = { body: { control: { paused: false }, accounts: [] } };

type AnimatedStyle = { transform?: Record<string, number | string>[]; backgroundColor?: string };
/** The style Reanimated last applied to a view (what its jest props carry). */
const animatedStyle = (node: { props: Record<string, unknown> }): AnimatedStyle =>
  (node.props.jestAnimatedStyle as { value?: AnimatedStyle } | undefined)?.value ?? {};

const advance = async (ms: number) => {
  await act(async () => {
    jest.advanceTimersByTime(ms);
  });
};

/** Advances the fake clock in small steps until `done`, and says how long it took (ms). */
async function elapsedUntil(done: () => boolean, step = 4, limit = 2000): Promise<number> {
  let elapsed = 0;
  while (!done() && elapsed < limit) {
    await advance(step);
    elapsed += step;
  }
  return elapsed;
}

afterEach(() => jest.useRealTimers());

/** The arrival is the newest item: «now», or just after the latest fixture item, so the test does not depend on the
 * hour (the fixture's «n-hoy» is today at 00:30, which is later than «now» between 00:00 and 00:30). */
const newest = (items: { at: string }[]) =>
  new Date(Math.max(Date.now(), ...items.map((item) => Date.parse(item.at) + 60_000))).toISOString();

describe('Notificaciones · the list (MovNotificaciones)', () => {
  it('a notification that arrives enters at the top with the arrival motion; the others do not', async () => {
    const first = notificacionesFixture();
    const arrived: Notificaciones = {
      ...first,
      items: [notificationFixture({ id: 'n-nueva', title: 'Sofía Muestra aceptó tu invitación', layer: 'red', link: '/personas/c9', at: newest(first.items) }), ...first.items],
      unread: first.unread + 1,
    };
    let later = false;
    fakeServer({
      'GET /api/v1/notificaciones': () => ({ body: later ? arrived : first }),
      'GET /api/v1/tu-turno': { body: turnoFixture({ notifications_unread: 1 }) },
    });
    await renderApp(<NotificacionesScreen />);
    await screen.findByText('Próximo');
    expect(screen.queryByTestId(/^notif-llega-/)).toBeNull();

    later = true;
    const list = screen.getByTestId('screen-notificaciones');
    await act(async () => list.props.refreshControl.props.onRefresh());
    expect(await screen.findByTestId('notif-llega-n-nueva')).toBeOnTheScreen();
    expect(screen.queryByTestId('notif-llega-n-hoy')).toBeNull();
    // At the top of the day.
    const rows = screen.getAllByTestId(/^notif-n-/).map((row) => row.props.testID);
    expect(rows[0]).toBe('notif-n-nueva');
  });

  it('«Marcar todo como leído» turns «Nueva» off in a cascade, top to bottom', async () => {
    jest.useFakeTimers();
    const hour = 60 * 60 * 1000;
    const unread = (): Notificaciones =>
      notificacionesFixture({
        upcoming: [],
        items: [
          notificationFixture({ id: 'n1', title: 'Primera', at: new Date(Date.now() - hour).toISOString() }),
          notificationFixture({ id: 'n2', title: 'Segunda', at: new Date(Date.now() - 2 * hour).toISOString() }),
        ],
        unread: 2,
      });
    let read = false;
    const api = fakeServer({
      'GET /api/v1/notificaciones': () => {
        const data = unread();
        return { body: read ? { ...data, items: data.items.map((item) => ({ ...item, read: true })), unread: 0 } : data };
      },
      'GET /api/v1/tu-turno': { body: turnoFixture({ notifications_unread: 2 }) },
    });
    api.on('POST /api/v1/notificaciones/leer', () => {
      read = true;
      return { body: { unread: 0 } };
    });
    await renderApp(<NotificacionesScreen />);
    await screen.findByText('Segunda');
    const shows = (id: string) => within(screen.getByTestId(`notif-${id}`)).queryByText('Nueva') !== null;
    expect(shows('n1') && shows('n2')).toBe(true);

    await fireEvent.press(screen.getByRole('button', { name: 'Marcar todo como leído' }));
    const first = await elapsedUntil(() => !shows('n1'));
    expect(shows('n2')).toBe(true);
    const second = first + (await elapsedUntil(() => !shows('n2')));
    const { duration } = notifTimings.readOff;
    expect(first).toBeGreaterThanOrEqual(duration - 20);
    expect(first).toBeLessThanOrEqual(duration + 40);
    expect(second).toBeGreaterThan(first);
    expect(second - first).toBeLessThanOrEqual(notifMotion.readStaggerMs + 40);
    expect(within(screen.getByTestId('notif-n1')).queryByTestId('notif-lit')).toBeNull();
    expect(api.find('POST', '/api/v1/notificaciones/leer')[0]?.body).toEqual({ todas: true });
  });
});

describe('Notificaciones · the bell (MovNotificaciones)', () => {
  const rotation = (index: number) => Number.parseFloat(String(animatedStyle(screen.getAllByTestId('bell')[index]!).transform?.[0]?.rotate ?? '0'));
  const dotScale = (testID: string) => Number(animatedStyle(screen.getAllByTestId(testID)[0]!).transform?.[0]?.scale ?? 1);

  it('sways every bell and pops the dot in from 0 on an arrival, with one LEVE; the dot closes when all is read', async () => {
    jest.useFakeTimers();
    let unread = 1;
    fakeServer({ 'GET /api/v1/tu-turno': () => ({ body: turnoFixture({ notifications_unread: unread }) }), 'GET /api/v1/operador/overview': OVERVIEW });
    const { client } = await renderApp(
      <>
        <TopBar />
        <TopBar />
      </>,
    );
    await waitFor(() => expect(screen.getAllByTestId('unread-dot')).toHaveLength(2));
    // The first answer is not an arrival.
    expect(Haptics.impactAsync).not.toHaveBeenCalled();
    expect(rotation(0)).toBe(0);

    unread = 2;
    await act(async () => {
      await client.invalidateQueries({ queryKey: keys.tuTurno });
    });
    await advance(16);
    expect(Haptics.impactAsync).toHaveBeenCalledTimes(1);
    expect(Haptics.impactAsync).toHaveBeenCalledWith('light');
    await advance(notifTimings.bellStep.duration / 2 - 16);
    // Halfway through the first step: both bells lean toward bellSway[0], the dot is still growing.
    expect(rotation(0)).toBeGreaterThan(0);
    expect(rotation(0)).toBeLessThan(notifMotion.bellSway[0]);
    expect(rotation(1)).toBeGreaterThan(0);
    expect(dotScale('unread-dot')).toBeLessThan(1);
    await advance(notifMotion.bellSwayMs + 400);
    expect(rotation(0)).toBe(0);
    expect(dotScale('unread-dot')).toBeCloseTo(1, 2);

    unread = 0;
    await act(async () => {
      await client.invalidateQueries({ queryKey: keys.tuTurno });
    });
    await advance(16);
    expect(screen.queryByTestId('unread-dot')).toBeNull();
    expect(screen.getAllByTestId('unread-dot-closing')).toHaveLength(2);
    await advance(1500);
    expect(screen.queryByTestId('unread-dot-closing')).toBeNull();
    expect(screen.getAllByLabelText('Notificaciones')).toHaveLength(2);
  });

  it('a push received with the app open refreshes the bell', async () => {
    const api = fakeServer({ 'GET /api/v1/tu-turno': { body: turnoFixture({ notifications_unread: 0 }) }, 'GET /api/v1/operador/overview': OVERVIEW });
    await renderApp(<TopBar />);
    await waitFor(() => expect(api.find('GET', '/api/v1/tu-turno')).toHaveLength(1));
    const received = jest.mocked(Notifications.addNotificationReceivedListener).mock.calls[0]?.[0];
    expect(received).toBeDefined();
    await act(async () => received?.({} as Notifications.Notification));
    await waitFor(() => expect(api.find('GET', '/api/v1/tu-turno').length).toBeGreaterThan(1));
  });
});
