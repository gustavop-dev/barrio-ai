import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import { AppState, Dimensions, type AppStateStatus } from 'react-native';
import { State } from 'react-native-gesture-handler';
import * as Haptics from 'expo-haptics';
import { fireGestureHandler, getByGestureTestId } from 'react-native-gesture-handler/jest-utils';
import { REFRESH } from '@compartido/api/hooks';
import { oficinaEventosKey } from '@compartido/api/oficina';
import { PLAN_WIDTH, sceneScale } from '@compartido/scene/plan';
import { renderApp } from '@/test/render';
import { fakeServer, type FakeHandler } from '@/test/server';
import '@/api/transport';
import { CaptureSheetHost } from '@/capture/CaptureSheet';
import { closeCaptureSheet, openCaptureSheet, resetCaptureStoreForTests } from '@/capture/store';
import { resetFakeAudio } from '@/test/fakeAudio';
import { OficinaScreen } from './OficinaScreen';

// Only the GPU boundary is mocked; the real lifecycle, shared engine, polling and gestures run.
jest.mock('@shopify/react-native-skia', () => ({
  Canvas: require('react-native').View, useImage: () => null,
  Skia: { Matrix: () => { const m = { identity: () => m, translate: () => m, scale: () => m }; return m; } },
}));
const route = require('expo-router').__state as { pathname: string };
const now = '2026-11-07T15:00:00Z';
const activity = { updated_at: now, roles: {
  operador_cuenta: { status: 'trabajando', detail: 'Ejecutando comentario aprobado', since: now },
  copywriter_a: { status: 'en_espera', detail: '', since: null },
  relaciones_comunidad: { status: 'en_espera', detail: '', since: null },
  conversaciones_inbox: { status: 'diseno', detail: 'Contrato diseñado; aún sin implementar', since: null },
} };
const events = { events: [{ id: 7, ts: now, tipo: 'consulta_biblioteca', rol: 'copywriter_a', destino: 'biblioteca', detalle: 'clase 03' }], now };
const A = 'GET /api/v1/oficina/actividad', E = 'GET /api/v1/oficina/eventos', O = 'GET /api/v1/operador/overview';
function server(extra: Record<string, FakeHandler> = {}) {
  return fakeServer({ [A]: { body: activity }, [E]: { body: { events: [], now } }, [O]: { body: { control: { paused: false } } }, ...extra });
}
beforeEach(() => { route.pathname = '/'; Object.defineProperty(AppState, 'currentState', { configurable: true, value: 'active' }); });
afterEach(() => { jest.useRealTimers(); });

it('shows the visual editor as the fourth editorial member with real activity and a registry link', async () => {
  server({ [A]: { body: { ...activity, roles: { ...activity.roles,
    editor_visual: { status: 'trabajando', detail: 'Preparando foto, infografía o carrusel para la pieza', since: now },
  } } } });
  await renderApp(<OficinaScreen />);
  await screen.findByText('Editor visual: Preparando foto, infografía o carrusel para la pieza');
  await fireEvent.press(screen.getByTestId('team-chip-editorial'));
  expect(within(screen.getByTestId('office-panel')).getByText('4 INTEGRANTES · LA MESA LARGA')).toBeOnTheScreen();
  await fireEvent.press(screen.getByRole('button', { name: 'Editor visual, Trabajando' }));
  const panel = within(screen.getByTestId('office-panel'));
  expect(panel.getByText('Propone y prepara la foto, infografía o carrusel de la pieza; el director decide.')).toBeOnTheScreen();
  expect(panel.getByText('Trabajando · Preparando foto, infografía o carrusel para la pieza')).toBeOnTheScreen();
  await fireEvent.press(panel.getByRole('button', { name: 'Ver definición y conexiones' }));
  expect(require('expo-router').router.push).toHaveBeenCalledWith('/equipo?agente=editor_visual');
});

