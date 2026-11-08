// MovNotificaciones with «menos movimiento»: the bell does not sway (the haptic stays), the dot goes
// at once when everything is read, and «Marcar todo como leído» turns every «Nueva» off at once.
import type { Notificaciones } from '@compartido/api/notificaciones';
import { keys } from '@compartido/api/queryClient';
import { notificacionesFixture, notificationFixture, turnoFixture } from '@compartido/fixtures/turno';
import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';
import * as Haptics from 'expo-haptics';
import { getAnimatedStyle } from 'react-native-reanimated';
import '@/api/transport';
import { TopBar } from '@/components/shell/TopBar';
import { renderApp } from '@/test/render';
import { fakeServer } from '@/test/server';
import { notifTimings } from '@/theme/motion';
import { NotificacionesScreen } from './NotificacionesScreen';

jest.mock('@/theme/motion', () => ({ ...jest.requireActual('@/theme/motion'), useMotion: () => ({ reduced: true }) }));

const wait = (ms: number) =>
  act(async () => {
    await new Promise((resolve) => setTimeout(resolve, ms));
  });

afterEach(() => jest.useRealTimers());

describe('Notificaciones · reduced motion (MovNotificaciones «menos movimiento»)', () => {
  it('the bell stays still on an arrival (the haptic stays) and the dot goes at once', async () => {
    let unread = 1;
    fakeServer({
      'GET /api/v1/tu-turno': () => ({ body: turnoFixture({ notifications_unread: unread }) }),
      'GET /api/v1/operador/overview': { body: { control: { paused: false }, accounts: [] } },
    });
    const { client } = await renderApp(<TopBar />);
    await screen.findByTestId('unread-dot');

    unread = 2;
    await act(async () => {
      await client.invalidateQueries({ queryKey: keys.tuTurno });
    });
    await waitFor(() => expect(Haptics.impactAsync).toHaveBeenCalledWith('light'));
    await wait(notifTimings.bellStep.duration / 2);
    const style = getAnimatedStyle(screen.getByTestId('bell')) as { transform?: { rotate?: string }[] };
    expect(style.transform?.[0]?.rotate ?? '0deg').toBe('0deg');

    unread = 0;
    await act(async () => {
      await client.invalidateQueries({ queryKey: keys.tuTurno });
    });
    await waitFor(() => expect(screen.queryByTestId('unread-dot')).toBeNull());
    expect(screen.queryByTestId('unread-dot-closing')).toBeNull();
  });

  it('«Marcar todo como leído» turns every «Nueva» off at once', async () => {
    jest.useFakeTimers();
    let read = false;
    const data = (): Notificaciones =>
      notificacionesFixture({ upcoming: [], items: [notificationFixture({ id: 'n1', title: 'Primera' }), notificationFixture({ id: 'n2', title: 'Segunda' })], unread: 2 });
    const api = fakeServer({
      'GET /api/v1/notificaciones': () => ({ body: read ? { ...data(), items: data().items.map((item) => ({ ...item, read: true })), unread: 0 } : data() }),
      'GET /api/v1/tu-turno': { body: turnoFixture({ notifications_unread: 2 }) },
    });
    api.on('POST /api/v1/notificaciones/leer', () => {
      read = true;
      return { body: { unread: 0 } };
    });
    await renderApp(<NotificacionesScreen />);
    await screen.findByText('Segunda');
    expect(screen.getAllByText('Nueva')).toHaveLength(2);
    await fireEvent.press(screen.getByRole('button', { name: 'Marcar todo como leído' }));
    // A frame later, long before readOff would end (notifTimings.readOff): nothing is left fading.
    await act(async () => {
      jest.advanceTimersByTime(16);
    });
    expect(screen.queryByText('Nueva')).toBeNull();
    expect(screen.queryByTestId('notif-lit')).toBeNull();
    jest.useRealTimers();
  });
});
