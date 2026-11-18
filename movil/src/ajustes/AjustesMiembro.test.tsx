// Ajustes › Mi perfil, Mi voz and Organización (organizaciones, phase 7), on the app: what each member sees and edits of
// herself, what only the admin sees, the notice of a member in onboarding and the #perfil / #voz anchors.
import type { MiPerfil, MiVoz, Yo } from '@compartido/api/types';
import { organizacionFixture, perfilFixture, vozConfirmadaFixture, vozConPropuestaFixture, vozFixture, yoAltaFixture, yoFixture } from '@compartido/fixtures/miembro';
import { ALTA_NOTICE } from '@compartido/logic/miembro';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import { ScrollView } from 'react-native';
import '@/api/transport';
import { saveToken } from '@/api/token';
import { renderApp } from '@/test/render';
import { fakeServer, type FakeHandler } from '@/test/server';
import { AjustesScreen } from './AjustesScreen';

jest.mock('expo-web-browser', () => ({ openBrowserAsync: jest.fn(async () => ({ type: 'opened' })) }));
jest.mock('expo-constants', () => {
  const actual = jest.requireActual('expo-constants').default;
  return { __esModule: true, default: { easConfig: actual.easConfig, expoConfig: { name: '0ff1ce', slug: 'oficina-0ff1ce', version: '0.1.0' } } };
});

const routerState = (jest.requireMock('expo-router') as { __state: { params: Record<string, string> } }).__state;
const USER = { username: 'ana', is_superuser: false, permissions: [] };
const MEMBER: Yo = yoFixture({ username: 'ana', is_admin: false }, { id: 'm-2', display_name: 'Ana Pérez', role: 'CTO', is_admin: false, first: false });

function server({ yo = MEMBER, perfil = perfilFixture(), voz = vozFixture() }: { yo?: Yo; perfil?: MiPerfil; voz?: MiVoz } = {}, extra: Record<string, FakeHandler> = {}) {
  return fakeServer({
    'GET /api/v1/auth/session': { body: { authenticated: true, user: USER } },
    'GET /api/v1/yo': { body: yo },
    'GET /api/v1/yo/perfil': { body: perfil },
    'GET /api/v1/yo/voz': { body: voz },
    'GET /api/v1/organizacion': { body: organizacionFixture() },
    ...extra,
  });
}

const render = () => renderApp(<AjustesScreen />, { session: true, recorder: true });
const perfilSection = () => screen.findByTestId('ajustes-mi-perfil');
const vozSection = () => screen.findByTestId('ajustes-mi-voz');

beforeEach(async () => {
  routerState.params = {};
  await saveToken('0ff1ce_dt_prueba');
});

