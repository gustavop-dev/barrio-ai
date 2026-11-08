import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { overviewFixture, renderApp, tuTurnoFixture } from '../test/app';
import { fakeServer, SESSION_OK, type Handler, type Reply } from '../test/fakeServer';
import { accountFixture, contactFixture, opportunityFixture, page, redSummaryFixture, referentFixture } from '../test/fixtures/personas';

function server(routes: Record<string, Handler | Reply>) {
  return fakeServer({
    'GET /api/v1/auth/session': { body: SESSION_OK },
    'GET /api/v1/tu-turno': { body: tuTurnoFixture() },
    'GET /api/v1/operador/overview': { body: overviewFixture() },
    ...routes,
  });
}

function wide() {
  vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        matches: query === '(min-width: 1100px)' || query === '(min-width: 900px)',
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }) as unknown as MediaQueryList,
  );
}

const lucia = contactFixture('c-1', {
  your_turn: true,
  display_stage: 'opportunity',
  stage: 'connected',
  last_event: { at: new Date(Date.now() - 2 * 86_400_000).toISOString(), event: 'followed', detail: '' },
});
const diego = contactFixture('c-2', {
  display_name: 'Diego Supuesto',
  headline: 'Founder @ Rumbo Pagos (seed)',
  source: 'search',
  evidence: { query: 'founders pre-seed Colombia' },
  classification: {},
  display_stage: 'candidate',
  stage: 'candidate',
});

