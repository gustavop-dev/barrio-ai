// Tu turno: groups by priority, Nueva/Vista, «Más tarde», card actions with and without a note,
// empty, loading and error states, and the swipe actions.
import { APPROVAL_CARD, CONVERSATION_CARD, EXPIRING_CARD, questionCard, turnoFixture, UNCERTAIN_CARD } from '@compartido/fixtures/turno';
import { PROFILE_CARD, PROFILE_PROPOSAL } from '@compartido/fixtures/perfil';
import { EXPERIMENT_CARD, MONTHLY_CARD, REFERENTS_SETUP_CARD } from '@compartido/fixtures/referentes';
import type { TuTurno } from '@compartido/api/types';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import * as Haptics from 'expo-haptics';
import { fireGestureHandler, getByGestureTestId } from 'react-native-gesture-handler/jest-utils';
import { State } from 'react-native-gesture-handler';
import '@/api/transport';
import { renderApp } from '@/test/render';
import { fakeServer, type FakeHandler } from '@/test/server';
import { TuTurnoScreen } from './TuTurnoScreen';

function turno(overrides: Partial<TuTurno> = {}): TuTurno {
  return turnoFixture({ count: 3, critical: true, items: [UNCERTAIN_CARD, CONVERSATION_CARD, questionCard()], ...overrides });
}

async function renderTurno(data: TuTurno = turno(), extra: Record<string, FakeHandler> = {}) {
  const server = fakeServer({ 'GET /api/v1/tu-turno': { body: data }, 'POST /api/v1/tu-turno/vistos': { body: { count: 1 } }, ...extra });
  await renderApp(<TuTurnoScreen />);
  return server;
}

