import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { Action, ActionState, ContactBrief } from '../api/types';
import { fakeServer } from '../test/fakeServer';
import { renderAt } from '../test/render';
import { Acciones } from './Acciones';

function action(id: string, state: ActionState, extra: Partial<Action> = {}): Action {
  return {
    id,
    capability: 'INT-03',
    payload: { text: `Comentario ${id}: gracias por compartir el caso, ¿cómo midieron el resultado?` },
    payload_hash: 'a'.repeat(64),
    version: 1,
    state,
    source: 'agent',
    rationale: 'Aporta una pregunta concreta sobre el método.',
    citations: ['B04-u12'],
    risks: ['Puede parecer genérico'],
    decision_note: '',
    decided_at: null,
    created_at: '2026-11-06T18:00:00Z',
    post: { id: `p-${id}`, author_name: 'Ana Referente', text: 'Así lanzamos nuestro producto.', share_url: 'https://www.linkedin.com/feed/update/urn:li:activity:1', posted_at: '2026-11-06T12:00:00Z' },
    piece_id: null,
    scheduled_for: null,
    execution: null,
    ...extra,
  };
}

const FINAL_TEXT = 'Before writing a line of code for a new feature, ask one question: what decision will this help someone make?';

/** An own publication as the backend serializes it: no post, the piece and its hour instead. */
function ownPublication(id: string, state: ActionState, extra: Partial<Action> = {}): Action {
  return action(id, state, {
    capability: 'CONT-09',
    payload: { text: FINAL_TEXT },
    rationale: 'Scope features from the decision they support. — Clearer hook.',
    citations: ['LI-04-M005-K01'],
    risks: ['Objeción conservada: Could use an example'],
    post: null,
    piece_id: 'piece-1',
    scheduled_for: '2026-11-07T13:30:00Z',
    ...extra,
  });
}

const routes = [{ path: '/acciones', element: <Acciones /> }];

