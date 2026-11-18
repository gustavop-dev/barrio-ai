// Ajustes › Mi perfil, Mi voz and Organización (organizaciones, phase 7), on the PWA: what each member sees and edits of
// herself, what only the admin sees, and the notice of a member in onboarding.
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { MiPerfil, MiVoz, Yo } from '../../../compartido/src/api/types';
import { organizacionFixture, perfilFixture, vozConfirmadaFixture, vozConPropuestaFixture, vozFixture, yoAltaFixture, yoFixture } from '../../../compartido/src/fixtures/miembro';
import { ALTA_NOTICE } from '../../../compartido/src/logic/miembro';
import { overviewFixture } from '../test/app';
import { fakeServer, SESSION_OK, type Handler, type Reply } from '../test/fakeServer';
import { renderAt } from '../test/render';
import { Ajustes } from './Ajustes';

const MEMBER: Yo = yoFixture({ is_admin: false }, { id: 'm-2', display_name: 'Ana Pérez', role: 'CTO', is_admin: false, first: false });

function server({ yo = MEMBER, perfil = perfilFixture(), voz = vozFixture() }: { yo?: Yo | null; perfil?: MiPerfil; voz?: MiVoz } = {}, extra: Record<string, Handler | Reply> = {}) {
  return fakeServer({
    'GET /api/v1/auth/session': { body: SESSION_OK },
    'GET /api/v1/operador/overview': { body: overviewFixture({ accounts: [] }) },
    ...(yo ? { 'GET /api/v1/yo': { body: yo } } : {}),
    'GET /api/v1/yo/perfil': { body: perfil },
    'GET /api/v1/yo/voz': { body: voz },
    'GET /api/v1/organizacion': { body: organizacionFixture() },
    ...extra,
  });
}

const routes = [{ path: '/ajustes', element: <Ajustes /> }];
const region = (name: string) => screen.getByRole('region', { name });