it('opens with a still scene and loading narration, then real activity and design tags', async () => {
  const api = server();
  const respond = api.fetch.getMockImplementation()!;
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => { release = resolve; });
  api.fetch.mockImplementation(async (url, options) => {
    if (url.endsWith('/oficina/actividad')) await waiting;
    return respond(url, options);
  });
  await renderApp(<OficinaScreen />);
  expect(screen.getByText('Abriendo la oficina…')).toBeOnTheScreen();
  await act(async () => release());
  expect(await screen.findByText('Operación: Ejecutando comentario aprobado')).toBeOnTheScreen();
  expect(screen.getByText('EN DISEÑO', { includeHiddenElements: true })).toBeOnTheScreen();
});
it('keeps unknown roles without data on activity errors and recovers with retry', async () => {
  const api = server({ [A]: { status: 503 } }); await renderApp(<OficinaScreen />);
  await screen.findByText('No se pudo leer la actividad.');
  expect(screen.getByText('Mientras tanto los personajes quedan quietos: la oficina no simula trabajo.')).toBeOnTheScreen();
  await fireEvent.press(screen.getByRole('button', { name: 'Operación' }));
  expect(within(screen.getByTestId('office-panel')).getByText('Sin datos')).toBeOnTheScreen();
  api.on(A, { body: activity }); await fireEvent.press(screen.getByRole('button', { name: 'Reintentar' }));
  expect(await screen.findByText('Operación: Ejecutando comentario aprobado')).toBeOnTheScreen();
});
it('opens an agent sheet from a scene tap, switches to its team and closes', async () => {
  server(); await renderApp(<OficinaScreen />); await screen.findByText('Operación: Ejecutando comentario aprobado');
  const w = Dimensions.get('window').width, scale = sceneScale(w, Dimensions.get('window').height - 160);
  const x = (w - PLAN_WIDTH * scale) / 2 + 96 * scale;
  await act(async () => fireGestureHandler(getByGestureTestId('office-tap'), [{ state: State.ACTIVE, x, y: 44 * scale }]));
  const panel = await screen.findByTestId('office-panel');
  expect(Haptics.selectionAsync).toHaveBeenCalledTimes(1);
  expect(screen.getByText('Operador de cuenta · Trabajando en su puesto')).toBeOnTheScreen();
  expect(within(panel).getByText('Operador de cuenta')).toBeOnTheScreen();
  expect(within(panel).getByText('Es un servicio de software, no un agente de IA. Solo ejecuta lo que el equipo ya decidió.')).toBeOnTheScreen();
  await fireEvent.press(within(panel).getByText('Ver su equipo · Operación'));
  expect(within(screen.getByTestId('office-panel')).getByText('ESPACIO DEL EQUIPO')).toBeOnTheScreen();
  expect(screen.queryByRole('button', { name: 'Cerrar' })).toBeNull();
  await fireEvent(within(screen.getByTestId('office-panel')).getByLabelText('Altura del panel'), 'accessibilityAction', { nativeEvent: { actionName: 'dismiss' } });
  await waitFor(() => expect(screen.queryByTestId('office-panel')).toBeNull());
});

