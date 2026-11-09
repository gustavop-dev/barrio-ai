import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AjustesConPush } from '../api/capturas';
import type { LinkedInStatus, Overview } from '../api/types';
import { installFakeMedia, removeFakeMedia } from '../capture/fakeMedia';
import { resetMicStateForTests } from '../capture/recorder';
import { overviewFixture } from '../test/app';
import { fakeServer, SESSION_OK, type Handler, type Reply } from '../test/fakeServer';
import { renderAt } from '../test/render';
import { Ajustes } from './Ajustes';
import { LINKEDIN_REASONS, linkedinReturnMessage } from './ajustes/linkedin';

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

const UNIPILE = {
  id: 'acc-1',
  label: 'LinkedIn Gustavo',
  provider: 'unipile',
  status: 'running',
  is_locked: false,
  paused: false,
  paused_reason: '',
  last_checked_at: new Date(Date.now() - 4 * 60_000).toISOString(),
  capacity: {
    'INT-03': { daily: 3, weekly: 12, daily_used: 1, weekly_used: 4, left: 2 },
    'INT-02': { daily: 20, weekly: 80, daily_used: 20, weekly_used: 30, left: 0 },
  },
};
const OFFICIAL = { ...UNIPILE, id: 'acc-li', label: 'LinkedIn oficial', provider: 'linkedin', capacity: {} };

const AJUSTES: AjustesConPush = {
  autonomy: { 'INT-03': 'auto', 'INT-02': 'auto', 'CONT-09': 'auto', 'RED-01': 'auto', 'RED-02': 'approval', 'RED-04': 'off' },
  lead: { enabled: true, capabilities: ['INT-03', 'CONT-09'], model: 'jev-1.14.0' },
  limits: { 'INT-03': { daily: 3, weekly: 12 } },
  window: { start: '07:00', end: '21:00', timezone: 'America/Bogota', open_now: true, min_spacing_seconds: 1200 },
  ai_spend: {
    today: [
      { budget: 'general', label: 'General (comentarios)', spent_usd: 1.2, limit_usd: 3 },
      { budget: 'editorial', label: 'Editorial', spent_usd: 1.6, limit_usd: 2 },
    ],
    month_usd: 61,
    total_usd: 98,
    limit_usd: 120,
    lead_month_usd: 0.01,
    transcription_month_usd: 0.4,
  },
  facts_count: 3,
  orientation: { text: 'Más ProjectApp este mes.', updated_at: '2026-11-06T10:00:00Z', updated_by: 'gustavo' },
  push_types: [
    { kind: 'piece_scheduled', label: 'Pieza lista', goes_to: 'notificaciones', default: true, enabled: true },
    { kind: 'piece_published', label: 'Pieza publicada', goes_to: 'notificaciones', default: true, enabled: true },
    { kind: 'question_new', label: 'Pregunta nueva', goes_to: 'tu_turno', default: true, enabled: false },
  ],
};

const RED = {
  enabled: true,
  stages: {},
  capacity: { 'RED-01': { daily: 15, weekly: 60, daily_used: 13, weekly_used: 20, left: 2, mode: 'auto' } },
  reads_today: { comments: 4, search: 1, profile: 7, execution: 6 },
  read_caps: { comments: 60, search: 20, profile: 30 },
  llm: { spent_today: 0.04, daily: 0.3, model: 'x' },
  invites_blocked: { blocked: false, reason: '' },
  last_discovery_at: null,
  last_sync_at: null,
};

function server(
  { overview = overviewFixture({ accounts: [UNIPILE, OFFICIAL] }), status = CONNECTED, ajustes = AJUSTES }: { overview?: Overview; status?: LinkedInStatus; ajustes?: AjustesConPush } = {},
  extra: Record<string, Handler | Reply> = {},
) {
  return fakeServer({
    'GET /api/v1/auth/session': { body: SESSION_OK },
    'GET /api/v1/operador/overview': { body: overview },
    'GET /api/v1/ajustes': { body: ajustes },
    'GET /api/v1/red/summary': { body: RED },
    'GET /api/v1/linkedin/status': { body: status },
    'GET /api/v1/orientacion': { body: AJUSTES.orientation },
    'GET /api/v1/ajustes/preferencias': { body: { gallery_ai_edit: 'auto', updated_at: null } },
    ...extra,
  });
}

