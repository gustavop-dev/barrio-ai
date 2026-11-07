import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { WeeklySummaries, WeeklySummary } from '../../api/types';
import { fakeServer } from '../../test/fakeServer';
import { resultadosFixture } from '../../test/fixtures/resultados';
import { renderAt } from '../../test/render';
import { Resultados } from '../Resultados';

const routes = [{ path: '/resultados', element: <Resultados /> }];
const URL = '/api/v1/resultados/resumen-semanal';
const PROPOSAL = 'Prioriza IA aplicada en los posts de la próxima semana.';

function summary(overrides: Partial<WeeklySummary> = {}): WeeklySummary {
  return {
    id: 's-1',
    week_start: '2026-11-02',
    week_end: '2026-11-08',
    label: 'Semana del 2 al 8 de noviembre',
    state: 'visto',
    state_label: 'Visto',
    analysis: {
      titular: 'Semana con 3 posts y 840 impresiones de mediana a las 72 h',
      lo_que_funciono: [{ texto: 'El post de IA aplicada llegó a 1.200 impresiones.', cifra: 'publicaciones.posts.72h.impresiones: 1200' }],
      lo_que_no: [{ texto: 'Solo 1 de 2 invitaciones resueltas acabó en conexión.', cifra: 'red.aceptacion.conectadas: 1' }],
      recomendaciones: [{ texto: 'Repetir applied_ai: su post tuvo 3,5 % de interacción.', cifra: 'interaccion_pct: 3.5' }],
      orientacion_propuesta: PROPOSAL,
      advertencias: ['Pocos datos: 2 de 3 posts con corte de 72 h.'],
      validacion: { ok: true, descartado: [] },
    },
    model: 'claude-opus-5-5',
    cost_usd: 0.12,
    created_at: '2026-11-09T12:31:00Z',
    decided_at: null,
    decided_by: null,
    can_undo: false,
    ...overrides,
  };
}

function overview(overrides: Partial<WeeklySummaries> = {}): WeeklySummaries {
  return {
    latest: summary(),
    previous: [],
    generate: {
      week_start: '2026-11-02',
      week_end: '2026-11-08',
      label: 'Semana del 2 al 8 de noviembre',
      available: false,
      reason: 'La semana pasada ya tiene su resumen.',
      pending: false,
      last_error: null,
      automatic: true,
      automatic_at: '2026-11-09T12:30:00Z',
      estimated_usd: 0.13,
      max_usd: 0.34,
    },
    ...overrides,
  };
}

function block() {
  return within(screen.getByRole('region', { name: 'Resumen de la semana' }));
}

