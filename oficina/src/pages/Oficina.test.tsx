import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { oficinaEventosKey } from '../api/oficina';
import type { Activity } from '../api/types';
import { overviewFixture } from '../test/app';
import { fakeServer, type Handler, type Reply } from '../test/fakeServer';
import { renderAt } from '../test/render';
import { Oficina } from './Oficina';

const ACTIVIDAD = 'GET /api/v1/oficina/actividad';
const EVENTOS = 'GET /api/v1/oficina/eventos';
const OVERVIEW = 'GET /api/v1/operador/overview';

function activity(): Activity {
  const now = new Date().toISOString();
  return {
    updated_at: now,
    roles: {
      operador_cuenta: { status: 'trabajando', detail: 'Ejecutando comentario aprobado', since: now },
      relaciones_comunidad: { status: 'en_espera', detail: '', since: null },
      conversaciones_inbox: { status: 'diseno', detail: 'Contrato diseñado; aún sin implementar', since: null },
      copywriter_a: { status: 'en_espera', detail: '', since: null },
    },
  };
}

function server(routes: Record<string, Handler | Reply> = {}) {
  return fakeServer({
    [ACTIVIDAD]: { body: activity() },
    [OVERVIEW]: { body: overviewFixture() },
    [EVENTOS]: { body: { events: [], now: new Date().toISOString() } },
    ...routes,
  });
}

const renderOficina = () => renderAt('/', [{ path: '/', element: <Oficina /> }]);

function mockWide(wide: boolean) {
  vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        matches: wide && query.includes('min-width: 1100px'),
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

afterEach(() => {
  vi.restoreAllMocks();
});

describe('Oficina · states', () => {
  it('paints the scene still while the activity loads, with nothing above it', async () => {
    server({ [ACTIVIDAD]: () => new Promise<Reply>(() => {}) });
    renderOficina();
    expect(screen.getByText('Leyendo actividad…')).toBeInTheDocument();
    expect(screen.getByText('Abriendo la oficina…')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /La oficina en pixel art/ })).toBeInTheDocument();
    // Rev 18: no scene bar, no light or ambient toggles, no Tu turno card above the scene.
    expect(screen.queryByText(/PLANTA ABIERTA/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /ambiente|Luz de mañana|Tarde en el estudio/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/dependen de ti/)).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Oficina' })).toBeInTheDocument();
  });

  it('says the activity is unavailable, keeps everyone still and retries', async () => {
    const api = server({ [ACTIVIDAD]: { status: 503, body: { detail: 'Servicio no disponible' } } });
    const user = userEvent.setup();
    renderOficina();
    expect(await screen.findByText('No se pudo leer la actividad.')).toBeInTheDocument();
    expect(screen.getByText('Mientras tanto los personajes quedan quietos: la oficina no simula trabajo.')).toBeInTheDocument();
    expect(screen.getByText('Actividad no disponible')).toBeInTheDocument();
    // No «now» line while the activity is unknown.
    expect(screen.queryByText('Abriendo la oficina…')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Operación/ }));
    expect(within(screen.getByRole('dialog')).getByRole('button', { name: /Operador de cuenta/ })).toHaveTextContent('Sin datos');

    api.on(ACTIVIDAD, { body: activity() });
    await user.click(screen.getByRole('button', { name: 'Reintentar' }));
    await waitFor(() => expect(screen.queryByText('No se pudo leer la actividad.')).not.toBeInTheDocument());
    expect(api.find('GET', '/api/v1/oficina/actividad').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/^Actividad real · /)).toBeInTheDocument();
  });

  it('darkens the frozen scene while the machine is paused', async () => {
    server({ [OVERVIEW]: { body: overviewFixture({ control: { paused: true, reason: 'Revisando los topes', source: 'db', updated_at: null, updated_by: null } }) } });
    renderOficina();
    expect(await screen.findByTestId('oficina-pausa')).toBeInTheDocument();
    expect(await screen.findByText('La máquina está en pausa. Nadie toca tu LinkedIn.')).toBeInTheDocument();
  });

  it('shows the real activity and tags roles in design', async () => {
    server();
    renderOficina();
    expect(await screen.findByText(/^Actividad real · hace un momento/)).toBeInTheDocument();
    expect(screen.queryByTestId('oficina-pausa')).not.toBeInTheDocument();
    expect(screen.getByText('EN DISEÑO')).toBeInTheDocument();
    // Without events, the line says who is really working.
    expect(screen.getByText('Operación: Ejecutando comentario aprobado')).toBeInTheDocument();
  });
});