const routes = [
  { path: '/ajustes', element: <Ajustes /> },
  { path: '/login', element: <p>Pantalla de login</p> },
  { path: '/tu-turno/sabe', element: <p>Lo que sabe</p> },
];

const region = (name: string | RegExp) => screen.getByRole('region', { name });

beforeEach(() => resetMicStateForTests('granted'));
afterEach(() => {
  Reflect.deleteProperty(navigator, 'userAgent');
  Reflect.deleteProperty(navigator, 'serviceWorker');
  removeFakeMedia();
});

describe('Ajustes · estructura', () => {
  it('lists every section in the desktop sub-index, with anchors', async () => {
    server();
    renderAt('/ajustes', routes);
    expect(screen.getByRole('heading', { name: 'Ajustes', level: 1 })).toBeInTheDocument();
    const index = screen.getByRole('navigation', { name: 'Secciones de Ajustes' });
    expect(within(index).getAllByRole('link').map((a) => a.getAttribute('href'))).toEqual([
      '/ajustes#maquina',
      '/ajustes#orientacion',
      '/ajustes#autonomia',
      '/ajustes#gasto',
      '/ajustes#linkedin',
      '/ajustes#captura',
      '/ajustes#notificaciones',
      '/ajustes#sabe',
      '/ajustes#sesion',
    ]);
    for (const id of ['maquina', 'orientacion', 'autonomia', 'gasto', 'linkedin', 'captura', 'notificaciones', 'sabe', 'sesion']) {
      expect(document.getElementById(id)).not.toBeNull();
    }
  });
});

describe('Ajustes · Máquina', () => {
  it('stops the whole machine with a mandatory reason', async () => {
    const api = server(undefined, {
      'POST /api/v1/operador/control': (request) => ({
        body: { paused: true, reason: (request.body as { reason: string }).reason, source: 'db', updated_at: new Date().toISOString(), updated_by: 'gustavo' },
      }),
    });
    const user = userEvent.setup();
    renderAt('/ajustes', routes);
    const machine = await screen.findByRole('region', { name: 'Máquina' });
    expect(await within(machine).findByText('En marcha')).toBeInTheDocument();
    expect(within(machine).getByText('La máquina está en marcha. Observa, redacta y actúa dentro de los topes.')).toBeInTheDocument();
    await user.click(within(machine).getByRole('button', { name: 'Parada total' }));

    const modal = screen.getByRole('dialog', { name: 'Parada total' });
    const confirm = within(modal).getByRole('button', { name: 'Detener la máquina' });
    expect(confirm).toBeDisabled();
    await user.type(within(modal).getByLabelText(/Motivo/), 'Reviso los topes');
    await user.click(confirm);

    expect(await screen.findByText('Máquina detenida.')).toBeInTheDocument();
    expect(api.find('POST', '/api/v1/operador/control')[0]?.body).toEqual({ paused: true, reason: 'Reviso los topes' });
    expect(within(machine).getByText('Detenida')).toBeInTheDocument();
    expect(within(machine).getByText('Motivo: Reviso los topes.')).toBeInTheDocument();
    expect(within(machine).getByText('Desde la app')).toBeInTheDocument();
  });

  it('resumes a machine stopped from the app', async () => {
    const api = server(
      { overview: overviewFixture({ control: { paused: true, reason: 'Revisando', source: 'db', updated_at: new Date().toISOString(), updated_by: 'gustavo' } }) },
      { 'POST /api/v1/operador/control': { body: { paused: false, reason: '', source: 'none', updated_at: null, updated_by: null } } },
    );
    const user = userEvent.setup();
    renderAt('/ajustes', routes);
    const machine = await screen.findByRole('region', { name: 'Máquina' });
    expect(await within(machine).findByText('gustavo')).toBeInTheDocument();
    await user.click(within(machine).getByRole('button', { name: 'Reanudar' }));
    await user.click(within(screen.getByRole('dialog', { name: '¿Reanudar la máquina?' })).getByRole('button', { name: 'Reanudar' }));
    expect(await screen.findByText('Máquina en marcha.')).toBeInTheDocument();
    expect(api.find('POST', '/api/v1/operador/control')[0]?.body).toEqual({ paused: false, reason: '' });
  });

  it('cannot resume a stop that comes from the server', async () => {
    server({ overview: overviewFixture({ control: { paused: true, reason: 'Revisión del despliegue', source: 'env', updated_at: null, updated_by: null } }) });
    renderAt('/ajustes', routes);
    const machine = await screen.findByRole('region', { name: 'Máquina' });
    expect(await within(machine).findByText('Desde el servidor')).toBeInTheDocument();
    expect(within(machine).getByRole('button', { name: 'Reanudar' })).toBeDisabled();
    expect(within(machine).getByText(/OPERATOR_PAUSED=true/)).toBeInTheDocument();
  });

  it('pauses only the Unipile account, with a reason, and leaves the official one out', async () => {
    const api = server(undefined, { 'POST /api/v1/operador/accounts/acc-1/pause': { body: { ...UNIPILE, paused: true } } });
    const user = userEvent.setup();
    renderAt('/ajustes', routes);
    const machine = await screen.findByRole('region', { name: 'Máquina' });
    expect(await within(machine).findByText('LinkedIn Gustavo (Unipile)')).toBeInTheDocument();
    expect(within(machine).getByText('Conectada')).toBeInTheDocument();
    expect(within(machine).getByText('Comprobada hace 4 min')).toBeInTheDocument();
    expect(within(machine).queryByText(/LinkedIn oficial/)).not.toBeInTheDocument();
    await user.click(within(machine).getByRole('button', { name: 'Pausar solo esta cuenta' }));
    const modal = screen.getByRole('dialog', { name: '¿Pausar solo esta cuenta?' });
    await user.type(within(modal).getByLabelText(/Motivo/), 'LinkedIn avisó de actividad rara');
    await user.click(within(modal).getByRole('button', { name: 'Pausar la cuenta' }));
    expect(await screen.findByText('Cuenta en pausa.')).toBeInTheDocument();
    expect(api.find('POST', '/api/v1/operador/accounts/acc-1/pause')[0]?.body).toEqual({ paused: true, reason: 'LinkedIn avisó de actividad rara' });
  });
});