describe('Personas · Barrio', () => {
  it('shows the funnel chips with counts and the rows of people', async () => {
    server({ 'GET /api/v1/red/summary': { body: redSummaryFixture() }, 'GET /api/v1/red/contacts': page([lucia, diego]) });
    renderApp('/personas');

    expect(await screen.findByRole('heading', { level: 1, name: 'Personas' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Barrio' })).toHaveAttribute('aria-selected', 'true');
    const chips = within(await screen.findByRole('group', { name: 'Filtrar por etapa' }));
    expect(await chips.findByRole('button', { name: 'Todas · 51' })).toHaveAttribute('aria-pressed', 'true');
    expect(chips.getAllByRole('button').map((chip) => chip.textContent)).toEqual([
      'Todas · 51',
      'Por clasificar · 12',
      'Encaja · 9',
      'Seguido · 8',
      'Invitado · 6',
      'Conectado · 7',
      'En conversación · aún no disponible',
      'Oportunidad · 1',
      'Te invitó · 1',
      'Cerrado · 2',
      'Descartado · 6',
    ]);
    expect(chips.getByRole('button', { name: 'En conversación · aún no disponible' })).toBeDisabled();

    const list = within(await screen.findByRole('list', { name: 'Personas del barrio' }));
    const first = list.getByRole('link', { name: /Lucía Ficticia/ });
    expect(first).toHaveAttribute('href', '/personas/c-1');
    expect(within(first).getByText('Oportunidad')).toBeInTheDocument();
    expect(within(first).getByText('Comprador')).toBeInTheDocument();
    expect(within(first).getByText('ProjectApp')).toBeInTheDocument();
    expect(within(first).getByText('Comentó en un post de Elena Prueba · Seguido hace 2 días')).toBeInTheDocument();
    expect(within(first).getByText('Te toca')).toBeInTheDocument();

    const second = list.getByRole('link', { name: /Diego Supuesto/ });
    expect(within(second).getByText('Sin clasificar todavía')).toBeInTheDocument();
    expect(within(second).getByText(/Búsqueda: founders pre-seed Colombia/)).toBeInTheDocument();
    expect(within(second).queryByText('Te toca')).not.toBeInTheDocument();
  });

  it('filters by stage from a chip and says so when nobody is there', async () => {
    const api = server({
      'GET /api/v1/red/summary': { body: redSummaryFixture() },
      'GET /api/v1/red/contacts': ({ search }) => (search.get('stage') === 'fit' ? page([]) : page([lucia])),
    });
    renderApp('/personas');
    const chips = within(await screen.findByRole('group', { name: 'Filtrar por etapa' }));
    await userEvent.click(await chips.findByRole('button', { name: 'Encaja · 9' }));
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/personas?etapa=fit'));
    expect(await screen.findByText('Nadie en «Encaja» ahora mismo')).toBeInTheDocument();
    expect(api.find('GET', '/api/v1/red/contacts').at(-1)!.search.get('stage')).toBe('fit');
    await userEvent.click(screen.getByRole('button', { name: 'Quitar filtros' }));
    expect(await screen.findByRole('link', { name: /Lucía Ficticia/ })).toBeInTheDocument();
  });

  it('keeps the old /red?etapa= links and asks for the opportunity stage', async () => {
    const api = server({ 'GET /api/v1/red/summary': { body: redSummaryFixture() }, 'GET /api/v1/red/contacts': page([lucia]) });
    renderApp('/personas?etapa=opportunity');
    expect(await screen.findByRole('button', { name: 'Oportunidad · 1' })).toHaveAttribute('aria-pressed', 'true');
    await waitFor(() => expect(api.find('GET', '/api/v1/red/contacts')[0]!.search.get('stage')).toBe('opportunity'));
  });

  it('searches by name and filters by role, modality and origin', async () => {
    const api = server({ 'GET /api/v1/red/summary': { body: redSummaryFixture() }, 'GET /api/v1/red/contacts': page([lucia]) });
    renderApp('/personas');
    await screen.findByRole('link', { name: /Lucía Ficticia/ });

    await userEvent.type(screen.getByRole('searchbox', { name: 'Buscar por nombre' }), 'luc');
    await waitFor(() => expect(api.find('GET', '/api/v1/red/contacts').at(-1)!.search.get('q')).toBe('luc'));

    const more = screen.getByRole('button', { name: 'Más filtros: rol, modalidad y origen' });
    expect(more).toHaveAttribute('aria-expanded', 'false');
    await userEvent.click(more);
    await userEvent.selectOptions(screen.getByLabelText('Rol del barrio'), 'comprador');
    await userEvent.selectOptions(screen.getByLabelText('Modalidad'), 'projectapp');
    await userEvent.selectOptions(screen.getByLabelText('Origen'), 'commenter');
    await waitFor(() => {
      const last = api.find('GET', '/api/v1/red/contacts').at(-1)!.search;
      expect([last.get('q'), last.get('role'), last.get('modality'), last.get('source')]).toEqual(['luc', 'comprador', 'projectapp', 'commenter']);
    });
    expect(screen.getByRole('button', { name: 'Más filtros: rol, modalidad y origen (3 activos)' })).toBeInTheDocument();
    // The row link keeps the filters, so the list comes back the same.
    expect(screen.getByRole('link', { name: /Lucía Ficticia/ }).getAttribute('href')).toContain('rol=comprador');
  });

  it('warns when the network is off and when invitations are paused', async () => {
    server({
      'GET /api/v1/red/summary': { body: redSummaryFixture({ enabled: false, invites_blocked: { blocked: true, reason: 'LinkedIn rechazó invitaciones por límite semanal.' } }) },
      'GET /api/v1/red/contacts': page([lucia]),
    });
    renderApp('/personas');
    expect(await screen.findByText('La red está apagada en el servidor')).toBeInTheDocument();
    const paused = screen.getByText('Invitaciones en pausa: LinkedIn las limitó').closest('.note') as HTMLElement;
    expect(paused).toHaveTextContent('LinkedIn rechazó invitaciones por límite semanal.');
    expect(paused).toHaveTextContent('El equipo sigue observando y siguiendo.');
  });

  it('shows the empty state, and an error with retry', async () => {
    let fail = true;
    server({
      'GET /api/v1/red/summary': { body: redSummaryFixture() },
      'GET /api/v1/red/contacts': () => (fail ? { status: 500, body: { detail: 'Error del servidor' } } : page([])),
    });
    renderApp('/personas');
    expect(await screen.findByText('Error del servidor')).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(await screen.findByText('Aún no hay personas')).toBeInTheDocument();
    expect(screen.getByText('El equipo empieza a descubrir cuando lee los comentarios de los referentes.')).toBeInTheDocument();
  });

  it('loads more people page by page', async () => {
    const api = server({
      'GET /api/v1/red/summary': { body: redSummaryFixture() },
      'GET /api/v1/red/contacts': ({ search }) => (search.get('page') === '2' ? page([diego]) : page([lucia], 'http://x/api/v1/red/contacts?page=2')),
    });
    renderApp('/personas');
    await userEvent.click(await screen.findByRole('button', { name: 'Cargar más' }));
    expect(await screen.findByRole('link', { name: /Diego Supuesto/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Lucía Ficticia/ })).toBeInTheDocument();
    expect(api.find('GET', '/api/v1/red/contacts').map((r) => r.search.get('page'))).toContain('2');
    expect(screen.queryByRole('button', { name: 'Cargar más' })).not.toBeInTheDocument();
  });
});

describe('Personas · Oportunidades', () => {
  const board = [
    opportunityFixture('o-1'),
    opportunityFixture('o-2', {
      person: 'Marta Inventada',
      contact: null,
      person_name: 'Marta Inventada',
      company: 'Cosecha Data',
      modality: 'personal_startups',
      stage: 'conversacion',
      next_action: 'Responder su mensaje',
      next_action_at: null,
      days_in_stage: 4,
    }),
    opportunityFixture('o-3', { person: 'Pablo Ficticio', company: 'Faro Salud', stage: 'sin_acuerdo', closed_at: '2026-10-30T15:00:00Z', contact: null, person_name: 'Pablo Ficticio' }),
  ];

  it('groups the opportunities by stage on mobile and moves one with the stage selector', async () => {
    const api = server({
      'GET /api/v1/oportunidades': page(board),
      'PATCH /api/v1/oportunidades/o-2': ({ body }) => ({ body: { ...board[1], ...(body as object) } }),
    });
    renderApp('/personas?pestana=oportunidades');
    expect(await screen.findByRole('tab', { name: 'Oportunidades' })).toHaveAttribute('aria-selected', 'true');
    const groups = await screen.findAllByRole('heading', { level: 3 });
    expect(groups.map((h) => h.textContent)).toEqual(['Necesidad identificada · 1', 'Conversación · 1']);

    const lucia = screen.getByRole('article', { name: 'Lucía Ficticia, Necesidad identificada' });
    expect(within(lucia).getByRole('link', { name: 'Lucía Ficticia' })).toHaveAttribute('href', '/personas/c-1');
    expect(within(lucia).getByText('Huerta Labs')).toBeInTheDocument();
    expect(within(lucia).getByText('ProjectApp')).toBeInTheDocument();
    expect(within(lucia).getByText(/Enviar la propuesta de piloto · /)).toBeInTheDocument();
    expect(within(lucia).getByText('1 día en esta etapa')).toBeInTheDocument();

    const marta = screen.getByRole('article', { name: 'Marta Inventada, Conversación' });
    expect(within(marta).queryByRole('link')).not.toBeInTheDocument();
    await userEvent.selectOptions(within(marta).getByRole('combobox', { name: /^Etapa de Marta Inventada/ }), 'reunion');
    await waitFor(() => expect(api.find('PATCH', '/api/v1/oportunidades/o-2')).toHaveLength(1));
    expect(api.find('PATCH', '/api/v1/oportunidades/o-2')[0]!.body).toEqual({ stage: 'reunion' });
    expect(await screen.findByText('Movida a «Reunión»')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Deshacer' }));
    await waitFor(() => expect(api.find('PATCH', '/api/v1/oportunidades/o-2')).toHaveLength(2));
    expect(api.find('PATCH', '/api/v1/oportunidades/o-2')[1]!.body).toEqual({ stage: 'conversacion' });

    const closed = screen.getByText('Cerradas sin acuerdo · 1');
    expect(closed.closest('details')).not.toHaveAttribute('open');
    expect(screen.getByText('Faro Salud · ProjectApp · cerrada el 30 de octubre')).toBeInTheDocument();
  });

  it('says so when «Deshacer» fails, and the card stays in the stage it was moved to (PRS-07)', async () => {
    // The server keeps what it saved: it accepts the move and refuses the undo.
    let stage = 'conversacion';
    let patches = 0;
    const api = server({
      'GET /api/v1/oportunidades': () => page(board.map((item) => (item.id === 'o-2' ? { ...item, stage } : item))),
      'PATCH /api/v1/oportunidades/o-2': ({ body }) => {
        patches += 1;
        if (patches > 1) return { status: 500, body: { detail: 'Error del servidor' } };
        stage = (body as { stage: string }).stage;
        return { body: { ...board[1], stage } };
      },
    });
    renderApp('/personas?pestana=oportunidades');
    const marta = await screen.findByRole('article', { name: 'Marta Inventada, Conversación' });
    await userEvent.selectOptions(within(marta).getByRole('combobox', { name: /^Etapa de Marta Inventada/ }), 'reunion');
    expect(await screen.findByText('Movida a «Reunión»')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Deshacer' }));
    await waitFor(() => expect(api.find('PATCH', '/api/v1/oportunidades/o-2')).toHaveLength(2));
    expect(await screen.findByText('No se pudo deshacer: sigue en «Reunión»')).toBeInTheDocument();
    expect(screen.getByRole('article', { name: 'Marta Inventada, Reunión' })).toBeInTheDocument();
    expect(screen.queryByRole('article', { name: 'Marta Inventada, Conversación' })).not.toBeInTheDocument();
  });

  it('shows a board with a column per stage on desktop', async () => {
    wide();
    server({ 'GET /api/v1/oportunidades': page(board) });
    renderApp('/personas?pestana=oportunidades');
    const columns = within(await screen.findByRole('list', { name: 'Tablero de oportunidades por etapa' })).getAllByRole('listitem');
    expect(columns.map((column) => column.getAttribute('aria-label'))).toEqual([
      'Conversación: 1',
      'Necesidad identificada: 1',
      'Cualificada: 0',
      'Reunión: 0',
      'Propuesta: 0',
      'Acuerdo: 0',
    ]);
  });

  it('creates an opportunity picking someone from Personas, with the required fields', async () => {
    const api = server({
      'GET /api/v1/oportunidades': page([]),
      'GET /api/v1/red/contacts': page([contactFixture('c-1')]),
      'POST /api/v1/oportunidades': ({ body }) => ({ status: 201, body: opportunityFixture('o-9', body as object) }),
    });
    renderApp('/personas?pestana=oportunidades');
    expect(await screen.findByText('Aún no hay oportunidades')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Nueva oportunidad' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Nueva oportunidad' }));

    await userEvent.click(dialog.getByRole('button', { name: 'Registrar oportunidad' }));
    expect(dialog.getByText('Elige a alguien de Personas.')).toBeInTheDocument();
    expect(dialog.getByText('Elige la modalidad.')).toBeInTheDocument();
    expect(dialog.getByText('Elige cómo llegó.')).toBeInTheDocument();
    expect(api.find('POST', '/api/v1/oportunidades')).toHaveLength(0);

    await userEvent.type(dialog.getByLabelText('Buscar en Personas'), 'luc');
    await userEvent.click(await dialog.findByRole('button', { name: /Lucía Ficticia/ }));
    expect(api.find('GET', '/api/v1/red/contacts').at(-1)!.search.get('q')).toBe('luc');
    // The classification prefills the modality.
    expect(dialog.getByLabelText('Modalidad')).toHaveValue('projectapp');
    await userEvent.selectOptions(dialog.getByLabelText('Etapa'), 'reunion');
    await userEvent.selectOptions(dialog.getByLabelText('Cómo llegó'), 'cito_contenido');
    await userEvent.type(dialog.getByLabelText(/Siguiente acción/), 'Enviar la propuesta');
    await userEvent.type(dialog.getByLabelText(/^Fecha/), '2026-11-12');
    await userEvent.click(dialog.getByRole('button', { name: 'Registrar oportunidad' }));

    await waitFor(() => expect(api.find('POST', '/api/v1/oportunidades')).toHaveLength(1));
    const body = api.find('POST', '/api/v1/oportunidades')[0]!.body as Record<string, unknown>;
    expect(body).toMatchObject({ contact: 'c-1', person_name: '', modality: 'projectapp', stage: 'reunion', attribution: 'cito_contenido', next_action: 'Enviar la propuesta' });
    expect(String(body.next_action_at)).toMatch(/^2026-11-1[12]T/);
  });

  it('edits and deletes an opportunity', async () => {
    const api = server({
      'GET /api/v1/oportunidades': page([board[0]!]),
      'PATCH /api/v1/oportunidades/o-1': ({ body }) => ({ body: { ...board[0], ...(body as object) } }),
      'DELETE /api/v1/oportunidades/o-1': { status: 204 },
    });
    renderApp('/personas?pestana=oportunidades');
    await userEvent.click(await screen.findByRole('button', { name: 'Editar la oportunidad con Lucía Ficticia' }));
    let dialog = within(screen.getByRole('dialog', { name: 'Editar oportunidad' }));
    expect(dialog.getByText('Lucía Ficticia')).toBeInTheDocument();
    expect(dialog.getByLabelText('Cómo llegó')).toHaveValue('cito_contenido');
    await userEvent.clear(dialog.getByLabelText(/Presupuesto/));
    await userEvent.type(dialog.getByLabelText(/Presupuesto/), '8.000 USD');
    await userEvent.click(dialog.getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(api.find('PATCH', '/api/v1/oportunidades/o-1')).toHaveLength(1));
    expect(api.find('PATCH', '/api/v1/oportunidades/o-1')[0]!.body).toMatchObject({ budget: '8.000 USD', contact: 'c-1' });

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: 'Editar la oportunidad con Lucía Ficticia' }));
    dialog = within(screen.getByRole('dialog', { name: 'Editar oportunidad' }));
    await userEvent.click(dialog.getByRole('button', { name: 'Eliminar' }));
    dialog = within(screen.getByRole('dialog', { name: 'Eliminar la oportunidad' }));
    await userEvent.click(dialog.getByRole('button', { name: 'Eliminar' }));
    await waitFor(() => expect(api.find('DELETE', '/api/v1/oportunidades/o-1')).toHaveLength(1));
    expect(await screen.findByText('Oportunidad eliminada')).toBeInTheDocument();
  });
});

