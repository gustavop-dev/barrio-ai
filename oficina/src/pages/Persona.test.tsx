import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { Contact } from '../api/types';
import { overviewFixture, renderApp, tuTurnoFixture } from '../test/app';
import { fakeServer, SESSION_OK, type Handler, type Reply } from '../test/fakeServer';
import { contactFixture, opportunityFixture, page, redSummaryFixture } from '../test/fixtures/personas';
import { journey } from './personas/journey';

function server(contact: Contact | null, routes: Record<string, Handler | Reply> = {}) {
  return fakeServer({
    'GET /api/v1/auth/session': { body: SESSION_OK },
    'GET /api/v1/tu-turno': { body: tuTurnoFixture() },
    'GET /api/v1/operador/overview': { body: overviewFixture() },
    'GET /api/v1/red/summary': { body: redSummaryFixture() },
    'GET /api/v1/red/contacts': page(contact ? [contact] : []),
    [`GET /api/v1/red/contacts/${contact?.id ?? 'c-404'}`]: contact ? { body: contact } : { status: 404, body: { detail: 'No encontrado.' } },
    ...routes,
  });
}

/** The card, not the list row with the same name. */
async function card() {
  return within((await screen.findByRole('heading', { level: 2, name: /Lucía Ficticia/ })).closest('article') as HTMLElement);
}

const connected = contactFixture('c-1', {
  stage: 'connected',
  display_stage: 'connected',
  is_following: true,
  network_distance: 'FIRST_DEGREE',
  followed_at: '2026-10-22T15:00:00Z',
  invited_at: '2026-10-24T15:00:00Z',
  connected_at: '2026-10-26T15:00:00Z',
  notes: [{ id: 'n-1', at: '2026-11-06T15:00:00Z', text: 'Prefiere hablar en español.', by: 'gustavo' }],
  history: [
    { at: '2026-10-21T14:00:00Z', event: 'discovered', detail: 'Comentó en un post de Elena Prueba.' },
    { at: '2026-10-22T15:00:00Z', event: 'followed', detail: '' },
    { at: '2026-10-24T15:00:00Z', event: 'invited', detail: 'Sin nota.' },
    { at: '2026-10-26T15:00:00Z', event: 'connected', detail: '' },
  ],
  next_step: { owner: null, text: 'Conectados', at: null },
});