describe('Ajustes · Orientación para el equipo', () => {
  it('edits and saves the orientation', async () => {
    const api = server(undefined, { 'PUT /api/v1/orientacion': (request) => ({ body: { ...AJUSTES.orientation, ...(request.body as object) } }) });
    const user = userEvent.setup();
    renderAt('/ajustes', routes);
    const section = await screen.findByRole('region', { name: 'Orientación para el equipo' });
    const field = await within(section).findByLabelText('Qué quieres que el equipo tenga en cuenta ahora');
    expect(field).toHaveValue('Más ProjectApp este mes.');
    expect(within(section).getByText(/por gustavo\.$/)).toBeInTheDocument();
    const save = within(section).getByRole('button', { name: 'Guardar orientación' });
    expect(save).toBeDisabled();
    await user.type(field, ' Nada de rondas.');
    await user.click(save);
    expect(await screen.findByText(/Orientación guardada/)).toBeInTheDocument();
    expect(api.find('PUT', '/api/v1/orientacion')[0]?.body).toEqual({ text: 'Más ProjectApp este mes. Nada de rondas.' });
  });
});

describe('Ajustes · Autonomía y límites', () => {
  it('is folded, and opens with #autonomia to show modes, lead, window, caps and reads', async () => {
    server();
    renderAt('/ajustes#autonomia', routes);
    const section = screen.getByRole('region', { name: 'Autonomía y límites' });
    expect(section.querySelector('details')).toHaveAttribute('open');
    expect(await within(section).findByText('Modo por capacidad · solo lectura')).toBeInTheDocument();
    const modes = within(section).getByText('Invitar sin nota').closest('.aj-mode') as HTMLElement;
    expect(within(modes).getByText('Aprobación')).toBeInTheDocument();
    expect(within(within(section).getByText('Aceptar invitaciones').closest('.aj-mode') as HTMLElement).getByText('Apagado')).toBeInTheDocument();
    expect(within(section).getByText('Activo')).toBeInTheDocument();
    expect(within(section).getByText('Comentarios, Publicación diaria')).toBeInTheDocument();
    expect(within(section).getByText('07:00–21:00 · America/Bogota')).toBeInTheDocument();
    expect(within(section).getByText('Abierta')).toBeInTheDocument();
    expect(within(section).getByText('20 min entre acciones')).toBeInTheDocument();
    const read = (group: string) =>
      within(within(section).getByRole('group', { name: group }))
        .getAllByRole('meter')
        .map((m) => `${m.getAttribute('aria-label')}: ${m.getAttribute('aria-valuetext')}`);
    expect(read('Topes de hoy')).toEqual(['Comentarios: 1 de 3', 'Reacciones: 20 de 20', 'Seguir: 13 de 15']);
    expect(read('Topes de la semana')).toEqual(['Comentarios: 4 de 12', 'Reacciones: 30 de 80', 'Seguir: 20 de 60']);
    expect(read('Lecturas de la red')).toEqual(['Comentarios leídos: 4 de 60', 'Búsquedas: 1 de 20', 'Perfiles: 7 de 30']);
    expect(within(within(section).getByRole('group', { name: 'Lecturas de la red' })).getByText('6 hoy · sin tope: ninguna escritura sale sin ellas')).toBeInTheDocument();
    expect(within(within(section).getByRole('group', { name: 'Topes de hoy' })).getByRole('meter', { name: 'Reacciones' })).toHaveClass('bad');
  });

  it('starts folded without the anchor', async () => {
    server();
    renderAt('/ajustes', routes);
    expect(screen.getByRole('region', { name: 'Autonomía y límites' }).querySelector('details')).not.toHaveAttribute('open');
  });
});

