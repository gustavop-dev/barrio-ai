// The person card: header with «Abrir en LinkedIn», the next step and its owner, the journey with dates, why
// the person fits and where they came from, «Conversación», the opportunity with «Editar», notes (written and
// by voice), the history, and the actions «Marcar como oportunidad» and «Descartar».
import { contactFixture, conversationFixture, opportunityFixture, page } from '@compartido/fixtures/personas';
import { keys } from '@compartido/api/queryClient';
import type { Contact } from '@compartido/api/types';
import { journey } from '@compartido/logic/journey';
import { fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import { router } from 'expo-router';
import '@/api/transport';
import { useCaptureSheet } from '@/capture/store';
import { renderApp, testQueryClient } from '@/test/render';
import { fakeServer, type FakeHandler } from '@/test/server';
import { PersonaScreen } from './PersonaScreen';

const SESSION_OK = { authenticated: true, user: { username: 'gustavo', is_superuser: true, permissions: ['approve_actions'] } };

/** Shows what the capture sheet was opened with (the app layout hosts the real sheet). */
function CaptureProbe() {
  const sheet = useCaptureSheet();
  const { Text } = require('react-native');
  return <Text testID="capture-probe">{sheet.open ? JSON.stringify(sheet.context) : 'cerrada'}</Text>;
}

async function renderCard(contact: Contact | null, routes: Record<string, FakeHandler> = {}) {
  const id = contact?.id ?? 'c-404';
  const server = fakeServer({
    [`GET /api/v1/red/contacts/${id}`]: contact ? { body: contact } : { status: 404, body: { detail: 'No encontrado.' } },
    ...routes,
  });
  const client = testQueryClient();
  client.setQueryData(keys.session, SESSION_OK);
  await renderApp(
    <>
      <PersonaScreen contactId={id} />
      <CaptureProbe />
    </>,
    { client, session: true },
  );
  return server;
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
    const { Linking } = require('react-native');
    const open = jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
    await renderCard(connected);
    expect(await screen.findByText('Lucía Ficticia')).toBeOnTheScreen();
    expect(screen.getByText('Cofundadora @ Huerta Labs (pre-seed)')).toBeOnTheScreen();
    expect(screen.getByText('Medellín, Colombia · 1.er grado · Lo sigues')).toBeOnTheScreen();
    expect(within(screen.getByTestId('persona-head')).getByText('Conectada')).toBeOnTheScreen(); // agrees with Lucía (backlog #18)
    await fireEvent.press(screen.getByTestId('persona-name'));
    expect(open).toHaveBeenLastCalledWith('https://www.linkedin.com/in/persona-c-1');
    await fireEvent.press(screen.getAllByText('Abrir en LinkedIn')[0]!);
    expect(open).toHaveBeenLastCalledWith('https://www.linkedin.com/in/persona-c-1');

    const track = within(screen.getByLabelText('Recorrido de Lucía Ficticia'));
    expect(track.getByLabelText('Descubierta, hecho, 21 oct')).toBeOnTheScreen();
    expect(track.getByLabelText('Seguida, hecho, 22 oct')).toBeOnTheScreen();
    expect(track.getByLabelText('Conectada, ahora, 26 oct')).toBeSelected();
    expect(track.getByLabelText('En conversación, pendiente')).toBeOnTheScreen();
    expect(track.getByLabelText('Oportunidad, pendiente')).toBeOnTheScreen();

    expect(screen.getByText('Comprador')).toBeOnTheScreen();
    expect(screen.getByText('Hispanohablante (declarado)')).toBeOnTheScreen();
    expect(screen.getByLabelText('Confianza 82 %')).toBeOnTheScreen();
    expect(screen.getByText('Clasificada el 21 de octubre')).toBeOnTheScreen();

    expect(screen.getByText('Comentó en un post de Elena Prueba')).toBeOnTheScreen();
    expect(screen.getByText(/We keep adding AI to the roadmap/)).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('link', { name: /Ver el post/ }));
    expect(open).toHaveBeenLastCalledWith('https://www.linkedin.com/feed/update/urn:li:activity:9');

    expect(screen.getByText('Aún no hay una conversación leída con esta persona')).toBeOnTheScreen();
    expect(screen.getByText('Prefiere hablar en español.')).toBeOnTheScreen();
    expect(screen.getByText('Tu nota · 6 nov')).toBeOnTheScreen();

    const history = within(screen.getByTestId('history'));
    expect(history.getAllByTestId(/^history-/).map((row) => within(row).getAllByText(/.+/)[0]!.props.children)).toEqual(['Conectada', 'Invitada', 'Seguida', 'Descubierta']);

    // Connected people cannot be discarded (the API answers 409); an opportunity can still be marked.
    expect(screen.queryByText('Descartar')).toBeNull();
    expect(screen.getByText('Marcar como oportunidad')).toBeOnTheScreen();
  });

  it('shows the conversation read by the team: its read, the last messages and the thread on LinkedIn', async () => {
    const { Linking } = require('react-native');
    const open = jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
    await renderCard(
      contactFixture('c-1', {
        stage: 'connected',
        display_stage: 'connected',
        connected_at: '2026-10-26T15:00:00Z',
        your_turn: true,
        next_step: { owner: 'gustavo', text: 'Te toca: responder su mensaje', at: null },
        // A network modality the opportunity form cannot take: the prefill must come from the conversation.
        classification: { ...contactFixture().classification, modality: 'alianzas' },
        conversation: conversationFixture(),
      }),
    );
    const block = within(await screen.findByTestId('conversation'));
    expect(block.getByText('Posible oportunidad · ProjectApp')).toBeOnTheScreen();
    expect(block.getByText('Espera tu respuesta')).toBeOnTheScreen();
    expect(block.getByText('Oportunidad 86 % · Espera respuesta 81 % · Venta o spam 4 %')).toBeOnTheScreen();
    const messages = within(block.getByTestId('messages'));
    expect(messages.getAllByTestId(/^message-/)).toHaveLength(3);
    expect(within(messages.getByTestId('message-m-1')).getByText('Tú · 5 oct')).toBeOnTheScreen();
    expect(within(messages.getByTestId('message-m-3')).getByText('Lucía Ficticia · 6 oct')).toBeOnTheScreen();
    expect(within(messages.getByTestId('message-m-3')).getByText(/¿tienes disponibilidad para un proyecto corto de IA en enero\?/)).toBeOnTheScreen();
    expect(block.getByText('La app nunca envía mensajes: respondes tú en LinkedIn.')).toBeOnTheScreen();
    await fireEvent.press(block.getByTestId('conversation-link'));
    expect(open).toHaveBeenLastCalledWith('https://www.linkedin.com/messaging/thread/2-SHVlcnRhTGFicw==/');
    expect(block.queryByRole('button')).toBeNull(); // read-only: nothing here answers

    expect(screen.getByTestId('next-step')).toHaveAccessibleName(/Siguiente paso · Te toca\. Te toca: responder su mensaje/);
    expect(screen.getByLabelText('En conversación, ahora, 5 oct')).toBeSelected();

    // «Marcar como oportunidad» takes the modality the team read in the conversation.
    await fireEvent.press(screen.getByText('Marcar como oportunidad'));
    const form = within(await screen.findByTestId('opportunity-form'));
    expect(form.getByRole('button', { name: 'Modalidad' })).toHaveAccessibilityValue({ text: 'ProjectApp' });
  });

  it('shows the next step and who it depends on, with the open action and Tu turno', async () => {
    await renderCard(
      contactFixture('c-1', {
        stage: 'followed',
        display_stage: 'followed',
        followed_at: '2026-11-05T15:00:00Z',
        next_step: { owner: 'equipo', text: 'El equipo la invitará cuando termine la espera', at: '2026-11-07T15:00:00Z', action: { id: 'a-1', capability: 'RED-02', state: 'approved' } },
        your_turn: true,
      }),
    );
    const next = await screen.findByTestId('next-step');
    expect(next).toHaveAccessibleName(/^Siguiente paso · Te toca\. El equipo la invitará cuando termine la espera\. Para el 7 nov\. Invitación sin nota · Aprobada$/);
    await fireEvent.press(screen.getByText('Ver en el Calendario'));
    expect(router.dismissTo).toHaveBeenLastCalledWith('/calendario');
    await fireEvent.press(screen.getByText('Ir a Tu turno'));
    expect(router.dismissTo).toHaveBeenLastCalledWith('/tu-turno');
  });

  it('adds a note and opens a voice note about the person in the capture sheet', async () => {
    const server = await renderCard(contactFixture('c-1'), {
      'POST /api/v1/red/contacts/c-1/notas': (request) => ({
        status: 201,
        body: contactFixture('c-1', { notes: [{ id: 'n-2', at: '2026-11-07T15:00:00Z', text: (request.body as { text: string }).text, by: 'gustavo' }] }),
      }),
    });
    expect(await screen.findByText('Aún no hay notas sobre esta persona.')).toBeOnTheScreen();

    await fireEvent.press(screen.getByText('Nota de voz'));
    expect(JSON.parse(screen.getByTestId('capture-probe').props.children)).toEqual({ tipo: 'persona', id: 'c-1', label: 'Lucía Ficticia' });

    await fireEvent.press(screen.getByText('Añadir nota'));
    expect(screen.getByRole('button', { name: 'Guardar nota' })).toBeDisabled();
    await fireEvent.changeText(screen.getByTestId('note-text'), 'Tiene presupuesto para Q1.');
    await fireEvent.press(screen.getByText('Guardar nota'));
    await waitFor(() => expect(server.find('POST', '/api/v1/red/contacts/c-1/notas')).toHaveLength(1));
    expect(server.find('POST', '/api/v1/red/contacts/c-1/notas')[0]!.body).toEqual({ text: 'Tiene presupuesto para Q1.' });
    expect(await screen.findByText('Nota guardada')).toBeOnTheScreen();
  });

  it('discards with a mandatory note, only in the allowed stages', async () => {
    const server = await renderCard(contactFixture('c-1'), {
      'POST /api/v1/red/contacts/c-1/discard': () => ({ body: contactFixture('c-1', { stage: 'discarded', display_stage: 'discarded' }) }),
    });
    await fireEvent.press(await screen.findByText('Descartar'));
    const sheet = within(await screen.findByTestId('confirm-sheet'));
    expect(sheet.getByText('Descartar a Lucía Ficticia')).toBeOnTheScreen();
    expect(sheet.getByText(/No volverá a proponerse/)).toBeOnTheScreen();
    expect(sheet.getByRole('button', { name: 'Descartar' })).toBeDisabled();
    await fireEvent.changeText(sheet.getByTestId('confirm-note'), 'No es comprador.');
    await fireEvent.press(sheet.getByRole('button', { name: 'Descartar' }));
    await waitFor(() => expect(server.find('POST', '/api/v1/red/contacts/c-1/discard')).toHaveLength(1));
    expect(server.find('POST', '/api/v1/red/contacts/c-1/discard')[0]!.body).toEqual({ note: 'No es comprador.' });
    expect(await screen.findByText('Descartada: no volverá a proponerse')).toBeOnTheScreen();
  });

  it('marks the person as an opportunity with the form prefilled', async () => {
    const server = await renderCard(contactFixture('c-1'), {
      'POST /api/v1/oportunidades': (request) => ({ status: 201, body: opportunityFixture('o-9', request.body as object) }),
    });
    await fireEvent.press(await screen.findByText('Marcar como oportunidad'));
    const form = within(await screen.findByTestId('opportunity-form'));
    expect(within(form.getByTestId('opp-picked')).getByText('Lucía Ficticia')).toBeOnTheScreen();
    expect(form.getByRole('button', { name: 'Modalidad' })).toHaveAccessibilityValue({ text: 'ProjectApp' });
    await fireEvent.press(form.getByRole('button', { name: 'Cómo llegó' }));
    await fireEvent.press(form.getByRole('radio', { name: 'Lo dijo la persona' }));
    await fireEvent.changeText(form.getByTestId('opp-need'), 'Un piloto de IA en enero.');
    await fireEvent.press(form.getByText('Registrar oportunidad'));
    await waitFor(() => expect(server.find('POST', '/api/v1/oportunidades')).toHaveLength(1));
    expect(server.find('POST', '/api/v1/oportunidades')[0]!.body).toMatchObject({ contact: 'c-1', modality: 'projectapp', attribution: 'lo_dijo', need: 'Un piloto de IA en enero.' });
  });

  it('shows the open opportunity and edits it', async () => {
    const contact = contactFixture('c-1', {
      stage: 'connected',
      display_stage: 'opportunity',
      opportunity: { id: 'o-1', stage: 'necesidad', stage_label: 'Necesidad identificada', modality: 'projectapp', next_action: 'Enviar la propuesta de piloto', next_action_at: '2026-11-12T17:00:00Z' },
      next_step: { owner: 'gustavo', text: 'Oportunidad: Necesidad identificada · Enviar la propuesta de piloto', at: '2026-11-12T17:00:00Z' },
    });
    const server = await renderCard(contact, {
      'GET /api/v1/oportunidades': page([opportunityFixture('o-1')]),
      'PATCH /api/v1/oportunidades/o-1': (request) => ({ body: opportunityFixture('o-1', request.body as object) }),
    });
    expect(within(await screen.findByTestId('persona-head')).getByText('Oportunidad')).toBeOnTheScreen();
    expect(screen.queryByText('Marcar como oportunidad')).toBeNull();
    expect(await screen.findByText('Decidir y construir una primera funcionalidad de IA.')).toBeOnTheScreen();
    expect(screen.getByText('LinkedIn')).toBeOnTheScreen();
    expect(screen.getByText('Citó un post o el perfil')).toBeOnTheScreen();
    expect(screen.getByText('1 día en esta etapa')).toBeOnTheScreen();
    expect(server.find('GET', '/api/v1/oportunidades')[0]!.path).toContain('contact=c-1');
    expect(screen.getByLabelText('Oportunidad, ahora, Necesidad identificada')).toBeOnTheScreen();

    await fireEvent.press(screen.getByText('Editar oportunidad'));
    const form = within(await screen.findByTestId('opportunity-form'));
    await fireEvent.press(form.getByRole('button', { name: 'Etapa' }));
    await fireEvent.press(form.getByRole('radio', { name: 'Reunión' }));
    await fireEvent.press(form.getByText('Guardar cambios'));
    await waitFor(() => expect(server.find('PATCH', '/api/v1/oportunidades/o-1')).toHaveLength(1));
    expect(server.find('PATCH', '/api/v1/oportunidades/o-1')[0]!.body).toMatchObject({ stage: 'reunion', contact: 'c-1' });
  });

  it('says when the person does not exist', async () => {
    await renderCard(null);
    expect(await screen.findByText('No encontramos a esta persona')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Volver a Personas'));
    expect(router.back).toHaveBeenCalled();
  });

  it('builds the journey of an incoming invitation and of a discarded person', () => {
    const incoming = journey(contactFixture('c-1', { source: 'incoming', stage: 'incoming' }));
    expect(incoming.map((s) => [s.label, s.state])).toEqual([
      ['Descubierta', 'done'],
      ['Te invitó', 'current'],
      ['Conectada', 'pending'],
      ['En conversación', 'pending'],
      ['Oportunidad', 'pending'],
    ]);
    const discarded = journey(contactFixture('c-1', { stage: 'discarded', history: [{ at: '2026-10-25T15:00:00Z', event: 'discarded', detail: 'No encaja' }] }));
    expect(discarded.map((s) => [s.label, s.state, s.date])).toEqual([
      ['Descubierta', 'done', '21 oct'],
      ['Descartada', 'alt', '25 oct'],
    ]);
  });
});
