import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Actividad, Calendario } from '../api/types';
import { fakeServer, SESSION_OK, type Handler, type Reply } from '../test/fakeServer';
import { actividadFixture, calendarioFixture, NOW, piece, shellOverview, shellTurno, WEEK_DAYS } from '../test/fixtures/calendario';
import { renderCalendario as renderApp } from '../test/fixtures/calendarioRender';

function server(routes: Record<string, Handler | Reply> = {}, calendar: (desde: string, hasta: string) => Calendario = (d, h) => calendarioFixture(d, h, WEEK_DAYS)) {
  return fakeServer({
    'GET /api/v1/auth/session': { body: SESSION_OK },
    'GET /api/v1/tu-turno': { body: shellTurno() },
    'GET /api/v1/operador/overview': { body: shellOverview() },
    'GET /api/v1/calendario': (request) => ({ body: calendar(request.search.get('desde') ?? '', request.search.get('hasta') ?? '') }),
    'GET /api/v1/actividad': { body: actividadFixture() },
    'GET /api/v1/editorial/pieces/p7': { body: piece() },
    'GET /api/v1/editorial/pieces/p8': {
      body: piece({ id: 'p8', slot_date: '2026-11-08', scheduled_for: '2026-11-08T14:00:00Z', status: 'scheduled', thesis: 'Turning a sales call into a product spec.', action: { id: 'act-8', state: 'approved', payload_hash: 'h' }, metrics: null }),
    },
    'GET /api/v1/editorial/pieces/p4': { body: piece({ id: 'p4', slot_date: '2026-11-04', status: 'skipped', state: 'skipped', thesis: null }) },
    ...routes,
  });
}

const panel = () => screen.getByRole('region', { name: 'Detalle del día' });
const location = () => screen.getByTestId('location').textContent;

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(NOW);
});
afterEach(() => {
  vi.useRealTimers();
});

