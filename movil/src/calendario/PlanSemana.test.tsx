// «La semana» (Calendario › Semana): the type and planned idea of each day with the reader's need and the audience
// signal behind it, a day's sheet (type, swap, discard) and «Volver a planear» behind its cost.
import { semanaFixture } from '@compartido/fixtures/estrategia';
import { fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import '@/api/transport';
import { renderApp } from '@/test/render';
import { fakeServer, type FakeHandler } from '@/test/server';
import { evidenceLine, monthLine, PlanSemana } from './PlanSemana';

function server(routes: Record<string, FakeHandler> = {}) {
  return fakeServer({ 'GET /api/v1/estrategia/semana': { body: semanaFixture() }, ...routes });
}

describe('La semana', () => {
  it('shows each day with its type, idea, what the reader needs and the audience signal behind it', async () => {
    const api = server();
    await renderApp(<PlanSemana fecha="2026-11-10" today="2026-11-07" />);
    const card = await screen.findByTestId('plan-semana');
    expect(api.find('GET', '/api/v1/estrategia/semana')[0]?.path).toBe('/api/v1/estrategia/semana?dia=2026-11-10');
    expect(within(card).getByText('Planeada')).toBeOnTheScreen();
    expect(within(card).getByText('What an MVP really needs on day one')).toBeOnTheScreen();
    expect(within(card).getByText('Para el lector: Decidir el alcance de su MVP esta semana.')).toBeOnTheScreen();
    expect(within(card).getByTestId('plan-senal-2026-11-09')).toHaveTextContent('Algo que contaste de un comprador: Un comprador preguntó si necesita app móvil desde el día uno.');
    expect(within(card).getByTestId('plan-senal-2026-11-12')).toHaveTextContent('Sin señal de la audiencia todavía: el director la busca ese día.');
    expect(within(card).getByText('Convertir atención en conversaciones')).toBeOnTheScreen();  // a day without idea says what its type is for
    expect(within(card).getByTestId('plan-mes')).toHaveTextContent('En cuatro semanas: Crecimiento 36 % · Autoridad 29 % · Venta 21 % · Personal 14 %');
  });

  it('changes the type of a day from its sheet', async () => {
    const api = server({ 'PATCH /api/v1/estrategia/dias/2026-11-09': { body: semanaFixture() } });
    await renderApp(<PlanSemana fecha="2026-11-10" today="2026-11-07" />);
    await fireEvent.press(await screen.findByTestId('plan-dia-2026-11-09'));
    const sheet = await screen.findByTestId('plan-dia-hoja');
    expect(within(sheet).getByText('Si cambias el tipo, su idea queda apartada para otro día.')).toBeOnTheScreen();
    await fireEvent.press(within(sheet).getByText('Personal'));
    await waitFor(() => expect(api.find('PATCH', '/api/v1/estrategia/dias/2026-11-09')[0]?.body).toEqual({ tipo: 'P' }));
  });

  it('swaps two days and discards a planned idea', async () => {
    const api = server({
      'POST /api/v1/estrategia/mover': { body: semanaFixture() },
      'PATCH /api/v1/estrategia/dias/2026-11-12': { body: semanaFixture() },
    });
    await renderApp(<PlanSemana fecha="2026-11-10" today="2026-11-07" />);
    await fireEvent.press(await screen.findByTestId('plan-dia-2026-11-09'));
    await fireEvent.press(within(await screen.findByTestId('plan-dia-hoja')).getByText('sáb 14 · Personal'));
    await waitFor(() => expect(api.find('POST', '/api/v1/estrategia/mover')[0]?.body).toEqual({ desde: '2026-11-09', hasta: '2026-11-14' }));
    await waitFor(() => expect(screen.queryByTestId('plan-dia-hoja')).toBeNull());
    await fireEvent.press(screen.getByTestId('plan-dia-2026-11-12'));
    await fireEvent.press(within(await screen.findByTestId('plan-dia-hoja')).getByTestId('plan-descartar'));
    await waitFor(() => expect(api.find('PATCH', '/api/v1/estrategia/dias/2026-11-12')[0]?.body).toEqual({ descartar_idea: true }));
  });

  it('a day already prepared keeps its type', async () => {
    const plan = semanaFixture();
    plan.days[0] = { ...plan.days[0]!, editable: false };
    server({ 'GET /api/v1/estrategia/semana': { body: plan } });
    await renderApp(<PlanSemana fecha="2026-11-10" today="2026-11-07" />);
    await fireEvent.press(await screen.findByTestId('plan-dia-2026-11-09'));
    const sheet = await screen.findByTestId('plan-dia-hoja');
    expect(within(sheet).getByText('Ese día ya pasó o su post ya está preparado: su tipo no cambia.')).toBeOnTheScreen();
    expect(within(sheet).queryByTestId('plan-tipo')).toBeNull();
  });

  it('plans the week again only after showing what it costs', async () => {
    const api = server({ 'POST /api/v1/estrategia/planear': { status: 202, body: { job: { id: 'j1' } } } });
    await renderApp(<PlanSemana fecha="2026-11-10" today="2026-11-07" />);
    await fireEvent.press(await screen.findByTestId('plan-volver-a-planear'));
    const sheet = await screen.findByTestId('confirm-sheet');
    expect(within(sheet).getByText(/Tiene coste: unos 0,20 USD \(como mucho 0,47 USD\)/)).toBeOnTheScreen();
    expect(api.find('POST', '/api/v1/estrategia/planear')).toHaveLength(0);
    await fireEvent.press(within(sheet).getByText('Planear'));
    await waitFor(() => expect(api.find('POST', '/api/v1/estrategia/planear')[0]?.body).toMatchObject({ semana: '2026-11-09' }));
    expect(await screen.findByText('El director está planeando la semana. Tarda uno o dos minutos y aparecerá aquí.')).toBeOnTheScreen();
  });

  it('shows nothing for a week that already passed or with the strategy off', async () => {
    server();
    const { unmount } = await renderApp(<PlanSemana fecha="2026-10-28" today="2026-11-07" />);
    expect(screen.queryByTestId('plan-semana')).toBeNull();
    unmount();
    server({ 'GET /api/v1/estrategia/semana': { body: semanaFixture({ enabled: false }) } });
    await renderApp(<PlanSemana fecha="2026-11-10" today="2026-11-07" />);
    await waitFor(() => expect(screen.queryByText('Cargando la semana…')).toBeNull());
    expect(screen.queryByTestId('plan-semana')).toBeNull();
  });
});

describe('La semana, its lines', () => {
  it('says which audience signal backs an idea, or that there is none yet', () => {
    const plan = semanaFixture();
    expect(evidenceLine(plan.days[0]!)).toBe('Algo que contaste de un comprador: Un comprador preguntó si necesita app móvil desde el día uno.');
    expect(evidenceLine(plan.days[3]!)).toBe('Sin señal de la audiencia todavía: el director la busca ese día.');
    expect(evidenceLine(plan.days[1]!)).toBeNull();
    expect(monthLine(plan)).toBe('Crecimiento 36 % · Autoridad 29 % · Venta 21 % · Personal 14 %');
  });
});
