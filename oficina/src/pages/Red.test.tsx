import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { Contact, RedSummary } from '../api/types';
import { fakeServer } from '../test/fakeServer';
import { renderAt } from '../test/render';
import { Red } from './Red';

// Shaped like the network contract (CONTRATO-API.md, «Red»). Invented people only.

function summary(extra: Partial<RedSummary> = {}): RedSummary {
  return {
    enabled: true,
    stages: { candidate: 3, fit: 5, discarded: 9, followed: 2, invited: 1, connected: 0, closed: 0, incoming: 1 },
    capacity: {
      'RED-01': { daily: 10, daily_used: 2, weekly: 40, weekly_used: 6, left: 8, mode: 'approval' },
      'RED-02': { daily: 5, daily_used: 0, weekly: 20, weekly_used: 0, left: 5, mode: 'approval' },
      'RED-04': { daily: 10, daily_used: 0, weekly: 40, weekly_used: 0, left: 10, mode: 'off' },
    },
    reads_today: { comments: 4, search: 1, profile: 7, sync: 1 },
    read_caps: { comments: 60, search: 20, profile: 30, sync: 4 },
    llm: { spent_today: 0.04, daily: 0.3, model: 'claude-sonnet-5-5' },
    invites_blocked: { blocked: false, reason: '' },
    last_discovery_at: '2026-11-06T09:00:00Z',
    last_sync_at: null,
    ...extra,
  };
}

function contact(id: string, extra: Partial<Contact> = {}): Contact {
  return {
    id,
    account_id: 'acc-1',
    provider_user_id: `ACo${id}`,
    public_identifier: `persona-${id}`,
    display_name: 'Lucía Ficticia',
    headline: 'Cofundadora @ Huerta Labs (pre-seed)',
    profile_url: `https://www.linkedin.com/in/persona-${id}`,
    location: 'Medellín',
    source: 'commenter',
    evidence: {
      post_id: 'p-9',
      post_url: 'https://www.linkedin.com/feed/update/urn:li:activity:9',
      referent: 'Tomás Referente',
      comment: 'Validar con clientes antes de construir nos ahorró meses.',
      query: null,
      invitation_message: null,
    },
    network_distance: 'SECOND_DEGREE',
    is_following: false,
    stage: 'fit',
    classification: {
      fit: true,
      role: 'comprador',
      modality: 'projectapp',
      affinity: 'hispanohablante_declarada',
      reason: 'Fundadora que busca equipo técnico para su MVP.',
      confidence: 0.8,
      model: 'claude-sonnet-5-5',
      classified_at: '2026-11-06T10:00:00Z',
    },
    history: [
      { at: '2026-11-04T10:00:00Z', event: 'discovered', detail: 'Comentario en un post de Tomás Referente' },
      { at: '2026-11-04T10:05:00Z', event: 'classified', detail: 'comprador · projectapp' },
      { at: '2026-11-05T08:00:00Z', event: 'note', detail: 'Revisar su empresa' },
      { at: '2026-11-06T08:00:00Z', event: 'incoming', detail: 'Invitación recibida' },
    ],
    followed_at: null,
    invited_at: null,
    connected_at: null,
    discovered_at: '2026-11-04T10:00:00Z',
    updated_at: '2026-11-06T10:00:00Z',
    open_action: { id: 'act-1', capability: 'RED-01', state: 'proposed' },
    ...extra,
  };
}

const page = (results: Contact[]) => ({ body: { count: results.length, next: null, previous: null, results } });

const routes = [{ path: '/red', element: <Red /> }];

