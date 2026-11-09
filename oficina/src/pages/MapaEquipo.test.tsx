import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { graphFixture } from '../../../compartido/src/fixtures/grafo';
import { fakeServer, type Reply } from '../test/fakeServer';
import { renderAt } from '../test/render';
import { MapaEquipo } from './MapaEquipo';

const PATH = 'GET /api/v1/equipo/grafo';
const renderMap = (path = '/equipo') => renderAt(path, [{ path: '/equipo', element: <MapaEquipo /> }]);

describe('Mapa del equipo', () => {
  it('shows groups, course units, real activity and navigates connections in both directions', async () => {
    const server = fakeServer({ [PATH]: { body: graphFixture() } });
    const user = userEvent.setup();
    renderMap();
    await user.click(await screen.findByText('Mesa editorial · 3'));
    await user.click(screen.getByRole('button', { name: /Director editorial/ }));
    expect(screen.getByText('Elige el brief de la pieza y coordina las herramientas.')).toBeInTheDocument();
    await user.click(screen.getByText('Curso · 1 unidades'));
    expect(screen.getByText('LI-04-M005-K01')).toBeVisible();
    expect(screen.getByText(/Brief entregado/)).toBeVisible();
    expect(screen.getByText(/Terminado/)).toBeVisible();
    await user.click(screen.getByRole('button', { name: /Solicita a: Copywriter A/ }));
    expect(screen.getByText('Sin actividad registrada para este agente.')).toBeVisible();
    await user.click(screen.getByRole('button', { name: /Recibe de: Director editorial/ }));
    await user.click(screen.getByRole('button', { name: /Solicita a: Especialista visual/ }));
    expect(screen.getByText('Este agente aún no ejecuta trabajo.')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Ver todos los agentes' }));
    expect(screen.getByText('Mesa editorial · 3')).toBeVisible();
    expect(server.requests.every((call) => call.method === 'GET')).toBe(true);
  });

  it('shows loading without invented activity', () => {
    fakeServer({ [PATH]: () => new Promise<Reply>(() => {}) });
    renderMap();
    expect(screen.getByRole('status')).toHaveTextContent('Cargando el mapa');
    expect(screen.queryByText(/Brief entregado/)).not.toBeInTheDocument();
  });

  it('retries an error and renders the empty state', async () => {
    const server = fakeServer({ [PATH]: { status: 503, body: { detail: 'Temporal' } } });
    const user = userEvent.setup();
    renderMap();
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo cargar el mapa');
    server.on(PATH, { body: { ...graphFixture(), nodes: [] } });
    await user.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(await screen.findByText('El mapa todavía no tiene agentes.')).toBeVisible();
  });

  it('handles a stale agent link and keeps the groups available', async () => {
    fakeServer({ [PATH]: { body: graphFixture() } });
    renderMap('/equipo?agente=removed');
    expect(await screen.findByText('Este agente ya no está en el mapa.')).toBeVisible();
    expect(screen.getByText('Mesa editorial · 3')).toBeVisible();
  });

  it('filters the group list to the selected cycle', async () => {
    const graph = graphFixture();
    graph.cycles.push({ id: 'visual_future', label: 'Visual futuro', status: 'planned', orchestrator: 'director_editorial', participants: ['editor_visual'], triggers: [] });
    fakeServer({ [PATH]: { body: graph } });
    const user = userEvent.setup();
    renderMap();
    await user.selectOptions(await screen.findByLabelText('Ver ciclo'), 'visual_future');
    await user.click(screen.getByText('Mesa editorial · 1'));
    expect(screen.getByRole('button', { name: /Especialista visual/ })).toBeVisible();
    expect(screen.queryByRole('button', { name: /Copywriter A/ })).not.toBeInTheDocument();
  });
});