describe('Calendario · semana (móvil)', () => {
  it('shows the week strip and today’s panel by default', async () => {
    const api = server();
    renderApp('/calendario');

    expect(await screen.findByRole('heading', { name: 'Calendario', level: 1 })).toBeInTheDocument();
    expect(screen.getByText('2–8 nov 2026')).toBeInTheDocument();
    const strip = screen.getByRole('group', { name: /Semana del/ });
    expect(within(strip).getAllByRole('button')).toHaveLength(7);
    await waitFor(() => expect(within(strip).getByRole('button', { name: /Sábado 7 de noviembre, hoy/ })).toHaveAttribute('aria-pressed', 'true'));
    expect(api.find('GET', '/api/v1/calendario')[0]!.search.toString()).toBe('desde=2026-11-02&hasta=2026-11-08');

    const day = panel();
    expect(within(day).getByRole('heading', { name: 'Sábado 7 de noviembre', level: 2 })).toBeInTheDocument();
    expect(within(day).getByText('Hoy')).toBeInTheDocument();
    expect(await within(day).findByRole('button', { name: '6 comentarios' })).toBeInTheDocument();
    expect(within(day).getByRole('button', { name: '1 conexión nueva que encaja' })).toBeInTheDocument();

    // Tu parte
    const tuParte = within(day).getByRole('group', { name: 'Tu parte' });
    expect(within(tuParte).getByText('Responde: ¿En qué idioma van tus textos públicos?')).toBeInTheDocument();
    expect(within(tuParte).getByRole('link', { name: 'Ir a la Bandeja' })).toHaveAttribute('href', '/tu-turno');

    // Publicación del día, from the piece detail
    const publication = within(day).getByRole('group', { name: 'Publicación del día' });
    expect(within(publication).getByText('Scope features from the decision they support.')).toBeInTheDocument();
    expect(await within(publication).findByText('Salió a las 09:00')).toBeInTheDocument();
    expect(within(publication).getByText(/Most feature requests arrive as a solution\. Before scoping/)).toBeInTheDocument();
    expect(within(publication).getByText('Impresiones: 1.210 (última lectura)')).toBeInTheDocument();
    expect(within(publication).queryByRole('button', { name: 'Vetar' })).toBeNull();
    expect(within(publication).getByRole('link', { name: 'Ver cómo se escribió' })).toHaveAttribute('href', '/calendario/pieza/p7');

    // Programado: queued actions and expected invitations
    const scheduled = within(day).getByRole('group', { name: 'Programado' });
    expect(await within(scheduled).findByText('Comentario en el post de Elena Prueba')).toBeInTheDocument();
    expect(within(scheduled).getAllByText('Saldrá cuando abra la ventana, hoy a las 12:00')).toHaveLength(1);
    expect(within(scheduled).getByText('Invitar a Sofía Muestra (sin nota)')).toBeInTheDocument();
    expect(within(scheduled).getByText('Invitaciones previstas: 2 personas')).toBeInTheDocument();
    expect(within(scheduled).getByText('Andrés Ejemplo y Sofía Muestra · Estimación sujeta a los topes')).toBeInTheDocument();

    // Lo importante, in time order
    const important = within(day).getByRole('list', { name: 'Lo importante del día' });
    expect(within(important).getAllByRole('listitem').map((li) => li.querySelector('.tl-title')?.textContent)).toEqual([
      'Publicaste: Scope features from the decision they support.',
      'Oportunidad con Lucía Ficticia: Necesidad identificada',
      'Aceptaste la invitación de Diego Supuesto',
      'Responde: ¿En qué idioma van tus textos públicos?',
    ]);
  });

  it('selects another day and keeps it in the URL', async () => {
    server();
    const user = userEvent.setup();
    renderApp('/calendario');
    await user.click(await screen.findByRole('button', { name: /Miércoles 4 de noviembre/ }));

    expect(location()).toBe('/calendario?fecha=2026-11-04');
    expect(within(panel()).getByRole('heading', { name: 'Miércoles 4 de noviembre' })).toBeInTheDocument();
    expect(within(panel()).getByText('Pasado')).toBeInTheDocument();
    expect(await within(panel()).findByText('Sin publicación. El director decidió no publicar: No había material genuino ese día.')).toBeInTheDocument();
    expect(within(panel()).queryByRole('group', { name: 'Programado' })).toBeNull();
  });

  it('opens the day of the URL and moves a week with the arrows', async () => {
    const api = server();
    const user = userEvent.setup();
    renderApp('/calendario?fecha=2026-11-06');
    expect(await within(panel()).findByRole('heading', { name: 'Viernes 6 de noviembre' })).toBeInTheDocument();
    const important = await within(panel()).findByRole('list', { name: 'Lo importante del día' });
    const uncertain = within(important).getByText('Comentario: no se sabe si salió').closest('li')!;
    expect(within(uncertain).getByText('Incierta')).toBeInTheDocument();
    expect(within(uncertain).getByRole('link', { name: 'Resuélvela en la Bandeja' })).toHaveAttribute('href', '/tu-turno#turno-uncertain-prop-9');

    await user.click(screen.getByRole('button', { name: 'Semana siguiente' }));
    expect(location()).toBe('/calendario?fecha=2026-11-13');
    await waitFor(() => expect(api.find('GET', '/api/v1/calendario').some((r) => r.search.get('desde') === '2026-11-09')).toBe(true));
    expect(screen.getByText('9–15 nov 2026')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Hoy' }));
    expect(location()).toBe('/calendario');
  });

  it('toggles the layers through the URL and hides their events', async () => {
    server();
    const user = userEvent.setup();
    renderApp('/calendario');
    const chips = await screen.findByRole('group', { name: 'Capas' });
    expect(await within(chips).findByRole('button', { name: /Conversaciones · parcial/ })).toBeEnabled();
    const publicaciones = within(chips).getByRole('button', { name: 'Publicaciones' });
    expect(publicaciones).toHaveAttribute('aria-pressed', 'true');
    await screen.findByText('Publicaste: Scope features from the decision they support.');

    await user.click(publicaciones);
    expect(location()).toBe('/calendario?capas=tuyo%2Cred%2Cconversaciones%2Csistema');
    expect(publicaciones).toHaveAttribute('aria-pressed', 'false');
    expect(screen.queryByText('Publicaste: Scope features from the decision they support.')).toBeNull();
    expect(screen.getByRole('button', { name: /Lunes 2 de noviembre, Red$/ })).toBeInTheDocument();

    await user.click(publicaciones);
    expect(location()).toBe('/calendario');
  });

  it('marks a layer that the backend does not have yet as unavailable', async () => {
    server({}, (d, h) => calendarioFixture(d, h, WEEK_DAYS, { layers: { tuyo: false, publicaciones: true, red: true, conversaciones: 'parcial', sistema: true } }));
    renderApp('/calendario');
    const tuyo = await screen.findByRole('button', { name: 'Tuyo · aún no disponible' });
    expect(tuyo).toBeDisabled();
    await within(panel()).findByRole('group', { name: 'Publicación del día' });
    expect(within(panel()).queryByRole('group', { name: 'Tu parte' })).toBeNull();
  });

  it('filters «Ver todo lo del día» by the number tapped in the summary', async () => {
    const api = server();
    const user = userEvent.setup();
    renderApp('/calendario');
    await user.click(await within(panel()).findByRole('button', { name: '6 comentarios' }));

    const details = panel().querySelector('details.cal-all') as HTMLDetailsElement;
    await waitFor(() => expect(details.open).toBe(true));
    await waitFor(() =>
      expect(api.find('GET', '/api/v1/actividad').some((r) => r.search.get('tipo') === 'comentarios' && r.search.get('desde') === '2026-11-07' && r.search.get('hasta') === '2026-11-07')).toBe(
        true,
      ),
    );
    expect(within(details).getByRole('button', { name: 'Comentarios' })).toHaveAttribute('aria-pressed', 'true');
    expect(await within(details).findByText('Comentaste en el post de Elena Prueba')).toBeInTheDocument();
  });

  it('vetoes tomorrow’s piece with a mandatory note', async () => {
    const api = server({ 'POST /api/v1/operador/actions/act-8/reject': { body: {} } });
    const user = userEvent.setup();
    renderApp('/calendario?fecha=2026-11-08');
    const publication = await within(panel()).findByRole('group', { name: 'Publicación del día' });
    expect(within(panel()).getByText('Programado')).toBeInTheDocument();
    expect(await within(publication).findByText('Mañana a las 09:00 · sale en 23 h')).toBeInTheDocument();

    await user.click(await within(publication).findByRole('button', { name: 'Vetar' }));
    const dialog = screen.getByRole('dialog', { name: 'Vetar la pieza' });
    expect(within(dialog).getByText(/La pieza no saldrá a las 09:00 y ese día quedará sin publicación/)).toBeInTheDocument();
    const confirm = within(dialog).getByRole('button', { name: 'Vetar' });
    expect(confirm).toBeDisabled();
    await user.type(within(dialog).getByLabelText(/Nota/), 'No es el momento');
    await user.click(confirm);

    await waitFor(() => expect(api.find('POST', '/api/v1/operador/actions/act-8/reject')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/operador/actions/act-8/reject')[0]!.body).toEqual({ note: 'No es el momento' });
    expect(await screen.findByText('Vetada')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('warns that vetoing a network action discards the person', async () => {
    server();
    const user = userEvent.setup();
    renderApp('/calendario');
    const scheduled = await within(panel()).findByRole('group', { name: 'Programado' });
    const row = (await within(scheduled).findByText('Invitar a Sofía Muestra (sin nota)')).closest('li')!;
    await user.click(within(row).getByRole('button', { name: 'Vetar' }));
    expect(within(screen.getByRole('dialog', { name: 'Vetar la acción' })).getByText(/descarta a Sofía Muestra para siempre/)).toBeInTheDocument();
  });

  it('says when a day is too far ahead', async () => {
    server();
    renderApp('/calendario?fecha=2026-11-30');
    expect(await within(panel()).findByText('Todavía no hay nada programado tan lejos.')).toBeInTheDocument();
  });

  it('shows the free slot of a future day and offers to prepare the next piece when nothing is coming', async () => {
    const empty: Actividad = actividadFixture({ upcoming: { pieces: [], queued: [] } });
    const api = server({
      'GET /api/v1/actividad': { body: empty },
      'POST /api/v1/editorial/plan': { status: 202, body: { slot_date: '2026-11-09', job: { id: 'j1', status: 'queued' } } },
    });
    const user = userEvent.setup();
    renderApp('/calendario?fecha=2026-11-09');
    expect(await within(panel()).findByText('Hueco libre. El equipo prepara cada pieza 6 h antes de su hora.')).toBeInTheDocument();
    await user.click(await within(panel()).findByRole('button', { name: 'Preparar la siguiente pieza' }));
    const dialog = screen.getByRole('dialog', { name: 'Preparar la siguiente pieza' });
    expect(within(dialog).getByText(/Tiene coste: cada etapa llama a Claude/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Preparar' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/editorial/plan')).toHaveLength(1));
    expect(await within(panel()).findByText(/Preparación en cola para el lunes 9 de noviembre\. El circuito tarda unos minutos/)).toBeInTheDocument();
    expect(api.find('POST', '/api/v1/editorial/plan')[0]!.body).toEqual({ request_id: expect.any(String) });
  });

  it('keeps the strip and offers a retry when the calendar fails', async () => {
    let fail = true;
    const api = server();
    api.on('GET /api/v1/calendario', (request) =>
      fail ? { status: 500, body: { detail: 'Error del servidor' } } : { body: calendarioFixture(request.search.get('desde')!, request.search.get('hasta')!, WEEK_DAYS) },
    );
    const user = userEvent.setup();
    renderApp('/calendario');
    expect(await screen.findByText('No se pudo cargar el calendario')).toBeInTheDocument();
    expect(screen.getByText('Error del servidor')).toBeInTheDocument();
    expect(within(screen.getByRole('group', { name: /Semana del/ })).getAllByRole('button')).toHaveLength(7);
    fail = false;
    await user.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(await within(panel()).findByRole('button', { name: '6 comentarios' })).toBeInTheDocument();
    expect(api.find('GET', '/api/v1/calendario').length).toBeGreaterThan(1);
  });
});

describe('Calendario · mes', () => {
  it('requests the whole grid and shows a compact month of dots', async () => {
    const api = server();
    const user = userEvent.setup();
    renderApp('/calendario?vista=mes');
    expect(await screen.findByText('Noviembre 2026')).toBeInTheDocument();
    await waitFor(() => expect(api.find('GET', '/api/v1/calendario').some((r) => r.search.toString() === 'desde=2026-10-26&hasta=2026-12-06')).toBe(true));
    const grid = screen.getByRole('group', { name: 'Días del mes' });
    expect(within(grid).getAllByRole('button')).toHaveLength(42);
    expect(within(grid).getByRole('button', { name: /Lunes 2 de noviembre, Publicaciones, Red/ })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Mes siguiente' }));
    expect(location()).toBe('/calendario?vista=mes&fecha=2026-12-07');
    expect(await screen.findByText('Diciembre 2026')).toBeInTheDocument();
    expect(await screen.findByText('No hay nada registrado en este mes.')).toBeInTheDocument();
  });

  it('switches view with the segmented control', async () => {
    server();
    const user = userEvent.setup();
    renderApp('/calendario');
    const views = await screen.findByRole('group', { name: 'Vista' });
    await user.click(within(views).getByRole('button', { name: 'Mes' }));
    expect(location()).toBe('/calendario?vista=mes');
    await user.click(within(views).getByRole('button', { name: 'Semana' }));
    expect(location()).toBe('/calendario');
  });
});

describe('Calendario · lista', () => {
  it('shows «Próximo», the queue and every day newest first', async () => {
    server();
    renderApp('/calendario?vista=lista');
    expect(await screen.findByText('Línea de tiempo')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Hoy' })).toBeNull();

    const next = screen.getByRole('region', { name: 'Próximo' });
    expect(await within(next).findByText('Turning a sales call into a product spec.')).toBeInTheDocument();
    expect(within(next).getByText('Mañana a las 09:00 · sale en 23 h')).toBeInTheDocument();
    expect(within(next).getByText('Del negocio al producto · ProjectApp · Lector comprador')).toBeInTheDocument();
    expect(within(next).getByRole('link', { name: 'Ver cómo se escribió' })).toHaveAttribute('href', '/calendario/pieza/p8');
    expect(within(next).getByText('En cola')).toBeInTheDocument();
    expect(within(next).getAllByRole('button', { name: 'Vetar' })).toHaveLength(3);

    const timeline = screen.getByRole('region', { name: 'Lo que pasó' });
    const groups = within(timeline).getAllByRole('heading', { level: 3 }).map((h) => h.textContent);
    expect(groups).toEqual(['Hoy, Sábado 7 de noviembre', 'Ayer, Viernes 6 de noviembre', 'Jueves 5 de noviembre']);
    expect(within(timeline).getByText('Comentaste en el post de Elena Prueba')).toBeInTheDocument();
    expect(within(timeline).getByText('Reaccionaste Recomiendo al post de Tomás Demo')).toBeInTheDocument();
    expect(within(timeline).getByText('Head of Product @ Kanoa · Par')).toBeInTheDocument();
    expect(within(timeline).getByRole('link', { name: 'Ver ficha' })).toHaveAttribute('href', '/personas/c11');
    const uncertain = within(timeline).getByText('Comentaste en el post de Pablo Ficticio').closest('li')!;
    expect(within(uncertain).getByText('Incierta')).toBeInTheDocument();
    expect(within(uncertain).getByRole('link', { name: 'Resuélvela en la Bandeja' })).toHaveAttribute('href', '/tu-turno#turno-uncertain-i-4');
    expect(within(timeline).getByText('Publicaste: AI features should start from a workflow.')).toBeInTheDocument();
    expect(within(timeline).getByRole('link', { name: 'Ver la pieza' })).toHaveAttribute('href', '/calendario/pieza/p5');
  });

  it('expands a comment with the post, the full text and «Por qué»', async () => {
    server();
    const user = userEvent.setup();
    renderApp('/calendario?vista=lista');
    const row = (await screen.findByText('Comentaste en el post de Elena Prueba')).closest('li')!;
    await user.click(within(row).getByRole('button', { name: 'Ver el comentario' }));
    expect(within(row).getByText('How we scope features at Kanoa.')).toBeInTheDocument();
    expect(within(row).getByText('Naming the decision first is underrated.')).toBeInTheDocument();
    expect(within(row).getByText('Por qué')).toBeInTheDocument();
  });

  it('filters by type and shows what did not go out through the URL', async () => {
    const api = server();
    const user = userEvent.setup();
    renderApp('/calendario?vista=lista');
    await screen.findByText('Comentaste en el post de Elena Prueba');
    await user.click(screen.getByRole('button', { name: 'Reacciones' }));
    expect(location()).toBe('/calendario?vista=lista&tipo=reacciones');
    await waitFor(() => expect(api.find('GET', '/api/v1/actividad').some((r) => r.search.get('tipo') === 'reacciones')).toBe(true));

    await user.click(screen.getByRole('switch', { name: /Mostrar lo que no salió/ }));
    expect(location()).toBe('/calendario?vista=lista&tipo=reacciones&no_salio=1');
    await waitFor(() => expect(api.find('GET', '/api/v1/actividad').some((r) => r.search.get('no_salio') === '1' && r.search.get('tipo') === 'reacciones')).toBe(true));
  });

  it('loads more with the next offset', async () => {
    const api = server({
      'GET /api/v1/actividad': (request) => ({
        body: request.search.get('offset') === '50' ? actividadFixture({ items: [], next_offset: null }) : actividadFixture({ next_offset: 50 }),
      }),
    });
    const user = userEvent.setup();
    renderApp('/calendario?vista=lista');
    await user.click(await screen.findByRole('button', { name: 'Cargar más' }));
    await waitFor(() => expect(api.find('GET', '/api/v1/actividad').some((r) => r.search.get('offset') === '50')).toBe(true));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Cargar más' })).toBeNull());
  });

  it('offers to prepare a piece when nothing is scheduled', async () => {
    server({ 'GET /api/v1/actividad': { body: actividadFixture({ upcoming: { pieces: [], queued: [] } }) } });
    renderApp('/calendario?vista=lista');
    const next = await screen.findByRole('region', { name: 'Próximo' });
    expect(await within(next).findByText('No hay pieza programada para los próximos días.')).toBeInTheDocument();
    expect(within(next).getByRole('button', { name: 'Preparar la siguiente pieza' })).toBeInTheDocument();
  });
});

describe('Calendario · escritorio', () => {
  beforeEach(() => {
    vi.spyOn(window, 'matchMedia').mockImplementation(
      (query: string) =>
        ({ matches: query.includes('min-width: 900px'), media: query, addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {}, onchange: null, dispatchEvent: () => false }) as unknown as MediaQueryList,
    );
  });

  it('renders the week grid with an all-day strip, timed chips and the «now» line', async () => {
    server();
    renderApp('/calendario');
    const chip = await screen.findByRole('link', { name: '09:00 · Publicaste: Scope features from the decision they support.' });
    expect(chip).toHaveAttribute('href', '/calendario/pieza/p7');
    expect(screen.getByText('Todo el día')).toBeInTheDocument();
    expect(within(screen.getByRole('list', { name: 'Todo el día, Lunes 2 de noviembre' })).getByText('3 conexiones nuevas')).toBeInTheDocument();
    expect(within(screen.getByRole('list', { name: 'Con hora, Sábado 7 de noviembre' })).getByText('Ahora')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Detalle del día' })).toBeInTheDocument();
  });

  it('renders the month grid with chips, «sin post» and the pending dot', async () => {
    server();
    renderApp('/calendario?vista=mes');
    expect(await screen.findByRole('button', { name: /Sábado 7 de noviembre, hoy, Tuyo, Publicaciones, Conversaciones, Red, te toca algo/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Martes 3 de noviembre, sin post/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '09:00 · Publicaste: AI features should start from a workflow, not a model.' })).toHaveAttribute('href', '/calendario/pieza/p2');
    expect(screen.getByRole('button', { name: '1 más el Sábado 7 de noviembre' })).toBeInTheDocument();
  });
});
