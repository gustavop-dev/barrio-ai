// Personas: Barrio (funnel chips, search and the filter sheet, warnings, empty, error and «Cargar más»),
// Oportunidades (grouped by stage, the drag and the stage selector with «Deshacer», the form), Referentes
// (the URL check, «Observar ahora», deactivate with «Deshacer», remove) and the deep links of the old views.
import { accountFixture, contactFixture, opportunityFixture, page, redSummaryFixture, referentFixture } from '@compartido/fixtures/personas';
import { normalizeProfileUrl } from '@compartido/api/personas';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import { router } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { State } from 'react-native-gesture-handler';
import { fireGestureHandler, getByGestureTestId } from 'react-native-gesture-handler/jest-utils';
import '@/api/transport';
import { routeForUrl } from '@/push/routes';
import { renderApp } from '@/test/render';
import { fakeServer, type FakeHandler, type SentRequest } from '@/test/server';
import { PersonasScreen } from './PersonasScreen';

const routerState = (jest.requireMock('expo-router') as { __state: { params: Record<string, string> } }).__state;

function query(request: SentRequest): Record<string, string> {
  const search = request.path.split('?')[1] ?? '';
  return Object.fromEntries(search.split('&').filter(Boolean).map((pair) => pair.split('=').map((part) => decodeURIComponent(part.replace(/\+/g, ' '))) as [string, string]));
}