describe('Resultados · Resumen de la semana', () => {
  it('shows the latest summary first: headline, the three lists with their figure, and the warnings', async () => {
    fakeServer({ 'GET /api/v1/resultados': { body: resultadosFixture() }, [`GET ${URL}`]: { body: overview() } });
    renderAt('/resultados', routes);

    const heading = await screen.findByRole('heading', { level: 3, name: 'Semana con 3 posts y 840 impresiones de mediana a las 72 h' });
    expect(heading).toBeInTheDocument();
    // The block comes before the period controls and the four sections.
    const sections = screen.getAllByRole('region').map((region) => region.getAttribute('id'));
    expect(sections[0]).toBe('resumen');
    expect(block().getByText('Semana del 2 al 8 de noviembre')).toBeInTheDocument();
    expect(block().getByText('Analista del barrio')).toBeInTheDocument();
    expect(block().getByRole('heading', { name: 'Lo que funcionó' })).toBeInTheDocument();
    expect(block().getByText('El post de IA aplicada llegó a 1.200 impresiones.')).toBeInTheDocument();
    expect(block().getByText('Dato: publicaciones.posts.72h.impresiones: 1200')).toBeInTheDocument();
    expect(block().getByText('Solo 1 de 2 invitaciones resueltas acabó en conexión.')).toBeInTheDocument();
    expect(block().getByText('Repetir applied_ai: su post tuvo 3,5 % de interacción.')).toBeInTheDocument();
    expect(block().getByText('Pocos datos: 2 de 3 posts con corte de 72 h.')).toBeInTheDocument();
    expect(block().getByText(PROPOSAL)).toBeInTheDocument();
    expect(block().getByText(/0,12 USD/)).toBeInTheDocument();
    // Nothing to generate: the last week already has its summary.
    expect(block().queryByRole('button', { name: 'Generar ahora' })).not.toBeInTheDocument();
  });

  it('marks a new summary as seen once', async () => {
    const api = fakeServer({
      'GET /api/v1/resultados': { body: resultadosFixture() },
      [`GET ${URL}`]: { body: overview({ latest: summary({ state: 'nuevo', state_label: 'Nuevo' }) }) },
      [`POST ${URL}/s-1/visto`]: { body: { summary: summary() } },
    });
    renderAt('/resultados', routes);
    expect(await block().findByText('Nuevo')).toBeInTheDocument();
    await waitFor(() => expect(api.find('POST', `${URL}/s-1/visto`)).toHaveLength(1));
  });

  it('uses the proposal as the orientation and undoes it from the toast', async () => {
    const api = fakeServer({
      'GET /api/v1/resultados': { body: resultadosFixture() },
      [`GET ${URL}`]: { body: overview() },
      [`POST ${URL}/s-1/aplicar`]: {
        body: { summary: summary({ state: 'aplicado', can_undo: true }), orientation: { text: PROPOSAL }, previous_orientation: 'La de antes.' },
      },
      [`POST ${URL}/s-1/deshacer`]: { body: { summary: summary(), orientation: { text: 'La de antes.' } } },
    });
    const user = userEvent.setup();
    renderAt('/resultados', routes);
    await user.click(await block().findByRole('button', { name: 'Usar como orientación' }));
    await waitFor(() => expect(api.find('POST', `${URL}/s-1/aplicar`)).toHaveLength(1));
    expect(await screen.findByText('Orientación actualizada. El equipo la usa desde su próxima tarea.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Deshacer' }));
    await waitFor(() => expect(api.find('POST', `${URL}/s-1/deshacer`)).toHaveLength(1));
    expect(await screen.findByText('Deshecho')).toBeInTheDocument();
  });

  it('discards the summary, and an undo that fails says why', async () => {
    const api = fakeServer({
      'GET /api/v1/resultados': { body: resultadosFixture() },
      [`GET ${URL}`]: { body: overview() },
      [`POST ${URL}/s-1/descartar`]: { body: { summary: summary({ state: 'descartado', can_undo: true }) } },
      [`POST ${URL}/s-1/deshacer`]: { status: 409, body: { detail: 'La orientación cambió después; edítala en Ajustes.' } },
    });
    const user = userEvent.setup();
    renderAt('/resultados', routes);
    await user.click(await block().findByRole('button', { name: 'Descartar' }));
    await waitFor(() => expect(api.find('POST', `${URL}/s-1/descartar`)).toHaveLength(1));
    expect(await screen.findByText('Resumen descartado')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Deshacer' }));
    expect(await screen.findByText('La orientación cambió después; edítala en Ajustes.')).toBeInTheDocument();
  });

  it('shows a decided proposal without its actions', async () => {
    fakeServer({
      'GET /api/v1/resultados': { body: resultadosFixture() },
      [`GET ${URL}`]: { body: overview({ latest: summary({ state: 'aplicado', state_label: 'Usado como orientación', decided_at: '2026-11-09T14:00:00Z' }) }) },
    });
    renderAt('/resultados', routes);
    expect(await block().findByText(/La usaste como orientación del equipo el/)).toBeInTheDocument();
    expect(block().getByText('Usado como orientación')).toBeInTheDocument();
    expect(block().queryByRole('button', { name: 'Usar como orientación' })).not.toBeInTheDocument();
  });

  it('lists the previous weeks folded', async () => {
    const older = summary({
      id: 's-0',
      label: 'Semana del 26 de octubre al 1 de noviembre',
      state: 'descartado',
      state_label: 'Descartado',
      analysis: { ...summary().analysis, titular: 'Semana sin red', orientacion_propuesta: null },
    });
    fakeServer({ 'GET /api/v1/resultados': { body: resultadosFixture() }, [`GET ${URL}`]: { body: overview({ previous: [older] }) } });
    const user = userEvent.setup();
    renderAt('/resultados', routes);
    const fold = await block().findByText('Ver semanas anteriores · 1');
    await user.click(fold);
    expect(block().getByText('Semana del 26 de octubre al 1 de noviembre')).toBeInTheDocument();
    expect(block().getByText('Semana sin red')).toBeInTheDocument();
    expect(block().getByText('Descartado')).toBeInTheDocument();
  });

  it('asks to confirm the cost before generating a missing summary', async () => {
    const offer = overview().generate;
    const api = fakeServer({
      'GET /api/v1/resultados': { body: resultadosFixture() },
      [`GET ${URL}`]: { body: overview({ latest: null, generate: { ...offer, available: true, reason: null } }) },
      [`POST ${URL}/generar`]: { status: 202, body: { week_start: '2026-11-02', job: { id: 'j-1', status: 'queued' } } },
    });
    const user = userEvent.setup();
    renderAt('/resultados', routes);
    expect(await block().findByText('Todavía no hay resúmenes semanales')).toBeInTheDocument();
    await user.click(block().getByRole('button', { name: 'Generar ahora' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Generar el resumen de la semana' }));
    expect(dialog.getByText(/la semana del 2 al 8 de noviembre/)).toBeInTheDocument();
    expect(dialog.getByText('Tiene coste: unos 0,13 USD (como mucho 0,34 USD), del presupuesto del resumen semanal.')).toBeInTheDocument();
    await user.click(dialog.getByRole('button', { name: 'Generar' }));
    await waitFor(() => expect(api.find('POST', `${URL}/generar`)).toHaveLength(1));
    expect(api.find('POST', `${URL}/generar`)[0]!.body).toEqual({ request_id: expect.any(String) });
    expect(await block().findByText(/El analista está escribiendo el resumen de la semana del 2 al 8 de noviembre/)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('cancelling the confirmation spends nothing', async () => {
    const offer = overview().generate;
    const api = fakeServer({
      'GET /api/v1/resultados': { body: resultadosFixture() },
      [`GET ${URL}`]: { body: overview({ latest: summary({ week_start: '2026-10-26' }), generate: { ...offer, available: true, reason: null } }) },
    });
    const user = userEvent.setup();
    renderAt('/resultados', routes);
    expect(await block().findByText(/Aún no hay resumen de la semana del 2 al 8 de noviembre/)).toBeInTheDocument();
    await user.click(block().getByRole('button', { name: 'Generar ahora' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancelar' }));
    expect(api.find('POST', `${URL}/generar`)).toHaveLength(0);
  });

  it('says when the summary cannot load without hiding the rest of Resultados', async () => {
    fakeServer({ 'GET /api/v1/resultados': { body: resultadosFixture() }, [`GET ${URL}`]: { status: 500, body: { detail: 'Error' } } });
    renderAt('/resultados', routes);
    expect(await screen.findByText('No se pudo cargar el resumen de la semana.')).toBeInTheDocument();
    expect(await screen.findByText('Tasa de aceptación')).toBeInTheDocument();
  });
});
