// Calendario: the week strip and its panel, swiping weeks, the day sheet, the views, the layers, the
// veto with «Deshacer», the states (far future, error, empty month, Horas de Bogotá) and Lista.
import type { Actividad, Calendario } from '@compartido/api/types';
import { actividadFixture, calendarioFixture, NOW, piece, shellOverview, WEEK_DAYS } from '@compartido/fixtures/calendario';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import * as Haptics from 'expo-haptics';
import { State } from 'react-native-gesture-handler';
import { fireGestureHandler, getByGestureTestId } from 'react-native-gesture-handler/jest-utils';
import '@/api/transport';
import { renderApp } from '@/test/render';
import { fakeServer, type FakeHandler, type SentRequest } from '@/test/server';
import * as motion from '@/theme/motion';
import { CalendarioScreen } from './CalendarioScreen';
import { cancelVeto, flushVetoes } from './pendingVeto';

const expoRouter = jest.requireMock('expo-router') as {
  router: Record<string, jest.Mock>;
  __state: { params: Record<string, string>; pathname: string };
};

function search(request: SentRequest): URLSearchParams {
  return new URLSearchParams(request.path.split('?')[1] ?? '');
}

function server(routes: Record<string, FakeHandler> = {}, calendar: (desde: string, hasta: string) => Calendario = (d, h) => calendarioFixture(d, h, WEEK_DAYS)) {
  return fakeServer({
    'GET /api/v1/tu-turno': { body: { count: 0, items: [] } },
    'GET /api/v1/operador/overview': { body: shellOverview() },
    'GET /api/v1/calendario': (request) => ({ body: calendar(search(request).get('desde') ?? '', search(request).get('hasta') ?? '') }),
    'GET /api/v1/actividad': { body: actividadFixture() },
    'GET /api/v1/editorial/pieces/p7': { body: piece() },
    'GET /api/v1/editorial/pieces/p8': {
      body: piece({ id: 'p8', slot_date: '2026-11-08', scheduled_for: '2026-11-08T14:00:00Z', status: 'scheduled', thesis: 'Turning a sales call into a product spec.', action: { id: 'act-8', state: 'approved', payload_hash: 'h' }, metrics: null }),
    },
    'GET /api/v1/editorial/pieces/p4': { body: piece({ id: 'p4', slot_date: '2026-11-04', status: 'skipped', state: 'skipped', thesis: null }) },
    'GET /api/v1/editorial/pieces/p2': { body: piece({ id: 'p2', slot_date: '2026-11-02' }) },
    'GET /api/v1/editorial/pieces/p6': { body: piece({ id: 'p6', slot_date: '2026-11-06', status: 'blocked' }) },
    ...routes,
  });
}

async function renderCalendario(params: Record<string, string> = {}) {
  expoRouter.__state.params = params;
  return renderApp(<CalendarioScreen />);
}

const panel = () => screen.getByTestId('panel-dia');
const hidden = { includeHiddenElements: true };
const sheet = () => screen.getByTestId('hoja-dia');
const lastParams = () => expoRouter.router.setParams!.mock.calls.at(-1)?.[0];

/** Lays the pager out (no layout pass under Jest), then drags it. */
async function swipe(testID: string, translationX: number) {
  await fireEvent(screen.getByTestId(testID), 'layout', { nativeEvent: { layout: { x: 0, y: 0, width: 358, height: 80 } } });
  await act(async () => {
    fireGestureHandler(getByGestureTestId(`${testID}-swipe`), [
      { state: State.BEGAN, translationX: 0 },
      { state: State.ACTIVE, translationX: translationX / 2, velocityX: 0 },
      { state: State.ACTIVE, translationX, velocityX: 0 },
      { state: State.END, translationX, velocityX: 0 },
    ]);
  });
}

beforeEach(() => {
  jest.useFakeTimers({
    now: NOW,
    doNotFake: ['hrtime', 'nextTick', 'performance', 'queueMicrotask', 'requestAnimationFrame', 'cancelAnimationFrame', 'requestIdleCallback', 'cancelIdleCallback', 'setImmediate', 'clearImmediate', 'setInterval', 'clearInterval', 'setTimeout', 'clearTimeout'],
  });
  expoRouter.router.setParams = jest.fn();
  expoRouter.__state.pathname = '/calendario';
  // Bogotá's offset, so «Horas de Bogotá» only shows where a test asks for it.
  jest.spyOn(Date.prototype, 'getTimezoneOffset').mockReturnValue(300);
});