describe('Acciones', () => {
  it('offers Aprobar only on proposed, Vetar on proposed/approved and Resolver on uncertain', async () => {
    fakeServer({
      'GET /api/v1/operador/actions': {
        body: {
          count: 4,
          next: null,
          previous: null,
          results: [
            action('a1', 'proposed'),
            action('a2', 'approved'),
            action('a3', 'uncertain'),
            action('a4', 'confirmed', {
              execution: { state: 'confirmed', external_id: 'c1', external_url: 'https://www.linkedin.com/feed/update/urn:li:comment:1', note: '', http_status: 201, started_at: null, finished_at: '2026-11-06T19:00:00Z' },
            }),
          ],
        },
      },
    });
    renderAt('/acciones', routes);
    const cards = await screen.findAllByRole('article');
    const buttons = cards.map((card) => within(card).queryAllByRole('button').map((b) => b.textContent));
    expect(buttons).toEqual([['Aprobar', 'Vetar'], ['Vetar'], ['Resolver'], []]);
    expect(within(cards[3]!).getByRole('link', { name: /Ver en LinkedIn/ })).toHaveAttribute('href', 'https://www.linkedin.com/feed/update/urn:li:comment:1');
    expect(within(cards[0]!).getByRole('link', { name: /Ver el post en LinkedIn/ })).toBeInTheDocument();
    expect(within(cards[0]!).getByRole('link', { name: 'B04-u12' })).toHaveAttribute('href', '/conocimiento?unidad=B04-u12');
    expect(within(cards[0]!).getByText('Puede parecer genérico')).toBeInTheDocument();
  });

  it('vetoes a proposed action with a note and shows the new state', async () => {
    document.cookie = 'csrftoken=tok';
    let vetoed = false;
    const server = fakeServer({
      'GET /api/v1/operador/actions': () => ({ body: { count: 1, next: null, previous: null, results: [action('a1', vetoed ? 'rejected' : 'proposed', vetoed ? { decision_note: 'No aporta' } : {})] } }),
      'POST /api/v1/operador/actions/a1/reject': () => {
        vetoed = true;
        return { body: action('a1', 'rejected', { decision_note: 'No aporta' }) };
      },
    });
    const user = userEvent.setup();
    renderAt('/acciones', routes);

    await user.click(await screen.findByRole('button', { name: 'Vetar' }));
    const dialog = screen.getByRole('dialog', { name: 'Vetar la acción' });
    const confirm = within(dialog).getByRole('button', { name: 'Vetar' });
    expect(confirm).toBeDisabled();
    await user.type(within(dialog).getByLabelText('Nota'), 'No aporta');
    await user.click(confirm);

    await waitFor(() => expect(within(screen.getByRole('article')).getByText('Vetada')).toBeInTheDocument());
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Vetar' })).not.toBeInTheDocument();
    const [reject] = server.find('POST', '/api/v1/operador/actions/a1/reject');
    expect(reject?.body).toEqual({ note: 'No aporta' });
    expect(reject?.headers['x-csrftoken']).toBe('tok');
  });

  it('shows the 409 detail when the veto arrives too late', async () => {
    fakeServer({
      'GET /api/v1/operador/actions': { body: [action('a2', 'approved')] },
      'POST /api/v1/operador/actions/a2/reject': { status: 409, body: { detail: 'La acción ya se está ejecutando.' } },
    });
    const user = userEvent.setup();
    renderAt('/acciones', routes);
    await user.click(await screen.findByRole('button', { name: 'Vetar' }));
    const dialog = screen.getByRole('dialog');
    await user.type(within(dialog).getByLabelText('Nota'), 'Tarde');
    await user.click(within(dialog).getByRole('button', { name: 'Vetar' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('La acción ya se está ejecutando.');
  });

  it('renders an own publication (CONT-09, post null) with its final text, day and published link', async () => {
    fakeServer({
      'GET /api/v1/operador/actions': {
        body: {
          count: 3,
          next: null,
          previous: null,
          results: [
            ownPublication('o1', 'approved'),
            ownPublication('o2', 'confirmed', {
              piece_id: 'piece-2',
              execution: {
                state: 'confirmed',
                external_id: 'urn:li:share:7400000000000000001',
                external_url: 'https://www.linkedin.com/feed/update/urn:li:share:7400000000000000001/',
                note: '',
                http_status: 201,
                started_at: '2026-11-06T13:30:00Z',
                finished_at: '2026-11-06T13:30:02Z',
              },
            }),
            action('a1', 'proposed'),
          ],
        },
      },
    });
    renderAt('/acciones', routes);
    const cards = await screen.findAllByRole('article');
    const [scheduled, published, comment] = cards as [HTMLElement, HTMLElement, HTMLElement];

    expect(within(scheduled).getByRole('heading', { name: /Publicación propia/ })).toBeInTheDocument();
    expect(within(scheduled).getByText('TEXTO FINAL')).toBeInTheDocument();
    expect(within(scheduled).getByText(FINAL_TEXT)).toHaveAttribute('lang', 'en');
    expect(within(scheduled).getByText(/Día programado/).parentElement).toHaveTextContent(/2026/);
    expect(within(scheduled).getByText(/Sale sola a esa hora/)).toBeInTheDocument();
    expect(within(scheduled).getByRole('link', { name: /Ver la pieza/ })).toHaveAttribute('href', '/contenido/piece-1');
    expect(within(scheduled).queryByText(/POST DE ORIGEN/)).not.toBeInTheDocument();
    expect(within(scheduled).getAllByRole('button').map((b) => b.textContent)).toEqual(['Vetar']);

    expect(within(published).getByRole('link', { name: /Ver el post publicado en LinkedIn/ })).toHaveAttribute(
      'href',
      'https://www.linkedin.com/feed/update/urn:li:share:7400000000000000001/',
    );
    expect(within(published).queryByRole('button')).not.toBeInTheDocument();
    expect(within(comment).getByRole('heading', { name: /Comentario/ })).toBeInTheDocument();
    expect(within(comment).getByText(/POST DE ORIGEN/)).toBeInTheDocument();
  });

  it('vetoes an own publication: the day stays without a post', async () => {
    let vetoed = false;
    const server = fakeServer({
      'GET /api/v1/operador/actions': () => ({ body: [ownPublication('o1', vetoed ? 'rejected' : 'approved')] }),
      'POST /api/v1/operador/actions/o1/reject': () => {
        vetoed = true;
        return { body: ownPublication('o1', 'rejected', { decision_note: 'No me representa' }) };
      },
    });
    const user = userEvent.setup();
    renderAt('/acciones', routes);
    await user.click(await screen.findByRole('button', { name: 'Vetar' }));
    const dialog = screen.getByRole('dialog', { name: 'Vetar la publicación' });
    expect(dialog).toHaveTextContent('ese día quedará sin publicación');
    await user.type(within(dialog).getByLabelText('Nota'), 'No me representa');
    await user.click(within(dialog).getByRole('button', { name: 'Vetar' }));
    await waitFor(() => expect(within(screen.getByRole('article')).getByText('Vetada')).toBeInTheDocument());
    expect(server.find('POST', '/api/v1/operador/actions/o1/reject')[0]?.body).toEqual({ note: 'No me representa' });
  });

  it('filters by capability: comments, reactions or own publications', async () => {
    const mixed = [action('a1', 'proposed'), action('r1', 'proposed', { capability: 'INT-02', payload: { reaction: 'like' } }), ownPublication('o1', 'approved')];
    const server = fakeServer({ 'GET /api/v1/operador/actions': { body: { count: 3, next: null, previous: null, results: mixed } } });
    const user = userEvent.setup();
    renderAt('/acciones', routes);
    expect(await screen.findAllByRole('article')).toHaveLength(3);

    await user.selectOptions(screen.getByLabelText('Capacidad'), 'publicaciones');
    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(1));
    expect(screen.getByRole('heading', { name: /Publicación propia/ })).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/acciones?capacidad=publicaciones');
    expect(server.requests.at(-1)?.search.get('capability')).toBe('CONT-09');

    await user.selectOptions(screen.getByLabelText('Capacidad'), 'reacciones');
    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(1));
    expect(screen.getByRole('heading', { name: /Reacción/ })).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText('Estado'), 'failed');
    expect(screen.getByTestId('location')).toHaveTextContent('/acciones?state=failed&capacidad=reacciones');

    await user.selectOptions(screen.getByLabelText('Capacidad'), 'comentarios');
    expect(screen.getByTestId('location')).toHaveTextContent('/acciones?state=failed&capacidad=comentarios');
    expect(server.requests.at(-1)?.search.get('capability')).toBe('INT-03');
  });

  it('filters by state through the query string', async () => {
    const server = fakeServer({ 'GET /api/v1/operador/actions': { body: { count: 0, next: null, previous: null, results: [] } } });
    const user = userEvent.setup();
    renderAt('/acciones?state=uncertain', routes);
    expect(await screen.findByText(/No hay acciones en estado «Incierta»/)).toBeInTheDocument();
    expect(server.requests[0]?.search.get('state')).toBe('uncertain');
    await user.selectOptions(screen.getByLabelText('Estado'), 'failed');
    expect(await screen.findByText(/«Fallida»/)).toBeInTheDocument();
    expect(server.requests.at(-1)?.search.get('state')).toBe('failed');
    expect(screen.getByTestId('location')).toHaveTextContent('/acciones?state=failed');
  });
});

