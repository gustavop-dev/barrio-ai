// Resultados › «Revisión mensual» (?pestana=mensual): the whole report, nuevo → visto, the partial line, what came of
// last month's changes, each proposed change with «Aprobar», «Editar y aprobar» (his text), «Rechazar» (his reason)
// and «Revertir» behind its confirmation, a refused decision that keeps the buttons, the empty state with and without
// «Generar ahora», and the teaser in «Panorama» that opens the tab.
import { monthlyGenerateFixture, monthlyReviewFixture, monthlyReviewsFixture, strategyChangeFixture } from '@compartido/fixtures/revision';
import { resultadosFixture } from '@compartido/fixtures/resultados';
import type { MonthlyReviews, StrategyChange, WeeklySummaries } from '@compartido/api/types';
import { fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import { router } from 'expo-router';
import '@/api/transport';
import { renderApp } from '@/test/render';
import { fakeServer, type FakeHandler } from '@/test/server';
import { ResultadosScreen } from './ResultadosScreen';

const routerState = (jest.requireMock('expo-router') as { __state: { params: Record<string, string> } }).__state;

const URL = '/api/v1/resultados/revision-mensual';
const CHANGE = `${URL}/cambios/ch-1`;
const PROPOSAL = strategyChangeFixture().proposal;
const TITULAR = monthlyReviewFixture().titular!;
const EDITED = 'Publica un caso práctico cada semana, con el problema del cliente arriba.';

const NO_SUMMARY: WeeklySummaries = {
  latest: null,
  previous: [],
  generate: {
    week_start: '2026-11-09',
    week_end: '2026-11-15',
    label: 'Semana del 9 al 15 de noviembre',
    available: false,
    reason: null,
    pending: false,
    last_error: null,
    automatic: false,
    automatic_at: null,
    estimated_usd: 0.13,
    max_usd: 0.34,
  },
};

async function renderRevision(data: MonthlyReviews, routes: Record<string, FakeHandler> = {}, params: Record<string, string> = { pestana: 'mensual' }) {
  routerState.params = params;
  const server = fakeServer({
    'GET /api/v1/resultados': { body: resultadosFixture() },
    'GET /api/v1/resultados/resumen-semanal': { body: NO_SUMMARY },
    [`GET ${URL}`]: { body: data },
    ...routes,
  });
  await renderApp(<ResultadosScreen />);
  return server;
}

/** The overview with one change, as the backend answers once that change is decided. */
function withChange(change: StrategyChange): MonthlyReviews {
  return monthlyReviewsFixture({ latest: monthlyReviewFixture({ changes: [change] }) });
}

const block = () => within(screen.getByTestId('revision-mensual'));
const change = (id = 'ch-1') => within(screen.getByTestId(`revision-cambio-${id}`));
const sheet = async () => within(await screen.findByTestId('confirm-sheet'));

/** Fakes only `Date` (timers stay real so the async queries keep working). */
function useFakeNow(iso: string) {
  jest.useFakeTimers({
    now: new Date(iso),
    doNotFake: ['hrtime', 'nextTick', 'performance', 'queueMicrotask', 'requestAnimationFrame', 'cancelAnimationFrame', 'requestIdleCallback', 'cancelIdleCallback', 'setImmediate', 'clearImmediate', 'setInterval', 'clearInterval', 'setTimeout', 'clearTimeout'],
  });
}

beforeEach(() => {
  routerState.params = {};
});

afterEach(() => {
  jest.useRealTimers();
});

describe('Resultados › Revisión mensual', () => {
  it('is a tab of Resultados with the whole report: headline, method, the lists with their figure and what cannot be concluded', async () => {
    await renderRevision(monthlyReviewsFixture());
    expect(await block().findByText(TITULAR)).toBeOnTheScreen();
    expect(screen.getByRole('tab', { name: 'Revisión mensual · 1' })).toBeSelected();
    expect(block().getByText('Revisión de octubre de 2026')).toBeOnTheScreen();
    expect(block().getByText('Analista del barrio')).toBeOnTheScreen();
    expect(block().getByText(/señala pistas, no es una prueba estadística/)).toBeOnTheScreen();
    for (const title of ['Lo que pasó', 'Lo que funcionó', 'Lo que no', 'Lo que todavía no se puede concluir']) expect(block().getByText(title)).toBeOnTheScreen();
    expect(block().getByText('Se publicaron 9 posts, 2 más que en septiembre.')).toBeOnTheScreen();
    expect(block().getByText('Dato: metricas.publicaciones.mes: 9')).toBeOnTheScreen();
    expect(block().getByText('Los casos prácticos llegaron a 1.180 impresiones de mediana.')).toBeOnTheScreen();
    expect(block().getByText('Solo 3 de 12 invitaciones resueltas acabaron en conexión.')).toBeOnTheScreen();
    expect(block().getByText('• Con 2 posts de opinión no se puede decir si funcionan peor.')).toBeOnTheScreen();
    expect(block().getByText('• Se quitaron 2 frases con cifras que no están en los datos del mes.')).toBeOnTheScreen();
    expect(block().getByText(/0,19 USD/)).toBeOnTheScreen();
    expect(block().queryByText('Parcial')).toBeNull();
    expect(block().queryByText('Generar ahora')).toBeNull();

    // The data notices stay folded.
    expect(block().queryByText('• La semana del 2026-10-26 no tiene posts medidos a las 72 h.')).toBeNull();
    await fireEvent.press(block().getByText('Avisos sobre los datos · 1'));
    expect(block().getByText('• La semana del 2026-10-26 no tiene posts medidos a las 72 h.')).toBeOnTheScreen();
  });

  it('shows each proposed change: the proposal, why, the evidence, what is expected and how it will be measured', async () => {
    await renderRevision(monthlyReviewsFixture());
    await screen.findByTestId('revision-cambio-ch-1');
    expect(block().getByText('Cambios propuestos')).toBeOnTheScreen();
    expect(block().getByText('1 cambio de estrategia espera tu decisión.')).toBeOnTheScreen();
    expect(change().getByText('Más posts de caso práctico')).toBeOnTheScreen();
    expect(change().getByText('Por decidir')).toBeOnTheScreen();
    expect(change().getByText(PROPOSAL)).toBeOnTheScreen();
    expect(change().getByText('Los dos casos prácticos del mes tuvieron el doble de impresiones a las 72 h que el resto.')).toBeOnTheScreen();
    expect(change().getByText('Dato: por_tipo.caso.mediana_impresiones_72h: 1180')).toBeOnTheScreen();
    expect(change().getByText('Comparado con: metricas.mediana_impresiones_72h.mes: 590')).toBeOnTheScreen();
    expect(change().getByText('Que la mediana de impresiones a las 72 h suba el mes que viene.')).toBeOnTheScreen();
    expect(change().getByText('Se medirá con: Mediana de impresiones de los posts a las 72 h')).toBeOnTheScreen();
    expect(change().getByText('Valor del mes revisado: 590')).toBeOnTheScreen();
    expect(change().getByTestId('cambio-aprobar-ch-1')).toBeOnTheScreen();
    expect(change().getByTestId('cambio-editar-ch-1')).toBeOnTheScreen();
    expect(change().getByTestId('cambio-rechazar-ch-1')).toBeOnTheScreen();
    expect(change().queryByTestId('cambio-revertir-ch-1')).toBeNull();
  });

  it('marks a new review as seen once', async () => {
    const server = await renderRevision(monthlyReviewsFixture({ latest: monthlyReviewFixture({ state: 'nuevo', state_label: 'Nueva' }) }), {
      [`POST ${URL}/rv-10/visto`]: { body: { review: monthlyReviewFixture() } },
    });
    expect(await block().findByText('Nueva')).toBeOnTheScreen();
    await waitFor(() => expect(server.find('POST', `${URL}/rv-10/visto`)).toHaveLength(1));
    await waitFor(() => expect(server.find('GET', URL).length).toBeGreaterThan(1));
    expect(server.find('POST', `${URL}/rv-10/visto`)).toHaveLength(1);
  });

  it('says a partial review is partial and why', async () => {
    await renderRevision(monthlyReviewsFixture({ latest: monthlyReviewFixture({ partial: true, semanas_con_datos: 2, semanas_del_mes: 4 }) }));
    expect(await block().findByText('Parcial')).toBeOnTheScreen();
    expect(block().getByTestId('revision-parcial')).toHaveTextContent(
      'Parcial: solo 2 de 4 semanas tienen posts medidos y hacen falta 4 para comparar el mes. Léela como pistas, no como conclusiones.',
    );
  });

  it('says what came of last month’s changes, each with its verdict', async () => {
    await renderRevision(monthlyReviewsFixture());
    const previous = within(await screen.findByTestId('revision-cambios-previos'));
    expect(previous.getByText('Qué pasó con los cambios del mes anterior')).toBeOnTheScreen();
    expect(within(previous.getByTestId('revision-previo-ch-0')).getByText('Se conserva')).toBeOnTheScreen();
    expect(within(previous.getByTestId('revision-previo-ch-0')).getByText('Responder antes a los comentarios')).toBeOnTheScreen();
    expect(within(previous.getByTestId('revision-previo-ch-00')).getByText('Empeoró')).toBeOnTheScreen();
    expect(within(previous.getByTestId('revision-previo-ch-000')).getByText('Sin dato')).toBeOnTheScreen();
    expect(previous.getByText('La tasa de respuesta pasó de 20 a 31.')).toBeOnTheScreen();
    expect(previous.getByText('Dato: metricas.tasa_respuesta_comentarios.mes: 31')).toBeOnTheScreen();
  });

  it('«Aprobar» approves the proposal as it is, and the change then says so', async () => {
    const approved = strategyChangeFixture({ state: 'aprobado', state_label: 'Aprobado', final_text: PROPOSAL, decided_at: '2026-11-16T15:00:00Z', can_decide: false, can_revert: true });
    let current = monthlyReviewsFixture();
    const server = await renderRevision(current, {
      [`GET ${URL}`]: () => ({ body: current }),
      [`POST ${CHANGE}/aprobar`]: () => {
        current = withChange(approved);
        return { body: { change: approved, orientation: { text: PROPOSAL } } };
      },
    });
    await fireEvent.press(await screen.findByTestId('cambio-aprobar-ch-1'));
    await waitFor(() => expect(server.find('POST', `${CHANGE}/aprobar`)).toHaveLength(1));
    expect(server.find('POST', `${CHANGE}/aprobar`)[0]!.body).toEqual({});
    expect(await screen.findByText('Cambio aprobado. El equipo lo usa desde su próxima tarea.')).toBeOnTheScreen();
    expect(await change().findByText(/^Lo aprobaste el .*\. Entró en la orientación del equipo con este texto:$/)).toBeOnTheScreen();
    expect(change().getByText('Aprobado')).toBeOnTheScreen();
    expect(change().getByText(PROPOSAL)).toBeOnTheScreen();
    expect(change().queryByTestId('cambio-aprobar-ch-1')).toBeNull();
    expect(change().getByTestId('cambio-revertir-ch-1')).toBeOnTheScreen();
  });

  it('«Editar y aprobar» opens the proposal to edit, counts its characters and sends his text', async () => {
    const approved = strategyChangeFixture({ state: 'aprobado', state_label: 'Aprobado', final_text: EDITED, decided_at: '2026-11-16T15:00:00Z', can_decide: false, can_revert: true });
    const server = await renderRevision(monthlyReviewsFixture(), { [`POST ${CHANGE}/aprobar`]: { body: { change: approved } } });
    await fireEvent.press(await screen.findByTestId('cambio-editar-ch-1'));
    const confirm = await sheet();
    expect(confirm.getByText('Lo que escribas entra tal cual en la orientación del equipo. Podrás revertirlo desde Resultados.')).toBeOnTheScreen();
    const field = confirm.getByTestId('confirm-note');
    expect(field.props.value).toBe(PROPOSAL);
    expect(field.props.maxLength).toBe(600);
    expect(confirm.getByText(`${PROPOSAL.length} de 600 caracteres`)).toBeOnTheScreen();
    await fireEvent.changeText(field, EDITED);
    expect(confirm.getByText(`${EDITED.length} de 600 caracteres`)).toBeOnTheScreen();
    await fireEvent.press(confirm.getByRole('button', { name: 'Aprobar' }));
    await waitFor(() => expect(server.find('POST', `${CHANGE}/aprobar`)).toHaveLength(1));
    expect(server.find('POST', `${CHANGE}/aprobar`)[0]!.body).toEqual({ text: EDITED });
    expect(await screen.findByText('Cambio aprobado. El equipo lo usa desde su próxima tarea.')).toBeOnTheScreen();
    await waitFor(() => expect(screen.queryByTestId('confirm-sheet')).toBeNull());
  });

  it('«Rechazar» asks for an optional reason and sends it', async () => {
    const rejected = strategyChangeFixture({ state: 'rechazado', state_label: 'Rechazado', decided_at: '2026-11-16T15:00:00Z', decision_note: 'Ya publicamos casos de sobra.', can_decide: false });
    const server = await renderRevision(monthlyReviewsFixture(), { [`POST ${CHANGE}/rechazar`]: { body: { change: rejected } } });
    await fireEvent.press(await screen.findByTestId('cambio-rechazar-ch-1'));
    const confirm = await sheet();
    expect(confirm.getByText('No entra en la orientación. El analista no lo volverá a proponer igual en los próximos tres meses.')).toBeOnTheScreen();
    await fireEvent.changeText(confirm.getByTestId('confirm-note'), 'Ya publicamos casos de sobra.');
    await fireEvent.press(confirm.getByRole('button', { name: 'Rechazar' }));
    await waitFor(() => expect(server.find('POST', `${CHANGE}/rechazar`)).toHaveLength(1));
    expect(server.find('POST', `${CHANGE}/rechazar`)[0]!.body).toEqual({ note: 'Ya publicamos casos de sobra.' });
    expect(await screen.findByText('Cambio rechazado')).toBeOnTheScreen();
  });

  it('shows a rejected change with his reason and without its buttons', async () => {
    const rejected = strategyChangeFixture({ state: 'rechazado', state_label: 'Rechazado', decided_at: '2026-11-16T15:00:00Z', decision_note: 'Ya publicamos casos de sobra.', can_decide: false });
    await renderRevision(withChange(rejected));
    await screen.findByTestId('revision-cambio-ch-1');
    expect(change().getByText('Rechazado')).toBeOnTheScreen();
    expect(change().getByText(/^Lo rechazaste el .*próximos tres meses\.$/)).toBeOnTheScreen();
    expect(change().getByText('Tu nota: Ya publicamos casos de sobra.')).toBeOnTheScreen();
    expect(change().queryByTestId('cambio-aprobar-ch-1')).toBeNull();
    expect(change().queryByTestId('cambio-revertir-ch-1')).toBeNull();
    expect(block().getByText('Ningún cambio espera tu decisión.')).toBeOnTheScreen();
  });

  it('reverts an approved change only after confirming it', async () => {
    const approved = strategyChangeFixture({ state: 'aprobado', state_label: 'Aprobado', final_text: EDITED, decided_at: '2026-11-03T15:00:00Z', can_decide: false, can_revert: true });
    const reverted = { ...approved, state: 'revertido' as const, state_label: 'Revertido', reverted_at: '2026-11-16T15:00:00Z', can_revert: false };
    const server = await renderRevision(withChange(approved), { [`POST ${CHANGE}/revertir`]: { body: { change: reverted, found: true } } });
    await screen.findByTestId('revision-cambio-ch-1');
    expect(change().getByText(EDITED)).toBeOnTheScreen();
    expect(change().getByText(`Propuesta original: «${PROPOSAL}»`)).toBeOnTheScreen();

    await fireEvent.press(change().getByTestId('cambio-revertir-ch-1'));
    let confirm = await sheet();
    expect(confirm.getByText('Se quita de la orientación del equipo exactamente lo que añadió este cambio; lo demás no se toca.')).toBeOnTheScreen();
    await fireEvent.press(confirm.getByText('Cancelar'));
    await waitFor(() => expect(screen.queryByTestId('confirm-sheet')).toBeNull());
    expect(server.find('POST', `${CHANGE}/revertir`)).toHaveLength(0);

    await fireEvent.press(change().getByTestId('cambio-revertir-ch-1'));
    confirm = await sheet();
    await fireEvent.press(confirm.getByRole('button', { name: 'Revertir' }));
    await waitFor(() => expect(server.find('POST', `${CHANGE}/revertir`)).toHaveLength(1));
    expect(server.find('POST', `${CHANGE}/revertir`)[0]!.body).toEqual({});
    expect(await screen.findByText('Cambio revertido: ya no está en la orientación.')).toBeOnTheScreen();
  });

  it('a decision the backend refuses keeps the change and its buttons, and says why', async () => {
    const server = await renderRevision(monthlyReviewsFixture(), { [`POST ${CHANGE}/aprobar`]: { status: 409, body: { detail: 'Este cambio ya se decidió.' } } });
    await fireEvent.press(await screen.findByTestId('cambio-aprobar-ch-1'));
    await waitFor(() => expect(server.find('POST', `${CHANGE}/aprobar`)).toHaveLength(1));
    expect(await change().findByText('Este cambio ya se decidió.')).toBeOnTheScreen();
    expect(change().getByText('No se puede ahora')).toBeOnTheScreen();
    expect(change().getByText('Por decidir')).toBeOnTheScreen();
    expect(change().getByTestId('cambio-aprobar-ch-1')).toBeOnTheScreen();
    expect(screen.queryByText('Cambio aprobado. El equipo lo usa desde su próxima tarea.')).toBeNull();
  });

  it('without a review, offers «Generar ahora» behind the cost confirmation', async () => {
    const server = await renderRevision(monthlyReviewsFixture({ latest: null, generate: monthlyGenerateFixture({ available: true, reason: null }) }), {
      [`POST ${URL}/generar`]: { status: 202, body: { month_start: '2026-10-01', job: { id: 'j-1', status: 'queued' } } },
    });
    expect(await block().findByText('Todavía no hay revisiones mensuales')).toBeOnTheScreen();
    expect(block().getByText(/Necesita alrededor de un mes de datos\./)).toBeOnTheScreen();
    expect(screen.getByRole('tab', { name: 'Revisión mensual' })).toBeSelected();
    await fireEvent.press(block().getByText('Generar ahora'));
    const confirm = await sheet();
    expect(confirm.getByText(/El analista escribe la revisión de octubre de 2026/)).toBeOnTheScreen();
    expect(confirm.getByText('Tiene coste: unos 0,19 USD (como mucho 0,47 USD), del presupuesto de la revisión mensual.')).toBeOnTheScreen();
    await fireEvent.press(confirm.getByRole('button', { name: 'Generar' }));
    await waitFor(() => expect(server.find('POST', `${URL}/generar`)).toHaveLength(1));
    expect(server.find('POST', `${URL}/generar`)[0]!.body).toEqual({ request_id: expect.any(String) });
    expect(await block().findByText(/El analista está escribiendo la revisión de octubre de 2026/)).toBeOnTheScreen();
    await waitFor(() => expect(screen.queryByTestId('confirm-sheet')).toBeNull());
  });

  it('without a review nor one to generate, says why and when the next one arrives', async () => {
    useFakeNow('2026-11-16T12:00:00Z');
    const offer = monthlyGenerateFixture({ available: false, reason: 'Todavía no hay un mes con posts medidos.', automatic_at: '2026-12-07T13:30:00Z' });
    const server = await renderRevision(monthlyReviewsFixture({ latest: null, generate: offer }));
    expect(await block().findByText('Todavía no hay revisiones mensuales')).toBeOnTheScreen();
    expect(block().getByText('Todavía no hay un mes con posts medidos.')).toBeOnTheScreen();
    expect(block().getByText(/El analista la escribe el primer lunes de cada mes a las .*\. La próxima llega el lunes 7 de diciembre\.$/)).toBeOnTheScreen();
    expect(block().queryByText('Generar ahora')).toBeNull();
    expect(server.find('POST', `${URL}/generar`)).toHaveLength(0);
  });

  it('says when the review cannot load, with «Reintentar»', async () => {
    const server = await renderRevision(monthlyReviewsFixture(), { [`GET ${URL}`]: { status: 500, body: { detail: 'Fallo del servidor.' } } });
    expect(await block().findByText('No se pudo cargar la revisión mensual')).toBeOnTheScreen();
    expect(block().getByText('Fallo del servidor.')).toBeOnTheScreen();
    server.on(`GET ${URL}`, { body: monthlyReviewsFixture() });
    await fireEvent.press(block().getByText('Reintentar'));
    expect(await block().findByText(TITULAR)).toBeOnTheScreen();
  });
});

describe('Resultados › Panorama with a monthly review', () => {
  it('shows its headline under the weekly summary and opens the tab', async () => {
    await renderRevision(monthlyReviewsFixture(), {}, {});
    const teaser = within(await screen.findByTestId('revision-mensual-resumen'));
    expect(teaser.getByText(TITULAR)).toBeOnTheScreen();
    expect(teaser.getByText('Revisión de octubre de 2026')).toBeOnTheScreen();
    expect(teaser.getByText('1 cambio de estrategia espera tu decisión.')).toBeOnTheScreen();
    expect(screen.getByRole('tab', { name: 'Panorama' })).toBeSelected();
    expect(screen.getByRole('tab', { name: 'Revisión mensual · 1' })).toBeOnTheScreen();
    await fireEvent.press(teaser.getByText('Ver la revisión'));
    expect(router.setParams).toHaveBeenLastCalledWith({ pestana: 'mensual' });
    expect(await screen.findByTestId('revision-mensual')).toBeOnTheScreen();
    expect(screen.getByRole('tab', { name: 'Revisión mensual · 1' })).toBeSelected();
  });

  it('shows nothing of it while there is no review', async () => {
    await renderRevision(monthlyReviewsFixture({ latest: null }), {}, {});
    expect(await screen.findByText('1 · ¿Genera negocio?')).toBeOnTheScreen();
    expect(screen.queryByTestId('revision-mensual-resumen')).toBeNull();
    expect(screen.getByRole('tab', { name: 'Revisión mensual' })).toBeOnTheScreen();
  });
});