describe('Oficina · panel sheet', () => {
  it('opens a team in a half-height sheet and closes it with «Cerrar»', async () => {
    server();
    const user = userEvent.setup();
    renderOficina();
    await screen.findByText(/^Actividad real/);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Relaciones', pressed: false }));
    const sheet = screen.getByRole('dialog', { name: 'Relaciones' });
    expect(sheet).toHaveAttribute('aria-modal', 'false');
    expect(within(sheet).getByText('ESPACIO DEL EQUIPO')).toBeInTheDocument();
    expect(within(sheet).getByText('2 INTEGRANTES · LA MESA DE LA COCINA')).toBeInTheDocument();
    expect(within(sheet).getByText('0 trabajando · 1 en espera · 1 en diseño')).toBeInTheDocument();
    expect(within(sheet).getByRole('button', { name: /Relaciones con la comunidad/ })).toHaveTextContent('En espera');
    expect(within(sheet).getByRole('button', { name: /Conversaciones e inbox/ })).toHaveTextContent('En diseño');
    expect(screen.getByRole('button', { name: 'Relaciones', pressed: true })).toBeInTheDocument();
    // The scene stays in the page, untouched.
    expect(screen.getByRole('img', { name: /La oficina en pixel art/ })).toBeInTheDocument();

    await user.click(within(sheet).getByRole('button', { name: 'Cerrar' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('opens a role from its team and closes when swiped down, or with Esc', async () => {
    server();
    const user = userEvent.setup();
    renderOficina();
    await screen.findByText(/^Actividad real/);

    await user.click(screen.getByRole('button', { name: 'Operación' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: /Operador de cuenta/ }));
    const sheet = screen.getByRole('dialog', { name: 'Operador de cuenta' });
    expect(within(sheet).getByText('SERVICIO · OPERACIÓN')).toBeInTheDocument();
    expect(within(sheet).getByText(/no un agente de IA/)).toBeInTheDocument();
    expect(within(sheet).getByText('Trabajando · Ejecutando comentario aprobado')).toBeInTheDocument();
    expect(within(sheet).getByText('Nada todavía en esta sesión.')).toBeInTheDocument();
    expect(within(sheet).getByRole('link', { name: 'Ver en el Calendario' })).toHaveAttribute('href', '/calendario');

    // A short drag snaps back; a long one closes.
    const grip = screen.getByTestId('sheet-grip');
    fireEvent.pointerDown(grip, { clientY: 400, pointerId: 1 });
    fireEvent.pointerMove(grip, { clientY: 420, pointerId: 1 });
    fireEvent.pointerUp(grip, { clientY: 420, pointerId: 1 });
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    fireEvent.pointerDown(grip, { clientY: 400, pointerId: 1 });
    fireEvent.pointerMove(grip, { clientY: 520, pointerId: 1 });
    fireEvent.pointerUp(grip, { clientY: 520, pointerId: 1 });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Mesa editorial' }));
    expect(screen.getByRole('dialog', { name: 'Mesa editorial' })).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows the librarian as a service of the library, pointing to who uses it', async () => {
    server();
    const user = userEvent.setup();
    renderOficina();
    await screen.findByText(/^Actividad real/);

    await user.click(screen.getByRole('button', { name: 'Biblioteca' }));
    const sheet = screen.getByRole('dialog', { name: 'Bibliotecario' });
    expect(within(sheet).getByText('SERVICIO · BIBLIOTECA')).toBeInTheDocument();
    expect(within(sheet).getByText('Busca en la biblioteca lo que cada agente necesita: las clases del curso y lo que el equipo sabe de ti.')).toBeInTheDocument();
    expect(within(sheet).getByText(/Cada visita a la biblioteca es una consulta real de un agente/)).toBeInTheDocument();
    // It links to no knowledge view.
    expect(within(sheet).queryByRole('link')).not.toBeInTheDocument();

    await user.click(within(sheet).getByRole('button', { name: 'Ver quién la usa · Observatorio' }));
    const team = screen.getByRole('dialog', { name: 'Observatorio' });
    expect(within(team).getByText('2 INTEGRANTES · JUNTO A LA BIBLIOTECA')).toBeInTheDocument();
  });

  it('uses the side panel on desktop, with Operación by default', async () => {
    mockWide(true);
    server();
    const user = userEvent.setup();
    renderOficina();
    await screen.findByText(/^Actividad real/);
    const side = screen.getByRole('complementary', { name: 'Operación' });
    expect(within(side).getByRole('button', { name: /Operador de cuenta/ })).toHaveTextContent('Trabajando');
    await user.click(screen.getByRole('button', { name: 'El barrio' }));
    expect(screen.getByRole('complementary', { name: 'El barrio' })).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

describe('Oficina · events', () => {
  it('narrates real events, polls from the last one seen and lists them in the role panel', async () => {
    const ts = new Date().toISOString();
    const api = server({
      [EVENTOS]: { body: { events: [{ id: 7, ts, tipo: 'consulta_biblioteca', rol: 'copywriter_a', destino: 'biblioteca', detalle: 'clase 03' }], now: ts } },
    });
    const user = userEvent.setup();
    const { client } = renderOficina();
    await screen.findByText(/^Actividad real/);
    expect(await screen.findByText('Copywriter A va a la biblioteca: “clase 03”')).toBeInTheDocument();
    expect(api.find('GET', '/api/v1/oficina/eventos')[0]!.search.get('desde')).toBeNull();

    api.on(EVENTOS, { body: { events: [], now: new Date().toISOString() } });
    await client.refetchQueries({ queryKey: oficinaEventosKey });
    await waitFor(() => expect(api.find('GET', '/api/v1/oficina/eventos').length).toBe(2));
    expect(api.find('GET', '/api/v1/oficina/eventos')[1]!.search.get('desde')).toBe(ts);

    await user.click(screen.getByRole('button', { name: 'Mesa editorial' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: /Copywriter A/ }));
    const sheet = screen.getByRole('dialog', { name: 'Copywriter A' });
    expect(within(sheet).getByText('LO ÚLTIMO QUE HIZO')).toBeInTheDocument();
    expect(within(sheet).getAllByText('Copywriter A va a la biblioteca: “clase 03”').length).toBeGreaterThan(0);
  });

  it('stops polling when the feed is not available to this user', async () => {
    const api = server({ [EVENTOS]: { status: 403, body: { detail: 'Sin permiso' } } });
    renderOficina();
    await screen.findByText(/^Actividad real/);
    await waitFor(() => expect(api.find('GET', '/api/v1/oficina/eventos').length).toBe(1));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