// ---------------------------------------------------------------- network (Red): invented people, never real data

const LONG_COMMENT =
  'Muy buen punto sobre validar antes de construir. En nuestra startup pasamos tres meses haciendo un MVP que nadie pidió, y lo que nos salvó fue hablar con veinte clientes antes de escribir una sola línea más de código.';

function contact(extra: Partial<ContactBrief> = {}): ContactBrief {
  return {
    id: 'c-1',
    display_name: 'Lucía Ficticia',
    headline: 'Cofundadora @ Huerta Labs (pre-seed)',
    profile_url: 'https://www.linkedin.com/in/lucia-ficticia',
    public_identifier: 'lucia-ficticia',
    network_distance: 'SECOND_DEGREE',
    stage: 'followed',
    source: 'commenter',
    evidence: {
      post_id: 'p-9',
      post_url: 'https://www.linkedin.com/feed/update/urn:li:activity:9',
      referent: 'Tomás Referente',
      comment: LONG_COMMENT,
      query: null,
      invitation_message: null,
    },
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
    ...extra,
  };
}

/** A network action as the backend serializes it: no post, no piece, the contact instead. */
function networkAction(id: string, capability: 'RED-01' | 'RED-02' | 'RED-04', state: ActionState, extra: Partial<Action> = {}): Action {
  return action(id, state, {
    capability,
    payload: capability === 'RED-04' ? { request_id: 'req-1', user_id: 'ACoFicticio1' } : { user_id: 'ACoFicticio1' },
    payload_hash: 'c'.repeat(64),
    rationale: 'Comentó con criterio en un post de un referente y encaja con ProjectApp.',
    citations: [],
    risks: [],
    post: null,
    piece_id: null,
    contact: contact(),
    ...extra,
  });
}