describe('Personas · Referentes', () => {
  it('lists the referents and deactivates one with undo', async () => {
    const api = server({
      'GET /api/v1/operador/accounts': { body: [accountFixture()] },
      'GET /api/v1/operador/referents': page([
        referentFixture('r-1', { last_observed_at: new Date(Date.now() - 3 * 3_600_000).toISOString() }),
        referentFixture('r-2', { display_name: 'Inés Ejemplo', active: false, contacts_count: 1, last_observed_at: new Date(Date.now() - 12.2 * 86_400_000).toISOString() }),
        referentFixture('r-3', { display_name: 'Tomás Demo', contacts_count: 0 }),
      ]),
      'PATCH /api/v1/operador/referents/r-1': ({ body }) => ({ body: referentFixture('r-1', body as object) }),
    });
    renderApp('/referentes');
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/personas?pestana=referentes'));
    const list = within(await screen.findByRole('list', { name: 'Referentes' }));
    const elena = list.getByRole('link', { name: /Elena Prueba/ });
    expect(elena).toHaveAttribute('href', 'https://www.linkedin.com/in/ref-r-1/');
    expect(elena).toHaveAttribute('target', '_blank');
    expect(list.getByText('Observado hace 3 h · 14 personas del barrio salieron de sus posts')).toBeInTheDocument();
    expect(list.getByText('Observado hace 12 días · 1 persona del barrio salió de sus posts')).toBeInTheDocument();
    expect(list.getByText('Aún sin observar · 0 personas del barrio salieron de sus posts')).toBeInTheDocument();
    expect(list.getByText('Inactivo')).toBeInTheDocument();
    expect(list.getByRole('button', { name: 'Reactivar a Inés Ejemplo' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Cuenta')).not.toBeInTheDocument();

    await userEvent.click(list.getByRole('button', { name: 'Desactivar a Elena Prueba' }));
    await waitFor(() => expect(api.find('PATCH', '/api/v1/operador/referents/r-1')).toHaveLength(1));
    expect(api.find('PATCH', '/api/v1/operador/referents/r-1')[0]!.body).toEqual({ active: false });
    await userEvent.click(await screen.findByRole('button', { name: 'Deshacer' }));
    await waitFor(() => expect(api.find('PATCH', '/api/v1/operador/referents/r-1')).toHaveLength(2));
    expect(api.find('PATCH', '/api/v1/operador/referents/r-1')[1]!.body).toEqual({ active: true });
  });

  it('removes a referent after confirming', async () => {
    const api = server({
      'GET /api/v1/operador/accounts': { body: [accountFixture()] },
      'GET /api/v1/operador/referents': page([referentFixture('r-1')]),
      'DELETE /api/v1/operador/referents/r-1': { status: 204 },
    });
    renderApp('/personas?pestana=referentes');
    await userEvent.click(await screen.findByRole('button', { name: 'Quitar a Elena Prueba' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Quitar a Elena Prueba' }));
    await userEvent.click(dialog.getByRole('button', { name: 'Quitar' }));
    await waitFor(() => expect(api.find('DELETE', '/api/v1/operador/referents/r-1')).toHaveLength(1));
    expect(await screen.findByText('Referente quitado')).toBeInTheDocument();
  });

  it('adds a referent with a validated profile URL and queues an observation', async () => {
    const api = server({
      'GET /api/v1/operador/accounts': { body: [accountFixture(), accountFixture('acc-2', 'Otra cuenta')] },
      'GET /api/v1/operador/referents': page([]),
      'POST /api/v1/operador/referents': ({ body }) => ({ status: 201, body: referentFixture('r-9', body as object) }),
      'POST /api/v1/operador/observe': { status: 202, body: { id: 'job-1', status: 'queued' } },
    });
    renderApp('/personas?pestana=referentes');
    expect(await screen.findByLabelText('Cuenta')).toHaveValue('acc-1');
    expect(await screen.findByText('Aún no hay referentes')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Añadir referente' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Añadir referente' }));
    await userEvent.type(dialog.getByLabelText('URL del perfil en LinkedIn'), 'https://example.com/in/x');
    await userEvent.type(dialog.getByLabelText(/Motivo/), 'Habla de arquitectura en startups.');
    await userEvent.click(dialog.getByRole('button', { name: 'Añadir referente' }));
    expect(dialog.getByLabelText('URL del perfil en LinkedIn')).toHaveAttribute('aria-invalid', 'true');
    expect(dialog.getByText('Pega la URL de un perfil: https://www.linkedin.com/in/…')).toBeInTheDocument();
    expect(api.find('POST', '/api/v1/operador/referents')).toHaveLength(0);

    await userEvent.clear(dialog.getByLabelText('URL del perfil en LinkedIn'));
    await userEvent.type(dialog.getByLabelText('URL del perfil en LinkedIn'), 'linkedin.com/in/tomas-demo');
    await userEvent.click(dialog.getByRole('button', { name: 'Añadir referente' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/operador/referents')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/operador/referents')[0]!.body).toEqual({
      account: 'acc-1',
      identifier: 'https://www.linkedin.com/in/tomas-demo/',
      reason: 'Habla de arquitectura en startups.',
    });

    await userEvent.click(await screen.findByRole('button', { name: 'Observar ahora' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/operador/observe')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/operador/observe')[0]!.body).toEqual({ account: 'acc-1' });
    expect(await screen.findByText('Observación encolada. Los posts nuevos aparecerán en unos minutos')).toBeInTheDocument();
  });
});
