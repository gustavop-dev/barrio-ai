// Resultados › Analítica de LinkedIn: the tab of ?pestana=linkedin, the request each period sends (presets, a custom
// range checked against the imported days, a link's range), the figures with their formats, and each state: partial
// or not comparable, members reached and top lists missing, a failed import, an error with «Reintentar», and the
// answer without a «directo» account that production gives today.
import { analiticaFixture, SIN_CUENTA } from '@compartido/fixtures/analitica';
import { kpi, resultadosFixture } from '@compartido/fixtures/resultados';
import type { AnaliticaData, WeeklySummaries } from '@compartido/api/types';
import { fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import { router } from 'expo-router';
import '@/api/transport';
import { renderApp } from '@/test/render';
import { fakeServer, type FakeHandler, type SentRequest } from '@/test/server';
import { ResultadosScreen } from './ResultadosScreen';

const routerState = (jest.requireMock('expo-router') as { __state: { params: Record<string, string> } }).__state;

const URL = '/api/v1/resultados/analitica';

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

const FAILED = { at: '2026-11-13T07:10:00Z', tipo: 'diaria', kind: 'blocked', error: 'Analítica detenida por el proveedor: LinkedIn pidió verificar la cuenta' };

function query(request: SentRequest): Record<string, string> {
  const search = request.path.split('?')[1] ?? '';
  return Object.fromEntries(search.split('&').filter(Boolean).map((pair) => pair.split('=').map(decodeURIComponent) as [string, string]));
}

/** The fixture with the period the request asked for, as the backend answers it. */
function answer(request: SentRequest): { body: AnaliticaData } {
  const asked = query(request);
  const base = analiticaFixture();
  if (asked.desde && asked.hasta) {
    const days = Math.round((Date.parse(asked.hasta) - Date.parse(asked.desde)) / 86_400_000) + 1;
    return { body: analiticaFixture({ periodo: { ...base.periodo, desde: asked.desde, hasta: asked.hasta, dias: days, preset: null } }) };
  }
  return { body: analiticaFixture({ periodo: { ...base.periodo, preset: (asked.periodo as AnaliticaData['periodo']['preset']) ?? null } }) };
}

async function renderAnalitica(routes: Record<string, FakeHandler> = {}, params: Record<string, string> = { pestana: 'linkedin' }) {
  routerState.params = params;
  const server = fakeServer({
    [`GET ${URL}`]: answer,
    'GET /api/v1/resultados': { body: resultadosFixture() },
    'GET /api/v1/resultados/resumen-semanal': { body: NO_SUMMARY },
    ...routes,
  });
  await renderApp(<ResultadosScreen />);
  return server;
}

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

describe('Resultados › Analítica de LinkedIn', () => {
  it('is a tab of Resultados kept in ?pestana=, next to «Panorama»', async () => {
    const server = await renderAnalitica({}, {});
    expect(screen.getByRole('tab', { name: 'Panorama' })).toBeSelected();
    expect(server.find('GET', URL)).toHaveLength(0);

    await fireEvent.press(screen.getByRole('tab', { name: 'Analítica de LinkedIn' }));
    expect(router.setParams).toHaveBeenLastCalledWith({ pestana: 'linkedin' });
    expect(await screen.findByTestId('ana-periodo-nota')).toBeOnTheScreen();
    expect(screen.getByRole('tab', { name: 'Analítica de LinkedIn' })).toBeSelected();
    expect(screen.queryByText('1 · ¿Genera negocio?')).toBeNull();

    await fireEvent.press(screen.getByRole('tab', { name: 'Panorama' }));
    expect(router.setParams).toHaveBeenLastCalledWith({ pestana: undefined });
    expect(await screen.findByText('1 · ¿Genera negocio?')).toBeOnTheScreen();
  });

  it('asks for 28 days by default and for each preset chosen, kept in ?periodo=', async () => {
    const server = await renderAnalitica();
    await screen.findByTestId('ana-periodo-nota');
    expect(query(server.find('GET', URL)[0]!)).toEqual({ periodo: '28d' });
    expect(screen.getByRole('tab', { name: '28 días' })).toBeSelected();
    for (const label of ['7 días', '14 días', '28 días', '90 días', '365 días']) expect(screen.getByRole('tab', { name: label })).toBeOnTheScreen();

    await fireEvent.press(screen.getByRole('tab', { name: '90 días' }));
    expect(router.setParams).toHaveBeenLastCalledWith({ periodo: '90d', desde: undefined, hasta: undefined });
    await waitFor(() => expect(query(server.find('GET', URL).at(-1)!)).toEqual({ periodo: '90d' }));
    expect(screen.getByRole('tab', { name: '90 días' })).toBeSelected();

    await fireEvent.press(screen.getByRole('tab', { name: '365 días' }));
    await waitFor(() => expect(query(server.find('GET', URL).at(-1)!)).toEqual({ periodo: '365d' }));
    await fireEvent.press(screen.getByRole('tab', { name: '7 días' }));
    await waitFor(() => expect(query(server.find('GET', URL).at(-1)!)).toEqual({ periodo: '7d' }));
    expect(router.setParams).toHaveBeenLastCalledWith({ periodo: '7d', desde: undefined, hasta: undefined });
  });

  it('checks «Personalizado» against the imported days, then asks for desde and hasta', async () => {
    const server = await renderAnalitica();
    await screen.findByTestId('ana-periodo-nota');
    await fireEvent.press(screen.getByRole('button', { name: 'Personalizado' }));
    const sheet = within(await screen.findByTestId('ana-rango'));
    expect(sheet.getByText('Hay datos del 10 oct de 2025 al 12 nov de 2026 (UTC). Como mucho 366 días.')).toBeOnTheScreen();
    // It starts from the period on screen.
    expect(sheet.getByLabelText('Desde').props.value).toBe('2026-11-06');
    expect(sheet.getByLabelText('Hasta').props.value).toBe('2026-11-12');
    const sent = server.find('GET', URL).length;

    await fireEvent.changeText(sheet.getByLabelText('Desde'), '2025-10-01');
    await fireEvent.press(sheet.getByText('Ver este periodo'));
    expect(sheet.getByText('Elige un día entre el 10 oct de 2025 y el 12 nov de 2026.')).toBeOnTheScreen();

    await fireEvent.changeText(sheet.getByLabelText('Desde'), '2026-1-1');
    expect(sheet.getByText('Escribe la fecha como AAAA-MM-DD.')).toBeOnTheScreen();

    await fireEvent.changeText(sheet.getByLabelText('Desde'), '2026-10-12');
    await fireEvent.changeText(sheet.getByLabelText('Hasta'), '2026-10-01');
    await fireEvent.press(sheet.getByText('Ver este periodo'));
    expect(sheet.getByText('«Desde» no puede ser posterior a «Hasta».')).toBeOnTheScreen();
    expect(server.find('GET', URL)).toHaveLength(sent);

    await fireEvent.changeText(sheet.getByLabelText('Desde'), '2026-10-01');
    await fireEvent.changeText(sheet.getByLabelText('Hasta'), '2026-10-10');
    await fireEvent.press(sheet.getByText('Ver este periodo'));
    expect(router.setParams).toHaveBeenLastCalledWith({ periodo: undefined, desde: '2026-10-01', hasta: '2026-10-10' });
    await waitFor(() => expect(query(server.find('GET', URL).at(-1)!)).toEqual({ desde: '2026-10-01', hasta: '2026-10-10' }));
    expect(await screen.findByText('Del 1 oct al 10 oct de 2026 · 10 días (UTC). Se compara con los 10 días anteriores.')).toBeOnTheScreen();
    expect(screen.queryByTestId('ana-rango')).toBeNull();
    expect(screen.getByRole('button', { name: 'Personalizado' })).toBeSelected();
    for (const label of ['7 días', '28 días', '365 días']) expect(screen.getByRole('tab', { name: label })).not.toBeSelected();
  });

  it('reads the custom range of a link (?desde=&hasta=) and ignores one that is not valid', async () => {
    const server = await renderAnalitica({}, { pestana: 'linkedin', desde: '2026-10-01', hasta: '2026-10-10' });
    await waitFor(() => expect(query(server.find('GET', URL)[0]!)).toEqual({ desde: '2026-10-01', hasta: '2026-10-10' }));
    expect(await screen.findByRole('button', { name: 'Personalizado' })).toBeSelected();
  });

  it('asks for the preset of a link when its range is reversed', async () => {
    const server = await renderAnalitica({}, { pestana: 'linkedin', periodo: '14d', desde: '2026-10-10', hasta: '2026-10-01' });
    await waitFor(() => expect(query(server.find('GET', URL)[0]!)).toEqual({ periodo: '14d' }));
  });

  it('shows the figures with their formats: KPIs, the daily chart, followers, posts, top lists and the audience', async () => {
    useFakeNow('2026-11-13T09:10:00Z');
    await renderAnalitica();
    expect(await screen.findByText('Del 6 nov al 12 nov de 2026 · 7 días (UTC). Se compara con los 7 días anteriores.')).toBeOnTheScreen();
    expect(screen.getByText('Actualizado hace 3 h.')).toBeOnTheScreen();

    const impressions = within(screen.getByTestId('kpi-Impresiones'));
    expect(impressions.getByLabelText('840')).toBeOnTheScreen();
    expect(impressions.getByText('▲ 20 %')).toBeOnTheScreen();
    expect(within(screen.getByTestId('kpi-Seguidores nuevos')).getByText('▼ −2')).toBeOnTheScreen();
    const rate = within(screen.getByTestId('kpi-Tasa de interacción'));
    expect(rate.getByLabelText('5 %')).toBeOnTheScreen();
    expect(rate.getByText('= igual que antes')).toBeOnTheScreen();
    const reached = within(screen.getByTestId('kpi-Miembros alcanzados'));
    expect(reached.getByLabelText('612')).toBeOnTheScreen();
    expect(reached.getByText('sin comparación')).toBeOnTheScreen();
    expect(screen.queryByTestId('ana-cobertura')).toBeNull();
    expect(screen.queryByTestId('ana-error-importacion')).toBeNull();

    // The daily chart: its summary for screen readers, another figure, and a tapped day.
    expect(screen.getByLabelText('Impresiones por día del 6 nov al 12 nov de 2026: 840 impresiones en total; el día con más fue el 9 nov de 2026, con 150.')).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('tab', { name: 'Interacciones' }));
    const chart = screen.getByTestId('ana-grafico');
    expect(chart).toHaveAccessibleName('Interacciones por día del 6 nov al 12 nov de 2026: 42 interacciones en total; el día con más fue el 9 nov de 2026, con 8.');
    expect(screen.getByText('Toca el gráfico para ver un día.')).toBeOnTheScreen();
    await fireEvent(chart, 'layout', { nativeEvent: { layout: { x: 0, y: 0, width: 308, height: 140 } } });
    await fireEvent.press(chart, { nativeEvent: { locationX: 4 } });
    expect(screen.getByText('6 nov de 2026: 5 interacciones')).toBeOnTheScreen();

    expect(screen.getByLabelText('1.480 seguidores, según LinkedIn el 13 nov de 2026, suben 7 desde el 6 nov')).toBeOnTheScreen();
    expect(screen.getByText('+7 desde el 6 nov')).toBeOnTheScreen();

    // Posts: lifetime figures as of their day, «—» for what LinkedIn did not give, the piece when it is one of ours.
    expect(screen.getByText(/^2 publicaciones\. Publicaciones del periodo con sus cifras de toda la vida/)).toBeOnTheScreen();
    const first = within(screen.getByTestId('ana-post-0'));
    expect(first.getByText('Publicada el 10 nov de 2026 · Imagen')).toBeOnTheScreen();
    expect(first.getByText('Desde que se publicó, al 13 nov de 2026')).toBeOnTheScreen();
    expect(first.getByLabelText('Impresiones: 1.840')).toBeOnTheScreen();
    expect(first.getByText('De tu red 62,5 % · fuera 37,5 %')).toBeOnTheScreen();
    await fireEvent.press(first.getByText('Abrir la pieza'));
    expect(router.push).toHaveBeenCalledWith({ pathname: '/calendario/pieza/[id]', params: { id: 'pieza-analitica-1' } });
    const second = within(screen.getByTestId('ana-post-1'));
    expect(second.getByLabelText('Alcanzados: sin dato')).toBeOnTheScreen();
    expect(second.queryByText('Abrir la pieza')).toBeNull();
    expect(second.getByText('Ver en LinkedIn')).toBeOnTheScreen();

    expect(screen.getByText('Según LinkedIn, del 6 nov al 12 nov de 2026.')).toBeOnTheScreen();
    expect(within(screen.getByTestId('bars-Principales por impresiones')).getByLabelText('Post del 10 nov: 1.840')).toBeOnTheScreen();
    expect(within(screen.getByTestId('bars-Principales por interacciones')).getByLabelText('Post del 7 nov: 14')).toBeOnTheScreen();

    expect(screen.getByText('Tus seguidores, según LinkedIn el 13 nov de 2026.')).toBeOnTheScreen();
    expect(screen.getByLabelText('Gerente de producto: < 1 %')).toBeOnTheScreen();
    expect(screen.getByLabelText('Fundador: 18,5 %')).toBeOnTheScreen();
    expect(screen.getByText('Quienes vieron tus publicaciones del 6 nov al 12 nov de 2026.')).toBeOnTheScreen();
    expect(screen.getByLabelText('Desarrollo de software: 33 %')).toBeOnTheScreen();
  });

  it('says when days are missing, members reached and the top lists are not for this period, and the nearest content range', async () => {
    const base = analiticaFixture();
    const partial = analiticaFixture({
      totales: {
        ...base.totales,
        impressions: { ...base.totales.impressions, value: 600, comparable: false, delta: null, delta_pct: null, days_with_data: 5 },
        members_reached: kpi(null, {
          previous: null,
          comparable: false,
          unavailable_reason: 'LinkedIn da los miembros alcanzados solo para un rango completo y no se pueden sumar por días; este periodo exacto no se ha importado.',
        }),
      },
      posts: { ...base.posts, publicados: [], top_linkedin: null, top_unavailable_reason: 'LinkedIn da sus publicaciones principales solo para el rango que se le pide; este periodo exacto no se ha importado.' },
      demografia: { ...base.demografia, contenido: { ...base.demografia.contenido!, desde: '2026-10-16', exacto: false } },
    });
    await renderAnalitica({ [`GET ${URL}`]: { body: partial } });
    const impressions = within(await screen.findByTestId('kpi-Impresiones'));
    expect(impressions.getByLabelText('600')).toBeOnTheScreen();
    expect(impressions.getByText('sin comparación')).toBeOnTheScreen();
    expect(within(screen.getByTestId('ana-cobertura')).getByText('Hay datos de 5 de 7 días: las cifras suman solo esos días y no se comparan con el periodo anterior.')).toBeOnTheScreen();

    const reached = within(screen.getByTestId('kpi-Miembros alcanzados'));
    expect(reached.getByLabelText('Sin dato')).toBeOnTheScreen();
    expect(reached.getByText(/^LinkedIn da los miembros alcanzados solo para un rango completo/)).toBeOnTheScreen();
    expect(reached.queryByText('0')).toBeNull();

    expect(screen.getByText('Sin publicaciones en este periodo.')).toBeOnTheScreen();
    expect(screen.getByTestId('ana-top-motivo')).toHaveTextContent(/^LinkedIn da sus publicaciones principales solo para el rango que se le pide/);
    expect(screen.getByText('Quienes vieron tus publicaciones del 16 oct al 12 nov de 2026: el rango importado más cercano, no exactamente este periodo.')).toBeOnTheScreen();
  });

  it('notes a previous period without all its days: the figures do not compare', async () => {
    const base = analiticaFixture();
    const body = analiticaFixture({ totales: { ...base.totales, impressions: { ...base.totales.impressions, comparable: false, delta: null, delta_pct: null } } });
    await renderAnalitica({ [`GET ${URL}`]: { body } });
    expect(await screen.findByText('El periodo anterior (del 30 oct al 5 nov de 2026) no tiene todos sus días importados: las cifras no se comparan.')).toBeOnTheScreen();
  });

  it('warns about a failed import above the figures it did not change', async () => {
    useFakeNow('2026-11-13T09:10:00Z');
    await renderAnalitica({ [`GET ${URL}`]: { body: analiticaFixture({ ultimo_error: FAILED }) } });
    const note = within(await screen.findByTestId('ana-error-importacion'));
    expect(note.getByText('La última importación de LinkedIn falló')).toBeOnTheScreen();
    expect(note.getByText('Analítica detenida por el proveedor: LinkedIn pidió verificar la cuenta. Fue hace 2 h; las cifras son de la última importación que salió bien.')).toBeOnTheScreen();
    expect(within(screen.getByTestId('kpi-Impresiones')).getByLabelText('840')).toBeOnTheScreen();
  });

  it('without a «directo» account (production today): one quiet card, no controls and no figures', async () => {
    await renderAnalitica({ [`GET ${URL}`]: { body: SIN_CUENTA } });
    const card = within(await screen.findByTestId('ana-no-disponible'));
    expect(card.getByText('Aún no hay analítica de LinkedIn')).toBeOnTheScreen();
    expect(card.getByText('Aún no hay una cuenta de LinkedIn conectada por el navegador (proveedor «directo»).')).toBeOnTheScreen();
    expect(card.getByText(/^Cuando el equipo la traiga, aquí verás impresiones/)).toBeOnTheScreen();
    expect(screen.queryByLabelText('Periodo')).toBeNull();
    expect(screen.queryByText('Personalizado')).toBeNull();
    expect(screen.queryByTestId('kpi-Impresiones')).toBeNull();
    expect(screen.queryByText('Reintentar')).toBeNull();
  });

  it('with an account never imported: the same card, with the failed attempt', async () => {
    useFakeNow('2026-11-13T09:10:00Z');
    const body = analiticaFixture({ disponible: false, motivo: 'Aún no se ha importado la analítica de LinkedIn de esta cuenta.', actualizado: null, ultimo_error: FAILED });
    await renderAnalitica({ [`GET ${URL}`]: { body } });
    const card = within(await screen.findByTestId('ana-no-disponible'));
    expect(card.getByText('Aún no se ha importado la analítica de LinkedIn de esta cuenta.')).toBeOnTheScreen();
    expect(card.getByText('Analítica detenida por el proveedor: LinkedIn pidió verificar la cuenta. Fue hace 2 h.')).toBeOnTheScreen();
    expect(screen.queryByTestId('kpi-Impresiones')).toBeNull();
  });

  it('says it could not load, and «Reintentar» brings the figures', async () => {
    const server = await renderAnalitica({ [`GET ${URL}`]: { status: 500, body: { detail: 'Error interno' } } });
    expect(await screen.findByText('No se pudo cargar la analítica de LinkedIn')).toBeOnTheScreen();
    expect(screen.queryByTestId('ana-no-disponible')).toBeNull();
    server.on(`GET ${URL}`, answer);
    await fireEvent.press(screen.getByText('Reintentar'));
    expect(await screen.findByTestId('kpi-Impresiones')).toBeOnTheScreen();
    expect(screen.queryByText('No se pudo cargar la analítica de LinkedIn')).toBeNull();
  });
});
