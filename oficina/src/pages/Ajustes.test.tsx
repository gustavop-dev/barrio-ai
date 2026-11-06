import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fakeServer, SESSION_OK } from '../test/fakeServer';
import { renderAt } from '../test/render';
import { Ajustes } from './Ajustes';

afterEach(() => {
  Reflect.deleteProperty(navigator, 'userAgent');
  Reflect.deleteProperty(navigator, 'serviceWorker');
});

const routes = [
  { path: '/ajustes', element: <Ajustes /> },
  { path: '/login', element: <p>Pantalla de login</p> },
];

describe('Ajustes', () => {
  it('tells iPhone users to add the app to the home screen before enabling push', async () => {
    Object.defineProperty(navigator, 'userAgent', { configurable: true, value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Safari/604.1' });
    fakeServer({ 'GET /api/v1/auth/session': { body: SESSION_OK } });
    renderAt('/ajustes', routes);
    expect(await screen.findByText(/Añadir a pantalla de inicio/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Activar notificaciones' })).not.toBeInTheDocument();
  });

  it('offers to enable push where it is supported', async () => {
    const registration = { pushManager: { getSubscription: vi.fn(async () => null), subscribe: vi.fn() } };
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: { ready: Promise.resolve(registration) } });
    vi.stubGlobal('PushManager', function PushManager() {});
    vi.stubGlobal('Notification', Object.assign(function Notification() {}, { permission: 'default', requestPermission: vi.fn() }));
    fakeServer({ 'GET /api/v1/auth/session': { body: SESSION_OK } });
    renderAt('/ajustes', routes);
    expect(await screen.findByText('Desactivadas')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Activar notificaciones' })).toBeEnabled();
  });

  it('logs out and returns to the login screen', async () => {
    const server = fakeServer({
      'GET /api/v1/auth/session': { body: SESSION_OK },
      'POST /api/v1/auth/logout': { status: 204 },
    });
    const user = userEvent.setup();
    renderAt('/ajustes', routes);
    expect(await screen.findByText('gustavo')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Cerrar sesión' }));
    expect(await screen.findByText('Pantalla de login')).toBeInTheDocument();
    expect(server.find('POST', '/api/v1/auth/logout')).toHaveLength(1);
  });
});