describe('Persona', () => {
  it('shows the header, the journey, why it fits, where it came from and the history', async () => {
    server(connected);
    renderApp('/personas/c-1');
    const view = await card();

    const name = view.getByRole('link', { name: /Lucía Ficticia/ });
    expect(name).toHaveAttribute('href', 'https://www.linkedin.com/in/persona-c-1');
    expect(name).toHaveAttribute('target', '_blank');
    expect(view.getByText('Cofundadora @ Huerta Labs (pre-seed)')).toBeInTheDocument();
    expect(view.getByText('Medellín, Colombia · 1.er grado · Lo sigues')).toBeInTheDocument();
    const [open] = view.getAllByRole('link', { name: 'Abrir en LinkedIn' });
    expect(open).toHaveAttribute('href', 'https://www.linkedin.com/in/persona-c-1');
    expect(open).toHaveAttribute('rel', 'noopener noreferrer');
    expect(view.getByText('Conectado', { selector: '.badge' })).toBeInTheDocument();

    const track = within(view.getByRole('list', { name: 'Recorrido de Lucía Ficticia' }));
    const steps = track.getAllByRole('listitem');
    expect(steps.map((step) => step.querySelector('.stage-label')?.firstChild?.textContent)).toEqual([
      'Descubierto',
      'Seguido',
      'Invitado',
      'Conectado',
      'En conversación',
      'Oportunidad',
    ]);
    expect(steps[3]).toHaveAttribute('aria-current', 'step');
    expect(steps[1]).toHaveTextContent('22 oct');
    expect(steps[4]).toHaveClass('pending');

    expect(view.getByText('Comprador')).toBeInTheDocument();
    expect(view.getByText('Hispanohablante (declarado)')).toBeInTheDocument();
    expect(view.getByRole('img', { name: 'Confianza 82 %' })).toBeInTheDocument();
    expect(view.getByText('Clasificada el 21 de octubre')).toBeInTheDocument();

    expect(view.getByText('Comentó en un post de Elena Prueba', { selector: 'p' })).toBeInTheDocument();
    expect(view.getByText(/We keep adding AI to the roadmap/)).toBeInTheDocument();
    expect(view.getByRole('link', { name: /Ver el post/ })).toHaveAttribute('href', 'https://www.linkedin.com/feed/update/urn:li:activity:9');

    expect(view.getByText('Aún no disponible')).toBeInTheDocument();
    expect(view.getByText('Prefiere hablar en español.')).toBeInTheDocument();
    expect(view.getByText('Tu nota · 6 nov')).toBeInTheDocument();

    const history = view.getAllByRole('time').map((time) => time.getAttribute('datetime'));
    expect(history).toEqual(['2026-10-26T15:00:00Z', '2026-10-24T15:00:00Z', '2026-10-22T15:00:00Z', '2026-10-21T14:00:00Z']);

    // Connected people cannot be discarded (the API answers 409); an opportunity can still be marked.
    expect(view.queryByRole('button', { name: 'Descartar' })).not.toBeInTheDocument();
    expect(view.getByRole('button', { name: 'Marcar como oportunidad' })).toBeInTheDocument();
  });

  it('shows the next step and who it depends on', async () => {
    server(
      contactFixture('c-1', {
        stage: 'followed',
        display_stage: 'followed',
        followed_at: '2026-11-05T15:00:00Z',
        next_step: { owner: 'equipo', text: 'El equipo la invitará cuando termine la espera', at: '2026-11-07T15:00:00Z', action: { id: 'a-1', capability: 'RED-02', state: 'approved' } },
        your_turn: true,
      }),
    );
    renderApp('/personas/c-1');
    const view = await card();
    const next = view.getByRole('region', { name: 'Siguiente paso' });
    expect(next).toHaveTextContent('Siguiente paso · Te toca');
    expect(next).toHaveTextContent('El equipo la invitará cuando termine la espera');
    expect(next).toHaveTextContent('Invitación sin nota · Aprobada');
    expect(within(next).getByRole('link', { name: 'Ver en el Calendario' })).toHaveAttribute('href', '/calendario');
    expect(within(next).getByRole('link', { name: 'Ir a Tu turno' })).toHaveAttribute('href', '/tu-turno');
  });

  it('adds a note and opens a voice note about the person', async () => {
    const api = server(contactFixture('c-1'), {
      'POST /api/v1/red/contacts/c-1/notas': ({ body }) => ({
        status: 201,
        body: contactFixture('c-1', { notes: [{ id: 'n-2', at: '2026-11-07T15:00:00Z', text: (body as { text: string }).text, by: 'gustavo' }] }),
      }),
    });
    const { onCapture } = renderApp('/personas/c-1');
    const view = await card();
    expect(view.getByText('Aún no hay notas sobre esta persona.')).toBeInTheDocument();

    await userEvent.click(view.getByRole('button', { name: 'Nota de voz' }));
    expect(onCapture).toHaveBeenCalledWith({ tipo: 'persona', id: 'c-1', label: 'Lucía Ficticia' });

    await userEvent.click(view.getByRole('button', { name: 'Añadir nota' }));
    const save = view.getByRole('button', { name: 'Guardar nota' });
    expect(save).toBeDisabled();
    await userEvent.type(view.getByLabelText('Nota'), 'Tiene presupuesto para Q1.');
    await userEvent.click(save);
    await waitFor(() => expect(api.find('POST', '/api/v1/red/contacts/c-1/notas')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/red/contacts/c-1/notas')[0]!.body).toEqual({ text: 'Tiene presupuesto para Q1.' });
    expect(await screen.findByText('Nota guardada')).toBeInTheDocument();
  });

  it('discards with a mandatory note, only in the allowed stages', async () => {
    const api = server(contactFixture('c-1'), {
      'POST /api/v1/red/contacts/c-1/discard': () => ({ body: contactFixture('c-1', { stage: 'discarded', display_stage: 'discarded' }) }),
    });
    renderApp('/personas/c-1');
    const view = await card();
    await userEvent.click(view.getByRole('button', { name: 'Descartar' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Descartar a Lucía Ficticia' }));
    expect(dialog.getByText(/No volverá a proponerse/)).toBeInTheDocument();
    const confirm = dialog.getByRole('button', { name: 'Descartar' });
    expect(confirm).toBeDisabled();
    await userEvent.type(dialog.getByLabelText(/Por qué la descartas/), 'No es comprador.');
    await userEvent.click(confirm);
    await waitFor(() => expect(api.find('POST', '/api/v1/red/contacts/c-1/discard')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/red/contacts/c-1/discard')[0]!.body).toEqual({ note: 'No es comprador.' });
    expect(await screen.findByText('Descartada: no volverá a proponerse')).toBeInTheDocument();
  });

  it('marks the person as an opportunity with the form prefilled', async () => {
    const api = server(contactFixture('c-1'), {
      'POST /api/v1/oportunidades': ({ body }) => ({ status: 201, body: opportunityFixture('o-9', body as object) }),
    });
    renderApp('/personas/c-1');
    const view = await card();
    await userEvent.click(view.getByRole('button', { name: 'Marcar como oportunidad' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Nueva oportunidad' }));
    expect(dialog.getByText('Lucía Ficticia')).toBeInTheDocument();
    expect(dialog.getByLabelText('Modalidad')).toHaveValue('projectapp');
    await userEvent.selectOptions(dialog.getByLabelText('Cómo llegó'), 'lo_dijo');
    await userEvent.type(dialog.getByLabelText(/Necesidad/), 'Un piloto de IA en enero.');
    await userEvent.click(dialog.getByRole('button', { name: 'Registrar oportunidad' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/oportunidades')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/oportunidades')[0]!.body).toMatchObject({ contact: 'c-1', modality: 'projectapp', attribution: 'lo_dijo', need: 'Un piloto de IA en enero.' });
  });

  it('shows the open opportunity and edits it', async () => {
    const contact = contactFixture('c-1', {
      stage: 'connected',
      display_stage: 'opportunity',
      opportunity: { id: 'o-1', stage: 'necesidad', stage_label: 'Necesidad identificada', modality: 'projectapp', next_action: 'Enviar la propuesta de piloto', next_action_at: '2026-11-12T17:00:00Z' },
      next_step: { owner: 'gustavo', text: 'Oportunidad: Necesidad identificada · Enviar la propuesta de piloto', at: '2026-11-12T17:00:00Z' },
    });
    const api = server(contact, {
      'GET /api/v1/oportunidades': page([opportunityFixture('o-1')]),
      'PATCH /api/v1/oportunidades/o-1': ({ body }) => ({ body: opportunityFixture('o-1', body as object) }),
    });
    renderApp('/personas/c-1');
    const view = await card();
    expect(view.getByText('Oportunidad', { selector: '.badge' })).toBeInTheDocument();
    expect(view.queryByRole('button', { name: 'Marcar como oportunidad' })).not.toBeInTheDocument();
    expect(await view.findByText('Decidir y construir una primera funcionalidad de IA.')).toBeInTheDocument();
    expect(view.getByText('LinkedIn')).toBeInTheDocument();
    expect(view.getByText('Citó un post o el perfil')).toBeInTheDocument();
    expect(view.getByText('1 día en esta etapa')).toBeInTheDocument();
    expect(api.find('GET', '/api/v1/oportunidades')[0]!.search.get('contact')).toBe('c-1');
    expect(view.getByRole('list', { name: 'Recorrido de Lucía Ficticia' })).toHaveTextContent('Necesidad identificada');

    await userEvent.click(view.getByRole('button', { name: 'Editar oportunidad' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Editar oportunidad' }));
    await userEvent.selectOptions(dialog.getByLabelText('Etapa'), 'reunion');
    await userEvent.click(dialog.getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(api.find('PATCH', '/api/v1/oportunidades/o-1')).toHaveLength(1));
    expect(api.find('PATCH', '/api/v1/oportunidades/o-1')[0]!.body).toMatchObject({ stage: 'reunion', contact: 'c-1' });
  });

  it('says when the person does not exist', async () => {
    server(null);
    renderApp('/personas/c-404');
    expect(await screen.findByText('No encontramos a esta persona')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /Volver a Personas/ })[0]).toHaveAttribute('href', '/personas');
  });

  it('builds the journey of an incoming invitation and of a discarded person', () => {
    const incoming = journey(contactFixture('c-1', { source: 'incoming', stage: 'incoming' }));
    expect(incoming.map((s) => [s.label, s.state])).toEqual([
      ['Descubierto', 'done'],
      ['Te invitó', 'current'],
      ['Conectado', 'pending'],
      ['En conversación', 'pending'],
      ['Oportunidad', 'pending'],
    ]);
    const discarded = journey(
      contactFixture('c-1', { stage: 'discarded', history: [{ at: '2026-10-25T15:00:00Z', event: 'discarded', detail: 'No encaja' }] }),
    );
    expect(discarded.map((s) => [s.label, s.state, s.date])).toEqual([
      ['Descubierto', 'done', '21 oct'],
      ['Descartado', 'alt', '25 oct'],
    ]);
  });
});
