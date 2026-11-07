import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { Action, ActionState } from '../api/types';
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
