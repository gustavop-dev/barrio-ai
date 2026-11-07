// Resultados › «Resumen de la semana»: the latest summary, nuevo → visto, «Usar como orientación» and «Descartar»
// with their 5 s «Deshacer», the decided state, the previous weeks folded, and «Generar ahora» behind the cost.
import { resultadosFixture } from '@compartido/fixtures/resultados';
import type { WeeklySummaries, WeeklySummary } from '@compartido/api/types';
import { fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import '@/api/transport';
import { renderApp } from '@/test/render';
import { fakeServer, type FakeHandler } from '@/test/server';
import { ResultadosScreen } from './ResultadosScreen';

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

async function renderSummary(data: WeeklySummaries, routes: Record<string, FakeHandler> = {}) {
  const server = fakeServer({ 'GET /api/v1/resultados': { body: resultadosFixture() }, [`GET ${URL}`]: { body: data }, ...routes });
  await renderApp(<ResultadosScreen />);
  return server;
}

const block = () => within(screen.getByTestId('resumen-semanal'));

describe('Resultados · Resumen de la semana', () => {
  it('shows the latest summary first: headline, the three lists with their figure, and the warnings', async () => {
    await renderSummary(overview());
    expect(await screen.findByText('Semana con 3 posts y 840 impresiones de mediana a las 72 h')).toBeOnTheScreen();
    expect(block().getByText('Semana del 2 al 8 de noviembre')).toBeOnTheScreen();
    expect(block().getByText('Analista del barrio')).toBeOnTheScreen();
    expect(block().getByText('Lo que funcionó')).toBeOnTheScreen();
    expect(block().getByText('El post de IA aplicada llegó a 1.200 impresiones.')).toBeOnTheScreen();
    expect(block().getByText('Dato: publicaciones.posts.72h.impresiones: 1200')).toBeOnTheScreen();
    expect(block().getByText('Solo 1 de 2 invitaciones resueltas acabó en conexión.')).toBeOnTheScreen();
    expect(block().getByText('Repetir applied_ai: su post tuvo 3,5 % de interacción.')).toBeOnTheScreen();
    expect(block().getByText('• Pocos datos: 2 de 3 posts con corte de 72 h.')).toBeOnTheScreen();
    expect(block().getByText(PROPOSAL)).toBeOnTheScreen();
    expect(block().getByText(/0,12 USD/)).toBeOnTheScreen();
    expect(block().queryByText('Generar ahora')).toBeNull();
  });

  it('marks a new summary as seen once', async () => {
    const server = await renderSummary(overview({ latest: summary({ state: 'nuevo', state_label: 'Nuevo' }) }), { [`POST ${URL}/s-1/visto`]: { body: { summary: summary() } } });
    expect(await block().findByText('Nuevo')).toBeOnTheScreen();
    await waitFor(() => expect(server.find('POST', `${URL}/s-1/visto`)).toHaveLength(1));
  });

  it('uses the proposal as the orientation and undoes it from the toast', async () => {
    const server = await renderSummary(overview(), {
      [`POST ${URL}/s-1/aplicar`]: { body: { summary: summary({ state: 'aplicado', can_undo: true }), orientation: { text: PROPOSAL }, previous_orientation: 'La de antes.' } },
      [`POST ${URL}/s-1/deshacer`]: { body: { summary: summary(), orientation: { text: 'La de antes.' } } },
    });
    await fireEvent.press(await block().findByText('Usar como orientación'));
    await waitFor(() => expect(server.find('POST', `${URL}/s-1/aplicar`)).toHaveLength(1));
    expect(await screen.findByText('Orientación actualizada. El equipo la usa desde su próxima tarea.')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Deshacer'));
    await waitFor(() => expect(server.find('POST', `${URL}/s-1/deshacer`)).toHaveLength(1));
    expect(await screen.findByText('Deshecho')).toBeOnTheScreen();
  });

  it('discards the summary, and an undo that fails says why', async () => {
    const server = await renderSummary(overview(), {
      [`POST ${URL}/s-1/descartar`]: { body: { summary: summary({ state: 'descartado', can_undo: true }) } },
      [`POST ${URL}/s-1/deshacer`]: { status: 409, body: { detail: 'La orientación cambió después; edítala en Ajustes.' } },
    });
    await fireEvent.press(await block().findByText('Descartar'));
    await waitFor(() => expect(server.find('POST', `${URL}/s-1/descartar`)).toHaveLength(1));
    expect(await screen.findByText('Resumen descartado')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Deshacer'));
    await waitFor(() => expect(within(screen.getByTestId('toast')).getByText('La orientación cambió después; edítala en Ajustes.')).toBeOnTheScreen());
  });

  it('shows a decided proposal without its actions', async () => {
    await renderSummary(overview({ latest: summary({ state: 'aplicado', state_label: 'Usado como orientación', decided_at: '2026-11-09T14:00:00Z' }) }));
    expect(await block().findByText(/La usaste como orientación del equipo el/)).toBeOnTheScreen();
    expect(block().getByText('Usado como orientación')).toBeOnTheScreen();
    expect(block().queryByText('Usar como orientación')).toBeNull();
  });

  it('lists the previous weeks folded', async () => {
    const older = summary({
      id: 's-0',
      label: 'Semana del 26 de octubre al 1 de noviembre',
      state: 'descartado',
      state_label: 'Descartado',
      analysis: { ...summary().analysis, titular: 'Semana sin red', orientacion_propuesta: null },
    });
    await renderSummary(overview({ previous: [older] }));
    const fold = await block().findByText('Ver semanas anteriores · 1');
    expect(block().queryByText('Semana sin red')).toBeNull();
    await fireEvent.press(fold);
    expect(block().getByText('Semana del 26 de octubre al 1 de noviembre')).toBeOnTheScreen();
    expect(block().getByText('Semana sin red')).toBeOnTheScreen();
    expect(block().getByText('Descartado')).toBeOnTheScreen();
  });

  it('asks to confirm the cost before generating a missing summary', async () => {
    const offer = overview().generate;
    const server = await renderSummary(overview({ latest: null, generate: { ...offer, available: true, reason: null } }), {
      [`POST ${URL}/generar`]: { status: 202, body: { week_start: '2026-11-02', job: { id: 'j-1', status: 'queued' } } },
    });
    expect(await block().findByText('Todavía no hay resúmenes semanales')).toBeOnTheScreen();
    await fireEvent.press(block().getByText('Generar ahora'));
    const sheet = within(await screen.findByTestId('confirm-sheet'));
    expect(sheet.getByText(/la semana del 2 al 8 de noviembre/)).toBeOnTheScreen();
    expect(sheet.getByText('Tiene coste: unos 0,13 USD (como mucho 0,34 USD), del presupuesto del resumen semanal.')).toBeOnTheScreen();
    await fireEvent.press(sheet.getByText('Generar'));
    await waitFor(() => expect(server.find('POST', `${URL}/generar`)).toHaveLength(1));
    expect(server.find('POST', `${URL}/generar`)[0]!.body).toEqual({ request_id: expect.any(String) });
    expect(await block().findByText(/El analista está escribiendo el resumen de la semana del 2 al 8 de noviembre/)).toBeOnTheScreen();
    await waitFor(() => expect(screen.queryByTestId('confirm-sheet')).toBeNull());
  });

  it('cancelling the confirmation spends nothing', async () => {
    const offer = overview().generate;
    const server = await renderSummary(overview({ latest: summary({ week_start: '2026-10-26' }), generate: { ...offer, available: true, reason: null } }));
    expect(await block().findByText(/Aún no hay resumen de la semana del 2 al 8 de noviembre/)).toBeOnTheScreen();
    await fireEvent.press(block().getByText('Generar ahora'));
    await fireEvent.press(within(await screen.findByTestId('confirm-sheet')).getByText('Cancelar'));
    expect(server.find('POST', `${URL}/generar`)).toHaveLength(0);
    expect(screen.queryByTestId('confirm-sheet')).toBeNull();
  });

  it('says when the summary cannot load without hiding the rest of Resultados', async () => {
    await renderSummary(overview(), { [`GET ${URL}`]: { status: 500, body: { detail: 'Error' } } });
    expect(await screen.findByText('No se pudo cargar el resumen de la semana.')).toBeOnTheScreen();
    expect(await screen.findByTestId('kpi-Tasa de aceptación')).toBeOnTheScreen();
  });
});