async function renderPersonas(routes: Record<string, FakeHandler>, params: Record<string, string> = {}) {
  routerState.params = params;
  const server = fakeServer(routes);
  await renderApp(<PersonasScreen />);
  return server;
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

beforeEach(() => {
  routerState.params = {};
});

describe('Personas · Barrio', () => {
  it('shows the funnel chips with counts and the rows of people', async () => {
    await renderPersonas({ 'GET /api/v1/red/summary': { body: redSummaryFixture() }, 'GET /api/v1/red/contacts': page([lucia, diego]) });
    expect(screen.getByText('Personas')).toBeOnTheScreen();
    expect(screen.getByRole('tab', { name: 'Barrio' })).toBeSelected();
    const chips = within(screen.getByTestId('stage-chips'));
    expect(await chips.findByRole('button', { name: 'Todas · 51' })).toBeSelected();
    for (const name of ['Por clasificar · 12', 'Encaja · 9', 'Seguido · 8', 'Invitado · 6', 'Conectado · 7', 'Oportunidad · 1', 'Te invitó · 1', 'Cerrado · 2', 'Descartado · 6']) {
      expect(chips.getByRole('button', { name })).toBeOnTheScreen();
    }
    expect(chips.getByRole('button', { name: 'En conversación · aún no disponible' })).toBeDisabled();

    const first = within(await screen.findByTestId('person-c-1'));
    expect(first.getByText('Lucía Ficticia')).toBeOnTheScreen();
    expect(first.getByText('Oportunidad')).toBeOnTheScreen();
    expect(first.getByText('Comprador')).toBeOnTheScreen();
    expect(first.getByText('ProjectApp')).toBeOnTheScreen();
    expect(first.getByText('Comentó en un post de Elena Prueba · Seguido hace 2 días')).toBeOnTheScreen();
    expect(first.getByText('Te toca')).toBeOnTheScreen();

    const second = within(screen.getByTestId('person-c-2'));
    expect(second.getByText('Sin clasificar todavía')).toBeOnTheScreen();
    expect(second.getByText(/Búsqueda: founders pre-seed Colombia/)).toBeOnTheScreen();
    expect(second.queryByText('Te toca')).toBeNull();

    await fireEvent.press(screen.getByTestId('person-c-1'));
    expect(router.push).toHaveBeenLastCalledWith({ pathname: '/personas/[id]', params: { id: 'c-1' } });
  });

  it('filters by stage from a chip, says so when nobody is there, and clears the filters', async () => {
    const server = await renderPersonas({
      'GET /api/v1/red/summary': { body: redSummaryFixture() },
      'GET /api/v1/red/contacts': (request) => (query(request).stage === 'fit' ? page([]) : page([lucia])),
    });
    await fireEvent.press(await screen.findByRole('button', { name: 'Encaja · 9' }));
    expect(router.setParams).toHaveBeenLastCalledWith(expect.objectContaining({ etapa: 'fit', pestana: undefined }));
    expect(await screen.findByText('Nadie en «Encaja» ahora mismo')).toBeOnTheScreen();
    expect(query(server.find('GET', '/api/v1/red/contacts').at(-1)!).stage).toBe('fit');
    await fireEvent.press(screen.getByText('Quitar filtros'));
    expect(await screen.findByTestId('person-c-1')).toBeOnTheScreen();
  });

  it('opens with the stage of an old /red?etapa= link and asks for it', async () => {
    const server = await renderPersonas({ 'GET /api/v1/red/summary': { body: redSummaryFixture() }, 'GET /api/v1/red/contacts': page([lucia]) }, { etapa: 'opportunity' });
    expect(await screen.findByRole('button', { name: 'Oportunidad · 1' })).toBeSelected();
    await waitFor(() => expect(query(server.find('GET', '/api/v1/red/contacts')[0]!).stage).toBe('opportunity'));
  });

  it('keeps every letter typed in the search box while the URL catches up late (PRS-02)', async () => {
    // Found by 14-fichas on the emulator: «Sof» became «S». The box writes ?q= after its pause; when the router took
    // longer than the next letters to apply ?q=S, that older value came back and replaced what had been typed since.
    await renderPersonas({ 'GET /api/v1/red/summary': { body: redSummaryFixture() }, 'GET /api/v1/red/contacts': page([lucia]) });
    await screen.findByTestId('person-c-1');
    const lastQ = () => (jest.mocked(router.setParams).mock.calls.at(-1)?.[0] as { q?: string } | undefined)?.q;

    await fireEvent.changeText(screen.getByTestId('barrio-search'), 'S');
    await waitFor(() => expect(lastQ()).toBe('S'));
    await fireEvent.changeText(screen.getByTestId('barrio-search'), 'So');
    await waitFor(() => expect(lastQ()).toBe('So'));
    // Only now does the router apply the first change, ?q=S, while the next letter is typed.
    routerState.params = { q: 'S' };
    await fireEvent.changeText(screen.getByTestId('barrio-search'), 'Sof');
    expect(screen.getByTestId('barrio-search').props.value).toBe('Sof');
    await waitFor(() => expect(lastQ()).toBe('Sof'));
    expect(screen.getByTestId('barrio-search').props.value).toBe('Sof');
  });

  it('searches by name and filters by role, modality and origin in a sheet', async () => {
    const server = await renderPersonas({ 'GET /api/v1/red/summary': { body: redSummaryFixture() }, 'GET /api/v1/red/contacts': page([lucia]) });
    await screen.findByTestId('person-c-1');

    await fireEvent.changeText(screen.getByTestId('barrio-search'), 'luc');
    await waitFor(() => expect(query(server.find('GET', '/api/v1/red/contacts').at(-1)!).q).toBe('luc'));

    await fireEvent.press(screen.getByRole('button', { name: 'Más filtros: rol, modalidad y origen' }));
    const sheet = within(await screen.findByTestId('barrio-filters'));
    await fireEvent.press(sheet.getByRole('button', { name: 'Rol del barrio' }));
    await fireEvent.press(sheet.getByRole('radio', { name: 'Comprador' }));
    await fireEvent.press(sheet.getByRole('button', { name: 'Modalidad' }));
    await fireEvent.press(sheet.getByRole('radio', { name: 'ProjectApp' }));
    await fireEvent.press(sheet.getByRole('button', { name: 'Origen' }));
    await fireEvent.press(sheet.getByRole('radio', { name: 'Comentó en un post' }));
    await waitFor(() => {
      const last = query(server.find('GET', '/api/v1/red/contacts').at(-1)!);
      expect([last.q, last.role, last.modality, last.source]).toEqual(['luc', 'comprador', 'projectapp', 'commenter']);
    });
    expect(router.setParams).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'luc', rol: 'comprador', modalidad: 'projectapp', origen: 'commenter' }));
    await fireEvent.press(sheet.getByText('Ver resultados'));
    expect(await screen.findByRole('button', { name: 'Más filtros: rol, modalidad y origen (3 activos)' })).toBeOnTheScreen();
  });

  it('warns when the network is off and when invitations are paused', async () => {
    await renderPersonas({
      'GET /api/v1/red/summary': { body: redSummaryFixture({ enabled: false, invites_blocked: { blocked: true, reason: 'LinkedIn rechazó invitaciones por límite semanal.' } }) },
      'GET /api/v1/red/contacts': page([lucia]),
    });
    expect(await screen.findByText('La red está apagada en el servidor')).toBeOnTheScreen();
    expect(screen.getByText('Invitaciones en pausa: LinkedIn las limitó')).toBeOnTheScreen();
    expect(screen.getByText('LinkedIn rechazó invitaciones por límite semanal.')).toBeOnTheScreen();
    expect(screen.getByText('El equipo sigue observando y siguiendo.')).toBeOnTheScreen();
  });

  it('shows an error with retry, and the empty state', async () => {
    const server = await renderPersonas({ 'GET /api/v1/red/summary': { body: redSummaryFixture() }, 'GET /api/v1/red/contacts': { status: 500, body: { detail: 'Error del servidor' } } });
    expect(await screen.findByText('Error del servidor')).toBeOnTheScreen();
    server.on('GET /api/v1/red/contacts', page([]));
    await fireEvent.press(screen.getByText('Reintentar'));
    expect(await screen.findByText('Aún no hay personas')).toBeOnTheScreen();
    expect(screen.getByText('El equipo empieza a descubrir cuando lee los comentarios de los referentes.')).toBeOnTheScreen();
  });

  it('loads more people page by page', async () => {
    const server = await renderPersonas({
      'GET /api/v1/red/summary': { body: redSummaryFixture() },
      'GET /api/v1/red/contacts': (request) => (query(request).page === '2' ? page([diego]) : page([lucia], 'http://x/api/v1/red/contacts?page=2')),
    });
    await fireEvent.press(await screen.findByText('Cargar más'));
    expect(await screen.findByTestId('person-c-2')).toBeOnTheScreen();
    expect(screen.getByTestId('person-c-1')).toBeOnTheScreen();
    expect(server.find('GET', '/api/v1/red/contacts').map((r) => query(r).page)).toContain('2');
    expect(screen.queryByText('Cargar más')).toBeNull();
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

  it('groups the opportunities by stage, most advanced first, and folds the closed ones', async () => {
    await renderPersonas({ 'GET /api/v1/oportunidades': page(board) }, { pestana: 'oportunidades' });
    expect(screen.getByRole('tab', { name: 'Oportunidades' })).toBeSelected();
    expect(await screen.findByText('Necesidad identificada · 1')).toBeOnTheScreen();
    expect(screen.getByText('Conversación · 1')).toBeOnTheScreen();
    expect(screen.queryByText('Reunión · 0')).toBeNull();

    const lucia = within(screen.getByTestId('opp-o-1'));
    expect(lucia.getByText('Huerta Labs')).toBeOnTheScreen();
    expect(lucia.getByText('ProjectApp')).toBeOnTheScreen();
    expect(lucia.getByText(/Enviar la propuesta de piloto · /)).toBeOnTheScreen();
    expect(lucia.getByText('1 día en esta etapa')).toBeOnTheScreen();
    await fireEvent.press(lucia.getByRole('link', { name: 'Lucía Ficticia' }));
    expect(router.push).toHaveBeenLastCalledWith({ pathname: '/personas/[id]', params: { id: 'c-1' } });
    expect(within(screen.getByTestId('opp-o-2')).queryByRole('link')).toBeNull();

    expect(screen.queryByText('Faro Salud · ProjectApp · cerrada el 30 de octubre')).toBeNull();
    await fireEvent.press(screen.getByText('Cerradas sin acuerdo · 1'));
    expect(screen.getByText('Faro Salud · ProjectApp · cerrada el 30 de octubre')).toBeOnTheScreen();
  });

  it('moves a card with the stage selector and undoes it from the toast', async () => {
    const server = await renderPersonas(
      { 'GET /api/v1/oportunidades': page(board), 'PATCH /api/v1/oportunidades/o-2': (request) => ({ body: { ...board[1], ...(request.body as object) } }) },
      { pestana: 'oportunidades' },
    );
    const marta = within(await screen.findByTestId('opp-o-2'));
    await fireEvent.press(marta.getByRole('button', { name: 'Etapa de Marta Inventada' }));
    await fireEvent.press(marta.getByRole('radio', { name: 'Reunión' }));
    await waitFor(() => expect(server.find('PATCH', '/api/v1/oportunidades/o-2')).toHaveLength(1));
    expect(server.find('PATCH', '/api/v1/oportunidades/o-2')[0]!.body).toEqual({ stage: 'reunion' });
    expect(await screen.findByText('Movida a «Reunión»')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Deshacer'));
    await waitFor(() => expect(server.find('PATCH', '/api/v1/oportunidades/o-2')).toHaveLength(2));
    expect(server.find('PATCH', '/api/v1/oportunidades/o-2')[1]!.body).toEqual({ stage: 'conversacion' });
  });

  it('says so when «Deshacer» fails, and the card stays in the stage it was moved to (PRS-07)', async () => {
    // The server keeps what it saved: it accepts the move and refuses the undo.
    let stage = 'conversacion';
    let patches = 0;
    const server = await renderPersonas(
      {
        'GET /api/v1/oportunidades': () => page(board.map((item) => (item.id === 'o-2' ? { ...item, stage } : item))),
        'PATCH /api/v1/oportunidades/o-2': (request) => {
          patches += 1;
          if (patches > 1) return { status: 500, body: { detail: 'Error del servidor' } };
          stage = (request.body as { stage: string }).stage;
          return { body: { ...board[1], stage } };
        },
      },
      { pestana: 'oportunidades' },
    );
    const marta = within(await screen.findByTestId('opp-o-2'));
    await fireEvent.press(marta.getByRole('button', { name: 'Etapa de Marta Inventada' }));
    await fireEvent.press(marta.getByRole('radio', { name: 'Reunión' }));
    expect(await screen.findByText('Movida a «Reunión»')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Deshacer'));
    await waitFor(() => expect(server.find('PATCH', '/api/v1/oportunidades/o-2')).toHaveLength(2));
    expect(await screen.findByText('No se pudo deshacer: sigue en «Reunión»')).toBeOnTheScreen();
    expect(screen.getByLabelText('Marta Inventada, Reunión')).toBeOnTheScreen();
    expect(screen.queryByLabelText('Marta Inventada, Conversación')).toBeNull();
  });

  it('moves a card by dragging it onto another stage after a long press, with «Deshacer»', async () => {
    const server = await renderPersonas(
      { 'GET /api/v1/oportunidades': page(board), 'PATCH /api/v1/oportunidades/o-2': (request) => ({ body: { ...board[1], ...(request.body as object) } }) },
      { pestana: 'oportunidades' },
    );
    await screen.findByTestId('opp-o-2');
    // Where the groups are in the list: «Necesidad identificada» on top, «Conversación» under it.
    await fireEvent(screen.getByTestId('opp-zone-necesidad'), 'layout', { nativeEvent: { layout: { x: 0, y: 200, width: 358, height: 240 } } });
    await fireEvent(screen.getByTestId('opp-zone-conversacion'), 'layout', { nativeEvent: { layout: { x: 0, y: 464, width: 358, height: 240 } } });

    await act(async () => {
      fireGestureHandler(getByGestureTestId('opp-drag-o-2'), [
        { state: State.BEGAN, absoluteY: 520, y: 40 },
        { state: State.ACTIVE, absoluteY: 520, y: 40 },
        { state: State.ACTIVE, absoluteY: 380, y: 40 },
        { state: State.ACTIVE, absoluteY: 300, y: 40 },
        { state: State.END, absoluteY: 300, y: 40 },
      ]);
    });
    await waitFor(() => expect(server.find('PATCH', '/api/v1/oportunidades/o-2')).toHaveLength(1));
    expect(server.find('PATCH', '/api/v1/oportunidades/o-2')[0]!.body).toEqual({ stage: 'necesidad' });
    expect(Haptics.impactAsync).toHaveBeenCalled();
    expect(await screen.findByText('Movida a «Necesidad identificada»')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Deshacer'));
    await waitFor(() => expect(server.find('PATCH', '/api/v1/oportunidades/o-2')[1]?.body).toEqual({ stage: 'conversacion' }));
  });

  it('a drag dropped back on its own stage changes nothing', async () => {
    const server = await renderPersonas({ 'GET /api/v1/oportunidades': page(board) }, { pestana: 'oportunidades' });
    await screen.findByTestId('opp-o-2');
    await fireEvent(screen.getByTestId('opp-zone-conversacion'), 'layout', { nativeEvent: { layout: { x: 0, y: 464, width: 358, height: 240 } } });
    await act(async () => {
      fireGestureHandler(getByGestureTestId('opp-drag-o-2'), [
        { state: State.BEGAN, absoluteY: 520, y: 40 },
        { state: State.ACTIVE, absoluteY: 520, y: 40 },
        { state: State.ACTIVE, absoluteY: 540, y: 40 },
        { state: State.END, absoluteY: 540, y: 40 },
      ]);
    });
    expect(server.find('PATCH', '/api/v1/oportunidades/o-2')).toHaveLength(0);
  });

  it('creates an opportunity picking someone from Personas, with the required fields', async () => {
    const server = await renderPersonas(
      {
        'GET /api/v1/oportunidades': page([]),
        'GET /api/v1/red/contacts': page([contactFixture('c-1')]),
        'POST /api/v1/oportunidades': (request) => ({ status: 201, body: opportunityFixture('o-9', request.body as object) }),
      },
      { pestana: 'oportunidades' },
    );
    expect(await screen.findByText('Aún no hay oportunidades')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Nueva oportunidad'));
    const form = within(await screen.findByTestId('opportunity-form'));

    await fireEvent.press(form.getByText('Registrar oportunidad'));
    expect(form.getByText('Elige a alguien de Personas.')).toBeOnTheScreen();
    expect(form.getByText('Elige la modalidad.')).toBeOnTheScreen();
    expect(form.getByText('Elige cómo llegó.')).toBeOnTheScreen();
    expect(server.find('POST', '/api/v1/oportunidades')).toHaveLength(0);

    await fireEvent.changeText(form.getByTestId('opp-person-search'), 'luc');
    await fireEvent.press(await form.findByText('Lucía Ficticia'));
    expect(query(server.find('GET', '/api/v1/red/contacts').at(-1)!).q).toBe('luc');
    // The classification prefills the modality.
    expect(form.getByRole('button', { name: 'Modalidad' })).toHaveAccessibilityValue({ text: 'ProjectApp' });
    await fireEvent.press(form.getByRole('button', { name: 'Etapa' }));
    await fireEvent.press(form.getByRole('radio', { name: 'Reunión' }));
    await fireEvent.press(form.getByRole('button', { name: 'Cómo llegó' }));
    await fireEvent.press(form.getByRole('radio', { name: 'Citó un post o el perfil' }));
    await fireEvent.changeText(form.getByTestId('opp-next'), 'Enviar la propuesta');
    await fireEvent.changeText(form.getByTestId('opp-date'), '2026-11-1');
    await fireEvent.press(form.getByText('Registrar oportunidad'));
    expect(form.getByText('Escribe la fecha como AAAA-MM-DD.')).toBeOnTheScreen();
    await fireEvent.changeText(form.getByTestId('opp-date'), '2026-11-12');
    await fireEvent.press(form.getByText('Registrar oportunidad'));

    await waitFor(() => expect(server.find('POST', '/api/v1/oportunidades')).toHaveLength(1));
    const body = server.find('POST', '/api/v1/oportunidades')[0]!.body as Record<string, unknown>;
    expect(body).toMatchObject({ contact: 'c-1', person_name: '', modality: 'projectapp', stage: 'reunion', attribution: 'cito_contenido', next_action: 'Enviar la propuesta' });
    expect(String(body.next_action_at)).toMatch(/^2026-11-1[12]T/);
  });

  it('edits and deletes an opportunity', async () => {
    const server = await renderPersonas(
      {
        'GET /api/v1/oportunidades': page([board[0]!]),
        'PATCH /api/v1/oportunidades/o-1': (request) => ({ body: { ...board[0], ...(request.body as object) } }),
        'DELETE /api/v1/oportunidades/o-1': { status: 204 },
      },
      { pestana: 'oportunidades' },
    );
    await fireEvent.press(await screen.findByRole('button', { name: 'Editar la oportunidad con Lucía Ficticia' }));
    let form = within(await screen.findByTestId('opportunity-form'));
    expect(form.getByText('Editar oportunidad')).toBeOnTheScreen();
    expect(form.getByText('Lucía Ficticia')).toBeOnTheScreen();
    expect(form.getByRole('button', { name: 'Cómo llegó' })).toHaveAccessibilityValue({ text: 'Citó un post o el perfil' });
    await fireEvent.changeText(form.getByTestId('opp-budget'), '8.000 USD');
    await fireEvent.press(form.getByText('Guardar cambios'));
    await waitFor(() => expect(server.find('PATCH', '/api/v1/oportunidades/o-1')).toHaveLength(1));
    expect(server.find('PATCH', '/api/v1/oportunidades/o-1')[0]!.body).toMatchObject({ budget: '8.000 USD', contact: 'c-1' });
    await waitFor(() => expect(screen.queryByTestId('opportunity-form')).toBeNull());

    await fireEvent.press(screen.getByRole('button', { name: 'Editar la oportunidad con Lucía Ficticia' }));
    form = within(await screen.findByTestId('opportunity-form'));
    await fireEvent.press(form.getByText('Eliminar'));
    expect(form.getByText(/Se borra la oportunidad con Lucía Ficticia/)).toBeOnTheScreen();
    await fireEvent.press(form.getByText('Eliminar'));
    await waitFor(() => expect(server.find('DELETE', '/api/v1/oportunidades/o-1')).toHaveLength(1));
    expect(await screen.findByText('Oportunidad eliminada')).toBeOnTheScreen();
  });
});

describe('Personas · Referentes', () => {
  it('lists the referents and deactivates one with undo', async () => {
    const server = await renderPersonas(
      {
        'GET /api/v1/operador/accounts': { body: [accountFixture()] },
        'GET /api/v1/operador/referents': page([
          referentFixture('r-1', { last_observed_at: new Date(Date.now() - 3 * 3_600_000).toISOString() }),
          referentFixture('r-2', { display_name: 'Inés Ejemplo', active: false, contacts_count: 1, last_observed_at: new Date(Date.now() - 12.2 * 86_400_000).toISOString() }),
          referentFixture('r-3', { display_name: 'Tomás Demo', contacts_count: 0 }),
        ]),
        'PATCH /api/v1/operador/referents/r-1': (request) => ({ body: referentFixture('r-1', request.body as object) }),
      },
      { pestana: 'referentes' },
    );
    const { Linking } = require('react-native');
    const open = jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
    const elena = within(await screen.findByTestId('referent-r-1'));
    await fireEvent.press(elena.getByRole('link', { name: /Elena Prueba/ }));
    expect(open).toHaveBeenCalledWith('https://www.linkedin.com/in/ref-r-1/');
    expect(elena.getByText('Observado hace 3 h · 14 personas del barrio salieron de sus posts')).toBeOnTheScreen();
    expect(screen.getByText('Observado hace 12 días · 1 persona del barrio salió de sus posts')).toBeOnTheScreen();
    expect(screen.getByText('Aún sin observar · 0 personas del barrio salieron de sus posts')).toBeOnTheScreen();
    expect(within(screen.getByTestId('referent-r-2')).getByText('Inactivo')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Reactivar a Inés Ejemplo' })).toBeOnTheScreen();
    expect(screen.queryByRole('button', { name: 'Cuenta' })).toBeNull();

    await fireEvent.press(screen.getByRole('button', { name: 'Desactivar a Elena Prueba' }));
    await waitFor(() => expect(server.find('PATCH', '/api/v1/operador/referents/r-1')).toHaveLength(1));
    expect(server.find('PATCH', '/api/v1/operador/referents/r-1')[0]!.body).toEqual({ active: false });
    expect(await screen.findByText('Referente desactivado')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Deshacer'));
    await waitFor(() => expect(server.find('PATCH', '/api/v1/operador/referents/r-1')).toHaveLength(2));
    expect(server.find('PATCH', '/api/v1/operador/referents/r-1')[1]!.body).toEqual({ active: true });
  });

  it('removes a referent after confirming', async () => {
    const server = await renderPersonas(
      {
        'GET /api/v1/operador/accounts': { body: [accountFixture()] },
        'GET /api/v1/operador/referents': page([referentFixture('r-1')]),
        'DELETE /api/v1/operador/referents/r-1': { status: 204 },
      },
      { pestana: 'referentes' },
    );
    await fireEvent.press(await screen.findByRole('button', { name: 'Quitar a Elena Prueba' }));
    const sheet = within(await screen.findByTestId('confirm-sheet'));
    expect(sheet.getByText('Quitar a Elena Prueba')).toBeOnTheScreen();
    await fireEvent.press(sheet.getByText('Quitar'));
    await waitFor(() => expect(server.find('DELETE', '/api/v1/operador/referents/r-1')).toHaveLength(1));
    expect(await screen.findByText('Referente quitado')).toBeOnTheScreen();
  });

  it('adds a referent with a validated profile URL and queues an observation', async () => {
    const server = await renderPersonas(
      {
        'GET /api/v1/operador/accounts': { body: [accountFixture(), accountFixture('acc-2', 'Otra cuenta')] },
        'GET /api/v1/operador/referents': page([]),
        'POST /api/v1/operador/referents': (request) => ({ status: 201, body: referentFixture('r-9', request.body as object) }),
        'POST /api/v1/operador/observe': { status: 202, body: { id: 'job-1', status: 'queued' } },
      },
      { pestana: 'referentes' },
    );
    expect(await screen.findByRole('button', { name: 'Cuenta' })).toHaveAccessibilityValue({ text: 'LinkedIn de Gustavo' });
    expect(await screen.findByText('Aún no hay referentes')).toBeOnTheScreen();

    await fireEvent.press(screen.getByText('Añadir referente'));
    const sheet = within(await screen.findByTestId('add-referent'));
    await fireEvent.changeText(sheet.getByTestId('referent-url'), 'https://example.com/in/x');
    await fireEvent.changeText(sheet.getByTestId('referent-reason'), 'Habla de arquitectura en startups.');
    await fireEvent.press(sheet.getAllByText('Añadir referente').at(-1)!);
    expect(sheet.getByText('Pega la URL de un perfil: https://www.linkedin.com/in/…')).toBeOnTheScreen();
    expect(server.find('POST', '/api/v1/operador/referents')).toHaveLength(0);

    await fireEvent.changeText(sheet.getByTestId('referent-url'), 'linkedin.com/in/tomas-demo');
    await fireEvent.press(sheet.getAllByText('Añadir referente').at(-1)!);
    await waitFor(() => expect(server.find('POST', '/api/v1/operador/referents')).toHaveLength(1));
    expect(server.find('POST', '/api/v1/operador/referents')[0]!.body).toEqual({
      account: 'acc-1',
      identifier: 'https://www.linkedin.com/in/tomas-demo/',
      reason: 'Habla de arquitectura en startups.',
    });

    await fireEvent.press(await screen.findByText('Observar ahora'));
    await waitFor(() => expect(server.find('POST', '/api/v1/operador/observe')).toHaveLength(1));
    expect(server.find('POST', '/api/v1/operador/observe')[0]!.body).toEqual({ account: 'acc-1' });
    expect(await screen.findByText('Observación encolada. Los posts nuevos aparecerán en unos minutos')).toBeOnTheScreen();
  });

  it('accepts only linkedin.com/in/… profile URLs', () => {
    expect(normalizeProfileUrl('linkedin.com/in/tomas-demo')).toBe('https://www.linkedin.com/in/tomas-demo/');
    expect(normalizeProfileUrl('https://es.linkedin.com/in/ana/')).toBe('https://www.linkedin.com/in/ana/');
    expect(normalizeProfileUrl('https://example.com/in/x')).toBeNull();
    expect(normalizeProfileUrl('http://www.linkedin.com/in/x')).toBeNull();
    expect(normalizeProfileUrl('https://www.linkedin.com/company/x')).toBeNull();
    expect(normalizeProfileUrl('   ')).toBeNull();
  });
});

describe('Personas · deep links', () => {
  it('opens Personas, its tabs, a person card and the old /red and /referentes paths as the PWA does', () => {
    expect(routeForUrl('/resultados')).toEqual({ pathname: '/resultados', params: {} });
    expect(routeForUrl('/resultados#resumen')).toEqual({ pathname: '/resultados', params: { ancla: 'resumen' } });
    expect(routeForUrl('/personas')).toEqual({ pathname: '/personas', params: {} });
    expect(routeForUrl('/personas?pestana=oportunidades')).toEqual({ pathname: '/personas', params: { pestana: 'oportunidades' } });
    expect(routeForUrl('/personas?etapa=fit&q=luc')).toEqual({ pathname: '/personas', params: { etapa: 'fit', q: 'luc' } });
    expect(routeForUrl('/personas/c-1')).toEqual({ pathname: '/personas/c-1', params: {} });
    expect(routeForUrl('/red')).toEqual({ pathname: '/personas', params: {} });
    expect(routeForUrl('/red?etapa=fit')).toEqual({ pathname: '/personas', params: { etapa: 'fit' } });
    expect(routeForUrl('/referentes')).toEqual({ pathname: '/personas', params: { pestana: 'referentes' } });
  });

  it('switching tabs starts each one clean, as the PWA', async () => {
    await renderPersonas({ 'GET /api/v1/red/summary': { body: redSummaryFixture() }, 'GET /api/v1/red/contacts': page([lucia]), 'GET /api/v1/oportunidades': page([]) }, { etapa: 'fit' });
    await fireEvent.press(screen.getByRole('tab', { name: 'Oportunidades' }));
    expect(router.setParams).toHaveBeenLastCalledWith({ pestana: 'oportunidades', etapa: undefined, q: undefined, rol: undefined, modalidad: undefined, origen: undefined });
    expect(await screen.findByText('Aún no hay oportunidades')).toBeOnTheScreen();
  });
});
