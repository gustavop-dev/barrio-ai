// Notificaciones: PRÓXIMO and the days, the layer dot and «Nueva», marking read on open (and the bell
// dot following), opening the link in the app, «Marcar todo como leído», the dropdown (Sin leer and the
// sections), the clamped rows that unfold without a link, pull to refresh, and the empty, unavailable and error states.
import type { Notificaciones } from '@compartido/api/notificaciones';
import { keys } from '@compartido/api/queryClient';
import type { TuTurno } from '@compartido/api/types';
import { notificacionesFixture, notificationFixture, turnoFixture } from '@compartido/fixtures/turno';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import { router } from 'expo-router';
import '@/api/transport';
import { renderApp, testQueryClient } from '@/test/render';
import { fakeServer, type FakeHandler } from '@/test/server';
import { colors, layers } from '@/theme/tokens';
import { NotificacionesScreen } from './NotificacionesScreen';

function server(data: Notificaciones | ((filtro: string) => Notificaciones), extra: Record<string, FakeHandler> = {}) {
  return fakeServer({
    'GET /api/v1/notificaciones': (request) => ({ body: typeof data === 'function' ? data(new URL(request.url).searchParams.get('filtro') ?? '') : data }),
    'POST /api/v1/notificaciones/leer': { body: { unread: 0 } },
    'GET /api/v1/tu-turno': { body: turnoFixture({ notifications_unread: 1 }) },
    ...extra,
  });
}

const row = (title: string) => screen.getByText(title).parent!.parent! as ReturnType<typeof screen.getByText>;

/** Opens the dropdown and picks a view. */
async function choose(label: string) {
  await fireEvent.press(screen.getByTestId('notif-filtro'));
  await fireEvent.press(screen.getByRole('radio', { name: label }));
}