describe('Red', () => {
  it('shows the summary: capacity and mode per capability, reads against caps, LLM budget and stage counts', async () => {
    fakeServer({
      'GET /api/v1/red/summary': { body: summary() },
      'GET /api/v1/red/contacts': page([]),
    });
    renderAt('/red', routes);

    expect(await screen.findByRole('meter', { name: 'Seguir hoy' })).toHaveAttribute('aria-valuenow', '2');
    expect(screen.getByRole('meter', { name: 'Seguir hoy' })).toHaveAttribute('aria-valuemax', '10');
    expect(screen.getByRole('meter', { name: 'Invitación sin nota hoy' })).toHaveAttribute('aria-valuemax', '5');
    expect(screen.getAllByText('Modo aprobación')).toHaveLength(2);
    expect(screen.getByText('Modo apagado')).toBeInTheDocument();
    expect(screen.getByRole('meter', { name: 'Lecturas de comentarios' })).toHaveAttribute('aria-valuetext', '4 de 60');
    expect(screen.getByRole('meter', { name: 'Perfiles consultados' })).toHaveAttribute('aria-valuetext', '7 de 30');
    expect(screen.getByRole('meter', { name: 'Gasto LLM de la red' })).toHaveAttribute('aria-valuetext', expect.stringMatching(/0,04.*0,30/));
    expect(screen.getByText('Modelo claude-sonnet-5-5')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver las propuestas pendientes' })).toHaveAttribute('href', '/acciones?state=proposed');

    const chips = within(screen.getByRole('group', { name: 'Filtrar por etapa' }));
    expect(chips.getByRole('button', { name: 'Todos 21' })).toHaveAttribute('aria-pressed', 'true');
    expect(chips.getByRole('button', { name: 'Encaja 5' })).toHaveAttribute('aria-pressed', 'false');
    expect(chips.getByRole('button', { name: 'Descartado 9' })).toBeInTheDocument();
    expect(chips.getByRole('button', { name: 'Te invitó 1' })).toBeInTheDocument();

    expect(screen.queryByText('Invitaciones en pausa')).not.toBeInTheDocument();
    expect(screen.queryByText('El bloque Red está apagado')).not.toBeInTheDocument();
    expect(await screen.findByText(/Todavía no hay contactos/)).toBeInTheDocument();
  });

  it('warns when invitations are blocked and when the block is off', async () => {
    fakeServer({
      'GET /api/v1/red/summary': { body: summary({ enabled: false, invites_blocked: { blocked: true, reason: 'Límite semanal de LinkedIn' } }) },
      'GET /api/v1/red/contacts': page([]),
    });
    renderAt('/red', routes);
    const blocked = (await screen.findByText('Invitaciones en pausa')).closest('.note') as HTMLElement;
    expect(blocked).toHaveTextContent('Motivo: Límite semanal de LinkedIn');
    expect(screen.getByText('El bloque Red está apagado').closest('.note')).toHaveTextContent('NETWORK_ENABLED=false');
  });

  it('renders each contact with its classification, evidence, last three events and open action', async () => {
    fakeServer({
      'GET /api/v1/red/summary': { body: summary() },
      'GET /api/v1/red/contacts': page([
        contact('c1', { is_following: true }),
        contact('c2', {
          display_name: 'Pablo Ficticio',
          stage: 'invited',
          source: 'search',
          evidence: { post_id: null, post_url: null, referent: null, comment: null, query: 'fundador fintech Bogotá', invitation_message: null },
          classification: {},
          history: [],
          open_action: null,
        }),
      ]),
    });
    renderAt('/red', routes);
    const [lucia, pablo] = (await screen.findAllByRole('article')) as [HTMLElement, HTMLElement];

    const profile = within(lucia).getByRole('link', { name: 'Lucía Ficticia' });
    expect(profile).toHaveAttribute('href', 'https://www.linkedin.com/in/persona-c1');
    expect(profile).toHaveAttribute('target', '_blank');
    expect(profile).toHaveAttribute('rel', 'noopener noreferrer');
    expect(within(lucia).getByRole('heading', { name: 'Lucía Ficticia' })).toBeInTheDocument();
    expect(within(lucia).getByText('Encaja')).toBeInTheDocument();
    expect(within(lucia).getByText('Cofundadora @ Huerta Labs (pre-seed)')).toBeInTheDocument();
    expect(within(lucia).getByText('2.º grado · Medellín · Lo sigues')).toBeInTheDocument();
    expect(within(lucia).getByText('Comentó en un post de Tomás Referente')).toBeInTheDocument();
    expect(within(lucia).getByText('Validar con clientes antes de construir nos ahorró meses.')).toBeInTheDocument();
    expect(within(lucia).getByText('Comprador')).toBeInTheDocument();
    expect(within(lucia).getByText('ProjectApp')).toBeInTheDocument();
    expect(within(lucia).getByText('Hispanohablante (declarado)')).toBeInTheDocument();
    expect(within(lucia).getByText(/^80\s%$/)).toBeInTheDocument();
    expect(within(lucia).getByText('Fundadora que busca equipo técnico para su MVP.')).toBeInTheDocument();

    const events = within(within(lucia).getByRole('list')).getAllByRole('listitem');
    expect(events.map((li) => li.querySelector('strong')?.textContent)).toEqual(['Te invitó', 'Nota', 'Clasificado']);
    expect(within(lucia).queryByText(/Descubierto/)).not.toBeInTheDocument();

    expect(within(lucia).getByText('Propuesta')).toBeInTheDocument();
    expect(within(lucia).getByRole('link', { name: 'Ver en Acciones' })).toHaveAttribute('href', '/acciones?state=proposed&capacidad=seguimientos');
    expect(within(lucia).getByRole('button', { name: 'Descartar' })).toBeInTheDocument();

    expect(within(pablo).getByText('Invitado')).toBeInTheDocument();
    expect(within(pablo).getByText('Búsqueda: fundador fintech Bogotá')).toBeInTheDocument();
    expect(within(pablo).getByText('Sin clasificar todavía.')).toBeInTheDocument();
    expect(within(pablo).queryByText('ACCIÓN ABIERTA')).not.toBeInTheDocument();
    // 409 once invited: no button.
    expect(within(pablo).queryByRole('button', { name: 'Descartar' })).not.toBeInTheDocument();
  });

  it('offers Descartar only for candidate, fit, followed and incoming', async () => {
    const stages = ['candidate', 'fit', 'followed', 'incoming', 'invited', 'connected', 'closed', 'discarded'] as const;
    fakeServer({
      'GET /api/v1/red/summary': { body: summary() },
      'GET /api/v1/red/contacts': page(stages.map((stage) => contact(`c-${stage}`, { stage, open_action: null }))),
    });
    renderAt('/red', routes);
    const cards = await screen.findAllByRole('article');
    expect(cards.map((card) => Boolean(within(card).queryByRole('button', { name: 'Descartar' })))).toEqual([true, true, true, true, false, false, false, false]);
  });

  it('filters by stage through the chips and the query string', async () => {
    const server = fakeServer({
      'GET /api/v1/red/summary': { body: summary() },
      'GET /api/v1/red/contacts': (request) => {
        const stage = request.search.get('stage');
        if (stage === 'followed') return page([contact('c3', { display_name: 'Marta Inventada', stage: 'followed' })]);
        return page([contact('c1'), contact('c3', { display_name: 'Marta Inventada', stage: 'followed' })]);
      },
    });
    const user = userEvent.setup();
    renderAt('/red', routes);
    expect(await screen.findAllByRole('article')).toHaveLength(2);
    expect(server.find('GET', '/api/v1/red/contacts')[0]?.search.get('stage')).toBeNull();

    await user.click(await screen.findByRole('button', { name: 'Seguido 2' }));
    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(1));
    expect(screen.getByRole('heading', { name: 'Marta Inventada' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Seguido 2' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText(/se espera al menos 48 h antes de invitar/)).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/red?etapa=followed');
    expect(server.requests.at(-1)?.search.get('stage')).toBe('followed');

    await user.click(screen.getByRole('button', { name: 'Conectado 0' }));
    expect(await screen.findByText('No hay contactos en «Conectado».')).toBeInTheDocument();
    expect(server.requests.at(-1)?.search.get('stage')).toBe('connected');

    await user.click(screen.getByRole('button', { name: 'Todos 21' }));
    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(2));
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/red$/);
  });

  it('discards a contact with a mandatory note', async () => {
    document.cookie = 'csrftoken=tok';
    let discarded = false;
    const server = fakeServer({
      'GET /api/v1/red/summary': { body: summary() },
      'GET /api/v1/red/contacts': () =>
        page([contact('c1', discarded ? { stage: 'discarded', open_action: null } : {})]),
      'POST /api/v1/red/contacts/c1/discard': () => {
        discarded = true;
        return { body: contact('c1', { stage: 'discarded', open_action: null }) };
      },
    });
    const user = userEvent.setup();
    renderAt('/red', routes);

    await user.click(await screen.findByRole('button', { name: 'Descartar' }));
    const dialog = screen.getByRole('dialog', { name: 'Descartar el contacto' });
    expect(dialog).toHaveTextContent('Lucía Ficticia pasa a «Descartado»');
    expect(dialog).toHaveTextContent('Su acción abierta se veta.');
    const confirm = within(dialog).getByRole('button', { name: 'Descartar' });
    expect(confirm).toBeDisabled();
    await user.type(within(dialog).getByLabelText('Nota'), '   ');
    expect(confirm).toBeDisabled();
    await user.clear(within(dialog).getByLabelText('Nota'));
    await user.type(within(dialog).getByLabelText('Nota'), 'Vende servicios, no compra');
    await user.click(confirm);

    await waitFor(() => expect(within(screen.getByRole('article')).getByText('Descartado')).toBeInTheDocument());
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Descartar' })).not.toBeInTheDocument();
    const [discard] = server.find('POST', '/api/v1/red/contacts/c1/discard');
    expect(discard?.body).toEqual({ note: 'Vende servicios, no compra' });
    expect(discard?.headers['x-csrftoken']).toBe('tok');
  });

  it('shows the 409 detail when the contact can no longer be discarded', async () => {
    fakeServer({
      'GET /api/v1/red/summary': { body: summary() },
      'GET /api/v1/red/contacts': page([contact('c1')]),
      'POST /api/v1/red/contacts/c1/discard': { status: 409, body: { detail: 'El contacto ya está invitado.' } },
    });
    const user = userEvent.setup();
    renderAt('/red', routes);
    await user.click(await screen.findByRole('button', { name: 'Descartar' }));
    const dialog = screen.getByRole('dialog');
    await user.type(within(dialog).getByLabelText('Nota'), 'Tarde');
    await user.click(within(dialog).getByRole('button', { name: 'Descartar' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('El contacto ya está invitado.');
  });

  it('keeps the list usable when the summary fails, and retries a failed list', async () => {
    let failList = true;
    const server = fakeServer({
      'GET /api/v1/red/summary': { status: 500, body: { detail: 'El resumen no está disponible.' } },
      'GET /api/v1/red/contacts': () => (failList ? { status: 500, body: { detail: 'Fallo leyendo contactos.' } } : page([contact('c1')])),
    });
    const user = userEvent.setup();
    renderAt('/red', routes);
    expect(await screen.findByText('El resumen no está disponible.')).toBeInTheDocument();
    expect(await screen.findByText('Fallo leyendo contactos.')).toBeInTheDocument();
    // Without the summary the chips still filter, only without counts.
    expect(screen.getByRole('button', { name: 'Encaja' })).toBeInTheDocument();

    failList = false;
    const retry = within(screen.getByText('Fallo leyendo contactos.').closest('.note') as HTMLElement).getByRole('button', { name: 'Reintentar' });
    await user.click(retry);
    expect(await screen.findByRole('heading', { name: 'Lucía Ficticia' })).toBeInTheDocument();
    expect(server.find('GET', '/api/v1/red/contacts').length).toBeGreaterThan(1);
  });
});