describe('Ajustes · Gasto de IA', () => {
  it('shows a line per budget and the month, the total and the extras', async () => {
    server();
    renderAt('/ajustes', routes);
    const section = await screen.findByRole('region', { name: 'Gasto de IA · hoy' });
    const general = await within(section).findByRole('meter', { name: 'General (comentarios)' });
    expect(general).toHaveAttribute('aria-valuetext', '1,20 USD de 3,00 USD');
    expect(within(section).getByRole('meter', { name: 'Editorial' })).toHaveClass('warn');
    expect(within(section).getByText('61,00 USD de 120,00 USD')).toBeInTheDocument();
    expect(within(section).getByText('98,00 USD')).toBeInTheDocument();
    expect(within(section).getByText('Transcripción de audios, este mes')).toBeInTheDocument();
  });

  it('says «Aún no disponible» when the settings endpoint does not exist yet', async () => {
    server(undefined, { 'GET /api/v1/ajustes': { status: 404, body: { detail: 'No encontrado.' } } });
    renderAt('/ajustes', routes);
    const section = screen.getByRole('region', { name: 'Gasto de IA · hoy' });
    expect(await within(section).findByText('Aún no disponible')).toBeInTheDocument();
  });
});

describe('Ajustes · LinkedIn oficial', () => {
  const section = () => region('LinkedIn oficial · publicación');

  it('shows the member, the expiry and offers to reconnect with a full navigation', async () => {
    const api = server();
    renderAt('/ajustes', routes);
    expect(await within(section()).findByText('Conectado')).toBeInTheDocument();
    expect(within(section()).getByText('urn:li:person:782bbtaQ')).toBeInTheDocument();
    expect(within(section()).getByText(/quedan 59 días/)).toBeInTheDocument();
    expect(within(section()).getByText('openid, profile, w_member_social')).toBeInTheDocument();
    expect(within(section()).getByText('202610')).toBeInTheDocument();
    const link = within(section()).getByRole('link', { name: 'Reconectar LinkedIn' });
    expect(link).toHaveAttribute('href', '/api/v1/linkedin/oauth/start');
    expect(link).not.toHaveAttribute('target');
    expect(JSON.stringify(api.requests.map((r) => r.path))).not.toMatch(/oauth/);
  });

  it('warns when the permission expires soon and when it expired', async () => {
    server({ status: { ...CONNECTED, days_left: 3, expiring_soon: true } });
    renderAt('/ajustes', routes);
    expect(await within(section()).findByText('Caduca pronto')).toBeInTheDocument();
    expect(within(section()).getByText(/quedan 3 días\)\. LinkedIn no deja renovarlo solo/)).toBeInTheDocument();
  });

  it('explains an expired token, a paused account and the live switch off', async () => {
    server({ status: { ...CONNECTED, connected: false, expired: true, days_left: 0, live: false, account: { id: 'acc-li', paused: true, paused_reason: 'x' } } });
    renderAt('/ajustes', routes);
    expect(await within(section()).findByText('Caducado')).toBeInTheDocument();
    expect(within(section()).getByText(/El permiso caducó/)).toBeInTheDocument();
    expect(within(section()).getByText(/LIVE_LINKEDIN_OFFICIAL=false/)).toBeInTheDocument();
  });

  it('cannot connect without the app configured or without permission', async () => {
    server({ status: linkedin({ configured: false }) });
    renderAt('/ajustes', routes);
    expect(await within(section()).findByText('Sin conectar')).toBeInTheDocument();
    expect(within(section()).getByText(/LINKEDIN_CLIENT_ID/)).toBeInTheDocument();
    expect(within(section()).queryByRole('link', { name: 'Conectar LinkedIn' })).not.toBeInTheDocument();
  });

  it('shows the OAuth return message once and cleans the URL', async () => {
    server();
    const user = userEvent.setup();
    renderAt('/ajustes?linkedin=error&motivo=scope', routes);
    expect(await screen.findByText('No se pudo conectar LinkedIn')).toBeInTheDocument();
    expect(screen.getByText(LINKEDIN_REASONS.scope!)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/ajustes'));
    await user.click(screen.getByRole('button', { name: 'Entendido' }));
    expect(screen.queryByText('No se pudo conectar LinkedIn')).not.toBeInTheDocument();
  });

  it('has a message for each of the 7 reasons', () => {
    expect(Object.keys(LINKEDIN_REASONS).sort()).toEqual(['canje', 'code', 'denegado', 'permiso', 'scope', 'sesion', 'state']);
    for (const reason of Object.keys(LINKEDIN_REASONS)) {
      expect(linkedinReturnMessage('error', reason)).toMatchObject({ ok: false, text: LINKEDIN_REASONS[reason] });
    }
    expect(linkedinReturnMessage('error', 'otro')?.text).toMatch(/motivo: otro/);
    expect(linkedinReturnMessage('ok', null)).toMatchObject({ ok: true, title: 'LinkedIn conectado' });
    expect(linkedinReturnMessage(null, null)).toBeNull();
  });
});