describe('Notificaciones', () => {
  it('groups what is coming and the last days, with the layer dot, time, detail and «Nueva»', async () => {
    server(notificacionesFixture());
    await renderApp(<NotificacionesScreen />);
    expect(await screen.findByText('Próximo')).toBeOnTheScreen();
    expect(screen.getAllByRole('header').map((h) => h.props.children)).toEqual(expect.arrayContaining(['Notificaciones', 'Próximo', 'Hoy', 'Ayer']));

    const upcoming = screen.getByTestId('notif-piece_scheduled:p2');
    expect(within(upcoming).getByText('Mañana 09:00')).toBeOnTheScreen();
    expect(within(upcoming).queryByText('Nueva')).toBeNull();
    expect(upcoming).toHaveAccessibleName(/^Mañana 09:00\. Sale la pieza/);

    const today = screen.getByTestId('notif-n-hoy');
    expect(within(today).getByText('Nueva')).toBeOnTheScreen();
    expect(within(today).getByText('00:30')).toBeOnTheScreen();
    expect(within(today).getByText('Las impresiones a las 24 h llegan mañana.')).toBeOnTheScreen();
    // Unread: the row is highlighted (superficie, a layer that fades when it is read).
    expect(within(today).getByTestId('notif-lit')).toHaveStyle({ backgroundColor: colors.surface });

    const yesterday = screen.getByTestId('notif-n-ayer');
    expect(within(yesterday).queryByText('Nueva')).toBeNull();
    expect(within(yesterday).queryByTestId('notif-lit')).toBeNull();
    expect(row('El verificador bloqueó la pieza del viernes')).toBeTruthy();
    // The dot takes the colour of the item's calendar layer.
    const dots = (id: string) => within(screen.getByTestId(id)).getByTestId('notif-dot');
    expect(dots('notif-n-ayer')).toHaveStyle({ backgroundColor: layers.sistema });
    expect(dots('notif-n-hoy')).toHaveStyle({ backgroundColor: layers.publicaciones });
    expect(screen.getByText(/Se guardan 7 días\. Lo anterior está en el/)).toBeOnTheScreen();
  });

  it('marks an item read when opening it, opens its link in the app and moves the bell dot', async () => {
    const api = server(notificacionesFixture());
    const client = testQueryClient();
    client.setQueryData<TuTurno>(keys.tuTurno, turnoFixture({ notifications_unread: 1 }));
    await renderApp(<NotificacionesScreen />, { client });
    await fireEvent.press(await screen.findByTestId('notif-n-hoy'));
    await waitFor(() => expect(api.find('POST', '/api/v1/notificaciones/leer')[0]?.body).toEqual({ ids: ['n-hoy'] }));
    expect(router.push).toHaveBeenCalledWith({ pathname: '/calendario/pieza/p1', params: {} });
    await waitFor(() => expect(client.getQueryData<TuTurno>(keys.tuTurno)?.notifications_unread).toBe(0));
  });

  it('opening a read item does not call the backend', async () => {
    const api = server(notificacionesFixture());
    await renderApp(<NotificacionesScreen />);
    await fireEvent.press(await screen.findByTestId('notif-n-antes'));
    expect(router.push).toHaveBeenCalledWith({ pathname: '/personas/c1', params: {} });
    expect(api.find('POST', '/api/v1/notificaciones/leer')).toHaveLength(0);
  });

  it('opens a legacy link where the PWA would send it, and never an outside one', async () => {
    const api = server(
      notificacionesFixture({
        upcoming: [],
        items: [
          notificationFixture({ id: 'n-capt', link: '/?enviado=1', title: 'Procesamos tu audio' }),
          notificationFixture({ id: 'n-fuera', link: 'https://evil.example/x', title: 'Enlace de fuera', read: false }),
        ],
      }),
    );
    await renderApp(<NotificacionesScreen />);
    await fireEvent.press(await screen.findByTestId('notif-n-fuera'));
    await waitFor(() => expect(api.find('POST', '/api/v1/notificaciones/leer')).toHaveLength(1));
    expect(router.push).not.toHaveBeenCalled();
    expect(router.navigate).not.toHaveBeenCalled();
  });

  it('marks everything read at once and the bell dot follows', async () => {
    let read = false;
    const api = server(() => {
      const data = notificacionesFixture();
      return read ? { ...data, items: data.items.map((item) => ({ ...item, read: true })), unread: 0 } : data;
    });
    api.on('POST /api/v1/notificaciones/leer', () => {
      read = true;
      return { body: { unread: 0 } };
    });
    const client = testQueryClient();
    client.setQueryData<TuTurno>(keys.tuTurno, turnoFixture({ notifications_unread: 1 }));
    await renderApp(<NotificacionesScreen />, { client });
    await screen.findByText('Nueva');
    const button = screen.getByRole('button', { name: 'Marcar todo como leído' });
    await fireEvent.press(button);
    expect(api.find('POST', '/api/v1/notificaciones/leer')[0]?.body).toEqual({ todas: true });
    await waitFor(() => expect(screen.queryByText('Nueva')).toBeNull());
    await waitFor(() => expect(client.getQueryData<TuTurno>(keys.tuTurno)?.notifications_unread).toBe(0));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Marcar todo como leído' })).toBeDisabled());
  });

  it('filters the unread ones, without what is coming', async () => {
    const api = server((filtro) => (filtro === 'sin_leer' ? notificacionesFixture({ items: [notificationFixture({ id: 'n-hoy' })] }) : notificacionesFixture()));
    await renderApp(<NotificacionesScreen />);
    await screen.findByText('Próximo');
    await choose('Sin leer');
    expect(screen.getByTestId('notif-filtro')).toHaveAccessibilityValue({ text: 'Sin leer' });
    await waitFor(() => expect(api.requests.some((r) => r.path === '/api/v1/notificaciones?filtro=sin_leer')).toBe(true));
    expect(await screen.findByText('Publicaste «Scope features from the decision they support.»')).toBeOnTheScreen();
    expect(screen.queryByText('Próximo')).toBeNull();
    expect(screen.queryByText('El verificador bloqueó la pieza del viernes')).toBeNull();
  });

  it('shows one section from the dropdown, asking the server for everything', async () => {
    const api = server(notificacionesFixture());
    await renderApp(<NotificacionesScreen />);
    await screen.findByText('Próximo');
    await choose('Ayer');
    expect(screen.getByTestId('notif-filtro')).toHaveAccessibilityValue({ text: 'Ayer' });
    expect(await screen.findByTestId('notif-n-ayer')).toBeOnTheScreen();
    expect(screen.queryByText('Próximo')).toBeNull();
    expect(screen.queryByTestId('notif-n-hoy')).toBeNull();
    expect(screen.queryByTestId('notif-n-antes')).toBeNull();
    expect(api.requests.some((r) => r.path === '/api/v1/notificaciones?filtro=sin_leer')).toBe(false);
    await choose('Próximo');
    expect(await screen.findByTestId('notif-piece_scheduled:p2')).toBeOnTheScreen();
    expect(screen.queryByTestId('notif-n-ayer')).toBeNull();
    await choose('Anteriores');
    expect(await screen.findByTestId('notif-n-antes')).toBeOnTheScreen();
    expect(screen.queryByTestId('notif-piece_scheduled:p2')).toBeNull();
  });

  it('says a section is empty', async () => {
    server(notificacionesFixture({ items: [] }));
    await renderApp(<NotificacionesScreen />);
    await screen.findByText('Próximo');
    await choose('Hoy');
    expect(await screen.findByText('Nada en «Hoy».')).toBeOnTheScreen();
  });

  it('shows two lines of the title and one of the detail; a row without a link unfolds its whole text', async () => {
    const api = server(
      notificacionesFixture({
        upcoming: [],
        items: [notificationFixture({ id: 'n-largo', link: '', title: 'Un aviso largo sin enlace', detail: 'Con un detalle que también es largo.' })],
      }),
    );
    await renderApp(<NotificacionesScreen />);
    const title = await screen.findByText('Un aviso largo sin enlace');
    expect(title).toHaveProp('numberOfLines', 2);
    expect(screen.getByText('Con un detalle que también es largo.')).toHaveProp('numberOfLines', 1);
    const rowButton = screen.getByTestId('notif-n-largo');
    expect(rowButton).toBeCollapsed();
    await fireEvent.press(rowButton);
    expect(screen.getByText('Un aviso largo sin enlace')).not.toHaveProp('numberOfLines');
    expect(screen.getByText('Con un detalle que también es largo.')).not.toHaveProp('numberOfLines');
    expect(screen.getByTestId('notif-n-largo')).toBeExpanded();
    await waitFor(() => expect(api.find('POST', '/api/v1/notificaciones/leer')[0]?.body).toEqual({ ids: ['n-largo'] }));
    expect(router.push).not.toHaveBeenCalled();
  });

  it('refreshes when pulled down', async () => {
    const api = server(notificacionesFixture());
    await renderApp(<NotificacionesScreen />);
    await screen.findByText('Próximo');
    const list = screen.getByTestId('screen-notificaciones');
    await act(async () => list.props.refreshControl.props.onRefresh());
    await waitFor(() => expect(api.find('GET', '/api/v1/notificaciones').length).toBeGreaterThan(1));
  });

  it('says there is nothing new and that older days stay in the Calendario', async () => {
    server(notificacionesFixture({ upcoming: [], items: [], unread: 0 }));
    await renderApp(<NotificacionesScreen />);
    expect(await screen.findByText('No hay nada nuevo. Lo de días anteriores sigue en el Calendario.')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Marcar todo como leído' })).toBeDisabled();
    await fireEvent.press(screen.getByRole('link', { name: 'Calendario' }));
    expect(router.navigate).toHaveBeenCalledWith('/calendario');
  });

  it('says «Aún no disponible» while the backend does not serve them', async () => {
    server(notificacionesFixture(), { 'GET /api/v1/notificaciones': { status: 404, body: { detail: 'No encontrado' } } });
    await renderApp(<NotificacionesScreen />);
    expect(await screen.findByText('Aún no disponible')).toBeOnTheScreen();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('shows the error with Reintentar', async () => {
    const api = server(notificacionesFixture(), { 'GET /api/v1/notificaciones': { status: 500, body: { detail: 'Fallo del servidor' } } });
    await renderApp(<NotificacionesScreen />);
    expect(await screen.findByText('Fallo del servidor')).toBeOnTheScreen();
    api.on('GET /api/v1/notificaciones', { body: notificacionesFixture() });
    await fireEvent.press(screen.getByRole('button', { name: 'Reintentar' }));
    expect(await screen.findByText('Próximo')).toBeOnTheScreen();
  });
});