afterEach(async () => {
  await flushVetoes();
  jest.useRealTimers();
  expoRouter.__state.params = {};
  expoRouter.__state.pathname = '/';
});

describe('Calendario · semana', () => {
  it('shows the week strip and today’s panel by default', async () => {
    const api = server();
    await renderCalendario();
    expect(screen.getByText('Calendario')).toBeOnTheScreen();
    expect(screen.getByText('2–8 nov 2026')).toBeOnTheScreen();
    expect(screen.queryByText(/Horas de Bogotá/)).toBeNull();
    const today = await screen.findByTestId('dia-2026-11-07');
    expect(today.props.accessibilityState).toMatchObject({ selected: true });
    await waitFor(() => expect(screen.getByTestId('dia-2026-11-07').props.accessibilityLabel).toBe('Sábado 7 de noviembre, hoy, Tuyo, Publicaciones, Conversaciones, Red'));
    expect(search(api.find('GET', '/api/v1/calendario')[0]!).toString()).toBe('desde=2026-11-02&hasta=2026-11-08');

    const day = panel();
    expect(within(day).getByText('Sábado 7 de noviembre')).toBeOnTheScreen();
    expect(within(day).getByText('Hoy')).toBeOnTheScreen();
    expect(within(day).getByText('6 comentarios')).toBeOnTheScreen();
    expect(within(day).getByText('1 conexión nueva que encaja')).toBeOnTheScreen();

    const tuParte = within(day).getByTestId('bloque-tu-parte');
    expect(within(tuParte).getByText('Responde: ¿En qué idioma van tus textos públicos?')).toBeOnTheScreen();
    expect(within(tuParte).getByText('Plazo: 17:00')).toBeOnTheScreen();
    await fireEvent.press(within(tuParte).getByText('Ir a Tu turno'));
    expect(expoRouter.router.navigate).toHaveBeenCalledWith({ pathname: '/tu-turno', params: {} });

    const publication = within(day).getByTestId('bloque-publicacion');
    expect(within(publication).getByText('Scope features from the decision they support.')).toBeOnTheScreen();
    expect(await within(publication).findByText('Salió a las 09:00')).toBeOnTheScreen();
    expect(within(publication).getByText(/Most feature requests arrive as a solution\. Before scoping/)).toBeOnTheScreen();
    expect(within(publication).getByText('Impresiones: 1.210 (última lectura)')).toBeOnTheScreen();
    expect(within(publication).queryByText('Vetar')).toBeNull();

    const scheduled = await within(day).findByTestId('bloque-programado');
    expect(await within(scheduled).findByText('Comentario en el post de Elena Prueba')).toBeOnTheScreen();
    expect(within(scheduled).getByText('Saldrá cuando abra la ventana, hoy a las 12:00')).toBeOnTheScreen();
    expect(within(scheduled).getByText('Invitar a Sofía Muestra (sin nota)')).toBeOnTheScreen();
    expect(within(scheduled).getByText('Invitaciones previstas: 2 personas')).toBeOnTheScreen();
    expect(within(scheduled).getByText('Andrés Ejemplo y Sofía Muestra · Estimación sujeta a los topes')).toBeOnTheScreen();

    const important = within(day).getByTestId('bloque-importante');
    expect(within(important).getAllByTestId(/^evento-/).map((row) => row.props.testID)).toEqual([
      'evento-piece_published:p7:2026-11-07',
      'evento-opportunity:o1:2026-11-07',
      'evento-invitation_accepted:a1:2026-11-07',
      'evento-deadline:q1:2026-11-07',
    ]);
  });

  it('a tap on a day keeps it in the params and opens its panel in a sheet (half and full)', async () => {
    server();
    await renderCalendario();
    await fireEvent.press(await screen.findByTestId('dia-2026-11-04'));
    expect(lastParams()).toMatchObject({ fecha: '2026-11-04' });
    // The 7th's panel leaves under the 4th's (MovCalendario), out of reach of screen readers, then goes.
    expect(screen.getByTestId('panel-dia-saliente', hidden)).toBeTruthy();
    await waitFor(() => expect(screen.queryByTestId('panel-dia-saliente', hidden)).toBeNull());
    const day = sheet();
    expect(within(day).getByText('Miércoles 4 de noviembre')).toBeOnTheScreen();
    expect(within(day).getByText('Pasado')).toBeOnTheScreen();
    expect(await within(day).findByText('Sin publicación. El director decidió no publicar: No había material genuino ese día.')).toBeOnTheScreen();
    expect(within(day).queryByTestId('bloque-programado')).toBeNull();
    // The inline panel follows the selected day too.
    expect(within(panel()).getByText('Miércoles 4 de noviembre')).toBeOnTheScreen();

    const grip = within(day).getByLabelText('Altura del panel');
    expect(grip.props.accessibilityActions).toEqual([
      { name: 'increment', label: 'Ampliar' },
      { name: 'decrement', label: 'Media pantalla' },
    ]);
    // Not modal: another day can be picked with the sheet up.
    await fireEvent.press(screen.getByTestId('dia-2026-11-06'));
    expect(within(sheet()).getByText('Viernes 6 de noviembre')).toBeOnTheScreen();
    expect(within(sheet()).queryByText('Miércoles 4 de noviembre')).toBeNull();
    await waitFor(() => expect(screen.queryByTestId('panel-dia-hoja-saliente', hidden)).toBeNull());
    await fireEvent.press(within(sheet()).getByLabelText('Cerrar'));
    await waitFor(() => expect(screen.queryByTestId('hoja-dia')).toBeNull());
  });

  it('opens the piece from the day sheet', async () => {
    server();
    await renderCalendario();
    await fireEvent.press(await screen.findByTestId('dia-2026-11-07'));
    const link = await within(sheet()).findByText('Ver cómo se escribió');
    await fireEvent.press(link);
    expect(expoRouter.router.push).toHaveBeenCalledWith({ pathname: '/calendario/pieza/p7', params: {} });
  });

  it('hides the sheet while another screen is on top, and brings it back on the same day', async () => {
    server();
    const view = await renderCalendario();
    await fireEvent.press(await screen.findByTestId('dia-2026-11-05'));
    expect(screen.getByTestId('hoja-dia')).toBeOnTheScreen();
    expoRouter.__state.pathname = '/tu-turno';
    await view.rerender(<CalendarioScreen />);
    expect(screen.queryByTestId('hoja-dia')).toBeNull();
    expoRouter.__state.pathname = '/calendario';
    await view.rerender(<CalendarioScreen />);
    expect(within(sheet()).getByText('Jueves 5 de noviembre')).toBeOnTheScreen();
  });

  it('swipes to the next and the previous week with a tick; a short swipe stays', async () => {
    const api = server();
    await renderCalendario();
    await screen.findByTestId('dia-2026-11-07');
    await swipe('pager-semana', -320);
    expect(lastParams()).toMatchObject({ fecha: '2026-11-14' });
    expect(Haptics.selectionAsync).toHaveBeenCalled();
    expect(await screen.findByText('9–15 nov 2026')).toBeOnTheScreen();
    await waitFor(() => expect(api.find('GET', '/api/v1/calendario').some((r) => search(r).get('desde') === '2026-11-09')).toBe(true));

    await swipe('pager-semana', 320);
    expect(await screen.findByText('2–8 nov 2026')).toBeOnTheScreen();

    const calls = expoRouter.router.setParams!.mock.calls.length;
    await swipe('pager-semana', 40);
    expect(expoRouter.router.setParams!.mock.calls.length).toBe(calls);
  });

  it('moves a week with the arrows and comes back with «Hoy»', async () => {
    server();
    await renderCalendario({ fecha: '2026-11-06' });
    expect(within(await screen.findByTestId('panel-dia')).getByText('Viernes 6 de noviembre')).toBeOnTheScreen();
    const uncertain = await within(panel()).findByTestId('evento-action_uncertain:prop-9:2026-11-06');
    expect(within(uncertain).getByText('Comentario: no se sabe si salió')).toBeOnTheScreen();
    expect(within(uncertain).getByText('Incierta')).toBeOnTheScreen();
    await fireEvent.press(within(uncertain).getByText('Resuélvela en Tu turno'));
    expect(expoRouter.router.navigate).toHaveBeenCalledWith({ pathname: '/tu-turno', params: { ancla: 'turno-uncertain-prop-9' } });

    await fireEvent.press(screen.getByLabelText('Semana siguiente'));
    expect(lastParams()).toMatchObject({ fecha: '2026-11-13' });
    expect(await screen.findByText('9–15 nov 2026')).toBeOnTheScreen();
    await fireEvent.press(screen.getByLabelText('Hoy'));
    expect(lastParams()).toEqual({ vista: undefined, fecha: undefined, capas: undefined, tipo: undefined, no_salio: undefined });
    expect(await screen.findByText('2–8 nov 2026')).toBeOnTheScreen();
  });

  it('toggles a layer through the params and hides its events', async () => {
    server();
    await renderCalendario();
    await within(panel()).findByTestId('evento-invitation_accepted:a1:2026-11-07');
    await fireEvent.press(screen.getByTestId('capa-red'));
    expect(lastParams()).toMatchObject({ capas: 'tuyo,publicaciones,conversaciones,sistema' });
    expect(screen.getByTestId('capa-red').props.accessibilityState).toMatchObject({ selected: false });
    expect(within(panel()).queryByTestId('evento-invitation_accepted:a1:2026-11-07')).toBeNull();
    await fireEvent.press(screen.getByTestId('capa-red'));
    expect(lastParams()).toMatchObject({ capas: undefined });
  });

  it('marks a layer the backend does not have yet as unavailable, and the partial one', async () => {
    server({}, (d, h) => calendarioFixture(d, h, WEEK_DAYS, { layers: { tuyo: false, publicaciones: true, red: true, conversaciones: 'parcial', sistema: true } }));
    await renderCalendario();
    await waitFor(() => expect(screen.getByTestId('capa-tuyo').props.accessibilityLabel).toBe('Tuyo · aún no disponible'));
    expect(screen.getByTestId('capa-tuyo').props.accessibilityState).toMatchObject({ disabled: true });
    expect(screen.getByText('Conversaciones · parcial')).toBeOnTheScreen();
    expect(within(panel()).queryByTestId('bloque-tu-parte')).toBeNull();
  });

  it('opens «Ver todo lo del día» filtered by the number tapped in the summary', async () => {
    const api = server();
    await renderCalendario();
    await fireEvent.press(await within(panel()).findByText('6 comentarios'));
    await waitFor(() =>
      expect(api.find('GET', '/api/v1/actividad').some((r) => search(r).toString() === 'tipo=comentarios&desde=2026-11-07&hasta=2026-11-07&limit=50')).toBe(true),
    );
    expect(within(panel()).getByRole('button', { name: 'Comentarios' })).toBeSelected();
    expect(await within(panel()).findByText('Comentaste en el post de Elena Prueba')).toBeOnTheScreen();
  });

  it('warns that vetoing a network action discards the person', async () => {
    server();
    await renderCalendario();
    const row = await within(panel()).findByTestId('en-cola-q-2');
    await fireEvent.press(within(row).getByText('Vetar'));
    const confirm = await screen.findByTestId('confirm-sheet');
    expect(within(confirm).getByText('Vetar la acción')).toBeOnTheScreen();
    expect(within(confirm).getByText(/descarta a Sofía Muestra para siempre/)).toBeOnTheScreen();
  });

  it('approves from «Programado» what waits for Gustavo, with its exact version', async () => {
    const base = actividadFixture();
    const waiting = { ...base.upcoming.queued[1]!, id: 'q-3', state: 'proposed', expected_at: null, awaiting_approval: true, payload_hash: 'b'.repeat(64), expires_at: '2026-11-08T20:00:00Z' };
    const api = server({
      'GET /api/v1/actividad': { body: { ...base, upcoming: { ...base.upcoming, queued: [waiting, ...base.upcoming.queued] } } },
      'POST /api/v1/operador/actions/q-3/approve': { status: 202, body: {} },
    });
    await renderCalendario();
    const row = await within(panel()).findByTestId('en-cola-q-3');
    expect(within(row).getByText(/^Espera tu aprobación · caduca /)).toBeOnTheScreen();
    expect(within(within(panel()).getByTestId('en-cola-q-2')).queryByText('Aprobar')).toBeNull();  // already approved: only Vetar
    await fireEvent.press(within(row).getByText('Aprobar'));
    await waitFor(() => expect(api.find('POST', '/api/v1/operador/actions/q-3/approve')[0]?.body).toEqual({ expected_hash: 'b'.repeat(64), note: '' }));
    expect(await screen.findByText('Aprobada. Sale cuando lo permitan la ventana y los topes.')).toBeOnTheScreen();
  });

  it('says when a day is too far ahead', async () => {
    server();
    await renderCalendario({ fecha: '2026-11-30' });
    expect(await within(panel()).findByText('Todavía no hay nada programado tan lejos.')).toBeOnTheScreen();
    expect(await within(panel()).findByText('El equipo prepara cada pieza 6 h antes de su hora.')).toBeOnTheScreen();
  });

  it('keeps the strip and offers a retry when the calendar fails', async () => {
    let fail = true;
    const api = server();
    api.on('GET /api/v1/calendario', (request) =>
      fail ? { status: 500, body: { detail: 'Error del servidor' } } : { body: calendarioFixture(search(request).get('desde')!, search(request).get('hasta')!, WEEK_DAYS) },
    );
    await renderCalendario();
    expect(await screen.findByText('No se pudo cargar el calendario')).toBeOnTheScreen();
    expect(screen.getByText('Error del servidor')).toBeOnTheScreen();
    expect(screen.getAllByTestId(/^dia-/)).toHaveLength(7);
    fail = false;
    await fireEvent.press(screen.getByText('Reintentar'));
    expect(await within(panel()).findByText('6 comentarios')).toBeOnTheScreen();
  });

  it('says «Horas de Bogotá» when the phone is in another time zone', async () => {
    jest.mocked(Date.prototype.getTimezoneOffset).mockReturnValue(-60);
    server();
    await renderCalendario();
    expect(await screen.findByText('2–8 nov 2026 · Horas de Bogotá')).toBeOnTheScreen();
  });
});