describe('Ajustes · Notificaciones', () => {
  const section = () => region('Notificaciones en este dispositivo');

  it('tells iPhone users to add the app to the home screen first', async () => {
    Object.defineProperty(navigator, 'userAgent', { configurable: true, value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Safari/604.1' });
    server();
    renderAt('/ajustes', routes);
    expect(within(section()).getByText(/Añadir a pantalla de inicio/)).toBeInTheDocument();
    expect(within(section()).getByText('Instala la app')).toBeInTheDocument();
    expect(within(section()).queryByRole('button', { name: 'Activar notificaciones' })).not.toBeInTheDocument();
  });

  it('offers to enable push where it is supported', async () => {
    const registration = { pushManager: { getSubscription: vi.fn(async () => null), subscribe: vi.fn() } };
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: { ready: Promise.resolve(registration) } });
    vi.stubGlobal('PushManager', function PushManager() {});
    vi.stubGlobal('Notification', Object.assign(function Notification() {}, { permission: 'default', requestPermission: vi.fn() }));
    server();
    renderAt('/ajustes', routes);
    expect(await within(section()).findByText('Desactivadas')).toBeInTheDocument();
    expect(within(section()).getByRole('button', { name: 'Activar notificaciones' })).toBeEnabled();
  });

  it('tests and disables an active subscription, with a confirmation', async () => {
    const unsubscribe = vi.fn(async () => true);
    const subscription = { endpoint: 'https://push.example/1', unsubscribe, options: {} };
    const registration = { pushManager: { getSubscription: vi.fn(async () => subscription), subscribe: vi.fn() } };
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: { ready: Promise.resolve(registration) } });
    vi.stubGlobal('PushManager', function PushManager() {});
    vi.stubGlobal('Notification', Object.assign(function Notification() {}, { permission: 'granted', requestPermission: vi.fn() }));
    const api = server(undefined, { 'POST /api/v1/push/test': { status: 202, body: {} }, 'POST /api/v1/push/unsubscribe': { status: 204 } });
    const user = userEvent.setup();
    renderAt('/ajustes', routes);
    expect(await within(section()).findByText('Activadas')).toBeInTheDocument();
    await user.click(within(section()).getByRole('button', { name: 'Probar notificación' }));
    expect(await screen.findByText(/Notificación de prueba enviada/)).toBeInTheDocument();
    expect(api.find('POST', '/api/v1/push/test')).toHaveLength(1);
    await user.click(within(section()).getByRole('button', { name: 'Desactivar' }));
    await user.click(within(screen.getByRole('dialog', { name: '¿Desactivar las notificaciones aquí?' })).getByRole('button', { name: 'Desactivar' }));
    expect(await screen.findByText('Notificaciones desactivadas en este dispositivo.')).toBeInTheDocument();
    expect(api.find('POST', '/api/v1/push/unsubscribe')[0]?.body).toEqual({ endpoint: 'https://push.example/1' });
    expect(unsubscribe).toHaveBeenCalled();
  });

  it('turns the push of one type off and saves every disabled type', async () => {
    const api = server(undefined, { 'PATCH /api/v1/ajustes/preferencias': { body: { gallery_ai_edit: 'auto', updated_at: null } } });
    const user = userEvent.setup();
    renderAt('/ajustes', routes);
    const published = await within(section()).findByRole('switch', { name: /Pieza publicada/ });
    expect(published).toBeChecked();
    expect(within(section()).getByRole('switch', { name: /Pregunta nueva/ })).not.toBeChecked();
    expect(within(section()).getByText('Va a Tu turno')).toBeInTheDocument();
    await user.click(published);
    expect(published).not.toBeChecked();
    await waitFor(() => expect(api.find('PATCH', '/api/v1/ajustes/preferencias')).toHaveLength(1));
    expect(api.find('PATCH', '/api/v1/ajustes/preferencias')[0]?.body).toEqual({ push_disabled: ['piece_published', 'question_new'], push_enabled: ['piece_scheduled'] });
  });
});

