import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { keys } from '../api/queryClient';
import type { MemoryFact, TuTurno } from '../api/types';
import { CaptureProvider } from '../capture/CaptureContext';
import { turnoAnchor } from '../components/Layout';
import { fakeServer, SESSION_OK, type Handler, type Reply } from '../test/fakeServer';
import { cardFixture, CONVERSATION_CARD, dayAt, EXPIRING_CARD, factFixture, hoursFromNow, questionCard, questionFixture, turnoFixture as tuTurnoFixture, UNCERTAIN_CARD } from '../test/fixtures/turno';
import { renderAt } from '../test/render';
import { TuTurno as TuTurnoPage } from './TuTurno';

/** The view alone (with the capture spy), so other screens being built do not get in the way. */
function renderApp(path: string) {
  const onCapture = vi.fn();
  const page = (
    <CaptureProvider onCapture={onCapture}>
      <TuTurnoPage />
    </CaptureProvider>
  );
  const utils = renderAt(path, [
    { path: '/tu-turno', element: page },
    { path: '/tu-turno/sabe', element: page },
    { path: '/calendario', element: <p>Calendario</p> },
  ]);
  return { ...utils, onCapture };
}

function server(turno: TuTurno, extra: Record<string, Handler | Reply> = {}) {
  return fakeServer({
    'GET /api/v1/auth/session': { body: SESSION_OK },
    'GET /api/v1/tu-turno': { body: turno },
    'POST /api/v1/tu-turno/vistos': ({ body }) => ({ body: { count: (body as { ids: string[] }).ids.length } }),
    ...extra,
  });
}

const QUESTION = questionCard({}, { state: 'nueva' });

function busyTurno(overrides: Partial<TuTurno> = {}): TuTurno {
  return tuTurnoFixture({
    count: 3,
    critical: true,
    urgent_count: 1,
    alerts: [UNCERTAIN_CARD, EXPIRING_CARD],
    questions: [QUESTION],
    items: [UNCERTAIN_CARD, EXPIRING_CARD, QUESTION],
    ...overrides,
  });
}

async function cardTitled(name: string | RegExp) {
  const heading = await screen.findByRole('heading', { name, level: 3 });
  return heading.closest('article') as HTMLElement;
}