describe('Ajustes · Mi perfil', () => {
  it('shows her profile with its help, and the sub-index gains Mi perfil and Mi voz', async () => {
    server();
    renderAt('/ajustes', routes);
    const section = await screen.findByRole('region', { name: 'Mi perfil' });
    expect(await within(section).findByLabelText('Cómo te presentas')).toHaveValue('Construyo producto con equipos pequeños.');
    expect(within(section).getByLabelText(/^Nombre/)).toHaveValue('Ana Pérez');
    expect(within(section).getByLabelText(/^Temas que no dominas/)).toHaveValue('Temas que no domina; nada inventado.');
    expect(within(section).getByRole('switch', { name: /Te aplica el trabajo personal en startups/ })).not.toBeChecked();
    // Nothing changed yet: saving is off.
    expect(within(section).getByRole('button', { name: 'Guardar perfil' })).toBeDisabled();
    const index = screen.getByRole('navigation', { name: 'Secciones de Ajustes' });
    const anchors = within(index).getAllByRole('link').map((a) => a.getAttribute('href'));
    expect(anchors).toContain('/ajustes#perfil');
    expect(anchors).toContain('/ajustes#voz');
    expect(anchors).not.toContain('/ajustes#organizacion');
    expect(anchors.indexOf('/ajustes#voz')).toBeLessThan(anchors.indexOf('/ajustes#sabe'));
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
    const user = userEvent.setup();
    renderAt('/ajustes', routes);
    const section = await screen.findByRole('region', { name: 'Mi perfil' });
    const identity = await within(section).findByLabelText('Cómo te presentas');
    await user.clear(identity);
    await user.type(identity, '  Lidero la tecnología de ProjectApp.  ');
    await user.click(within(section).getByRole('switch', { name: /Te aplica el trabajo personal en startups/ }));
    await user.click(within(section).getByRole('button', { name: 'Guardar perfil' }));
    await waitFor(() => expect(api.find('PATCH', '/api/v1/yo/perfil')).toHaveLength(1));
    expect(api.find('PATCH', '/api/v1/yo/perfil')[0]!.body).toEqual({ identity: 'Lidero la tecnología de ProjectApp.', personal_startups: true });
    expect(await within(section).findByRole('status')).toHaveTextContent('Guardado.');
    await user.click(within(section).getByText(/Historial \(3\)/));
    const history = within(section).getByRole('list', { name: 'Historial de tu perfil' });
    expect(within(history).getAllByRole('listitem')[0]).toHaveTextContent(/#3 · .* · ana · desde la app · cambió: Cómo te presentas, Te aplica el trabajo personal en startups/);
    expect(within(history).getAllByRole('listitem')[2]).toHaveTextContent(/#1 · .* · gustavo · en el alta/);
  });

  it('says «Sin cambios» when the server had those values already', async () => {
    server(undefined, { 'PATCH /api/v1/yo/perfil': { body: { ...perfilFixture(), saved: false } } });
    const user = userEvent.setup();
    renderAt('/ajustes', routes);
    const section = await screen.findByRole('region', { name: 'Mi perfil' });
    await user.type(await within(section).findByLabelText(/^Rol/), ' ');
    await user.type(within(section).getByLabelText(/^Rol/), 'x');
    await user.click(within(section).getByRole('button', { name: 'Guardar perfil' }));
    expect(await within(section).findByRole('status')).toHaveTextContent('Sin cambios: ya tenías esos valores.');
  });

  it('checks the limits before sending and shows the server’s reason when it refuses', async () => {
    const api = server(undefined, { 'PATCH /api/v1/yo/perfil': { status: 400, body: { detail: 'company_relation: como mucho 300 caracteres.' } } });
    const user = userEvent.setup();
    renderAt('/ajustes', routes);
    const section = await screen.findByRole('region', { name: 'Mi perfil' });
    const name = await within(section).findByLabelText(/^Nombre/);
    await user.clear(name);
    await user.type(name, 'Ana 2');
    expect(within(section).getByText(/Solo letras, espacios, apóstrofo o guion\./)).toBeInTheDocument();
    expect(within(section).getByRole('button', { name: 'Guardar perfil' })).toBeDisabled();
    const limits = within(section).getByLabelText(/^Temas que no dominas/);
    await user.clear(limits);
    expect(within(section).getByText(/No puede quedar vacío\./)).toBeInTheDocument();
    // Back to a valid draft: the server's own 400 is shown as it comes.
    await user.clear(name);
    await user.type(name, 'Ana María');
    await user.type(limits, 'Nada inventado.');
    await user.click(within(section).getByRole('button', { name: 'Guardar perfil' }));
    expect(await within(section).findByText('company_relation: como mucho 300 caracteres.')).toBeInTheDocument();
    expect(api.find('PATCH', '/api/v1/yo/perfil')[0]!.body).toEqual({ name: 'Ana María', limits: 'Nada inventado.' });
    expect(within(section).queryByRole('status')).not.toBeInTheDocument();
  });

  it('a person who is not a member (no «yo» member) sees neither Mi perfil nor Mi voz', async () => {
    const api = server({ yo: { ...MEMBER, member: null, organization: null, is_admin: false } });
    renderAt('/ajustes', routes);
    expect(await screen.findByRole('region', { name: 'Sesión y Acerca de' })).toBeInTheDocument();
    await waitFor(() => expect(api.find('GET', '/api/v1/yo')).toHaveLength(1));
    expect(screen.queryByRole('region', { name: 'Mi perfil' })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Mi voz' })).not.toBeInTheDocument();
    expect(api.find('GET', '/api/v1/yo/perfil')).toHaveLength(0);
  });
});

describe('Ajustes · Mi voz', () => {
  it('provisional: says what it means, her texts against the minimum and why she cannot ask yet', async () => {
    server();
    renderAt('/ajustes', routes);
    const section = await screen.findByRole('region', { name: 'Mi voz' });
    expect(await within(section).findByTestId('voz-estado')).toHaveTextContent('Provisional');
    expect(within(section).getByText(/marca tus borradores «Voz provisional»/)).toBeInTheDocument();
    expect(within(section).getByRole('meter', { name: 'Muestra para una propuesta' })).toHaveAttribute('aria-valuetext', '7 de 12 textos aprobados o editados');
    expect(within(section).getByText('Editados por ti').nextSibling).toHaveTextContent('2');
    expect(within(section).getByText('Faltan 5 textos tuyos aprobados o editados para pedir una propuesta.')).toBeInTheDocument();
    expect(within(section).queryByRole('button', { name: 'Pedir propuesta de mi voz' })).not.toBeInTheDocument();
  });

  it('a proposal ready: she reads it and confirms it with the exact body', async () => {
    const api = server({ voz: vozConPropuestaFixture() }, { 'POST /api/v1/yo/voz/decidir': { body: vozConfirmadaFixture() } });
    const user = userEvent.setup();
    renderAt('/ajustes', routes);
    const section = await screen.findByRole('region', { name: 'Mi voz' });
    expect(await within(section).findByText('Propuesta de tu voz (versión 1) lista')).toBeInTheDocument();
    expect(within(section).queryByLabelText('Texto de la propuesta 1')).not.toBeInTheDocument();
    await user.click(within(section).getByRole('button', { name: 'Ver la propuesta' }));
    expect(within(section).getByLabelText('Texto de la propuesta 1')).toHaveTextContent('# Tono de voz de Ana Pérez');
    await user.click(within(section).getByRole('button', { name: 'Confirmar' }));
    const dialog = await screen.findByRole('dialog', { name: 'Confirmar la versión 1 de tu voz' });
    expect(within(dialog).getByText(/Lo que necesita tu aprobación no cambia/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Confirmar mi voz' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/yo/voz/decidir')[0]?.body).toEqual({ number: 1, decision: 'confirmar' }));
    expect(await screen.findByText('Voz 1 confirmada: desde ahora el equipo escribe con ella.')).toBeInTheDocument();
  });

  it('discards a proposal with an optional note', async () => {
    const api = server({ voz: vozConPropuestaFixture() }, { 'POST /api/v1/yo/voz/decidir': { body: vozFixture() } });
    const user = userEvent.setup();
    renderAt('/ajustes', routes);
    const section = await screen.findByRole('region', { name: 'Mi voz' });
    await user.click(await within(section).findByRole('button', { name: 'Descartar' }));
    const dialog = await screen.findByRole('dialog', { name: 'Descartar la propuesta 1' });
    await user.type(within(dialog).getByRole('textbox'), 'Demasiado formal.');
    await user.click(within(dialog).getByRole('button', { name: 'Descartar la propuesta' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/yo/voz/decidir')[0]?.body).toEqual({ number: 1, decision: 'descartar', note: 'Demasiado formal.' }));
  });

  it('a refused decision keeps the dialog open with the reason', async () => {
    server({ voz: vozConPropuestaFixture() }, { 'POST /api/v1/yo/voz/decidir': { status: 400, body: { detail: 'La versión 1 ya está confirmada.' } } });
    const user = userEvent.setup();
    renderAt('/ajustes', routes);
    const section = await screen.findByRole('region', { name: 'Mi voz' });
    await user.click(await within(section).findByRole('button', { name: 'Confirmar' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Confirmar mi voz' }));
    expect(await within(dialog).findByText('La versión 1 ya está confirmada.')).toBeInTheDocument();
  });

  it('confirmed: its version, the versions list, and asking for a paid proposal after the cost warning', async () => {
    const api = server({ voz: vozConfirmadaFixture() }, { 'POST /api/v1/yo/voz/proponer': { status: 201, body: vozConPropuestaFixture() } });
    const user = userEvent.setup();
    renderAt('/ajustes', routes);
    const section = await screen.findByRole('region', { name: 'Mi voz' });
    expect(await within(section).findByTestId('voz-estado')).toHaveTextContent('Confirmada v2');
    expect(within(section).getByText('El equipo escribe con tu voz confirmada (versión 2).')).toBeInTheDocument();
    await user.click(within(section).getByText('Versiones (2)'));
    expect(within(within(section).getByRole('list', { name: 'Versiones de tu voz' })).getAllByRole('listitem')[0]).toHaveTextContent(/#1 · Descartada/);
    await user.click(within(section).getByRole('button', { name: 'Pedir propuesta de mi voz' }));
    const dialog = await screen.findByRole('dialog', { name: 'Pedir una propuesta de tu voz' });
    expect(within(dialog).getByText(/unos 0,17 USD/)).toBeInTheDocument();
    expect(api.find('POST', '/api/v1/yo/voz/proponer')).toHaveLength(0);
    await user.click(within(dialog).getByRole('button', { name: 'Pedir propuesta' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/yo/voz/proponer')).toHaveLength(1));
  });
});

describe('Ajustes · Organización y alta', () => {
  it('the admin sees the organization and its members, with nothing private', async () => {
    server({ yo: yoFixture() });
    renderAt('/ajustes', routes);
    const section = await screen.findByRole('region', { name: 'Organización' });
    expect(await within(section).findByText('posicionamiento-v3 · 2026-11-01')).toBeInTheDocument();
    const ana = within(section).getByTestId('miembro-m-2');
    expect(within(ana).getByText('Ana Pérez')).toBeInTheDocument();
    expect(within(ana).getByText('Inactivo')).toBeInTheDocument();
    expect(within(ana).getByText('Voz provisional')).toBeInTheDocument();
    expect(within(ana).getByText('API oficial: conectada · Navegador: sin conectar')).toBeInTheDocument();
    const gustavo = within(section).getByTestId('miembro-m-1');
    expect(within(gustavo).getByText('Administrador')).toBeInTheDocument();
    expect(within(gustavo).getByText('Activo')).toBeInTheDocument();
    const index = screen.getByRole('navigation', { name: 'Secciones de Ajustes' });
    expect(within(index).getByRole('link', { name: 'Organización' })).toHaveAttribute('href', '/ajustes#organizacion');
  });

  it('a member who is not admin never asks for the organization', async () => {
    const api = server();
    renderAt('/ajustes', routes);
    expect(await screen.findByRole('region', { name: 'Mi voz' })).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Organización' })).not.toBeInTheDocument();
    expect(api.find('GET', '/api/v1/organizacion')).toHaveLength(0);
  });

  it('a member in onboarding reads what is left on top; an active one does not', async () => {
    server({ yo: yoAltaFixture(), perfil: perfilFixture({ member: { id: 'm-2', display_name: 'Ana Pérez', role: 'CTO', active: false } }) });
    const { unmount } = renderAt('/ajustes', routes);
    expect(await screen.findByText(ALTA_NOTICE)).toBeInTheDocument();
    expect(await screen.findByText(/Mientras tu cuenta está en alta, tu perfil se guarda/)).toBeInTheDocument();
    unmount();
    server();
    renderAt('/ajustes', routes);
    expect(await screen.findByRole('region', { name: 'Mi perfil' })).toBeInTheDocument();
    expect(screen.queryByText(ALTA_NOTICE)).not.toBeInTheDocument();
    expect(region('Mi voz')).toBeInTheDocument();
  });
});