describe('Ajustes · Captura y galería', () => {
  const section = () => region('Captura y galería');

  it('shows the microphone permission and saves the AI-edit default', async () => {
    const api = server(undefined, { 'PATCH /api/v1/ajustes/preferencias': { body: { gallery_ai_edit: 'no', updated_at: null } } });
    const user = userEvent.setup();
    renderAt('/ajustes', routes);
    expect(within(section()).getByText('Permitido')).toBeInTheDocument();
    const toggle = within(section()).getByRole('radio', { name: 'No editar' });
    await waitFor(() => expect(toggle).toBeEnabled());
    expect(toggle).not.toBeChecked();
    await user.click(toggle);
    expect(await screen.findByText('Edición con IA guardada para las fotos nuevas.')).toBeInTheDocument();
    expect(api.find('PATCH', '/api/v1/ajustes/preferencias')[0]?.body).toEqual({ gallery_ai_edit: 'no' });
  });

  it('asks for the microphone when it was never asked', async () => {
    const { getUserMedia } = installFakeMedia();
    resetMicStateForTests('prompt');
    server();
    const user = userEvent.setup();
    renderAt('/ajustes', routes);
    expect(within(section()).getByText('Sin pedir')).toBeInTheDocument();
    await user.click(within(section()).getByRole('button', { name: 'Permitir el micrófono' }));
    expect(await within(section()).findByText('Permitido')).toBeInTheDocument();
    expect(getUserMedia).toHaveBeenCalled();
  });

  it('explains how to unblock a denied microphone', () => {
    resetMicStateForTests('denied');
    server();
    renderAt('/ajustes', routes);
    expect(within(section()).getByText('Bloqueado')).toBeInTheDocument();
    expect(within(section()).getByText('Para volver a permitirlo')).toBeInTheDocument();
  });
});

describe('Ajustes · lo demás', () => {
  it('links to what the team knows, with the count', async () => {
    server();
    renderAt('/ajustes', routes);
    const link = within(region('Lo que el equipo sabe de ti')).getByRole('link');
    expect(link).toHaveAttribute('href', '/tu-turno/sabe');
    expect(await within(link).findByText('3 datos confirmados')).toBeInTheDocument();
  });

  it('logs out and returns to the login screen; shows the version and the art credit', async () => {
    const api = server(undefined, { 'POST /api/v1/auth/logout': { status: 204 } });
    const user = userEvent.setup();
    renderAt('/ajustes', routes);
    const section = region('Sesión y Acerca de');
    expect(await within(section).findByText('Has entrado como gustavo.')).toBeInTheDocument();
    expect(within(section).getByText('oficina 0.1.0')).toBeInTheDocument();
    expect(within(section).getByRole('link', { name: /LimeZu en itch.io/ })).toHaveAttribute('href', 'https://limezu.itch.io/moderninteriors');
    await user.click(within(section).getByRole('button', { name: 'Cerrar sesión' }));
    expect(await screen.findByText('Pantalla de login')).toBeInTheDocument();
    expect(api.find('POST', '/api/v1/auth/logout')).toHaveLength(1);
  });
});