describe('Tu turno · Pendiente', () => {
  it('groups the cards Urgente → Importante → Cuando puedas, each with its label and «NUEVA»', async () => {
    server(busyTurno());
    renderApp('/tu-turno');

    expect(await screen.findByText('1 urgente · 1 importante · 1 cuando puedas')).toBeInTheDocument();
    const labels = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(labels).toEqual(['Urgente · 1', 'Importante · 1', 'Cuando puedas · 1']);

    const urgent = await cardTitled('Comprueba si salió tu comentario');
    expect(urgent).toHaveClass('tone-bad');
    expect(urgent).toHaveAttribute('id', turnoAnchor('uncertain:a1'));
    expect(within(urgent).getByText('Urgente')).toBeInTheDocument();
    expect(within(urgent).getByText('Nueva')).toBeInTheDocument();

    const important = await cardTitled('Reconecta LinkedIn');
    expect(within(important).getByText('Importante')).toBeInTheDocument();
    expect(within(important).queryByText('Nueva')).not.toBeInTheDocument();
    expect(within(important).getByText(/^Plazo: antes del/)).toBeInTheDocument();

    const question = await cardTitled(QUESTION.question!.question);
    expect(within(question).getByText('Cuando puedas')).toBeInTheDocument();
    expect(screen.getByText(/Lo que respondas pasa a la memoria confirmada/)).toBeInTheDocument();
  });

  it('marks the new cards as seen in one batched call, and keeps «NUEVA» for the visit', async () => {
    const api = server(busyTurno());
    const { client } = renderApp('/tu-turno');
    await cardTitled('Comprueba si salió tu comentario');

    await waitFor(() => expect(api.find('POST', '/api/v1/tu-turno/vistos')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/tu-turno/vistos')[0]!.body).toEqual({ ids: ['uncertain:a1', 'question:q1'] });

    // The next refresh brings them as «vista»: the tag stays while the view is open, with no new call.
    api.on('GET /api/v1/tu-turno', {
      body: busyTurno({ items: [{ ...UNCERTAIN_CARD, state: 'vista' }, EXPIRING_CARD, { ...QUESTION, state: 'vista' }] }),
    });
    await client.refetchQueries({ queryKey: keys.tuTurno });
    expect(client.getQueryData<TuTurno>(keys.tuTurno)?.items?.[0]?.state).toBe('vista');
    const urgent = await cardTitled('Comprueba si salió tu comentario');
    expect(within(urgent).getByText('Nueva')).toBeInTheDocument();
    expect(within(await cardTitled(QUESTION.question!.question)).getByText('Nueva')).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 1500));
    expect(api.find('POST', '/api/v1/tu-turno/vistos')).toHaveLength(1);
  });

  it('shows what an uncertain action tried and asks what was checked before resolving it', async () => {
    const api = server(busyTurno(), {
      'POST /api/v1/operador/actions/a1/resolve': { body: { id: 'a1', state: 'confirmed' } },
    });
    renderApp('/tu-turno');
    const card = await cardTitled('Comprueba si salió tu comentario');

    expect(within(card).getByText(/^Comentario en el post de Pablo Ficticio · /)).toBeInTheDocument();
    expect(within(card).getByText(/Scoping from the decision/)).toBeInTheDocument();
    expect(within(card).getByRole('link', { name: /Ver en LinkedIn/ })).toHaveAttribute('href', UNCERTAIN_CARD.attempt!.url);
    expect(within(card).getByText('Creada hace 14 h')).toBeInTheDocument();

    await userEvent.click(within(card).getByRole('button', { name: 'Sí, se aplicó' }));
    const dialog = screen.getByRole('dialog', { name: 'Confirmar que se aplicó' });
    const confirm = within(dialog).getByRole('button', { name: 'Sí, se aplicó' });
    expect(confirm).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText(/Qué comprobaste/), 'Aparece en el post');
    await userEvent.click(confirm);

    await waitFor(() => expect(api.find('POST', '/api/v1/operador/actions/a1/resolve')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/operador/actions/a1/resolve')[0]!.body).toEqual({ outcome: 'confirmed', note: 'Aparece en el post' });
    expect(await screen.findByText('Anotado: se aplicó')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows a conversation that is his turn, opens the opportunity form prefilled and closes it with an optional reason', async () => {
    const api = server(busyTurno({ items: [CONVERSATION_CARD], alerts: [], questions: [], tasks: { perfil: [], conversaciones: [CONVERSATION_CARD] } }), {
      'GET /api/v1/red/contacts': { body: { count: 0, next: null, previous: null, results: [] } },
      'POST /api/v1/oportunidades': ({ body }) => ({ status: 201, body: { id: 'o-9', ...(body as object) } }),
      'POST /api/v1/conversaciones/conv-1/cerrar': { body: { id: 'conv-1', needs_you: false } },
    });
    renderApp('/tu-turno');
    const card = await cardTitled('Lucía Ficticia te escribió');
    const view = within(card);

    expect(view.getByText('Conversación')).toBeInTheDocument();
    expect(view.getByText('Importante')).toBeInTheDocument();
    expect(view.getByText('Conversaciones e inbox')).toBeInTheDocument();
    expect(view.getByRole('link', { name: 'Lucía Ficticia' })).toHaveAttribute('href', '/personas/c-1');
    expect(view.getByText('Cofundadora @ Huerta Labs (pre-seed)')).toBeInTheDocument();
    expect(view.getByText('Comprador')).toBeInTheDocument();
    expect(view.getByText('Por qué importa')).toBeInTheDocument();
    expect(view.getByText('Posible oportunidad: ProjectApp (86 %) · Espera tu respuesta (81 %)')).toBeInTheDocument();
    expect(view.getByText(/^Último mensaje · hoy, /)).toBeInTheDocument();
    expect(view.getByText(/¿tienes disponibilidad para un proyecto corto de IA en enero\?/)).toBeInTheDocument();
    expect(view.queryByText(/Happy to share/)).not.toBeInTheDocument();  // only his last message
    expect(view.getByText('La app nunca envía mensajes: respondes tú en LinkedIn.')).toBeInTheDocument();
    const open = view.getByRole('link', { name: 'Abrir en LinkedIn' });
    expect(open).toHaveAttribute('href', 'https://www.linkedin.com/messaging/thread/2-SHVlcnRhTGFicw==/');
    expect(open).toHaveAttribute('target', '_blank');

    await userEvent.click(view.getByRole('button', { name: 'Marcar como oportunidad' }));
    const form = within(screen.getByRole('dialog', { name: 'Nueva oportunidad' }));
    expect(form.getByText('Lucía Ficticia')).toBeInTheDocument();
    expect(form.getByLabelText('Modalidad')).toHaveValue('projectapp');
    expect(form.getByLabelText('Canal')).toHaveValue('linkedin');
    expect(form.getByLabelText(/Notas/)).toHaveValue('Detectada por el equipo en una conversación de LinkedIn.');
    expect(api.find('POST', '/api/v1/oportunidades')).toHaveLength(0);  // nothing is created until he saves it
    await userEvent.selectOptions(form.getByLabelText('Cómo llegó'), 'lo_dijo');
    await userEvent.click(form.getByRole('button', { name: 'Registrar oportunidad' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/oportunidades')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/oportunidades')[0]!.body).toMatchObject({
      contact: 'c-1',
      modality: 'projectapp',
      channel: 'linkedin',
      attribution: 'lo_dijo',
      notes: 'Detectada por el equipo en una conversación de LinkedIn.',
    });
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());

    await userEvent.click(view.getByRole('button', { name: 'No responder' }));
    const ask = within(screen.getByRole('dialog', { name: 'No responder' }));
    expect(ask.getByText(/Nadie le responde por ti/)).toBeInTheDocument();
    await userEvent.type(ask.getByLabelText(/Motivo/), 'Lo hablamos por teléfono');
    await userEvent.click(ask.getByRole('button', { name: 'No responder' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/conversaciones/conv-1/cerrar')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/conversaciones/conv-1/cerrar')[0]!.body).toEqual({ how: 'no_responder', note: 'Lo hablamos por teléfono' });
    expect(await screen.findByText('Anotado: no responderás')).toBeInTheDocument();

    await userEvent.click(view.getByRole('button', { name: 'Hecho, respondí' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/conversaciones/conv-1/cerrar')).toHaveLength(2));
    expect(api.find('POST', '/api/v1/conversaciones/conv-1/cerrar')[1]!.body).toEqual({ how: 'respondi' });
  });

  it('reconnects LinkedIn with a full navigation and resumes the machine with an optional reason', async () => {
    const paused = cardFixture({
      id: 'machine_paused',
      critical: true,
      tone: 'bad',
      title: 'Reanuda la máquina',
      body: 'Revisando los topes de la semana',
      priority: 'urgente',
      state: 'vista',
      actions: [{ label: 'Reanudar', endpoint: '/api/v1/operador/control', body: { paused: false }, note_required: false, primary: true }],
    });
    const api = server(busyTurno({ items: [paused, EXPIRING_CARD] }), { 'POST /api/v1/operador/control': { body: { paused: false } } });
    renderApp('/tu-turno');

    const linkedin = await cardTitled('Reconecta LinkedIn');
    expect(within(linkedin).getByRole('link', { name: 'Reconectar LinkedIn' })).toHaveAttribute('href', '/api/v1/linkedin/oauth/start');

    const machine = await cardTitled('Reanuda la máquina');
    await userEvent.click(within(machine).getByRole('button', { name: 'Reanudar' }));
    const dialog = screen.getByRole('dialog', { name: 'Reanudar la máquina' });
    await userEvent.type(within(dialog).getByLabelText(/Motivo/), 'Topes revisados');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Reanudar' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/operador/control')[0]?.body).toEqual({ paused: false, reason: 'Topes revisados' }));
    expect(await screen.findByText('Máquina reanudada')).toBeInTheDocument();
  });

  it('answers a yes/no question with its detail and visibility, then undoes it from the toast', async () => {
    const api = server(busyTurno(), {
      'POST /api/v1/preguntas/q1/responder': { body: questionFixture({ state: 'answered' }) },
      'POST /api/v1/preguntas/q1/deshacer': { body: questionFixture() },
    });
    renderApp('/tu-turno');
    const card = await cardTitled(QUESTION.question!.question);

    expect(within(card).getByText(/Para el post del jueves/)).toBeInTheDocument();
    const answer = within(card).getByRole('button', { name: 'Responder' });
    expect(answer).toBeDisabled();
    // The suggestion comes preselected.
    expect(within(card).getByRole('radio', { name: /Público/ })).toBeChecked();

    await userEvent.click(within(card).getByRole('radio', { name: 'Sí' }));
    await userEvent.type(within(card).getByLabelText('Detalle (opcional)'), 'En 2023, en Rumbo');
    await userEvent.click(within(card).getByRole('radio', { name: /Privado/ }));
    await userEvent.click(answer);

    await waitFor(() => expect(api.find('POST', '/api/v1/preguntas/q1/responder')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/preguntas/q1/responder')[0]!.body).toEqual({ value: 'si', text: 'En 2023, en Rumbo', public_use: false });
    expect(await screen.findByText('Guardado. El equipo ya puede usarlo')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Deshacer' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/preguntas/q1/deshacer')).toHaveLength(1));
    expect(await screen.findByText('Respuesta deshecha. La pregunta vuelve a estar abierta')).toBeInTheDocument();
  });

  it('renders every answer type and sends its value', async () => {
    const choice = questionCard({ id: 'q2', question: '¿Aceptas proyectos de 3 meses?', answer_type: 'choice', options: ['Sí', 'No'], suggested_public: false });
    const number = questionCard({ id: 'q3', question: '¿Cuántos clientes tienes?', answer_type: 'number' });
    const date = questionCard({ id: 'q4', question: '¿Cuándo empezaste?', answer_type: 'date' });
    const text = questionCard({ id: 'q5', question: '¿Qué temas no quieres tocar?', answer_type: 'text' });
    const api = server(busyTurno({ items: [choice, number, date, text] }), {
      'POST /api/v1/preguntas/q2/responder': { body: {} },
      'POST /api/v1/preguntas/q3/responder': { body: {} },
      'POST /api/v1/preguntas/q4/responder': { body: {} },
      'POST /api/v1/preguntas/q5/responder': { body: {} },
    });
    renderApp('/tu-turno');

    const choiceCard = await cardTitled('¿Aceptas proyectos de 3 meses?');
    expect(within(choiceCard).getByRole('radio', { name: /Privado/ })).toBeChecked();
    await userEvent.selectOptions(within(choiceCard).getByLabelText('Elige una opción'), 'No');
    await userEvent.click(within(choiceCard).getByRole('button', { name: 'Responder' }));

    const numberCard = await cardTitled('¿Cuántos clientes tienes?');
    await userEvent.type(within(numberCard).getByLabelText('Tu respuesta'), '12');
    await userEvent.click(within(numberCard).getByRole('button', { name: 'Responder' }));

    const dateCard = await cardTitled('¿Cuándo empezaste?');
    await userEvent.type(within(dateCard).getByLabelText('Tu respuesta'), '2019-03-01');
    await userEvent.click(within(dateCard).getByRole('button', { name: 'Responder' }));

    const textCard = await cardTitled('¿Qué temas no quieres tocar?');
    await userEvent.type(within(textCard).getByLabelText('Tu respuesta'), 'Política');
    await userEvent.click(within(textCard).getByRole('button', { name: 'Responder' }));

    await waitFor(() => expect(api.find('POST', '/api/v1/preguntas/q5/responder')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/preguntas/q2/responder')[0]!.body).toEqual({ value: 'No', public_use: false });
    expect(api.find('POST', '/api/v1/preguntas/q3/responder')[0]!.body).toEqual({ value: '12', public_use: true });
    expect(api.find('POST', '/api/v1/preguntas/q4/responder')[0]!.body).toEqual({ value: '2019-03-01', public_use: true });
    expect(api.find('POST', '/api/v1/preguntas/q5/responder')[0]!.body).toEqual({ text: 'Política', public_use: true });
  });

  it('postpones, declines after confirming, and opens the capture tied to the question', async () => {
    const api = server(busyTurno(), {
      'POST /api/v1/preguntas/q1/mas-tarde': { body: questionFixture({ postponed_until: dayAt(3, 9) }) },
      'POST /api/v1/preguntas/q1/no-compartir': { body: questionFixture({ state: 'declined' }) },
    });
    const { onCapture } = renderApp('/tu-turno');
    const card = await cardTitled(QUESTION.question!.question);

    await userEvent.click(within(card).getByRole('button', { name: 'Responder con audio' }));
    expect(onCapture).toHaveBeenCalledWith({ tipo: 'pregunta', id: 'q1', label: QUESTION.question!.question });

    await userEvent.click(within(card).getByRole('button', { name: 'Más tarde' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/preguntas/q1/mas-tarde')).toHaveLength(1));
    expect(await screen.findByText(/^Pospuesta\. Vuelve el /)).toBeInTheDocument();

    await userEvent.click(within(card).getByRole('button', { name: 'No quiero compartir esto' }));
    const dialog = screen.getByRole('dialog', { name: 'No compartir esto' });
    expect(api.find('POST', '/api/v1/preguntas/q1/no-compartir')).toHaveLength(0);
    await userEvent.click(within(dialog).getByRole('button', { name: 'No quiero compartirlo' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/preguntas/q1/no-compartir')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/preguntas/q1/responder')).toHaveLength(0);
  });

  it('folds the postponed cards, the expired ones in a neutral tone, what was done and how it is ordered', async () => {
    const postponed = questionCard(
      { id: 'q7', agent: 'perfil', agent_label: 'Perfil', question: '¿Qué temas no quieres tocar en público?', postponed_until: dayAt(2, 9), pending: false },
      { state: 'pospuesta' },
    );
    const expired = questionCard({ id: 'q8', question: '¿Cuál fue tu primer cliente con IA?', expired: true, deadline: hoursFromNow(-5) }, { tone: 'muted', state: 'caducada' });
    server(
      busyTurno({
        later: [postponed, expired],
        recent: [{ kind: 'question', id: 'q0', title: '¿En qué idioma van tus textos públicos?', at: hoursFromNow(-50), how: 'Respondida' }],
      }),
    );
    renderApp('/tu-turno');

    const old = await cardTitled('¿Cuál fue tu primer cliente con IA?');
    expect(within(old).getByText('Ya no es urgente, pero sigue siendo útil.')).toBeInTheDocument();
    expect(within(old).getByText('Caducada')).toBeInTheDocument();
    expect(old).not.toHaveClass('tone-bad');

    const fold = screen.getByText('Pospuestas · 1').closest('details')!;
    expect(fold).not.toHaveAttribute('open');
    expect(within(fold).getByText('Responde a Perfil: ¿Qué temas no quieres tocar en público?')).toBeInTheDocument();
    expect(within(fold).getByText(/^Vuelve el .* · no cuenta en el contador$/)).toBeInTheDocument();

    const done = screen.getByText('Hecho recientemente · 1').closest('details')!;
    expect(within(done).getByText('¿En qué idioma van tus textos públicos?')).toBeInTheDocument();
    expect(within(done).getByText('Respondida')).toBeInTheDocument();
    expect(screen.getByText('Cómo se ordena lo que depende de ti')).toBeInTheDocument();
  });

  it('says that nothing depends on him, with the day so far and the Calendario', async () => {
    server(
      tuTurnoFixture({
        summary: { done_today: { posts: 1, comments: 6, follows: 4 } as TuTurno['summary']['done_today'], next_piece: null },
      }),
    );
    renderApp('/tu-turno');
    expect(await screen.findByText('Nada depende de ti hoy')).toBeInTheDocument();
    expect(screen.getByText('Hoy el equipo publicó 1 post, comentó en 6 y siguió a 4 personas.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver el Calendario' })).toHaveAttribute('href', '/calendario');
    expect(screen.queryByText('Cómo se ordena lo que depende de ti')).not.toBeInTheDocument();
  });

  it('works with the older payload: no items, priority nor state', async () => {
    const legacyAlert = { ...UNCERTAIN_CARD, priority: undefined, state: undefined };
    const legacyQuestion = { ...questionCard({ deadline: hoursFromNow(20) }), priority: undefined, state: undefined };
    const api = server(tuTurnoFixture({ count: 2, critical: true, alerts: [legacyAlert], questions: [legacyQuestion] }));
    renderApp('/tu-turno');

    expect(await screen.findByText('1 urgente · 1 importante')).toBeInTheDocument();
    const question = await cardTitled(QUESTION.question!.question);
    expect(within(question).getByText(/^Útil antes de/)).toHaveClass('soon');
    expect(screen.queryByText('Nueva')).not.toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 1500));
    expect(api.find('POST', '/api/v1/tu-turno/vistos')).toHaveLength(0);
  });

  it('shows the error with Reintentar when Tu turno does not load', async () => {
    server(tuTurnoFixture(), { 'GET /api/v1/tu-turno': { status: 500, body: { detail: 'Fallo del servidor' } } });
    renderApp('/tu-turno');
    expect(await screen.findByText('Fallo del servidor')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
  });
});

describe('Tu turno · Lo que el equipo sabe de ti', () => {
  const facts: MemoryFact[] = [
    factFixture(),
    factFixture({
      key: 'nota.empresa',
      topic: 'Empresa',
      text: 'Founder de ProjectApp.',
      edits: 2,
      origin: { kind: 'manual' },
      updated_at: hoursFromNow(-200),
    }),
    factFixture({
      key: 'experiencia.migracion',
      topic: 'Migraciones',
      text: 'Lideró una migración en 2023.',
      public_use: false,
      origin: { kind: 'question', agent: 'director_editorial', agent_label: 'Director editorial' },
      updated_at: hoursFromNow(-300),
    }),
  ];

  it('switches tabs by URL and lists each fact with its visibility, origin and version', async () => {
    server(tuTurnoFixture(), { 'GET /api/v1/memoria/hechos': { body: facts } });
    renderApp('/tu-turno');
    await userEvent.click(await screen.findByRole('tab', { name: 'Lo que el equipo sabe de ti' }));
    expect(screen.getByTestId('location')).toHaveTextContent('/tu-turno/sabe');
    expect(screen.getByRole('tab', { name: 'Lo que el equipo sabe de ti' })).toHaveAttribute('aria-selected', 'true');

    const language = (await screen.findByRole('heading', { name: 'Idioma de los textos públicos' })).closest('li')!;
    expect(within(language).getByText('Público')).toBeInTheDocument();
    expect(within(language).getByText(/^Respondiste a Perfil · /)).toBeInTheDocument();

    const company = screen.getByRole('heading', { name: 'Empresa' }).closest('li')!;
    expect(within(company).getByText(/^Lo añadiste tú · .* · v2$/)).toBeInTheDocument();

    const migration = screen.getByRole('heading', { name: 'Migraciones' }).closest('li')!;
    expect(within(migration).getByText('Privado')).toBeInTheDocument();
    expect(within(migration).getByText(/^Respondiste al Director editorial · /)).toBeInTheDocument();
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();
  });

  it('edits, retires after confirming and adds a fact', async () => {
    const api = server(tuTurnoFixture(), {
      'GET /api/v1/memoria/hechos': { body: facts },
      'POST /api/v1/memoria/hechos/nota.empresa/corregir': { body: facts[1] },
      'POST /api/v1/memoria/hechos/experiencia.migracion/retirar': { body: facts },
      'POST /api/v1/memoria/hechos': { status: 201, body: facts },
    });
    renderApp('/tu-turno/sabe');

    await userEvent.click(await screen.findByRole('button', { name: 'Editar: Empresa' }));
    let dialog = screen.getByRole('dialog', { name: 'Editar lo que sabe el equipo' });
    const text = within(dialog).getByLabelText('Texto');
    await userEvent.clear(text);
    await userEvent.type(text, 'Founder y CEO de ProjectApp.');
    await userEvent.click(within(dialog).getByRole('radio', { name: /Privado/ }));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/memoria/hechos/nota.empresa/corregir')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/memoria/hechos/nota.empresa/corregir')[0]!.body).toEqual({ text: 'Founder y CEO de ProjectApp.', public_use: false });
    expect(await screen.findByText('Guardado como v3')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Retirar: Migraciones' }));
    dialog = screen.getByRole('dialog', { name: 'Retirar este dato' });
    expect(api.find('POST', '/api/v1/memoria/hechos/experiencia.migracion/retirar')).toHaveLength(0);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Retirar' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/memoria/hechos/experiencia.migracion/retirar')).toHaveLength(1));
    expect(await screen.findByText('Retirado. El equipo ya no lo usará')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Añadir algo que quieras que sepan' }));
    dialog = screen.getByRole('dialog', { name: 'Añadir algo que quieras que sepan' });
    await userEvent.type(within(dialog).getByLabelText('Qué quieres que sepan'), 'No trabajo con apuestas.');
    await userEvent.type(within(dialog).getByLabelText(/Tema/), 'Límites');
    expect(within(dialog).getByRole('radio', { name: /Privado/ })).toBeChecked();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/memoria/hechos')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/memoria/hechos')[0]!.body).toEqual({ text: 'No trabajo con apuestas.', public_use: false, topic: 'Límites' });
  });

  it('searches when there are more than 20 facts', async () => {
    const many = Array.from({ length: 21 }, (_, index) =>
      factFixture({ key: `k${index}`, topic: `Tema ${index}`, text: index === 7 ? 'Trabajó en Ñandú Pagos' : `Dato ${index}` }),
    );
    server(tuTurnoFixture(), { 'GET /api/v1/memoria/hechos': { body: many } });
    renderApp('/tu-turno/sabe');
    const search = await screen.findByRole('searchbox', { name: 'Buscar en lo que sabe el equipo' });
    await userEvent.type(search, 'nandu');
    expect(screen.getByText('1 de 21')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Tema 7' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Tema 8' })).not.toBeInTheDocument();
  });

  it('explains that nobody will invent anything while there is nothing confirmed', async () => {
    server(tuTurnoFixture(), { 'GET /api/v1/memoria/hechos': { body: [] } });
    renderApp('/tu-turno/sabe');
    expect(await screen.findByText('Aún no hay nada confirmado')).toBeInTheDocument();
    expect(screen.getByText(/responde las preguntas del equipo para que puedan usarlas/)).toBeInTheDocument();
  });
});