describe('Acciones · red', () => {
  it('renders a RED-02 action with its contact card and approves it sending expected_hash', async () => {
    document.cookie = 'csrftoken=tok';
    let approved = false;
    const server = fakeServer({
      'GET /api/v1/operador/actions': () => ({
        body: { count: 1, next: null, previous: null, results: [networkAction('n1', 'RED-02', approved ? 'approved' : 'proposed')] },
      }),
      'POST /api/v1/operador/actions/n1/approve': () => {
        approved = true;
        return { body: networkAction('n1', 'RED-02', 'approved') };
      },
    });
    const user = userEvent.setup();
    renderAt('/acciones', routes);

    const card = await screen.findByRole('article');
    expect(within(card).getByRole('heading', { name: /Invitación sin nota/ })).toBeInTheDocument();
    const profile = within(card).getByRole('link', { name: 'Lucía Ficticia' });
    expect(profile).toHaveAttribute('href', 'https://www.linkedin.com/in/lucia-ficticia');
    expect(profile).toHaveAttribute('target', '_blank');
    expect(profile).toHaveAttribute('rel', 'noopener noreferrer');
    expect(within(card).getByText('Cofundadora @ Huerta Labs (pre-seed)')).toBeInTheDocument();
    expect(within(card).getByText('2.º grado')).toBeInTheDocument();
    expect(within(card).getByText('Comentó en un post de Tomás Referente')).toBeInTheDocument();
    const quote = within(card).getByText(/^Muy buen punto sobre validar/);
    expect(quote.textContent).toMatch(/…$/);
    expect(quote.textContent!.length).toBeLessThan(LONG_COMMENT.length);
    expect(within(card).getByRole('link', { name: /Ver el post/ })).toHaveAttribute('href', 'https://www.linkedin.com/feed/update/urn:li:activity:9');
    expect(within(card).getByText('Comprador')).toBeInTheDocument();
    expect(within(card).getByText('ProjectApp')).toBeInTheDocument();
    expect(within(card).getByText('Fundadora que busca equipo técnico para su MVP.')).toBeInTheDocument();
    expect(within(card).getByText('Comentó con criterio en un post de un referente y encaja con ProjectApp.')).toBeInTheDocument();
    expect(within(card).getByText('Enviar una invitación de conexión sin nota.')).toBeInTheDocument();
    expect(within(card).queryByText(/POST DE ORIGEN/)).not.toBeInTheDocument();
    expect(within(card).queryByText('TEXTO PROPUESTO')).not.toBeInTheDocument();
    expect(within(card).getAllByRole('button').map((b) => b.textContent)).toEqual(['Aprobar', 'Vetar']);

    await user.click(within(card).getByRole('button', { name: 'Aprobar' }));
    const dialog = screen.getByRole('dialog', { name: 'Aprobar esta versión' });
    expect(dialog).toHaveTextContent('Apruebas exactamente esta acción');
    await user.click(within(dialog).getByRole('button', { name: 'Aprobar' }));

    await waitFor(() => expect(within(screen.getByRole('article')).getByText('Aprobada')).toBeInTheDocument());
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    const [approve] = server.find('POST', '/api/v1/operador/actions/n1/approve');
    expect(approve?.body).toEqual({ expected_hash: 'c'.repeat(64), note: '' });
    expect(approve?.headers['x-csrftoken']).toBe('tok');
  });

  it('still renders an INT-03 action exactly as before next to network actions with post null', async () => {
    fakeServer({
      'GET /api/v1/operador/actions': {
        body: {
          count: 3,
          next: null,
          previous: null,
          results: [
            action('a1', 'proposed', { contact: null }),
            networkAction('f1', 'RED-01', 'approved', { contact: contact({ stage: 'fit', network_distance: '' }) }),
            networkAction('i1', 'RED-04', 'proposed', {
              contact: contact({
                id: 'c-2',
                display_name: 'Pablo Ficticio',
                profile_url: 'javascript:alert(1)',
                stage: 'incoming',
                source: 'incoming',
                network_distance: 'THIRD_DEGREE',
                evidence: { post_id: null, post_url: null, referent: null, comment: null, query: null, invitation_message: 'Hola, me gustó tu charla.' },
                classification: {},
              }),
            }),
          ],
        },
      },
    });
    renderAt('/acciones', routes);
    const [comment, follow, accept] = (await screen.findAllByRole('article')) as [HTMLElement, HTMLElement, HTMLElement];

    expect(within(comment).getByRole('heading', { name: /Comentario/ })).toBeInTheDocument();
    expect(within(comment).getByText('POST DE ORIGEN · Ana Referente')).toBeInTheDocument();
    expect(within(comment).getByText('Así lanzamos nuestro producto.')).toBeInTheDocument();
    expect(within(comment).getByText('TEXTO PROPUESTO')).toBeInTheDocument();
    expect(within(comment).getByText(/Comentario a1: gracias por compartir el caso/)).toBeInTheDocument();
    expect(within(comment).getByRole('link', { name: /Ver el post en LinkedIn/ })).toBeInTheDocument();
    expect(within(comment).getByRole('link', { name: 'B04-u12' })).toBeInTheDocument();
    expect(within(comment).queryByText('PERSONA')).not.toBeInTheDocument();
    expect(within(comment).queryByText('CLASIFICACIÓN')).not.toBeInTheDocument();
    expect(within(comment).getAllByRole('button').map((b) => b.textContent)).toEqual(['Aprobar', 'Vetar']);

    expect(within(follow).getByRole('heading', { name: /Seguir/ })).toBeInTheDocument();
    expect(within(follow).getByText('Seguir su perfil, sin pedir conexión.')).toBeInTheDocument();
    expect(within(follow).queryByText(/grado/)).not.toBeInTheDocument();
    expect(within(follow).getAllByRole('button').map((b) => b.textContent)).toEqual(['Vetar']);

    expect(within(accept).getByRole('heading', { name: /Aceptar invitación/ })).toBeInTheDocument();
    // Only https profile URLs become links.
    expect(within(accept).queryByRole('link', { name: 'Pablo Ficticio' })).not.toBeInTheDocument();
    expect(within(accept).getByText('Pablo Ficticio')).toBeInTheDocument();
    expect(within(accept).getByText('3.er grado')).toBeInTheDocument();
    expect(within(accept).getByText('Te invitó')).toBeInTheDocument();
    expect(within(accept).getByText('Hola, me gustó tu charla.')).toBeInTheDocument();
    expect(within(accept).getByText('Sin clasificar todavía.')).toBeInTheDocument();
    expect(within(accept).getByText('Aceptar la invitación de conexión que te envió.')).toBeInTheDocument();
  });

  it('vetoing a network action warns that the contact is discarded', async () => {
    const server = fakeServer({
      'GET /api/v1/operador/actions': { body: [networkAction('f1', 'RED-01', 'proposed')] },
      'POST /api/v1/operador/actions/f1/reject': { body: networkAction('f1', 'RED-01', 'rejected') },
    });
    const user = userEvent.setup();
    renderAt('/acciones', routes);
    await user.click(await screen.findByRole('button', { name: 'Vetar' }));
    const dialog = screen.getByRole('dialog', { name: 'Vetar la acción' });
    expect(dialog).toHaveTextContent('el contacto pasa a «Descartado»');
    await user.type(within(dialog).getByLabelText('Nota'), 'No es mi público');
    await user.click(within(dialog).getByRole('button', { name: 'Vetar' }));
    await waitFor(() => expect(server.find('POST', '/api/v1/operador/actions/f1/reject')[0]?.body).toEqual({ note: 'No es mi público' }));
  });

  it('filters by the network capabilities', async () => {
    const mixed = [action('a1', 'proposed'), networkAction('f1', 'RED-01', 'proposed'), networkAction('n1', 'RED-02', 'proposed')];
    const server = fakeServer({ 'GET /api/v1/operador/actions': { body: { count: 3, next: null, previous: null, results: mixed } } });
    const user = userEvent.setup();
    renderAt('/acciones', routes);
    expect(await screen.findAllByRole('article')).toHaveLength(3);
    await user.selectOptions(screen.getByLabelText('Capacidad'), 'invitaciones');
    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(1));
    expect(screen.getByRole('heading', { name: /Invitación sin nota/ })).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/acciones?capacidad=invitaciones');
    expect(server.requests.at(-1)?.search.get('capability')).toBe('RED-02');
  });
});
