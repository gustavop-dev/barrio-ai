// Ajustes: each section's main action (stop and resume, the account pause, saving the orientation,
// the push switches, «Probar notificación», revoking a device, the OAuth return refresh), the folded
// autonomy, the spend lines, the microphone, the Sabe link, logout, and the anchors of the links.
import type { AjustesConPush } from '@compartido/api/capturas';
import type { Account, LinkedInStatus, Overview } from '@compartido/api/types';
import { LINKEDIN_REASONS } from '@compartido/logic/linkedin';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import { router } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { AppState, Linking, ScrollView } from 'react-native';
import '@/api/transport';
import { saveToken } from '@/api/token';
import { audio, resetFakeAudio } from '@/test/fakeAudio';
import { renderApp } from '@/test/render';
import { fakeServer, type FakeHandler } from '@/test/server';
import { AjustesScreen } from './AjustesScreen';

jest.mock('expo-web-browser', () => ({ openBrowserAsync: jest.fn(async () => ({ type: 'opened' })) }));
// The version of app.json, as a build carries it (jest-expo leaves expoConfig empty).
jest.mock('expo-constants', () => {
  const actual = jest.requireActual('expo-constants').default;
  return { __esModule: true, default: { easConfig: actual.easConfig, expoConfig: { name: '0ff1ce', slug: 'oficina-0ff1ce', version: '0.1.0' } } };
});

const routerState = (jest.requireMock('expo-router') as { __state: { params: Record<string, string> } }).__state;
const mockedRouter = router as unknown as { setParams: jest.Mock };
const USER = { username: 'gustavo', is_superuser: true, permissions: [] };

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

const UNIPILE: Account = {
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
const OFFICIAL: Account = { ...UNIPILE, id: 'acc-li', label: 'LinkedIn oficial', provider: 'linkedin', capacity: {} };

function overview(control: Partial<Overview['control']> = {}): Overview {
  return {
    autopilot: { enabled: true, policy_version: 'v1' },
    control: { paused: false, reason: '', source: 'none', updated_at: null, updated_by: null, ...control },
    window: { start: '07:00', end: '21:00', timezone: 'America/Bogota', open_now: true, min_spacing_seconds: 1200 },
    accounts: [UNIPILE, OFFICIAL],
    today: { proposals: {}, llm_spent_usd: '0', llm_daily_cap_usd: '3', drafts: 0, drafts_daily_cap: 10 },
  } as unknown as Overview;
}

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
  devices: [],
  expo_push: { active: 1, last_success_at: null, last_error: null },
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
};

const DEVICES = [
  { id: 'd-este', name: 'Pixel de prueba', created_at: '2026-11-01T10:00:00Z', last_used_at: new Date().toISOString(), current: true, push: true },
  { id: 'd-otro', name: 'iPad de Gustavo', created_at: '2026-10-01T10:00:00Z', last_used_at: null, current: false, push: false },
];

function server(extra: Record<string, FakeHandler> = {}, { control = {}, status = CONNECTED }: { control?: Partial<Overview['control']>; status?: LinkedInStatus } = {}) {
  return fakeServer({
    'GET /api/v1/auth/session': { body: { authenticated: true, user: USER } },
    'GET /api/v1/operador/overview': { body: overview(control) },
    'GET /api/v1/ajustes': { body: AJUSTES },
    'GET /api/v1/red/summary': { body: RED },
    'GET /api/v1/linkedin/status': { body: status },
    'GET /api/v1/orientacion': { body: AJUSTES.orientation },
    'GET /api/v1/ajustes/preferencias': { body: { gallery_ai_edit_default: true, updated_at: null } },
    'GET /api/v1/auth/dispositivos': { body: DEVICES },
    ...extra,
  });
}

async function renderAjustes() {
  const result = await renderApp(<AjustesScreen />, { session: true, recorder: true });
  await screen.findByText('Has entrado como gustavo.');
  return result;
}

beforeEach(async () => {
  routerState.params = {};
  mockedRouter.setParams = jest.fn();
  resetFakeAudio();
  await saveToken('0ff1ce_dt_prueba');
});