it('receives a successful capture-sheet send without changing the POST, closing or success haptic', async () => {
  resetCaptureStoreForTests(); resetFakeAudio();
  const api = server({
    'GET /api/v1/capturas': { body: [] },
    'POST /api/v1/capturas': { status: 201, body: { id: 'motion-c1', state: 'recibida', can_undo: true } },
  });
  await renderApp(<><OficinaScreen /><CaptureSheetHost /></>, { recorder: true });
  await screen.findByText('Operación: Ejecutando comentario aprobado');
  await act(async () => openCaptureSheet());
  await fireEvent.changeText(screen.getByTestId('capture-note'), 'Una idea para el equipo');
  await fireEvent.press(screen.getByTestId('capture-send'));
  expect(await screen.findByText('Llegó tu captura a la oficina.')).toBeOnTheScreen();
  // MovCaptura: the sheet closes at the end of the envelope choreography (captureTimeline.send).
  await waitFor(() => expect(screen.queryByTestId('capture-sheet')).toBeNull(), { timeout: 4000 });
  expect(api.find('POST', '/api/v1/capturas')).toHaveLength(1);
  expect(api.find('POST', '/api/v1/capturas')[0]!.body).toEqual([['nota', 'Una idea para el equipo']]);
  expect(Haptics.notificationAsync).toHaveBeenCalledTimes(1);
  expect(Haptics.notificationAsync).toHaveBeenCalledWith('success');
  expect(screen.getByText('Deshacer')).toBeOnTheScreen();
  await act(async () => closeCaptureSheet());
});
it('narrates events once, advances the cursor and retains history after empty pages', async () => {
  const api = server({ [E]: { body: events } }); const { client } = await renderApp(<OficinaScreen />);
  await screen.findByText('Copywriter A va a la biblioteca: “clase 03”');
  api.on(E, { body: { events: [], now } });
  await act(async () => { await client.refetchQueries({ queryKey: oficinaEventosKey }); });
  expect(api.find('GET', '/api/v1/oficina/eventos')[1]!.path).toContain(`desde=${encodeURIComponent(now)}`);
  await act(async () => { await client.refetchQueries({ queryKey: oficinaEventosKey }); });
  expect(api.find('GET', '/api/v1/oficina/eventos')[2]!.path).toContain(`desde=${encodeURIComponent(now)}`);
  await fireEvent.press(screen.getByRole('button', { name: 'Mesa editorial' }));
  await fireEvent.press(within(screen.getByTestId('office-panel')).getByRole('button', { name: /Copywriter A/ }));
  expect(within(screen.getByTestId('office-panel')).getAllByText('Copywriter A va a la biblioteca: “clase 03”')).toHaveLength(1);
});
it('shows paused and unavailable states intentionally', async () => {
  server({ [O]: { body: { control: { paused: true } } }, [E]: { status: 404 } }); await renderApp(<OficinaScreen />);
  expect(await screen.findByText('La máquina está en pausa. Nadie toca tu LinkedIn.')).toBeOnTheScreen();
  expect(screen.getByTestId('oficina-pausa')).toBeOnTheScreen();
  expect(await screen.findByText('Aún no disponible')).toBeOnTheScreen();
});
it('retries a feed failure and handles the library service panel', async () => {
  const api = server({ [E]: { status: 500 } }); await renderApp(<OficinaScreen />);
  await screen.findByText('No se pudieron leer los eventos.'); api.on(E, { body: events });
  await fireEvent.press(screen.getByRole('button', { name: 'Reintentar' }));
  await screen.findByText('Copywriter A va a la biblioteca: “clase 03”');
  await fireEvent.press(screen.getByRole('button', { name: 'Biblioteca' }));
  expect(within(screen.getByTestId('office-panel')).getByText('SERVICIO · BIBLIOTECA')).toBeOnTheScreen();
  expect(within(screen.getByTestId('office-panel')).queryByText('Ver en el Calendario')).toBeNull();
  await fireEvent.press(screen.getByText('Ver quién la usa · Observatorio'));
  expect(within(screen.getByTestId('office-panel')).getByText('ESPACIO DEL EQUIPO')).toBeOnTheScreen();
});
it('stops every scene poll when unfocused or backgrounded and resumes on return', async () => {
  jest.useFakeTimers();
  let stateChanged: ((state: AppStateStatus) => void) | undefined;
  const remove = jest.fn();
  jest.spyOn(AppState, 'addEventListener').mockImplementation((_event, listener) => { stateChanged = listener; return { remove }; });
  const api = server(); const view = await renderApp(<OficinaScreen />);
  await act(async () => { await jest.advanceTimersByTimeAsync(100); });
  const before = api.requests.length;
  route.pathname = '/personas'; await view.rerender(<OficinaScreen />);
  await act(async () => { await jest.advanceTimersByTimeAsync(REFRESH.overview * 2); });
  expect(api.requests).toHaveLength(before);
  route.pathname = '/'; await view.rerender(<OficinaScreen />);
  await act(async () => { await jest.advanceTimersByTimeAsync(100); });
  expect(api.requests.length).toBeGreaterThan(before);
  await act(async () => stateChanged?.('background')); const background = api.requests.length;
  await act(async () => { await jest.advanceTimersByTimeAsync(REFRESH.overview * 2); });
  expect(api.requests).toHaveLength(background);
  await act(async () => stateChanged?.('active'));
  await act(async () => { await jest.advanceTimersByTimeAsync(100); });
  expect(api.requests.length).toBeGreaterThan(background);
  await view.unmount(); expect(remove).toHaveBeenCalled();
});

it('pinches and pans, resets with double tap, and dismisses the selected panel by dragging', async () => {
  server(); await renderApp(<OficinaScreen />); await screen.findByText('Operación: Ejecutando comentario aprobado');
  await act(async () => {
    fireGestureHandler(getByGestureTestId('office-pinch'), [
      { state: State.BEGAN, scale: 1, focalX: 100, focalY: 100 },
      { state: State.ACTIVE, scale: 1, focalX: 100, focalY: 100 },
      { state: State.ACTIVE, scale: 2, focalX: 100, focalY: 100 },
      { state: State.END, scale: 2, focalX: 100, focalY: 100 },
    ]);
    fireGestureHandler(getByGestureTestId('office-pan'), [
      { state: State.BEGAN, translationX: 0, translationY: 0 },
      { state: State.ACTIVE, translationX: 0, translationY: 0 },
      { state: State.ACTIVE, translationX: -100, translationY: -100 },
      { state: State.END, translationX: -100, translationY: -100 },
    ]);
    fireGestureHandler(getByGestureTestId('office-reset'), [{ state: State.ACTIVE, x: 100, y: 100 }]);
  });
  const w = Dimensions.get('window').width, scale = sceneScale(w, Dimensions.get('window').height - 160);
  await act(async () => fireGestureHandler(getByGestureTestId('office-tap'), [{ state: State.ACTIVE, x: (w - PLAN_WIDTH * scale) / 2 + 42 * scale, y: 70 * scale }]));
  expect(within(await screen.findByTestId('office-panel')).getByText('SERVICIO · BIBLIOTECA')).toBeOnTheScreen();
  await act(async () => fireGestureHandler(getByGestureTestId('snap-sheet-drag'), [
    { state: State.BEGAN, translationY: 0 }, { state: State.ACTIVE, translationY: 0 },
    { state: State.ACTIVE, translationY: 300 }, { state: State.END, translationY: 300, velocityY: 1500 },
  ]));
  await waitFor(() => expect(screen.queryByTestId('office-panel')).toBeNull());
});
