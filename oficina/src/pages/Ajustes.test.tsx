import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { LinkedInStatus } from '../api/types';
import { fakeServer, SESSION_OK } from '../test/fakeServer';
import { renderAt } from '../test/render';
import { Ajustes, LINKEDIN_REASONS, linkedinReturnMessage } from './Ajustes';

// Shape of connectors_linkedin.status_payload().
function linkedin(extra: Partial<LinkedInStatus> = {}): LinkedInStatus {
  return {
    configured: true,
    live: true,
    api_version: '202610',
    scopes_required: ['openid', 'profile', 'w_member_social'],
    connected: false,
    member_urn: null,
    member_name: null,
    scopes: [],
    expires_at: null,
    days_left: null,
    expired: false,
    expiring_soon: false,
    account: null,
    ...extra,
  };
}

const CONNECTED = linkedin({
  connected: true,
  member_urn: 'urn:li:person:782bbtaQ',
  member_name: 'Gustavo P',
  scopes: ['openid', 'profile', 'w_member_social'],
  expires_at: '2027-01-05T18:00:00Z',
  days_left: 59,
  account: { id: 'acc-li', paused: false, paused_reason: '' },
  connected_at: '2026-11-06T18:00:00Z',
});

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
    fakeServer({ 'GET /api/v1/auth/session': { body: SESSION_OK }, 'GET /api/v1/linkedin/status': { body: linkedin() } });
    renderAt('/ajustes', routes);
    expect(await screen.findByText(/Añadir a pantalla de inicio/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Activar notificaciones' })).not.toBeInTheDocument();
  });

  it('offers to enable push where it is supported', async () => {
    const registration = { pushManager: { getSubscription: vi.fn(async () => null), subscribe: vi.fn() } };
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: { ready: Promise.resolve(registration) } });
    vi.stubGlobal('PushManager', function PushManager() {});
    vi.stubGlobal('Notification', Object.assign(function Notification() {}, { permission: 'default', requestPermission: vi.fn() }));
    fakeServer({ 'GET /api/v1/auth/session': { body: SESSION_OK }, 'GET /api/v1/linkedin/status': { body: linkedin() } });
    renderAt('/ajustes', routes);
    expect(await screen.findByText('Desactivadas')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Activar notificaciones' })).toBeEnabled();
  });

  it('logs out and returns to the login screen', async () => {
    const server = fakeServer({
      'GET /api/v1/auth/session': { body: SESSION_OK },
      'GET /api/v1/linkedin/status': { body: linkedin() },
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

describe('Ajustes · LinkedIn oficial', () => {
  const section = () => screen.getByRole('region', { name: 'LinkedIn oficial' });

  it('shows the connected member, the expiry with days left and offers to reconnect with a full navigation', async () => {
    const server = fakeServer({ 'GET /api/v1/auth/session': { body: SESSION_OK }, 'GET /api/v1/linkedin/status': { body: CONNECTED } });
    renderAt('/ajustes', routes);
    expect(await within(section()).findByText('Conectado')).toBeInTheDocument();
    expect(within(section()).getByText('Gustavo P')).toBeInTheDocument();
    expect(within(section()).getByText('urn:li:person:782bbtaQ')).toBeInTheDocument();
    expect(within(section()).getByText(/quedan 59 días/)).toBeInTheDocument();
    expect(within(section()).getByText(/versión 202610/)).toBeInTheDocument();
    const link = within(section()).getByRole('link', { name: 'Reconectar LinkedIn' });
    expect(link).toHaveAttribute('href', '/api/v1/linkedin/oauth/start');
    expect(link).not.toHaveAttribute('target');
    // Navigating is the browser's job: the app never fetches the OAuth start.
    expect(server.find('GET', '/api/v1/linkedin/oauth/start')).toHaveLength(0);
    expect(JSON.stringify(server.requests.map((r) => r.path))).not.toMatch(/oauth/);
  });

  it('warns when the token is about to expire', async () => {
    fakeServer({
      'GET /api/v1/auth/session': { body: SESSION_OK },
      'GET /api/v1/linkedin/status': { body: { ...CONNECTED, days_left: 4, expiring_soon: true } },
    });
    renderAt('/ajustes', routes);
    expect(await within(section()).findByText('Caduca pronto')).toBeInTheDocument();
    expect(within(section()).getByText(/El acceso caduca en 4 días/)).toBeInTheDocument();
    expect(within(section()).getByRole('link', { name: 'Reconectar LinkedIn' })).toBeInTheDocument();
  });

  it('shows an expired token, the paused publication and the switch that keeps it off', async () => {
    fakeServer({
      'GET /api/v1/auth/session': { body: SESSION_OK },
      'GET /api/v1/linkedin/status': {
        body: {
          ...CONNECTED,
          connected: false,
          expired: true,
          days_left: 0,
          live: false,
          account: { id: 'acc-li', paused: true, paused_reason: 'Token de LinkedIn caducado: reconecta LinkedIn en Ajustes.' },
        },
      },
    });
    renderAt('/ajustes', routes);
    expect(await within(section()).findByText('Caducado')).toBeInTheDocument();
    expect(within(section()).getByText(/El acceso caducó y la publicación diaria está en pausa/)).toBeInTheDocument();
    expect(within(section()).getByText(/LIVE_LINKEDIN_OFFICIAL=false/)).toBeInTheDocument();
    expect(within(section()).getByRole('link', { name: 'Reconectar LinkedIn' })).toHaveAttribute('href', '/api/v1/linkedin/oauth/start');
  });

  it('offers «Conectar LinkedIn» when nothing is connected', async () => {
    fakeServer({ 'GET /api/v1/auth/session': { body: SESSION_OK }, 'GET /api/v1/linkedin/status': { body: linkedin() } });
    renderAt('/ajustes', routes);
    expect(await within(section()).findByText('Sin conectar')).toBeInTheDocument();
    expect(within(section()).getByRole('link', { name: 'Conectar LinkedIn' })).toHaveAttribute('href', '/api/v1/linkedin/oauth/start');
  });

  it('explains why it cannot connect: app not configured or no permission', async () => {
    fakeServer({ 'GET /api/v1/auth/session': { body: SESSION_OK }, 'GET /api/v1/linkedin/status': { body: linkedin({ configured: false }) } });
    renderAt('/ajustes', routes);
    expect(await within(section()).findByText(/Falta configurar la app de LinkedIn/)).toBeInTheDocument();
    expect(within(section()).queryByRole('link', { name: /Conectar LinkedIn/ })).not.toBeInTheDocument();
  });

  it('hides the button from a user without approve_actions', async () => {
    fakeServer({
      'GET /api/v1/auth/session': { body: { authenticated: true, user: { username: 'lector', is_superuser: false, permissions: ['operate_linkedin'] } } },
      'GET /api/v1/linkedin/status': { body: linkedin() },
    });
    renderAt('/ajustes', routes);
    expect(await within(section()).findByText(/no tiene el permiso «approve_actions»/)).toBeInTheDocument();
    expect(within(section()).queryByRole('link', { name: /Conectar LinkedIn/ })).not.toBeInTheDocument();
  });

  it('confirms ?linkedin=ok and clears it from the address', async () => {
    fakeServer({ 'GET /api/v1/auth/session': { body: SESSION_OK }, 'GET /api/v1/linkedin/status': { body: CONNECTED } });
    const user = userEvent.setup();
    renderAt('/ajustes?linkedin=ok', routes);
    const notice = await within(section()).findByRole('status');
    expect(notice).toHaveTextContent('LinkedIn conectado');
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/ajustes$/);
    await user.click(within(notice).getByRole('button', { name: 'Entendido' }));
    expect(within(section()).queryByText('LinkedIn conectado')).not.toBeInTheDocument();
  });

  it('explains ?linkedin=error&motivo=… in Spanish', async () => {
    fakeServer({ 'GET /api/v1/auth/session': { body: SESSION_OK }, 'GET /api/v1/linkedin/status': { body: linkedin() } });
    renderAt('/ajustes?linkedin=error&motivo=scope', routes);
    const alert = await within(section()).findByRole('alert');
    expect(alert).toHaveTextContent('No se pudo conectar LinkedIn');
    expect(alert).toHaveTextContent('w_member_social');
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/ajustes$/);
  });

  it('maps every reason of the OAuth callback', () => {
    expect(Object.keys(LINKEDIN_REASONS).sort()).toEqual(['canje', 'code', 'denegado', 'permiso', 'scope', 'sesion', 'state']);
    const expected: Record<string, RegExp> = {
      sesion: /sesión/,
      permiso: /approve_actions/,
      state: /10 minutos/,
      denegado: /denegaste/,
      code: /código de autorización/,
      scope: /w_member_social/,
      canje: /canjear/,
    };
    for (const [reason, pattern] of Object.entries(expected)) {
      const message = linkedinReturnMessage('error', reason);
      expect(message?.ok).toBe(false);
      expect(message?.text).toMatch(pattern);
    }
    expect(linkedinReturnMessage('error', 'otro')?.text).toMatch(/motivo: otro/);
    expect(linkedinReturnMessage('error', null)?.title).toBe('No se pudo conectar LinkedIn');
    expect(linkedinReturnMessage('ok', null)).toMatchObject({ ok: true, title: 'LinkedIn conectado' });
    expect(linkedinReturnMessage(null, null)).toBeNull();
  });
});