describe('Ajustes · Máquina', () => {
  it('stops the whole machine with a mandatory reason', async () => {
    const api = server({ 'POST /api/v1/operador/control': { body: { paused: true, reason: 'Reviso los topes', source: 'db', updated_at: null, updated_by: 'gustavo' } } });
    await renderAjustes();
    expect(await screen.findByText('La máquina está en marcha. Observa, redacta y actúa dentro de los topes.')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Parada total' }));
    const sheet = await screen.findByTestId('confirm-sheet');
    expect(within(sheet).getByRole('button', { name: 'Detener la máquina' })).toBeDisabled();
    await fireEvent.changeText(within(sheet).getByTestId('confirm-note'), 'Reviso los topes');
    await fireEvent.press(within(sheet).getByRole('button', { name: 'Detener la máquina' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/operador/control')[0]?.body).toEqual({ paused: true, reason: 'Reviso los topes' }));
    expect(await screen.findByText('Máquina detenida.')).toBeOnTheScreen();
    expect(await screen.findByText('Motivo: Reviso los topes.')).toBeOnTheScreen();
  });

  it('resumes a machine stopped from the app, with an optional note', async () => {
    const api = server(
      { 'POST /api/v1/operador/control': { body: { paused: false, reason: '', source: 'db', updated_at: null, updated_by: null } } },
      { control: { paused: true, reason: 'Revisando los topes de la semana.', source: 'db', updated_by: 'gustavo', updated_at: new Date().toISOString() } },
    );
    await renderAjustes();
    expect(await screen.findByText('Motivo: Revisando los topes de la semana.')).toBeOnTheScreen();
    expect(screen.getByLabelText('Origen: Desde la app')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Reanudar' }));
    const sheet = await screen.findByTestId('confirm-sheet');
    await fireEvent.press(within(sheet).getByRole('button', { name: 'Reanudar' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/operador/control')[0]?.body).toEqual({ paused: false, reason: '' }));
    expect(await screen.findByText('Máquina en marcha.')).toBeOnTheScreen();
  });

  it('cannot resume a stop that comes from the server', async () => {
    server({}, { control: { paused: true, reason: 'revisión del despliegue', source: 'env' } });
    await renderAjustes();
    expect(await screen.findByLabelText('Origen: Desde el servidor')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Reanudar' })).toBeDisabled();
    expect(screen.getByText('La parada viene del servidor (OPERATOR_PAUSED=true). No se puede levantar desde la app.')).toBeOnTheScreen();
  });

  it('pauses only the Unipile account, with a reason, and leaves the official one out', async () => {
    const api = server({ 'POST /api/v1/operador/accounts/acc-1/pause': { body: { ...UNIPILE, paused: true } } });
    await renderAjustes();
    expect(await screen.findByText('LinkedIn Gustavo (Unipile)')).toBeOnTheScreen();
    expect(screen.queryByText('LinkedIn oficial (linkedin)')).toBeNull();
    await fireEvent.press(screen.getByRole('button', { name: 'Pausar solo esta cuenta: LinkedIn Gustavo' }));
    const sheet = await screen.findByTestId('confirm-sheet');
    await fireEvent.changeText(within(sheet).getByTestId('confirm-note'), 'Demasiadas invitaciones');
    await fireEvent.press(within(sheet).getByRole('button', { name: 'Pausar la cuenta' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/operador/accounts/acc-1/pause')[0]?.body).toEqual({ paused: true, reason: 'Demasiadas invitaciones' }));
    expect(await screen.findByText('Cuenta en pausa.')).toBeOnTheScreen();
  });
});

describe('Ajustes · Orientación, autonomía y gasto', () => {
  it('edits and saves the orientation, with the counter', async () => {
    const api = server({ 'PUT /api/v1/orientacion': { body: { text: 'Nada de rondas.', updated_at: new Date().toISOString(), updated_by: 'gustavo' } } });
    await renderAjustes();
    const field = await screen.findByTestId('orientacion-field');
    expect(screen.getByRole('button', { name: 'Guardar orientación' })).toBeDisabled();
    await fireEvent.changeText(field, '  Nada de rondas.  ');
    expect(screen.getByText('19 de 4000 caracteres. Es privada: orienta las decisiones y nunca aparece en un texto público.')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Guardar orientación' }));
    await waitFor(() => expect(api.find('PUT', '/api/v1/orientacion')[0]?.body).toEqual({ text: 'Nada de rondas.' }));
    expect(await screen.findByText('Orientación guardada. El equipo la usa desde su próxima tarea.')).toBeOnTheScreen();
  });

  it('refuses an orientation over 4000 characters', async () => {
    server();
    await renderAjustes();
    await fireEvent.changeText(await screen.findByTestId('orientacion-field'), 'x'.repeat(4001));
    expect(screen.getByText('4001 de 4000 caracteres. Es privada: orienta las decisiones y nunca aparece en un texto público.')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Guardar orientación' })).toBeDisabled();
  });

  it('keeps autonomy folded, and opens it to show modes, lead, window, caps and reads', async () => {
    server();
    await renderAjustes();
    expect(screen.queryByText('Modo por capacidad · solo lectura')).toBeNull();
    await fireEvent.press(screen.getByRole('button', { name: 'Autonomía y límites' }));
    expect(await screen.findByText('Modo por capacidad · solo lectura')).toBeOnTheScreen();
    expect(screen.getByText('Invitar sin nota')).toBeOnTheScreen();
    expect(screen.getByText('Aprobación')).toBeOnTheScreen();
    expect(screen.getByLabelText('Capacidades: Comentarios, Publicación diaria')).toBeOnTheScreen();
    expect(screen.getByLabelText('Horario: 07:00–21:00 · America/Bogota')).toBeOnTheScreen();
    expect(screen.getByLabelText('Espaciado mínimo: 20 min entre acciones')).toBeOnTheScreen();
    // The caps wait for the overview and the network summary.
    await screen.findByText('13 de 15');
    await screen.findByText('4 de 60');
    const today = within(screen.getByLabelText('Topes de hoy'));
    expect(today.getByText('1 de 3')).toBeOnTheScreen();
    expect(today.getByText('20 de 20')).toBeOnTheScreen();
    expect(today.getByText('13 de 15')).toBeOnTheScreen();
    expect(within(screen.getByLabelText('Topes de la semana')).getByText('4 de 12')).toBeOnTheScreen();
    const reads = within(screen.getByLabelText('Lecturas de la red'));
    expect(reads.getByText('4 de 60')).toBeOnTheScreen();
    expect(reads.getByLabelText('Comprobaciones antes y después de escribir: 6 hoy · sin tope: ninguna escritura sale sin ellas')).toBeOnTheScreen();
  });

  it('shows a line per budget, the month against its limit, the total, the lead agent and transcription', async () => {
    server();
    await renderAjustes();
    expect(await screen.findByText('1,20 USD de 3,00 USD')).toBeOnTheScreen();
    expect(screen.getByRole('progressbar', { name: 'General (comentarios)' })).toHaveAccessibilityValue({ min: 0, max: 3, now: 1.2, text: '1,20 USD de 3,00 USD' });
    expect(screen.getByText('1,60 USD de 2,00 USD')).toBeOnTheScreen();
    expect(screen.getByLabelText('Este mes: 61,00 USD de 120,00 USD')).toBeOnTheScreen();
    expect(screen.getByLabelText('Desde el inicio: 98,00 USD')).toBeOnTheScreen();
    expect(screen.getByLabelText('Agente líder, este mes: 0,01 USD')).toBeOnTheScreen();
    expect(screen.getByLabelText('Transcripción de audios, este mes: 0,40 USD')).toBeOnTheScreen();
  });

  it('says «Aún no disponible» when the settings endpoint does not exist yet', async () => {
    server({ 'GET /api/v1/ajustes': { status: 404, body: { detail: 'No encontrado' } } });
    await renderAjustes();
    expect(await screen.findByText('El gasto por presupuesto todavía no llega del servidor.')).toBeOnTheScreen();
  });
});

describe('Ajustes · LinkedIn oficial', () => {
  it('shows the member, the expiry and the scopes', async () => {
    server();
    await renderAjustes();
    expect(await screen.findByText('Conectado')).toBeOnTheScreen();
    expect(screen.getByLabelText('Miembro: Gustavo P · urn:li:person:782bbtaQ')).toBeOnTheScreen();
    expect(screen.getByLabelText('Permisos: openid, profile, w_member_social')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Reconectar LinkedIn' })).toBeOnTheScreen();
  });

  it('warns when the permission expires soon and when it expired', async () => {
    server({}, { status: linkedin({ ...CONNECTED, expired: true, connected: false, days_left: 0 }) });
    await renderAjustes();
    expect(await screen.findByText('Caducado')).toBeOnTheScreen();
    expect(screen.getByText('El permiso caducó y la publicación diaria está en pausa. Reconecta LinkedIn para reanudarla.')).toBeOnTheScreen();
  });

  it('cannot connect without the app configured', async () => {
    server({}, { status: linkedin({ configured: false }) });
    await renderAjustes();
    expect(await screen.findByText(/Falta configurar la app de LinkedIn en el servidor/)).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Conectar LinkedIn' })).toBeNull();
  });

  it('opens the office in the in-app browser and refreshes the status when Gustavo comes back connected', async () => {
    let status = linkedin();
    const api = server({ 'GET /api/v1/linkedin/status': () => ({ body: status }) });
    const listeners: ((state: string) => void)[] = [];
    jest.spyOn(AppState, 'addEventListener').mockImplementation((_type, listener) => {
      listeners.push(listener as (state: string) => void);
      return { remove: jest.fn() } as never;
    });
    await renderAjustes();
    await fireEvent.press(await screen.findByRole('button', { name: 'Conectar LinkedIn' }));
    expect(WebBrowser.openBrowserAsync).toHaveBeenCalledWith('https://office.projectapp.co/ajustes#linkedin', expect.anything());
    expect(await screen.findByText('Esperando a que vuelvas…')).toBeOnTheScreen();
    const before = api.find('GET', '/api/v1/linkedin/status').length;
    status = CONNECTED;
    await act(async () => listeners.forEach((listener) => listener('active')));
    await waitFor(() => expect(api.find('GET', '/api/v1/linkedin/status').length).toBeGreaterThan(before));
    expect(await screen.findByText('LinkedIn conectado')).toBeOnTheScreen();
    expect(screen.getByText('Conectado')).toBeOnTheScreen();
  });

  it('shows the return message of a /ajustes?linkedin=error&motivo=… link and has one for each of the 7 reasons', async () => {
    routerState.params = { linkedin: 'error', motivo: 'state' };
    server();
    await renderAjustes();
    expect(await screen.findByText('No se pudo conectar LinkedIn')).toBeOnTheScreen();
    expect(screen.getByText(LINKEDIN_REASONS.state!)).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Entendido' }));
    expect(screen.queryByText('No se pudo conectar LinkedIn')).toBeNull();
    expect(mockedRouter.setParams).toHaveBeenCalledWith({ linkedin: undefined, motivo: undefined });
    expect(Object.keys(LINKEDIN_REASONS).sort()).toEqual(['canje', 'code', 'denegado', 'permiso', 'scope', 'sesion', 'state']);
  });
});

describe('Ajustes · Captura y galería', () => {
  it('shows the microphone permission and saves the AI-edit default', async () => {
    const api = server({ 'PATCH /api/v1/ajustes/preferencias': { body: { gallery_ai_edit_default: false, updated_at: null } } });
    await renderAjustes();
    expect(await screen.findByText('Permitido')).toBeOnTheScreen();
    const ai = screen.getByRole('switch', { name: 'El equipo puede editar mis fotos con IA' });
    await waitFor(() => expect(ai).toBeEnabled());
    await fireEvent.press(ai);
    await waitFor(() => expect(api.find('PATCH', '/api/v1/ajustes/preferencias')[0]?.body).toEqual({ gallery_ai_edit_default: false }));
    expect(await screen.findByText('Las fotos nuevas no se editarán con IA.')).toBeOnTheScreen();
  });

  it('asks for the microphone when it was never asked, and opens the phone settings when it is blocked', async () => {
    audio.permission = { granted: false, canAskAgain: true, status: 'undetermined' };
    server();
    await renderAjustes();
    expect(await screen.findByText('Sin pedir')).toBeOnTheScreen();
    audio.permission = { granted: false, canAskAgain: false, status: 'denied' };
    await fireEvent.press(screen.getByRole('button', { name: 'Permitir el micrófono' }));
    expect(await screen.findByText('Bloqueado')).toBeOnTheScreen();
    expect(audio.requested).toBe(1);
    const openSettings = jest.spyOn(Linking, 'openSettings').mockResolvedValue(undefined);
    await fireEvent.press(screen.getByRole('button', { name: 'Abrir los ajustes del teléfono' }));
    expect(openSettings).toHaveBeenCalled();
  });
});

describe('Ajustes · Notificaciones', () => {
  it('sends a test notification', async () => {
    const api = server({ 'POST /api/v1/push/test': { status: 202, body: { sent: 2 } } });
    await renderAjustes();
    await fireEvent.press(screen.getByRole('button', { name: 'Probar notificación' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/push/test')).toHaveLength(1));
    expect(await screen.findByText('Notificación de prueba enviada. Debería llegar en unos segundos.')).toBeOnTheScreen();
    expect(await screen.findByLabelText('Teléfonos que reciben avisos: 1')).toBeOnTheScreen();
  });

  it('turns the push of one type off and saves every disabled type', async () => {
    const api = server({ 'PATCH /api/v1/ajustes/preferencias': { body: { gallery_ai_edit_default: true, updated_at: null } } });
    await renderAjustes();
    await fireEvent.press(screen.getByRole('button', { name: 'Por tipo de notificación' }));
    const published = await screen.findByRole('switch', { name: 'Pieza publicada' });
    expect(published).toBeChecked();
    expect(screen.getByRole('switch', { name: 'Pregunta nueva' })).not.toBeChecked();
    await fireEvent.press(published);
    await waitFor(() =>
      expect(api.find('PATCH', '/api/v1/ajustes/preferencias')[0]?.body).toEqual({ push_disabled: ['piece_published', 'question_new'], push_enabled: ['piece_scheduled'] }),
    );
    expect(await screen.findByText('Push apagada: Pieza publicada.')).toBeOnTheScreen();
  });

  it('turns on the push of a type that is off and saves it as enabled, so the server keeps it', async () => {
    const api = server({ 'PATCH /api/v1/ajustes/preferencias': { body: { gallery_ai_edit_default: true, updated_at: null } } });
    await renderAjustes();
    await fireEvent.press(screen.getByRole('button', { name: 'Por tipo de notificación' }));
    await fireEvent.press(await screen.findByRole('switch', { name: 'Pregunta nueva' }));
    await waitFor(() =>
      expect(api.find('PATCH', '/api/v1/ajustes/preferencias')[0]?.body).toEqual({ push_disabled: [], push_enabled: ['piece_scheduled', 'piece_published', 'question_new'] }),
    );
    expect(await screen.findByText('Push activada: Pregunta nueva.')).toBeOnTheScreen();
  });

  it('turns a switch back when saving fails', async () => {
    server({ 'PATCH /api/v1/ajustes/preferencias': { status: 500, body: { detail: 'Fallo del servidor' } } });
    await renderAjustes();
    await fireEvent.press(screen.getByRole('button', { name: 'Por tipo de notificación' }));
    await fireEvent.press(await screen.findByRole('switch', { name: 'Pieza lista' }));
    expect(await screen.findByText('Fallo del servidor')).toBeOnTheScreen();
    await waitFor(() => expect(screen.getByRole('switch', { name: 'Pieza lista' })).toBeChecked());
  });

  it('revokes another device after confirming', async () => {
    const api = server({ 'DELETE /api/v1/auth/dispositivos/d-otro': { status: 204 } });
    await renderAjustes();
    await fireEvent.press(await screen.findByRole('button', { name: 'Cerrar la sesión de iPad de Gustavo' }));
    const sheet = await screen.findByTestId('confirm-sheet');
    await fireEvent.press(within(sheet).getByRole('button', { name: 'Cerrar su sesión' }));
    await waitFor(() => expect(api.find('DELETE', '/api/v1/auth/dispositivos/d-otro')).toHaveLength(1));
    expect(await screen.findByText('Sesión cerrada en iPad de Gustavo.')).toBeOnTheScreen();
  });

  it('revoking this phone signs it out', async () => {
    const api = server({ 'POST /api/v1/auth/token/revocar': { status: 204 } });
    await renderAjustes();
    await fireEvent.press(await screen.findByRole('button', { name: 'Cerrar la sesión de este teléfono' }));
    const sheet = await screen.findByTestId('confirm-sheet');
    await fireEvent.press(within(sheet).getByRole('button', { name: 'Cerrar sesión' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/auth/token/revocar')).toHaveLength(1));
    expect(api.find('DELETE', '/api/v1/auth/dispositivos/d-este')).toHaveLength(0);
  });
});

describe('Ajustes · Sabe y sesión', () => {
  it('links to what the team knows, with the count', async () => {
    server();
    await renderAjustes();
    expect(await screen.findByText('3 datos confirmados')).toBeOnTheScreen();
    await fireEvent.press(screen.getByTestId('sabe-link'));
    expect(router.navigate).toHaveBeenCalledWith({ pathname: '/tu-turno', params: { tab: 'sabe' } });
  });

  it('logs out after confirming, and shows the version and the art credit', async () => {
    const api = server({ 'POST /api/v1/auth/token/revocar': { status: 204 } });
    await renderAjustes();
    expect(screen.getByLabelText('Versión: app 0.1.0')).toBeOnTheScreen();
    const openURL = jest.spyOn(Linking, 'openURL').mockResolvedValue(undefined);
    await fireEvent.press(screen.getByRole('link', { name: 'LimeZu en itch.io' }));
    expect(openURL).toHaveBeenCalledWith('https://limezu.itch.io/moderninteriors');
    await fireEvent.press(screen.getByTestId('logout'));
    await fireEvent.press(within(await screen.findByTestId('confirm-sheet')).getByRole('button', { name: 'Cerrar sesión' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/auth/token/revocar')).toHaveLength(1));
  });
});

describe('Ajustes · anchors', () => {
  function layout(id: string, y: number) {
    fireEvent(screen.getByTestId(`ajustes-${id}`), 'layout', { nativeEvent: { layout: { x: 0, y, width: 390, height: 200 } } });
  }

  it('scrolls to #notificaciones, following it while the sections above grow', async () => {
    routerState.params = { ancla: 'notificaciones' };
    const scrollTo = jest.spyOn(ScrollView.prototype as unknown as { scrollTo: () => void }, 'scrollTo').mockImplementation(() => undefined);
    server();
    await renderAjustes();
    await act(async () => layout('notificaciones', 1400));
    expect(scrollTo).toHaveBeenLastCalledWith({ y: 1388, animated: true });
    await act(async () => layout('notificaciones', 1900));
    expect(scrollTo).toHaveBeenLastCalledWith({ y: 1888, animated: true });
    // Once Gustavo scrolls by himself, the anchor lets go.
    await fireEvent(screen.getByTestId('screen-ajustes'), 'scrollBeginDrag');
    await act(async () => layout('notificaciones', 2100));
    expect(scrollTo).toHaveBeenCalledTimes(2);
  });

  it('opens Autonomía y límites with #autonomia and scrolls to it', async () => {
    routerState.params = { ancla: 'autonomia' };
    const scrollTo = jest.spyOn(ScrollView.prototype as unknown as { scrollTo: () => void }, 'scrollTo').mockImplementation(() => undefined);
    server();
    await renderAjustes();
    expect(await screen.findByText('Modo por capacidad · solo lectura')).toBeOnTheScreen();
    await act(async () => layout('autonomia', 900));
    expect(scrollTo).toHaveBeenLastCalledWith({ y: 888, animated: true });
  });

  it('scrolls to #maquina (the pause banner’s link)', async () => {
    routerState.params = { ancla: 'maquina' };
    const scrollTo = jest.spyOn(ScrollView.prototype as unknown as { scrollTo: () => void }, 'scrollTo').mockImplementation(() => undefined);
    server();
    await renderAjustes();
    await act(async () => layout('maquina', 60));
    expect(scrollTo).toHaveBeenLastCalledWith({ y: 48, animated: true });
  });
});