describe('Tu turno', () => {
  it('keeps referent setup, monthly decisions, experiments and the profile checklist together', async () => {
    const server = await renderTurno(turnoFixture({ count: 4, items: [REFERENTS_SETUP_CARD, MONTHLY_CARD, EXPERIMENT_CARD, PROFILE_CARD] }), {
      'GET /api/v1/operador/referents': { body: [] },
      'GET /api/v1/perfil/profile-qa': { body: PROFILE_PROPOSAL },
    });
    expect(await screen.findByText('Identificar los cinco referentes main')).toBeOnTheScreen();
    expect(screen.getByText('3 importantes · 1 cuando puedas')).toBeOnTheScreen();
    expect(screen.getByRole('header', { name: 'Importante · 3' })).toBeOnTheScreen();
    expect(screen.getByRole('header', { name: 'Cuando puedas · 1' })).toBeOnTheScreen();
    expect(screen.getByText('Aprobar sustitución')).toBeOnTheScreen();
    expect(screen.getByText('Aprobar experimento')).toBeOnTheScreen();
    expect(screen.getByTestId(`edit-${MONTHLY_CARD.id}`)).toBeOnTheScreen();
    expect(screen.getByTestId(`edit-${EXPERIMENT_CARD.id}`)).toBeOnTheScreen();
    await fireEvent.press(screen.getByTestId('profile-open'));
    expect(await screen.findByText('Checklist por sección')).toBeOnTheScreen();
    expect(screen.getByTestId('profile-section-headline')).toBeOnTheScreen();
    expect(screen.queryByText(/^Comprobado$/)).toBeNull();
    expect(server.find('GET', '/api/v1/perfil/profile-qa')).toHaveLength(1);
    expect(server.requests.filter((r) => r.method === 'POST' && r.path.endsWith('/decidir'))).toEqual([]);
  });

  it('shows a skeleton while loading, then the cards grouped Urgente → Importante → Cuando puedas', async () => {
    await renderTurno();
    expect(screen.getByLabelText('Cargando lo que depende de ti…')).toBeOnTheScreen();
    expect(await screen.findByText('Comprueba si salió tu comentario')).toBeOnTheScreen();
    expect(screen.getByText('1 urgente · 1 importante · 1 cuando puedas')).toBeOnTheScreen();
    expect(screen.getByRole('header', { name: 'Urgente · 1' })).toBeOnTheScreen();
    expect(screen.getByRole('header', { name: 'Importante · 1' })).toBeOnTheScreen();
    expect(screen.getByRole('header', { name: 'Cuando puedas · 1' })).toBeOnTheScreen();
    // Nueva on the new cards only.
    expect(within(screen.getByTestId(`turno-card-${UNCERTAIN_CARD.id}`)).getByText('Nueva')).toBeOnTheScreen();
    expect(within(screen.getByTestId('turno-card-question:q1')).queryByText('Nueva')).toBeNull();
  });

  it('shows the error with «Reintentar» when Tu turno cannot load', async () => {
    const server = await renderTurno(turno(), { 'GET /api/v1/tu-turno': { status: 500, body: { detail: 'Fallo del servidor.' } } });
    expect(await screen.findByText('Fallo del servidor.')).toBeOnTheScreen();
    server.on('GET /api/v1/tu-turno', { body: turno() });
    await fireEvent.press(screen.getByText('Reintentar'));
    expect(await screen.findByText('Comprueba si salió tu comentario')).toBeOnTheScreen();
  });

  it('says nothing depends on Gustavo when there is nothing, with what the team did today', async () => {
    await renderTurno(turnoFixture({ items: [], summary: { done_today: { posts: 1, comments: 6, reactions: 0, follows: 4, invites: 0, accepts: 0 }, next_piece: null } }));
    expect(await screen.findByText('Nada depende de ti hoy')).toBeOnTheScreen();
    expect(screen.getByText('Hoy el equipo publicó 1 post, comentó en 6 y siguió a 4 personas.')).toBeOnTheScreen();
  });

  it('says nothing depends on Gustavo when only expired cards are left, and still shows them under «Ya no es urgente»', async () => {
    const expired = questionCard({ id: 'q8', question: '¿Fuiste al meetup del martes?', expired: true }, { state: 'caducada', tone: 'muted' });
    await renderTurno(turno({ items: [], count: 0, critical: false, later: [expired] }));
    expect(await screen.findByText('Nada depende de ti hoy')).toBeOnTheScreen();
    expect(screen.getByRole('header', { name: 'Ya no es urgente · 1' })).toBeOnTheScreen();
    expect(screen.getByText('¿Fuiste al meetup del martes?')).toBeOnTheScreen();
  });

  it('«Más tarde» postpones a question and says when it comes back', async () => {
    const server = await renderTurno(turno(), { 'POST /api/v1/preguntas/q1/mas-tarde': { body: { id: 'q1', postponed_until: '2026-11-10T09:00:00-05:00' } } });
    await screen.findByText('Más tarde');
    await fireEvent.press(screen.getByText('Más tarde'));
    await waitFor(() => expect(server.find('POST', '/api/v1/preguntas/q1/mas-tarde')).toHaveLength(1));
    expect(await screen.findByText(/^Pospuesta\. Vuelve el /)).toBeOnTheScreen();
  });

  it('runs a direct card action with its toast, and refreshes Tu turno', async () => {
    const server = await renderTurno(turno(), { 'POST /api/v1/conversaciones/conv-1/cerrar': { body: {} } });
    await fireEvent.press(await screen.findByText('Hecho, respondí'));
    await waitFor(() => expect(server.find('POST', '/api/v1/conversaciones/conv-1/cerrar')[0]?.body).toEqual({ how: 'respondi' }));
    expect(await screen.findByText('Anotado: respondiste')).toBeOnTheScreen();
    await waitFor(() => expect(server.find('GET', '/api/v1/tu-turno').length).toBeGreaterThan(1));
  });

  it('approves an action that waits for Gustavo with its exact version, and vetoing asks for a note first', async () => {
    const server = await renderTurno(turno({ items: [APPROVAL_CARD], count: 1, critical: false }), {
      'POST /api/v1/operador/actions/a-1/approve': { status: 202, body: {} },
      'POST /api/v1/operador/actions/a-1/reject': { body: {} },
    });
    expect(await screen.findByText('¿Apruebas seguir a Laura Prueba?')).toBeOnTheScreen();
    expect(screen.getByText('Head of Product en un marketplace B2B')).toBeOnTheScreen();
    expect(screen.getByText('Lidera producto en un marketplace B2B.')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Vetar'));
    const sheet = await screen.findByTestId('confirm-sheet');
    expect(within(sheet).getByText('Vetar la acción')).toBeOnTheScreen();
    await fireEvent.press(within(sheet).getByText('Cancelar'));
    await fireEvent.press(screen.getByText('Aprobar'));
    await waitFor(() => expect(server.find('POST', '/api/v1/operador/actions/a-1/approve')[0]?.body).toEqual({ expected_hash: 'a'.repeat(64) }));
    expect(await screen.findByText('Aprobada. Sale cuando lo permitan la ventana y los topes.')).toBeOnTheScreen();
    expect(server.find('POST', '/api/v1/operador/actions/a-1/reject')).toHaveLength(0);
  });

  it('asks for a note before resolving an uncertain action and sends it', async () => {
    const server = await renderTurno(turno(), { 'POST /api/v1/operador/actions/a1/resolve': { body: { id: 'a1' } } });
    await fireEvent.press(await screen.findByText('Sí, se aplicó'));
    const sheet = await screen.findByTestId('confirm-sheet');
    expect(within(sheet).getByText('Confirmar que se aplicó')).toBeOnTheScreen();
    await fireEvent.changeText(within(sheet).getByTestId('confirm-note'), 'El comentario aparece en el post.');
    await fireEvent.press(within(sheet).getByText('Sí, se aplicó'));
    await waitFor(() =>
      expect(server.find('POST', '/api/v1/operador/actions/a1/resolve')[0]?.body).toEqual({ outcome: 'confirmed', note: 'El comentario aparece en el post.' }),
    );
    expect(await screen.findByText('Anotado: se aplicó')).toBeOnTheScreen();
  });

  it('opens LinkedIn reconnect in the browser (the PWA, cookie session) instead of calling the API', async () => {
    const { Linking } = require('react-native');
    const open = jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
    const server = await renderTurno(turnoFixture({ count: 1, items: [EXPIRING_CARD] }));
    await fireEvent.press(await screen.findByText('Reconectar LinkedIn'));
    expect(open).toHaveBeenCalledWith('https://office.projectapp.co/ajustes#linkedin');
    expect(server.requests.some((r) => r.path.startsWith('/api/v1/linkedin'))).toBe(false);
  });

  it('answers a yes/no question with its visibility and offers to undo', async () => {
    const server = await renderTurno(turnoFixture({ count: 1, items: [questionCard()] }), { 'POST /api/v1/preguntas/q1/responder': { body: { id: 'q1', state: 'answered' } } });
    await fireEvent.press(await screen.findByText('Sí'));
    await fireEvent.press(screen.getByTestId('answer-submit-q1'));
    await waitFor(() => expect(server.find('POST', '/api/v1/preguntas/q1/responder')[0]?.body).toEqual({ value: 'si', public_use: true }));
    expect(await screen.findByText('Guardado. El equipo ya puede usarlo')).toBeOnTheScreen();
    expect(screen.getByText('Deshacer')).toBeOnTheScreen();
  });

  it('switches to «Lo que el equipo sabe de ti»', async () => {
    const server = await renderTurno(turno(), { 'GET /api/v1/memoria/hechos': { body: [] } });
    await screen.findByText('Comprueba si salió tu comentario');
    await fireEvent.press(screen.getByText('Lo que el equipo sabe de ti'));
    expect(await screen.findByText('Aún no hay nada confirmado')).toBeOnTheScreen();
    expect(server.find('GET', '/api/v1/memoria/hechos')).toHaveLength(1);
  });
});

describe('Tu turno · swipe actions', () => {
  function swipe(testID: string, translationX: number) {
    fireGestureHandler(getByGestureTestId(`${testID}-swipe`), [
      { state: State.BEGAN, translationX: 0 },
      { state: State.ACTIVE, translationX: translationX / 2, velocityX: 0 },
      { state: State.ACTIVE, translationX, velocityX: 0 },
      { state: State.END, translationX, velocityX: 0 },
    ]);
  }

  it('swipe right on a conversation closes it («Hecho, respondí») with a haptic', async () => {
    const server = await renderTurno(turno(), { 'POST /api/v1/conversaciones/conv-1/cerrar': { body: {} } });
    await screen.findByText('Hecho, respondí');
    await act(async () => swipe(`turno-card-${CONVERSATION_CARD.id}`, 320));
    await waitFor(() => expect(server.find('POST', '/api/v1/conversaciones/conv-1/cerrar')).toHaveLength(1));
    expect(await screen.findByText('Anotado: respondiste')).toBeOnTheScreen();
    expect(Haptics.impactAsync).toHaveBeenCalled();
  });

  it('swipe left on a question postpones it («Más tarde»)', async () => {
    const server = await renderTurno(turno(), { 'POST /api/v1/preguntas/q1/mas-tarde': { body: { id: 'q1', postponed_until: null } } });
    await screen.findByText('Más tarde');
    await act(async () => swipe('turno-card-question:q1', -320));
    await waitFor(() => expect(server.find('POST', '/api/v1/preguntas/q1/mas-tarde')).toHaveLength(1));
    expect(await screen.findByText('Pospuesta 3 días')).toBeOnTheScreen();
  });

  it('a short swipe does nothing', async () => {
    const server = await renderTurno();
    await screen.findByText('Hecho, respondí');
    await act(async () => swipe(`turno-card-${CONVERSATION_CARD.id}`, 40));
    expect(server.find('POST', '/api/v1/conversaciones/conv-1/cerrar')).toHaveLength(0);
  });

  it('swipe right on an action that needs a note opens its sheet first', async () => {
    const server = await renderTurno();
    await screen.findByText('Sí, se aplicó');
    await act(async () => swipe(`turno-card-${UNCERTAIN_CARD.id}`, 320));
    expect(await screen.findByTestId('confirm-sheet')).toBeOnTheScreen();
    expect(server.find('POST', '/api/v1/operador/actions/a1/resolve')).toHaveLength(0);
  });

  it('screen readers get the same swipe actions', async () => {
    const server = await renderTurno(turno(), { 'POST /api/v1/preguntas/q1/mas-tarde': { body: { id: 'q1' } } });
    await screen.findByText('Más tarde');
    const card = screen.getByTestId('turno-card-question:q1');
    expect(card.props.accessibilityActions).toEqual([{ name: 'swipeLeft', label: 'Más tarde' }]);
    await fireEvent(card, 'accessibilityAction', { nativeEvent: { actionName: 'swipeLeft' } });
    await waitFor(() => expect(server.find('POST', '/api/v1/preguntas/q1/mas-tarde')).toHaveLength(1));
  });
});
