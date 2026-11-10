// Resultados: the controls kept in the route params, the KPI «sin dato» rules and the ⓘ sheet, the business
// section, the chart and post taps that open a piece, the posts sorting, the team line, and the errors (one
// with retry when the request fails; one per section when a section arrives broken).
import { kpi, negocioOn, resultadosFixture } from '@compartido/fixtures/resultados';
import type { WeeklySummaries } from '@compartido/api/types';
import { fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import { router } from 'expo-router';
import '@/api/transport';
import { renderApp } from '@/test/render';
import { fakeServer, type FakeHandler, type SentRequest } from '@/test/server';
import { ResultadosScreen } from './ResultadosScreen';

const routerState = (jest.requireMock('expo-router') as { __state: { params: Record<string, string> } }).__state;

const NO_SUMMARY: WeeklySummaries = {
  latest: null,
  previous: [],
  generate: {
    week_start: '2026-11-02',
    week_end: '2026-11-08',
    label: 'Semana del 2 al 8 de noviembre',
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

function query(request: SentRequest): Record<string, string> {
  const search = request.path.split('?')[1] ?? '';
  return Object.fromEntries(search.split('&').filter(Boolean).map((pair) => pair.split('=').map(decodeURIComponent) as [string, string]));
}

async function renderResultados(routes: Record<string, FakeHandler> = {}) {
  const server = fakeServer({
    'GET /api/v1/resultados': { body: resultadosFixture() },
    'GET /api/v1/resultados/resumen-semanal': { body: NO_SUMMARY },
    ...routes,
  });
  await renderApp(<ResultadosScreen />);
  return server;
}

beforeEach(() => {
  routerState.params = {};
});

describe('Resultados', () => {
  it('shows the controls, the period, the section chips and the unavailable business block', async () => {
    await renderResultados();
    expect(screen.getByText('Resultados')).toBeOnTheScreen();
    expect(screen.getByLabelText('Periodo')).toBeOnTheScreen();
    expect(screen.getByRole('tab', { name: '28 días' })).toBeSelected();
    expect(screen.getByRole('button', { name: 'Modalidad' })).toHaveAccessibilityValue({ text: 'Todo' });
    expect(await screen.findByText(/Periodo en curso: datos hasta .*14:20\. Todo se compara con los 28 días anteriores\./)).toBeOnTheScreen();
    for (const chip of ['1 · Negocio', '2 · Gente', '3 · Contenido', '4 · Equipo']) expect(screen.getByText(chip)).toBeOnTheScreen();
    expect(screen.getByText('1 · ¿Genera negocio?')).toBeOnTheScreen();
    expect(screen.getByText('4 · ¿El equipo trabaja bien?')).toBeOnTheScreen();
    expect(screen.getByText('Mediremos oportunidades cuando registres la primera o conectemos el inbox.')).toBeOnTheScreen();
    expect(screen.getByText('Registrar una oportunidad')).toBeOnTheScreen();
    // Inbound keeps its tile while section 1 is unavailable.
    expect(screen.getByTestId('kpi-Inbound')).toBeOnTheScreen();
    expect(screen.queryByText('Oportunidades abiertas')).toBeNull();
  });

  it('never shows «sin dato» as 0 and opens the ⓘ definition with its formula in a sheet', async () => {
    await renderResultados();
    const followers = within(await screen.findByTestId('kpi-Seguidores'));
    expect(followers.getByLabelText('Sin dato')).toBeOnTheScreen();
    expect(followers.getByText('Sin captura de audiencia en este periodo.')).toBeOnTheScreen();
    expect(followers.queryByText('0')).toBeNull();

    const rate = within(screen.getByTestId('kpi-Tasa de aceptación'));
    expect(rate.getByLabelText('41 %')).toBeOnTheScreen();
    expect(rate.getByText('▼ −4 pts')).toBeOnTheScreen();
    await fireEvent.press(rate.getByLabelText('Definición de Tasa de aceptación'));
    const sheet = within(await screen.findByTestId('definition-sheet'));
    expect(sheet.getByText('Fórmula: conectados / (conectados + cerrados) × 100')).toBeOnTheScreen();

    expect(within(screen.getByTestId('kpi-Constancia')).getByText('24 de 28')).toBeOnTheScreen();
    expect(within(screen.getByTestId('kpi-Impresiones')).getByText('▲ 12 %')).toBeOnTheScreen();
  });

  it('changes the period and the modality, keeping them in the route params', async () => {
    const server = await renderResultados({
      'GET /api/v1/resultados': (request) => ({ body: resultadosFixture({ periodo: { ...resultadosFixture().periodo, dias: Number(query(request).dias) as 7 } }) }),
    });
    await screen.findByText(/Periodo en curso/);
    expect(query(server.find('GET', '/api/v1/resultados')[0]!).dias).toBe('28');

    await fireEvent.press(screen.getByRole('tab', { name: '7 días' }));
    expect(router.setParams).toHaveBeenLastCalledWith({ dias: '7', modalidad: undefined });
    expect(await screen.findByText(/Todo se compara con los 7 días anteriores/)).toBeOnTheScreen();

    await fireEvent.press(screen.getByRole('button', { name: 'Modalidad' }));
    await fireEvent.press(screen.getByRole('radio', { name: 'ProjectApp' }));
    await waitFor(() => expect(query(server.find('GET', '/api/v1/resultados').at(-1)!)).toEqual({ dias: '7', modalidad: 'projectapp' }));
    expect(router.setParams).toHaveBeenLastCalledWith({ dias: '7', modalidad: 'projectapp' });
    expect(screen.getAllByText('No se separa por modalidad: muestra toda la cuenta.')).toHaveLength(2);
  });

  it('reads the period and modality of a link (?dias=90&modalidad=personal_startups)', async () => {
    routerState.params = { dias: '90', modalidad: 'personal_startups' };
    const server = await renderResultados();
    await waitFor(() => expect(query(server.find('GET', '/api/v1/resultados')[0]!)).toEqual({ dias: '90', modalidad: 'personal_startups' }));
    expect(screen.getByRole('button', { name: 'Modalidad' })).toHaveAccessibilityValue({ text: 'Startups' });
  });

  it('draws section 1 when there are opportunities: KPIs, funnel, the 60/40 split and the active ones', async () => {
    await renderResultados({ 'GET /api/v1/resultados': { body: resultadosFixture({ negocio: negocioOn() }) } });
    const conversations = within(await screen.findByTestId('kpi-Conversaciones pertinentes'));
    expect(conversations.getByText('Disponible cuando conectemos el inbox.')).toBeOnTheScreen();
    const open = within(screen.getByTestId('kpi-Oportunidades abiertas'));
    expect(open.getByLabelText('2')).toBeOnTheScreen();
    expect(open.getByText('▲ 1')).toBeOnTheScreen();
    expect(within(screen.getByTestId('kpi-Propuestas enviadas')).getByText('= igual que antes')).toBeOnTheScreen();

    expect(screen.getByLabelText('Necesidad identificada: 3, 75 % del paso anterior')).toBeOnTheScreen();
    expect(screen.getByText('Cerrada sin acuerdo: 1')).toBeOnTheScreen();
    expect(screen.getByLabelText('Startups 50 %, ProjectApp 50 %, objetivo 60/40')).toBeOnTheScreen();
    expect(screen.getByText('1 oportunidad por clasificar no cuenta en el reparto.')).toBeOnTheScreen();
    expect(screen.getByText('Siguiente: Enviar la propuesta de piloto · 12 nov')).toBeOnTheScreen();
    expect(screen.queryByText('Registrar una oportunidad')).toBeNull();

    await fireEvent.press(screen.getByRole('link', { name: /Lucía Ficticia/ }));
    expect(router.push).toHaveBeenLastCalledWith({ pathname: '/personas/c-1', params: {} });
    await fireEvent.press(screen.getByRole('link', { name: /Mario Externo/ }));
    expect(router.navigate).toHaveBeenLastCalledWith({ pathname: '/personas', params: { pestana: 'oportunidades' } });
  });

  it('shows the audience funnel with the discarded aside and the roles without conversion', async () => {
    await renderResultados();
    expect(await screen.findByLabelText('Encaja: 21, 55 % del paso anterior')).toBeOnTheScreen();
    expect(screen.getByText('Descartados: 6 · Cerrados: 2 · Te invitaron: 1')).toBeOnTheScreen();
    expect(screen.getByLabelText('Comprador: 3')).toBeOnTheScreen();
    expect(screen.getByLabelText('Par: 2')).toBeOnTheScreen();
  });

  it('opens the piece from a bar of the chart, from the best post and from a post card', async () => {
    await renderResultados();
    await fireEvent.press(await screen.findByLabelText('Post 1, 2 nov: 1.840 impresiones'));
    expect(router.push).toHaveBeenLastCalledWith({ pathname: '/calendario/pieza/[id]', params: { id: 'p-1' } });
    await fireEvent.press(screen.getByLabelText('Post 2, 5 nov: 960 impresiones a las 24 h'));
    expect(router.push).toHaveBeenLastCalledWith({ pathname: '/calendario/pieza/[id]', params: { id: 'p-2' } });
    expect(screen.getByLabelText('Post 3, 7 nov: sin dato')).toBeOnTheScreen();
    expect(screen.getByText('La línea es la mediana de las 4 semanas anteriores (1.250). Toca una barra para ver la pieza.')).toBeOnTheScreen();

    expect(screen.getByText('2 nov · IA aplicada · 1.840 impresiones · 3,1 %')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Ver la pieza'));
    expect(router.push).toHaveBeenLastCalledWith({ pathname: '/calendario/pieza/[id]', params: { id: 'p-1' } });

    await fireEvent.press(within(screen.getByTestId('post-p-3')).getByText('Scope features from the decision they support.'));
    expect(router.push).toHaveBeenLastCalledWith({ pathname: '/calendario/pieza/[id]', params: { id: 'p-3' } });
  });

  it('lists the pillars and the posts as cards, sorted with «Ordenar por»', async () => {
    await renderResultados();
    const pillars = within(await screen.findByTestId('bars-Interacción media por pilar'));
    expect(pillars.getByText('3,4 %')).toBeOnTheScreen();
    expect(pillars.getByLabelText(/Arquitectura y entrega.*sin dato/)).toBeOnTheScreen();

    const order = () => screen.getAllByTestId(/^post-p-/).map((card) => card.props.testID);
    expect(order()).toEqual(['post-p-3', 'post-p-2', 'post-p-1']);
    expect(within(screen.getByTestId('post-p-3')).getByText('Aún sin corte')).toBeOnTheScreen();
    expect(within(screen.getByTestId('post-p-1')).getByText('Comprador · 3')).toBeOnTheScreen();
    expect(within(screen.getByTestId('post-p-3')).getByLabelText('24 h: sin dato')).toBeOnTheScreen();

    await fireEvent.press(screen.getByRole('button', { name: 'Ordenar por' }));
    await fireEvent.press(screen.getByRole('radio', { name: 'Impresiones a 7 días' }));
    expect(order()[0]).toBe('post-p-1');
  });

  it('summarises the team in compact stats, with the AI spend of the day and the month', async () => {
    await renderResultados();
    const comments = within(await screen.findByTestId('stat-Comentarios'));
    expect(comments.getByText('24 publicados · — con respuesta')).toBeOnTheScreen();
    expect(comments.getByLabelText('24 publicados · sin dato de con respuesta')).toBeOnTheScreen();
    expect(within(screen.getByTestId('stat-Red')).getByText('31 seguidos · 12 invitados · 5 aceptados')).toBeOnTheScreen();
    expect(within(screen.getByTestId('stat-Piezas')).getByText('24 publicadas · 1 bloqueada · 0 vetadas')).toBeOnTheScreen();
    await fireEvent.press(within(screen.getByTestId('stat-Red')).getByLabelText('Definición de Red'));
    expect(within(await screen.findByTestId('definition-sheet')).getByText('Seguidos: Definición de prueba.')).toBeOnTheScreen();
    const spend = within(screen.getByTestId('stat-Gasto de IA'));
    expect(spend.getByText('3,10 USD hoy')).toBeOnTheScreen();
    expect(spend.getByText('61,20 de 100,00 USD este mes')).toBeOnTheScreen();
  });

  it('opens the opportunity form from the unavailable block and registers one', async () => {
    const server = await renderResultados({
      'POST /api/v1/oportunidades': (request) => ({ status: 201, body: { id: 'o-9', ...(request.body as object) } }),
    });
    await fireEvent.press(await screen.findByText('Registrar una oportunidad'));
    const form = within(await screen.findByTestId('opportunity-form'));
    await fireEvent.press(form.getByRole('radio', { name: 'Alguien fuera de la red' }));
    await fireEvent.changeText(form.getByTestId('opp-name'), 'Mario Externo');
    await fireEvent.changeText(form.getByTestId('opp-company'), 'Cosecha Data');
    await fireEvent.press(form.getByRole('button', { name: 'Modalidad' }));
    await fireEvent.press(form.getByRole('radio', { name: 'Startups (personal)' }));
    await fireEvent.press(form.getByRole('button', { name: 'Cómo llegó' }));
    await fireEvent.press(form.getByRole('radio', { name: 'Lo dijo la persona' }));
    await fireEvent.press(form.getByText('Registrar oportunidad'));

    await waitFor(() => expect(server.find('POST', '/api/v1/oportunidades')).toHaveLength(1));
    expect(server.find('POST', '/api/v1/oportunidades')[0]!.body).toMatchObject({
      contact: null,
      person_name: 'Mario Externo',
      company: 'Cosecha Data',
      modality: 'personal_startups',
      channel: 'linkedin',
      stage: 'conversacion',
      attribution: 'lo_dijo',
      next_action_at: null,
    });
    expect(await screen.findByText('Oportunidad registrada')).toBeOnTheScreen();
    expect(screen.queryByTestId('opportunity-form')).toBeNull();
  });

  it('shows one error with retry when the results cannot load', async () => {
    const server = await renderResultados({ 'GET /api/v1/resultados': { status: 500, body: { detail: 'Error del servidor' } } });
    expect(await screen.findByText('No se pudieron cargar los resultados')).toBeOnTheScreen();
    expect(screen.getAllByText('No se pudo cargar esta sección.')).toHaveLength(4);
    server.on('GET /api/v1/resultados', { body: resultadosFixture() });
    await fireEvent.press(screen.getByText('Reintentar'));
    expect(await screen.findByText(/Periodo en curso/)).toBeOnTheScreen();
  });

  it('keeps the other sections when one arrives broken', async () => {
    jest.spyOn(console, 'error').mockImplementation(() => {});
    const broken = resultadosFixture();
    (broken as unknown as { contenido: null }).contenido = null;
    await renderResultados({ 'GET /api/v1/resultados': { body: broken } });
    expect(await screen.findByText('No se pudo mostrar esta sección')).toBeOnTheScreen();
    expect(screen.getByTestId('kpi-Tasa de aceptación')).toBeOnTheScreen();
    expect(screen.getByTestId('stat-Gasto de IA')).toBeOnTheScreen();
  });

  it('builds KPI fixtures with a comparable delta', () => {
    expect(kpi(5).delta).toBe(1);
  });
});
