// Tu turno and Notificaciones inside the whole app: the shell's counter and bell dot follow them.
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { overviewFixture, renderApp } from '../../test/app';
import { fakeServer, SESSION_OK } from '../../test/fakeServer';
import { notificacionesFixture, turnoFixture, UNCERTAIN_CARD } from '../../test/fixtures/turno';

describe('Tu turno y Notificaciones en la app', () => {
  it('clears the bell dot after «Marcar todo como leído»', async () => {
    let unread = 1;
    const api = fakeServer({
      'GET /api/v1/auth/session': { body: SESSION_OK },
      'GET /api/v1/operador/overview': { body: overviewFixture() },
      'GET /api/v1/tu-turno': () => ({ body: turnoFixture({ notifications_unread: unread }) }),
      'GET /api/v1/notificaciones': () => ({ body: notificacionesFixture({ unread }) }),
    });
    api.on('POST /api/v1/notificaciones/leer', () => {
      unread = 0;
      return { body: { unread: 0 } };
    });
    renderApp('/notificaciones');

    const accesos = await screen.findByRole('navigation', { name: 'Accesos' });
    expect(await within(accesos).findByRole('link', { name: 'Notificaciones, hay novedades' })).toBeInTheDocument();
    await userEvent.click(await screen.findByRole('button', { name: 'Marcar todo como leído' }));
    await waitFor(() => expect(within(accesos).getByRole('link', { name: 'Notificaciones' }).querySelector('.navdot')).toBeNull());
  });

  it('opens Tu turno at a card anchored from elsewhere', async () => {
    fakeServer({
      'GET /api/v1/auth/session': { body: SESSION_OK },
      'GET /api/v1/operador/overview': { body: overviewFixture() },
      'GET /api/v1/tu-turno': { body: turnoFixture({ count: 1, critical: true, items: [{ ...UNCERTAIN_CARD, state: 'vista' }] }) },
    });
    renderApp('/tu-turno#turno-uncertain-a1');
    expect(await screen.findByRole('heading', { name: 'Tu turno', level: 1 })).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'Comprueba si salió tu comentario' })).toBeInTheDocument();
    expect(document.getElementById('turno-uncertain-a1')).not.toBeNull();
  });
});
