import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { Notificaciones as NotificacionesData } from '../api/notificaciones';
import { keys } from '../api/queryClient';
import type { TuTurno } from '../api/types';
import { fakeServer, SESSION_OK, type Handler, type Reply } from '../test/fakeServer';
import { notificacionesFixture, notificationFixture, turnoFixture } from '../test/fixtures/turno';
import { renderAt, testQueryClient } from '../test/render';
import { Notificaciones } from './Notificaciones';

function server(data: NotificacionesData | ((filtro: string) => NotificacionesData), extra: Record<string, Handler | Reply> = {}) {
  return fakeServer({
    'GET /api/v1/auth/session': { body: SESSION_OK },
    'GET /api/v1/notificaciones': ({ search }) => ({ body: typeof data === 'function' ? data(search.get('filtro') ?? '') : data }),
    'POST /api/v1/notificaciones/leer': { body: { unread: 0 } },
    'GET /api/v1/tu-turno': { body: turnoFixture({ notifications_unread: 0 }) },
    ...extra,
  });
}

function renderView() {
  const client = testQueryClient();
  // The shell keeps Tu turno loaded for the bell dot.
  client.setQueryData<TuTurno>(keys.tuTurno, turnoFixture({ notifications_unread: 1 }));
  return renderAt(
    '/notificaciones',
    [
      { path: '/notificaciones', element: <Notificaciones /> },
      { path: '/calendario/pieza/:id', element: <p>Detalle de la pieza</p> },
      { path: '/calendario', element: <p>Calendario</p> },
      { path: '/tu-turno', element: <p>Tu turno</p> },
    ],
    client,
  );
}

function rowTitled(title: string) {
  return screen.getByText(title).closest('.notif-row') as HTMLElement;
}

describe('Notificaciones', () => {
  it('groups what is coming and the last days, with the layer dot, time, detail and «NUEVA»', async () => {
    server(notificacionesFixture());
    renderView();

    expect(await screen.findByRole('heading', { name: 'Próximo', level: 2 })).toBeInTheDocument();
    const groups = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(groups.slice(0, 3)).toEqual(['Próximo', 'Hoy', 'Ayer']);
    expect(groups).toHaveLength(4);

    const upcoming = rowTitled('Sale la pieza «Turning a sales call into a product spec.»');
    expect(upcoming).toHaveAttribute('href', '/calendario/pieza/p2');
    expect(within(upcoming).getByText('Mañana 09:00')).toBeInTheDocument();
    expect(within(upcoming).queryByText('Nueva')).not.toBeInTheDocument();
    expect(upcoming.querySelector('.notif-dot')?.getAttribute('style')).toContain('var(--capa-publicaciones)');

    const today = rowTitled('Publicaste «Scope features from the decision they support.»');
    expect(today).toHaveClass('unread');
    expect(within(today).getByText('Nueva')).toBeInTheDocument();
    expect(within(today).getByText('00:30')).toBeInTheDocument();
    expect(within(today).getByText('Las impresiones a las 24 h llegan mañana.')).toBeInTheDocument();

    const yesterday = rowTitled('El verificador bloqueó la pieza del viernes');
    expect(yesterday).not.toHaveClass('unread');
    expect(yesterday.querySelector('.notif-dot')?.getAttribute('style')).toContain('var(--capa-sistema)');

    expect(screen.getByText('Se guardan 7 días. Lo anterior está en el', { exact: false })).toBeInTheDocument();
  });

  it('marks an item read when opening it and goes to its destination', async () => {
    const api = server(notificacionesFixture());
    renderView();
    await userEvent.click(await screen.findByText('Publicaste «Scope features from the decision they support.»'));

    await waitFor(() => expect(api.find('POST', '/api/v1/notificaciones/leer')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/notificaciones/leer')[0]!.body).toEqual({ ids: ['n-hoy'] });
    expect(screen.getByTestId('location')).toHaveTextContent('/calendario/pieza/p1');
  });

  it('opening a read item does not call the backend', async () => {
    const api = server(notificacionesFixture());
    renderView();
    await userEvent.click(await screen.findByText('El verificador bloqueó la pieza del viernes'));
    expect(screen.getByTestId('location')).toHaveTextContent('/calendario/pieza/p3');
    expect(api.find('POST', '/api/v1/notificaciones/leer')).toHaveLength(0);
  });

  it('marks everything read at once and updates the bell dot', async () => {
    let read = false;
    const api = server(() => {
      const data = notificacionesFixture();
      return read ? { ...data, items: data.items.map((item) => ({ ...item, read: true })), unread: 0 } : data;
    });
    api.on('POST /api/v1/notificaciones/leer', () => {
      read = true;
      return { body: { unread: 0 } };
    });
    const { client } = renderView();
    const button = await screen.findByRole('button', { name: 'Marcar todo como leído' });
    await screen.findByText('Nueva');
    await userEvent.click(button);

    expect(api.find('POST', '/api/v1/notificaciones/leer')[0]!.body).toEqual({ todas: true });
    await waitFor(() => expect(screen.queryByText('Nueva')).not.toBeInTheDocument());
    await waitFor(() => expect(client.getQueryData<TuTurno>(keys.tuTurno)?.notifications_unread).toBe(0));
    expect(button).toBeDisabled();
  });

  it('filters the unread ones, without what is coming', async () => {
    const api = server((filtro) =>
      filtro === 'sin_leer' ? notificacionesFixture({ items: [notificationFixture({ id: 'n-hoy' })] }) : notificacionesFixture(),
    );
    renderView();
    await screen.findByRole('heading', { name: 'Próximo' });
    const unreadChip = screen.getByRole('button', { name: 'Sin leer' });
    await userEvent.click(unreadChip);

    expect(unreadChip).toHaveAttribute('aria-pressed', 'true');
    await waitFor(() => expect(api.requests.some((r) => r.path === '/api/v1/notificaciones' && r.search.get('filtro') === 'sin_leer')).toBe(true));
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Próximo' })).not.toBeInTheDocument());
    expect(screen.getByText('Publicaste «Scope features from the decision they support.»')).toBeInTheDocument();
    expect(screen.queryByText('El verificador bloqueó la pieza del viernes')).not.toBeInTheDocument();
  });

  it('says there is nothing new and that older days stay in the Calendario', async () => {
    server(notificacionesFixture({ upcoming: [], items: [], unread: 0 }));
    renderView();
    expect(await screen.findByText('No hay nada nuevo. Lo de días anteriores sigue en el Calendario.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Calendario' })).toHaveAttribute('href', '/calendario');
    expect(screen.getByRole('button', { name: 'Marcar todo como leído' })).toBeDisabled();
  });

  it('says «Aún no disponible» while the backend does not serve them', async () => {
    server(notificacionesFixture(), { 'GET /api/v1/notificaciones': { status: 404, body: { detail: 'No encontrado' } } });
    renderView();
    expect(await screen.findByText('Aún no disponible')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('shows the error with Reintentar', async () => {
    server(notificacionesFixture(), { 'GET /api/v1/notificaciones': { status: 500, body: { detail: 'Fallo del servidor' } } });
    renderView();
    expect(await screen.findByText('Fallo del servidor')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
  });
});
