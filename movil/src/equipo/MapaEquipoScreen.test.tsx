import { graphFixture } from '@compartido/fixtures/grafo';
import { api } from '@compartido/api/client';
import { fireEvent, screen } from '@testing-library/react-native';
import { router } from 'expo-router';
import '@/api/transport';
import { saveToken } from '@/api/token';
import { renderApp } from '@/test/render';
import { fakeServer } from '@/test/server';
import { MapaEquipoScreen } from './MapaEquipoScreen';

const PATH = 'GET /api/v1/equipo/grafo';
const state = (jest.requireMock('expo-router') as { __state: { params: Record<string, string> } }).__state;

beforeEach(async () => {
  state.params = {};
  await saveToken('0ff1ce_dt_prueba');
});

it('opens a group and requests navigation to its agent', async () => {
  fakeServer({ [PATH]: { body: graphFixture() } });
  await renderApp(<MapaEquipoScreen />);
  await fireEvent.press(await screen.findByText('Mesa editorial · 3'));
  await fireEvent.press(screen.getByRole('button', { name: 'Director editorial' }));
  expect(router.setParams).toHaveBeenCalledWith({ agente: 'director_editorial' });
});

it('offers cycle navigation from the shared registry', async () => {
  fakeServer({ [PATH]: { body: graphFixture() } });
  await renderApp(<MapaEquipoScreen />);
  await fireEvent.press(await screen.findByRole('button', { name: 'Ver ciclo' }));
  await fireEvent.press(screen.getByRole('radio', { name: 'Pieza diaria' }));
  expect(router.setParams).toHaveBeenCalledWith({ ciclo: 'pieza_diaria', agente: '' });
});

it('shows units, job and handoff evidence, and navigates a connection', async () => {
  state.params = { agente: 'director_editorial' };
  const server = fakeServer({ [PATH]: { body: graphFixture() } });
  await renderApp(<MapaEquipoScreen />);
  expect(await screen.findByText('Elige el brief de la pieza y coordina las herramientas.')).toBeOnTheScreen();
  await fireEvent.press(screen.getByText('Curso · 1 unidades'));
  expect(screen.getByText('LI-04-M005-K01')).toBeOnTheScreen();
  expect(screen.getByText(/Brief entregado/)).toBeOnTheScreen();
  expect(screen.getByText(/Terminado/)).toBeOnTheScreen();
  await fireEvent.press(screen.getByRole('button', { name: 'Solicita a: Copywriter A' }));
  expect(router.setParams).toHaveBeenCalledWith({ agente: 'copywriter_a' });
  expect(server.requests.every((call) => call.method === 'GET')).toBe(true);
});

it('shows the active visual editor with empty activity without inventing work', async () => {
  state.params = { agente: 'editor_visual' };
  fakeServer({ [PATH]: { body: graphFixture() } });
  await renderApp(<MapaEquipoScreen />);
  expect(await screen.findByText('Editor visual')).toBeOnTheScreen();
  expect(screen.queryByText('Este agente aún no ejecuta trabajo.')).not.toBeOnTheScreen();
  expect(screen.getByText('Sin actividad registrada para este agente.')).toBeOnTheScreen();
  await fireEvent.press(screen.getByRole('button', { name: 'Ver todos los agentes' }));
  expect(router.setParams).toHaveBeenCalledWith({ agente: '' });
  await fireEvent.press(screen.getByRole('button', { name: 'Volver' }));
  expect(router.back).toHaveBeenCalled();
});

it('retries errors and handles an empty graph', async () => {
  const server = fakeServer({ [PATH]: { status: 503, body: { detail: 'Temporal' } } });
  await renderApp(<MapaEquipoScreen />);
  expect(await screen.findByText('No se pudo cargar el mapa')).toBeOnTheScreen();
  server.on(PATH, { body: { ...graphFixture(), nodes: [] } });
  await fireEvent.press(screen.getByRole('button', { name: 'Reintentar' }));
  expect(await screen.findByText('El mapa todavía no tiene agentes.')).toBeOnTheScreen();
});

it('preserves the planned state declared by a registry without the visual runtime', async () => {
  state.params = { agente: 'editor_visual' };
  const graph = graphFixture();
  graph.nodes[2]!.status = 'planned';
  fakeServer({ [PATH]: { body: graph } });
  await renderApp(<MapaEquipoScreen />);
  expect(await screen.findByText('Este agente aún no ejecuta trabajo.')).toBeOnTheScreen();
});

it('keeps a loading state while the fake request is pending', async () => {
  const pending = jest.spyOn(api, 'get').mockImplementation(() => new Promise(() => {}));
  try {
    await renderApp(<MapaEquipoScreen />);
    expect(screen.getByText('Cargando el mapa…')).toBeOnTheScreen();
  } finally {
    pending.mockRestore();
  }
});