describe('Ajustes · Mi perfil', () => {
  it('shows her profile with its help; saving is off until something changes', async () => {
    server();
    await render();
    const section = await perfilSection();
    expect(await within(section).findByTestId('perfil-identity')).toHaveDisplayValue('Construyo producto con equipos pequeños.');
    expect(within(section).getByTestId('perfil-name')).toHaveDisplayValue('Ana Pérez');
    expect(within(section).getByText('Cómo se presenta: una o dos frases. · 40 / 600')).toBeOnTheScreen();
    expect(within(section).getByRole('switch', { name: 'Te aplica el trabajo personal en startups' })).not.toBeChecked();
    expect(within(section).getByTestId('perfil-guardar')).toBeDisabled();
    expect(screen.getByTestId('ajustes-perfil')).toBeOnTheScreen();
    expect(screen.getByTestId('ajustes-voz')).toBeOnTheScreen();
  });

  it('sends only what changed and says «Guardado.»; the history lists who changed what', async () => {
    // The server keeps what was saved: the refetch after saving reads it back.
    let current = perfilFixture();
    const api = server(undefined, {
      'GET /api/v1/yo/perfil': () => ({ body: current }),
      'PATCH /api/v1/yo/perfil': (request) => {
        current = {
          ...current,
          profile: { ...current.profile, ...(request.body as object) },
          history: [{ number: 3, created_at: '2026-11-18T17:00:00Z', by: 'ana', source: 'app', changed: ['identity', 'personal_startups'] }, ...current.history],
        };
        return { body: { ...current, saved: true } };
      },
    });
    await render();
    const section = await perfilSection();
    await fireEvent.changeText(await within(section).findByTestId('perfil-identity'), '  Lidero la tecnología de ProjectApp.  ');
    await fireEvent.press(within(section).getByRole('switch', { name: 'Te aplica el trabajo personal en startups' }));
    await fireEvent.press(within(section).getByTestId('perfil-guardar'));
    await waitFor(() => expect(api.find('PATCH', '/api/v1/yo/perfil')).toHaveLength(1));
    expect(api.find('PATCH', '/api/v1/yo/perfil')[0]?.body).toEqual({ identity: 'Lidero la tecnología de ProjectApp.', personal_startups: true });
    expect(await within(section).findByTestId('perfil-estado')).toHaveTextContent('Guardado.');
    await fireEvent.press(within(section).getByText('Historial (3)'));
    expect(within(section).getByTestId('perfil-revision-3')).toHaveTextContent(/^#3 · .* · ana · desde la app · cambió: Cómo te presentas, Te aplica el trabajo personal en startups$/);
    expect(within(section).getByTestId('perfil-revision-1')).toHaveTextContent(/#1 · .* · gustavo · en el alta/);
    expect(within(section).getByTestId('perfil-guardar')).toBeDisabled();
  });

  it('says «Sin cambios» when the server had those values already', async () => {
    server(undefined, { 'PATCH /api/v1/yo/perfil': { body: { ...perfilFixture(), saved: false } } });
    await render();
    const section = await perfilSection();
    await fireEvent.changeText(await within(section).findByTestId('perfil-role'), 'CTO y cofundadora');
    await fireEvent.press(within(section).getByTestId('perfil-guardar'));
    expect(await within(section).findByTestId('perfil-estado')).toHaveTextContent('Sin cambios: ya tenías esos valores.');
  });

  it('checks the limits before sending and shows the server’s reason when it refuses', async () => {
    const api = server(undefined, { 'PATCH /api/v1/yo/perfil': { status: 400, body: { detail: 'company_relation: como mucho 300 caracteres.' } } });
    await render();
    const section = await perfilSection();
    await fireEvent.changeText(await within(section).findByTestId('perfil-name'), 'Ana 2');
    expect(within(section).getByText('Solo letras, espacios, apóstrofo o guion.')).toBeOnTheScreen();
    expect(within(section).getByTestId('perfil-guardar')).toBeDisabled();
    await fireEvent.changeText(within(section).getByTestId('perfil-limits'), '   ');
    expect(within(section).getByText('No puede quedar vacío.')).toBeOnTheScreen();
    await fireEvent.changeText(within(section).getByTestId('perfil-identity'), 'x'.repeat(601));
    expect(within(section).getByText('Como mucho 600 caracteres (van 601).')).toBeOnTheScreen();
    // Back to a valid draft: the server's own 400 is shown as it comes.
    await fireEvent.changeText(within(section).getByTestId('perfil-name'), 'Ana María');
    await fireEvent.changeText(within(section).getByTestId('perfil-limits'), 'Nada inventado.');
    await fireEvent.changeText(within(section).getByTestId('perfil-identity'), 'Construyo producto con equipos pequeños.');
    await fireEvent.press(within(section).getByTestId('perfil-guardar'));
    expect(await within(section).findByText('company_relation: como mucho 300 caracteres.')).toBeOnTheScreen();
    expect(api.find('PATCH', '/api/v1/yo/perfil')[0]?.body).toEqual({ name: 'Ana María', limits: 'Nada inventado.' });
    expect(within(section).queryByTestId('perfil-estado')).toBeNull();
  });

  it('a person who is not a member sees neither Mi perfil nor Mi voz, and nothing is asked for them', async () => {
    const api = server({ yo: { ...MEMBER, member: null, organization: null, is_admin: false } });
    await render();
    await waitFor(() => expect(api.find('GET', '/api/v1/yo').length).toBeGreaterThan(0));
    expect(await screen.findByText('Has entrado como ana.')).toBeOnTheScreen();
    expect(screen.queryByTestId('ajustes-mi-perfil')).toBeNull();
    expect(screen.queryByTestId('ajustes-mi-voz')).toBeNull();
    expect(api.find('GET', '/api/v1/yo/perfil')).toHaveLength(0);
    expect(api.find('GET', '/api/v1/yo/voz')).toHaveLength(0);
  });
});

describe('Ajustes · Mi voz', () => {
  it('provisional: says what it means, her texts against the minimum and why she cannot ask yet', async () => {
    server();
    await render();
    const section = await vozSection();
    expect(await within(section).findByTestId('voz-estado')).toHaveTextContent('Provisional');
    expect(within(section).getByText(/marca tus borradores «Voz provisional»/)).toBeOnTheScreen();
    expect(within(section).getByRole('progressbar', { name: 'Muestra para una propuesta' })).toHaveAccessibilityValue({
      min: 0,
      max: 12,
      now: 7,
      text: '7 de 12 textos aprobados o editados',
    });
    expect(within(section).getByLabelText('Editados por ti: 2')).toBeOnTheScreen();
    expect(within(section).getByLabelText('Audios y notas: 3')).toBeOnTheScreen();
    expect(within(section).getByTestId('voz-sin-propuesta')).toHaveTextContent('Faltan 5 textos tuyos aprobados o editados para pedir una propuesta.');
    expect(within(section).queryByTestId('voz-proponer')).toBeNull();
    expect(within(section).queryByTestId('voz-confirmar')).toBeNull();
  });

  it('a proposal ready: she reads it and confirms it with the exact body', async () => {
    // The server keeps the decision: the refetch after it reads the confirmed voice back.
    let current = vozConPropuestaFixture();
    const api = server(undefined, {
      'GET /api/v1/yo/voz': () => ({ body: current }),
      'POST /api/v1/yo/voz/decidir': () => {
        current = vozConfirmadaFixture();
        return { body: current };
      },
    });
    await render();
    const section = await vozSection();
    expect(await within(section).findByText('Propuesta de tu voz (versión 1) lista')).toBeOnTheScreen();
    expect(within(section).queryByTestId('voz-propuesta-texto')).toBeNull();
    await fireEvent.press(within(section).getByTestId('voz-ver'));
    expect(within(section).getByTestId('voz-propuesta-texto')).toHaveTextContent(/# Tono de voz de Ana Pérez/);
    await fireEvent.press(within(section).getByTestId('voz-confirmar'));
    const sheet = await screen.findByTestId('confirm-sheet');
    expect(within(sheet).getByText('Confirmar la versión 1 de tu voz')).toBeOnTheScreen();
    expect(within(sheet).getByText(/Lo que necesita tu aprobación no cambia/)).toBeOnTheScreen();
    expect(within(sheet).queryByTestId('confirm-note')).toBeNull();
    await fireEvent.press(within(sheet).getByRole('button', { name: 'Confirmar mi voz' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/yo/voz/decidir')[0]?.body).toEqual({ number: 1, decision: 'confirmar' }));
    expect(await screen.findByText('Voz 1 confirmada: desde ahora el equipo escribe con ella.')).toBeOnTheScreen();
    expect(await within(section).findByText('Confirmada v2')).toBeOnTheScreen();
  });

  it('discards a proposal with an optional note', async () => {
    const api = server({ voz: vozConPropuestaFixture() }, { 'POST /api/v1/yo/voz/decidir': { body: vozFixture() } });
    await render();
    const section = await vozSection();
    await fireEvent.press(await within(section).findByTestId('voz-descartar'));
    const sheet = await screen.findByTestId('confirm-sheet');
    await fireEvent.changeText(within(sheet).getByTestId('confirm-note'), '  Demasiado formal. ');
    await fireEvent.press(within(sheet).getByRole('button', { name: 'Descartar la propuesta' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/yo/voz/decidir')[0]?.body).toEqual({ number: 1, decision: 'descartar', note: 'Demasiado formal.' }));
    expect(await screen.findByText('Propuesta 1 descartada. Sigue la voz que tenías.')).toBeOnTheScreen();
  });

  it('discards without a note: the body carries no note', async () => {
    const api = server({ voz: vozConPropuestaFixture() }, { 'POST /api/v1/yo/voz/decidir': { body: vozFixture() } });
    await render();
    await fireEvent.press(await within(await vozSection()).findByTestId('voz-descartar'));
    await fireEvent.press(within(await screen.findByTestId('confirm-sheet')).getByRole('button', { name: 'Descartar la propuesta' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/yo/voz/decidir')[0]?.body).toEqual({ number: 1, decision: 'descartar' }));
  });

  it('a refused decision keeps the sheet open with the reason', async () => {
    server({ voz: vozConPropuestaFixture() }, { 'POST /api/v1/yo/voz/decidir': { status: 400, body: { detail: 'La versión 1 ya está confirmada.' } } });
    await render();
    await fireEvent.press(await within(await vozSection()).findByTestId('voz-confirmar'));
    const sheet = await screen.findByTestId('confirm-sheet');
    await fireEvent.press(within(sheet).getByRole('button', { name: 'Confirmar mi voz' }));
    expect(await within(sheet).findByText('La versión 1 ya está confirmada.')).toBeOnTheScreen();
    expect(screen.getByTestId('confirm-sheet')).toBeOnTheScreen();
  });

  it('confirmed: its version, the versions list, and asking for a paid proposal after the cost warning', async () => {
    let current = vozConfirmadaFixture();
    const api = server(undefined, {
      'GET /api/v1/yo/voz': () => ({ body: current }),
      'POST /api/v1/yo/voz/proponer': () => {
        current = { ...vozConfirmadaFixture(), can_propose: false, proposal: vozConPropuestaFixture().proposal };
        return { status: 201, body: current };
      },
    });
    await render();
    const section = await vozSection();
    expect(await within(section).findByTestId('voz-estado')).toHaveTextContent('Confirmada v2');
    expect(within(section).getByText('El equipo escribe con tu voz confirmada (versión 2).')).toBeOnTheScreen();
    await fireEvent.press(within(section).getByText('Versiones (2)'));
    expect(within(section).getByTestId('voz-version-1')).toHaveTextContent(/#1.*Descartada/);
    expect(within(section).getByTestId('voz-version-2')).toHaveTextContent(/#2.*Confirmada/);
    await fireEvent.press(within(section).getByTestId('voz-proponer'));
    const sheet = await screen.findByTestId('confirm-sheet');
    expect(within(sheet).getByText(/unos 0,17 USD/)).toBeOnTheScreen();
    expect(api.find('POST', '/api/v1/yo/voz/proponer')).toHaveLength(0);
    await fireEvent.press(within(sheet).getByRole('button', { name: 'Pedir propuesta' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/yo/voz/proponer')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/yo/voz/proponer')[0]?.body).toEqual({});
    expect(await within(section).findByText('Propuesta de tu voz (versión 1) lista')).toBeOnTheScreen();
  });
});

describe('Ajustes · Organización y alta', () => {
  it('the admin sees the organization and its members, with nothing private', async () => {
    server({ yo: yoFixture() });
    await render();
    const section = await screen.findByTestId('ajustes-organizacion');
    expect(await within(section).findByLabelText('Posicionamiento: posicionamiento-v3 · 2026-11-01')).toBeOnTheScreen();
    const ana = within(section).getByTestId('miembro-m-2');
    expect(within(ana).getByText('Ana Pérez')).toBeOnTheScreen();
    expect(within(ana).getByText('Inactivo')).toBeOnTheScreen();
    expect(within(ana).getByText('Voz provisional')).toBeOnTheScreen();
    expect(within(ana).getByText('API oficial: conectada · Navegador: sin conectar')).toBeOnTheScreen();
    expect(within(ana).queryByText('Administrador')).toBeNull();
    const gustavo = within(section).getByTestId('miembro-m-1');
    expect(within(gustavo).getByText('Administrador')).toBeOnTheScreen();
    expect(within(gustavo).getByText('Activo')).toBeOnTheScreen();
  });

  it('a member who is not admin never asks for the organization', async () => {
    const api = server();
    await render();
    expect(await vozSection()).toBeOnTheScreen();
    expect(screen.queryByTestId('ajustes-organizacion')).toBeNull();
    expect(api.find('GET', '/api/v1/organizacion')).toHaveLength(0);
  });

  it('a member in onboarding reads what is left on top', async () => {
    server({ yo: yoAltaFixture(), perfil: perfilFixture({ member: { id: 'm-2', display_name: 'Ana Pérez', role: 'CTO', active: false } }) });
    await render();
    expect(await screen.findByText(ALTA_NOTICE)).toBeOnTheScreen();
    expect(within(screen.getByTestId('ajustes-alta')).getByText('Tu cuenta está en alta')).toBeOnTheScreen();
    expect(await screen.findByText(/Mientras tu cuenta está en alta, tu perfil se guarda/)).toBeOnTheScreen();
  });

  it('an active member sees no onboarding notice', async () => {
    server();
    await render();
    expect(await within(await perfilSection()).findByTestId('perfil-identity')).toBeOnTheScreen();
    expect(screen.queryByText(ALTA_NOTICE)).toBeNull();
    expect(screen.queryByTestId('ajustes-alta')).toBeNull();
    expect(screen.queryByText(/Mientras tu cuenta está en alta/)).toBeNull();
  });

  it('scrolls to #voz when a link asks for it', async () => {
    routerState.params = { ancla: 'voz' };
    const scrollTo = jest.spyOn(ScrollView.prototype as unknown as { scrollTo: () => void }, 'scrollTo').mockImplementation(() => undefined);
    server();
    await render();
    const anchor = await screen.findByTestId('ajustes-voz');
    await act(async () => fireEvent(anchor, 'layout', { nativeEvent: { layout: { x: 0, y: 2400, width: 390, height: 300 } } }));
    expect(scrollTo).toHaveBeenLastCalledWith({ y: 2388, animated: true });
    scrollTo.mockRestore();
  });
});