describe('Calendario · veto con «Deshacer»', () => {
  it('waits 5 s before vetoing tomorrow’s piece; «Deshacer» cancels it', async () => {
    const api = server({ 'POST /api/v1/operador/actions/act-8/reject': { body: {} } });
    await renderCalendario({ fecha: '2026-11-08' });
    const publication = await within(panel()).findByTestId('bloque-publicacion');
    expect(within(panel()).getByText('Programado')).toBeOnTheScreen();
    expect(await within(publication).findByText('Mañana a las 09:00 · sale en 23 h')).toBeOnTheScreen();

    await fireEvent.press(await within(publication).findByText('Vetar'));
    const confirm = await screen.findByTestId('confirm-sheet');
    expect(within(confirm).getByText(/La pieza no saldrá a las 09:00 y ese día quedará sin publicación/)).toBeOnTheScreen();
    await fireEvent.changeText(within(confirm).getByTestId('confirm-note'), 'No es el momento');
    await fireEvent.press(within(confirm).getAllByText('Vetar').at(-1)!);

    const toast = await screen.findByTestId('toast');
    expect(within(toast).getByText('Vetada')).toBeOnTheScreen();
    expect(within(publication).getByText('Vetada')).toBeOnTheScreen();
    expect(api.find('POST', '/api/v1/operador/actions/act-8/reject')).toHaveLength(0);

    await fireEvent.press(within(toast).getByText('Deshacer'));
    expect(await screen.findByText('Veto deshecho')).toBeOnTheScreen();
    await flushVetoes();
    expect(api.find('POST', '/api/v1/operador/actions/act-8/reject')).toHaveLength(0);
    expect(await within(publication).findByText('Vetar')).toBeOnTheScreen();
  });

  it('sends the veto with its note once the window has passed', async () => {
    jest.replaceProperty(motion.toastDurations as { withUndo: number }, 'withUndo', 30);
    const api = server({ 'POST /api/v1/operador/actions/act-8/reject': { body: {} } });
    await renderCalendario({ fecha: '2026-11-08' });
    await fireEvent.press(await within(panel()).findByText('Vetar'));
    const confirm = await screen.findByTestId('confirm-sheet');
    await fireEvent.changeText(within(confirm).getByTestId('confirm-note'), 'No es el momento');
    await fireEvent.press(within(confirm).getAllByText('Vetar').at(-1)!);
    await waitFor(() => expect(api.find('POST', '/api/v1/operador/actions/act-8/reject')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/operador/actions/act-8/reject')[0]!.body).toEqual({ note: 'No es el momento' });
    await waitFor(() => expect(api.find('GET', '/api/v1/editorial/pieces/p8').length).toBeGreaterThan(1));
  });

  it('vetoes from the day sheet and says when the veto failed', async () => {
    jest.replaceProperty(motion.toastDurations as { withUndo: number }, 'withUndo', 30);
    server({ 'POST /api/v1/operador/actions/act-8/reject': { status: 409, body: { detail: 'La acción ya se está ejecutando.' } } });
    await renderCalendario();
    await fireEvent.press(await screen.findByTestId('dia-2026-11-08'));
    await fireEvent.press(await within(sheet()).findByText('Vetar'));
    const confirm = await screen.findByTestId('confirm-sheet');
    await fireEvent.changeText(within(confirm).getByTestId('confirm-note'), 'No');
    await fireEvent.press(within(confirm).getAllByText('Vetar').at(-1)!);
    expect(within(await screen.findByTestId('toast')).getByText('Vetada')).toBeOnTheScreen();
    expect(await screen.findByText('No se pudo vetar. La acción ya se está ejecutando.')).toBeOnTheScreen();
    expect(Haptics.notificationAsync).toHaveBeenCalledWith('error');
  });
});

describe('Calendario · mes', () => {
  it('requests the whole grid, shows a compact month of dots and swipes to the next month', async () => {
    const api = server();
    await renderCalendario({ vista: 'mes' });
    expect(screen.getByText('Noviembre 2026')).toBeOnTheScreen();
    await waitFor(() => expect(api.find('GET', '/api/v1/calendario').some((r) => search(r).toString() === 'desde=2026-10-26&hasta=2026-12-06')).toBe(true));
    expect(screen.getAllByTestId(/^dia-/)).toHaveLength(42);
    await waitFor(() => expect(screen.getByTestId('dia-2026-11-02').props.accessibilityLabel).toBe('Lunes 2 de noviembre, Publicaciones, Red'));

    await swipe('pager-mes', -320);
    expect(lastParams()).toMatchObject({ vista: 'mes', fecha: '2026-12-07' });
    expect(await screen.findByText('Diciembre 2026')).toBeOnTheScreen();
    expect(await screen.findByText('No hay nada registrado en este mes.')).toBeOnTheScreen();
  });

  it('switches view with the segmented control', async () => {
    server();
    await renderCalendario();
    await fireEvent.press(screen.getByText('Mes'));
    expect(lastParams()).toMatchObject({ vista: 'mes' });
    expect(screen.getByRole('tab', { name: 'Mes' })).toBeSelected();
    // The week leaves under the month (MovCalendario), hidden from screen readers, then goes. Its
    // 120 ms fade runs on real timers here and can be over before the next line on a slow runner
    // (CI measures coverage): movimiento.test.tsx checks that view and its fade with fake timers.
    expect(await screen.findByText('Noviembre 2026')).toBeOnTheScreen();
    await waitFor(() => expect(screen.queryByTestId('vista-saliente', hidden)).toBeNull());
    expect(screen.getAllByTestId(/^dia-/)).toHaveLength(42);
    await fireEvent.press(screen.getByText('Lista'));
    expect(lastParams()).toMatchObject({ vista: 'lista' });
    expect(await screen.findByText('Línea de tiempo')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Semana'));
    expect(lastParams()).toMatchObject({ vista: undefined });
  });
});

describe('Calendario · lista', () => {
  it('shows «Próximo» with its countdown, the queue and every day newest first', async () => {
    server();
    await renderCalendario({ vista: 'lista' });
    expect(screen.getByText('Línea de tiempo')).toBeOnTheScreen();
    expect(screen.queryByLabelText('Hoy')).toBeNull();
    expect(await screen.findByText('Turning a sales call into a product spec.')).toBeOnTheScreen();
    expect(screen.getByText('Mañana a las 09:00 · sale en 23 h')).toBeOnTheScreen();
    expect(screen.getByText('Del negocio al producto · ProjectApp · Lector comprador')).toBeOnTheScreen();
    expect(screen.getByText('En cola')).toBeOnTheScreen();
    expect(screen.getAllByText('Vetar')).toHaveLength(3);

    const list = screen.getByTestId('calendario-lista');
    expect(within(list).getByText('Hoy')).toBeOnTheScreen();
    expect(within(list).getByText('Ayer')).toBeOnTheScreen();
    expect(within(list).getByText('Jueves 5 de noviembre')).toBeOnTheScreen();
    expect(within(list).getByText('Reaccionaste Recomiendo al post de Tomás Demo')).toBeOnTheScreen();
    expect(within(list).getByText('Head of Product @ Kanoa · Par')).toBeOnTheScreen();
    const uncertain = within(list).getByTestId('actividad-i-4');
    expect(within(uncertain).getByText('Incierta')).toBeOnTheScreen();
    await fireEvent.press(within(uncertain).getByText('Resuélvela en Tu turno'));
    expect(expoRouter.router.navigate).toHaveBeenCalledWith({ pathname: '/tu-turno', params: { ancla: 'turno-uncertain-i-4' } });
    await fireEvent.press(within(list).getByText('Ver la pieza'));
    expect(expoRouter.router.push).toHaveBeenCalledWith({ pathname: '/calendario/pieza/p5', params: {} });

    const comment = within(list).getByTestId('actividad-i-1');
    await fireEvent.press(within(comment).getByText('Ver el comentario'));
    expect(within(comment).getByText('How we scope features at Kanoa.')).toBeOnTheScreen();
    expect(within(comment).getByText('Naming the decision first is underrated.')).toBeOnTheScreen();
    expect(within(comment).getByText('Por qué')).toBeOnTheScreen();
  });

  it('filters by type and shows what did not go out through the params', async () => {
    const api = server();
    await renderCalendario({ vista: 'lista' });
    await screen.findByText('Comentaste en el post de Elena Prueba');
    await fireEvent.press(screen.getByText('Reacciones'));
    expect(lastParams()).toMatchObject({ vista: 'lista', tipo: 'reacciones' });
    await waitFor(() => expect(api.find('GET', '/api/v1/actividad').some((r) => search(r).get('tipo') === 'reacciones')).toBe(true));
    await fireEvent(screen.getByTestId('no-salio'), 'valueChange', true);
    expect(lastParams()).toMatchObject({ tipo: 'reacciones', no_salio: '1' });
    await waitFor(() => expect(api.find('GET', '/api/v1/actividad').some((r) => search(r).get('no_salio') === '1')).toBe(true));
  });

  it('loads more with the next offset', async () => {
    const api = server({
      'GET /api/v1/actividad': (request) => ({
        body: search(request).get('offset') === '50' ? actividadFixture({ items: [], next_offset: null }) : actividadFixture({ next_offset: 50 }),
      }),
    });
    await renderCalendario({ vista: 'lista' });
    await fireEvent.press(await screen.findByText('Cargar más'));
    await waitFor(() => expect(api.find('GET', '/api/v1/actividad').some((r) => search(r).get('offset') === '50')).toBe(true));
    await waitFor(() => expect(screen.queryByText('Cargar más')).toBeNull());
  });

  it('prepares the next piece behind the cost confirmation when nothing is scheduled', async () => {
    const empty: Actividad = actividadFixture({ upcoming: { pieces: [], queued: [] } });
    const api = server({
      'GET /api/v1/actividad': { body: empty },
      'POST /api/v1/editorial/plan': { status: 202, body: { slot_date: '2026-11-09', job: { id: 'j1', status: 'queued' } } },
    });
    await renderCalendario({ vista: 'lista' });
    expect(await screen.findByText('No hay pieza programada para los próximos días.')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Preparar la siguiente pieza'));
    const confirm = await screen.findByTestId('confirm-sheet');
    expect(within(confirm).getByText(/Tiene coste: cada etapa llama a Claude/)).toBeOnTheScreen();
    await fireEvent.press(within(confirm).getByText('Preparar'));
    await waitFor(() => expect(api.find('POST', '/api/v1/editorial/plan')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/editorial/plan')[0]!.body).toEqual({ request_id: expect.stringMatching(/^[0-9a-f-]{36}$/) });
    expect(await screen.findByText(/Preparación en cola para el lunes 9 de noviembre\. El circuito tarda unos minutos/)).toBeOnTheScreen();
  });
});

afterAll(() => {
  cancelVeto('act-8');
});
