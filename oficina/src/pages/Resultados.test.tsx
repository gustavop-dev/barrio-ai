import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { fakeServer } from '../test/fakeServer';
import { kpi, negocioOn, resultadosFixture } from '../test/fixtures/resultados';
import { renderAt } from '../test/render';
import { dataUntil, Resultados } from './Resultados';
import { sortPosts } from './resultados/PostsTable';

const routes = [{ path: '/resultados', element: <Resultados /> }];

/** Makes `(min-width: 900px)` (and wider queries, when asked) match, as on a desktop. */
function desktop(wide = false) {
  vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        matches: query === '(min-width: 900px)' || (wide && query === '(min-width: 1100px)'),
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }) as unknown as MediaQueryList,
  );
}

describe('Resultados', () => {
  it('shows the controls, the period, the section chips and the unavailable business block', async () => {
    fakeServer({ 'GET /api/v1/resultados': { body: resultadosFixture() } });
    renderAt('/resultados', routes);

    expect(screen.getByRole('heading', { level: 1, name: 'Resultados' })).toBeInTheDocument();
    expect(screen.getByLabelText('Periodo')).toHaveValue('28');
    expect(screen.getByLabelText('Modalidad')).toHaveValue('todo');
    expect(await screen.findByText(/Periodo en curso: datos hasta .*14:20\. Todo se compara con los 28 días anteriores\./)).toBeInTheDocument();

    const chips = within(screen.getByRole('navigation', { name: 'Secciones de Resultados' }));
    expect(chips.getAllByRole('link').map((link) => link.textContent)).toEqual(['1 · Negocio', '2 · Gente', '3 · Contenido', '4 · Equipo']);
    expect(chips.getByRole('link', { name: '1 · Negocio' })).toHaveAttribute('href', '#res-negocio');

    expect(screen.getByRole('heading', { name: '1 · ¿Genera negocio?' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '4 · ¿El equipo trabaja bien?' })).toBeInTheDocument();
    expect(screen.getByText('Mediremos oportunidades cuando registres la primera o conectemos el inbox.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Registrar una oportunidad' })).toBeInTheDocument();
    // Inbound still has its card while section 1 is unavailable.
    expect(screen.getByText('Inbound')).toBeInTheDocument();
    expect(screen.queryByText('Oportunidades abiertas')).not.toBeInTheDocument();
  });

  it('never shows «sin dato» as 0 and opens the ⓘ definition with its formula', async () => {
    fakeServer({ 'GET /api/v1/resultados': { body: resultadosFixture() } });
    renderAt('/resultados', routes);

    const followers = (await screen.findByText('Seguidores')).closest('.kpi') as HTMLElement;
    expect(within(followers).getByText('Sin dato')).toBeInTheDocument();
    expect(within(followers).getByText('Sin captura de audiencia en este periodo.')).toBeInTheDocument();
    expect(within(followers).queryByText('0')).not.toBeInTheDocument();

    const rate = screen.getByText('Tasa de aceptación').closest('.kpi') as HTMLElement;
    expect(within(rate).getByText('41 %')).toBeInTheDocument();
    expect(within(rate).getByText('▼ −4 pts')).toBeInTheDocument();
    await userEvent.click(within(rate).getByRole('button', { name: 'Definición de Tasa de aceptación' }));
    expect(within(rate).getByText('Fórmula: conectados / (conectados + cerrados) × 100')).toBeInTheDocument();

    const consistency = screen.getByText('Constancia').closest('.kpi') as HTMLElement;
    expect(within(consistency).getByText('24 de 28')).toBeInTheDocument();
  });

  it('changes the period and the modality, keeping them in the URL', async () => {
    const server = fakeServer({ 'GET /api/v1/resultados': ({ search }) => ({ body: resultadosFixture({ periodo: { ...resultadosFixture().periodo, dias: Number(search.get('dias')) as 7 } }) }) });
    renderAt('/resultados', routes);
    await screen.findByText(/Periodo en curso/);
    expect(server.find('GET', '/api/v1/resultados')[0]!.search.get('dias')).toBe('28');

    await userEvent.selectOptions(screen.getByLabelText('Periodo'), '7');
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/resultados?dias=7'));
    expect(await screen.findByText(/Todo se compara con los 7 días anteriores/)).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText('Modalidad'), 'projectapp');
    await waitFor(() => {
      const last = server.find('GET', '/api/v1/resultados').at(-1)!;
      expect(last.search.get('dias')).toBe('7');
      expect(last.search.get('modalidad')).toBe('projectapp');
    });
    expect(screen.getAllByText('No se separa por modalidad: muestra toda la cuenta.')).toHaveLength(2);
  });

  it('draws section 1 when there are opportunities: KPIs, funnel, the 60/40 split and the active ones', async () => {
    fakeServer({ 'GET /api/v1/resultados': { body: resultadosFixture({ negocio: negocioOn() }) } });
    renderAt('/resultados', routes);

    const conversations = (await screen.findByText('Conversaciones pertinentes')).closest('.kpi') as HTMLElement;
    expect(within(conversations).getByText('Disponible cuando conectemos el inbox.')).toBeInTheDocument();
    const open = screen.getByText('Oportunidades abiertas').closest('.kpi') as HTMLElement;
    expect(within(open).getByText('2')).toBeInTheDocument();
    expect(within(open).getByText('▲ 1')).toBeInTheDocument();
    const proposals = screen.getByText('Propuestas enviadas').closest('.kpi') as HTMLElement;
    expect(within(proposals).getByText('= igual que antes')).toBeInTheDocument();

    expect(screen.getByRole('img', { name: 'Necesidad identificada: 3, 75 % del paso anterior' })).toBeInTheDocument();
    expect(screen.getByText('Cerrada sin acuerdo: 1')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Startups 50 %, ProjectApp 50 %, objetivo 60/40' })).toBeInTheDocument();
    expect(screen.getByText('1 oportunidad por clasificar no cuenta en el reparto.')).toBeInTheDocument();

    expect(screen.getByRole('link', { name: /Lucía Ficticia/ })).toHaveAttribute('href', '/personas/c-1');
    expect(screen.getByRole('link', { name: /Mario Externo/ })).toHaveAttribute('href', '/personas?pestana=oportunidades');
    expect(screen.getByText(/Siguiente: Enviar la propuesta de piloto/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Registrar una oportunidad' })).not.toBeInTheDocument();
  });

  it('shows the audience funnel with the discarded aside and the roles without conversion', async () => {
    fakeServer({ 'GET /api/v1/resultados': { body: resultadosFixture() } });
    renderAt('/resultados', routes);
    expect(await screen.findByRole('img', { name: 'Encaja: 21, 55 % del paso anterior' })).toBeInTheDocument();
    expect(screen.getByText('Descartados: 6 · Cerrados: 2 · Te invitaron: 1')).toBeInTheDocument();
    // Roles in the design order (Comprador first), no conversion between them.
    expect(screen.getByRole('img', { name: 'Comprador: 3' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Par: 2' })).toBeInTheDocument();
  });

  it('shows the content chart, the best post, the pillars and the posts as cards on mobile', async () => {
    fakeServer({ 'GET /api/v1/resultados': { body: resultadosFixture() } });
    renderAt('/resultados', routes);

    const bar = await screen.findByRole('link', { name: 'Post 1, 2 nov: 1.840 impresiones' });
    expect(bar).toHaveAttribute('href', '/calendario/pieza/p-1');
    expect(screen.getByRole('link', { name: 'Post 2, 5 nov: 960 impresiones a las 24 h' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Post 3, 7 nov: sin dato' })).toBeInTheDocument();
    expect(screen.getByText('La línea es la mediana de las 4 semanas anteriores (1.250). Toca una barra para ver la pieza.')).toBeInTheDocument();

    expect(screen.getByText('2 nov · IA aplicada · 1.840 impresiones · 3,1 %')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver la pieza' })).toHaveAttribute('href', '/calendario/pieza/p-1');

    const pillars = within(screen.getByRole('list', { name: 'Interacción media por pilar' }));
    expect(pillars.getByText('3,4 %')).toBeInTheDocument();
    expect(pillars.getByText('sin dato', { exact: false })).toBeInTheDocument();

    const cards = within(screen.getByRole('list', { name: 'Posts del periodo' }));
    const order = () => cards.getAllByRole('link').map((link) => link.textContent);
    expect(order()).toEqual([
      'Scope features from the decision they support.',
      'A monolith is fine until your team says otherwise.',
      'AI features should start from a workflow, not a model.',
    ]);
    expect(cards.getByText('Aún sin corte')).toBeInTheDocument();
    expect(cards.getByText('Comprador · 3')).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText('Ordenar por'), 'impressions_7d');
    expect(order()[0]).toBe('AI features should start from a workflow, not a model.');
  });

  it('sorts the posts table by any column on desktop', async () => {
    desktop();
    fakeServer({ 'GET /api/v1/resultados': { body: resultadosFixture() } });
    renderAt('/resultados', routes);

    const table = await screen.findByRole('table');
    const rows = () => within(table).getAllByRole('row').slice(1).map((row) => within(row).getByRole('link').textContent);
    expect(within(table).getByRole('columnheader', { name: /Fecha/ })).toHaveAttribute('aria-sort', 'descending');
    expect(rows()[0]).toBe('Scope features from the decision they support.');

    await userEvent.click(within(table).getByRole('button', { name: /Interacción/ }));
    expect(within(table).getByRole('columnheader', { name: /Interacción/ })).toHaveAttribute('aria-sort', 'descending');
    expect(rows()).toEqual([
      'A monolith is fine until your team says otherwise.',
      'AI features should start from a workflow, not a model.',
      'Scope features from the decision they support.',
    ]);
    await userEvent.click(within(table).getByRole('button', { name: /Interacción/ }));
    expect(within(table).getByRole('columnheader', { name: /Interacción/ })).toHaveAttribute('aria-sort', 'ascending');
    // Missing values stay last in both directions.
    expect(rows().at(-1)).toBe('Scope features from the decision they support.');
  });

  it('summarises the team in compact stats, with the AI spend of the day and the month', async () => {
    fakeServer({ 'GET /api/v1/resultados': { body: resultadosFixture() } });
    renderAt('/resultados', routes);
    await screen.findByText('Gasto de IA');
    const section = within(screen.getByRole('heading', { name: '4 · ¿El equipo trabaja bien?' }).closest('section') as HTMLElement);
    expect(section.getByText('Comentarios').closest('.res-stat')).toHaveTextContent('24 publicados · —sin dato de con respuesta');
    expect(section.getByText('Red').closest('.res-stat')).toHaveTextContent('31 seguidos · 12 invitados · 5 aceptados');
    expect(section.getByText('Piezas').closest('.res-stat')).toHaveTextContent('24 publicadas · 1 bloqueada · 0 vetadas');
    await userEvent.click(section.getByRole('button', { name: 'Definición de Red' }));
    expect(section.getAllByText(/Seguidos: Definición de prueba/)).toHaveLength(1);
    const spend = section.getByText('Gasto de IA').closest('.res-stat') as HTMLElement;
    expect(spend).toHaveTextContent('3,10 USD hoy');
    expect(spend).toHaveTextContent('61,20 de 100,00 USD este mes');
  });

  it('opens the opportunity form from the unavailable block and registers one', async () => {
    const server = fakeServer({
      'GET /api/v1/resultados': { body: resultadosFixture() },
      'POST /api/v1/oportunidades': ({ body }) => ({ status: 201, body: { id: 'o-9', ...(body as object) } }),
    });
    renderAt('/resultados', routes);
    await userEvent.click(await screen.findByRole('button', { name: 'Registrar una oportunidad' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Nueva oportunidad' }));
    await userEvent.click(dialog.getByRole('button', { name: 'Alguien fuera de la red' }));
    await userEvent.type(dialog.getByLabelText('Nombre'), 'Mario Externo');
    await userEvent.type(dialog.getByLabelText(/Empresa/), 'Cosecha Data');
    await userEvent.selectOptions(dialog.getByLabelText('Modalidad'), 'personal_startups');
    await userEvent.selectOptions(dialog.getByLabelText('Cómo llegó'), 'lo_dijo');
    await userEvent.click(dialog.getByRole('button', { name: 'Registrar oportunidad' }));

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
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.getByText('Oportunidad registrada')).toBeInTheDocument();
  });

  it('shows an error with retry when the results cannot load', async () => {
    let fail = true;
    fakeServer({
      'GET /api/v1/resultados': () => (fail ? { status: 500, body: { detail: 'Error del servidor' } } : { body: resultadosFixture() }),
    });
    renderAt('/resultados', routes);
    expect(await screen.findByText('No se pudieron cargar los resultados')).toBeInTheDocument();
    expect(screen.getAllByText('No se pudo cargar esta sección.')).toHaveLength(4);
    fail = false;
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(await screen.findByText(/Periodo en curso/)).toBeInTheDocument();
  });

  it('keeps the other sections when one arrives broken', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    // React rethrows the render error in development; jsdom would print it although the boundary handles it.
    const quiet = (event: ErrorEvent) => event.preventDefault();
    window.addEventListener('error', quiet);
    const broken = resultadosFixture();
    (broken as unknown as { contenido: null }).contenido = null;
    fakeServer({ 'GET /api/v1/resultados': { body: broken } });
    renderAt('/resultados', routes);
    expect(await screen.findByText('No se pudo mostrar esta sección')).toBeInTheDocument();
    expect(screen.getByText('Tasa de aceptación')).toBeInTheDocument();
    expect(screen.getByText('Gasto de IA')).toBeInTheDocument();
    window.removeEventListener('error', quiet);
  });
});

describe('Resultados helpers', () => {
  it('reads «datos hasta» as today or as a date in the machine time zone', () => {
    const now = new Date('2026-11-07T22:00:00Z');
    expect(dataUntil('2026-11-07T19:20:00Z', 'America/Bogota', now)).toBe('hoy 14:20');
    expect(dataUntil('2026-11-06T19:20:00Z', 'America/Bogota', now)).toBe('6 nov 14:20');
  });

  it('sorts posts with missing values last', () => {
    const posts = resultadosFixture().contenido.posts;
    expect(sortPosts(posts, 'impressions_7d', 'asc').map((p) => p.piece_id)).toEqual(['p-1', 'p-2', 'p-3']);
    expect(sortPosts(posts, 'commenters', 'desc').map((p) => p.piece_id)).toEqual(['p-1', 'p-2', 'p-3']);
  });

  it('builds KPI fixtures with a comparable delta', () => {
    expect(kpi(5).delta).toBe(1);
  });
});
