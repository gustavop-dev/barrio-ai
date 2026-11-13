import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { TurnoCard } from '../api/types';
import { overviewFixture, renderApp, tuTurnoFixture } from '../test/app';
import { fakeServer, SESSION_OK } from '../test/fakeServer';
import { turnoAnchor, turnLabel } from './Layout';

function card(overrides: Partial<TurnoCard> = {}): TurnoCard {
  return {
    id: 'question:q1',
    type: 'pregunta',
    critical: false,
    tone: 'info',
    agent: 'director_editorial',
    agent_label: 'Director editorial',
    title: '¿Aceptas proyectos de 3 meses?',
    body: '',
    deadline: null,
    created_at: null,
    actions: [],
    ...overrides,
  };
}

function server(turno = tuTurnoFixture(), overview = overviewFixture()) {
  return fakeServer({
    'GET /api/v1/auth/session': { body: SESSION_OK },
    'GET /api/v1/tu-turno': { body: turno },
    'GET /api/v1/operador/overview': { body: overview },
  });
}

/** The top bar (mobile) and the sidebar (desktop) both exist in the DOM; CSS shows one. */
function topBar() {
  return screen.getByRole('navigation', { name: 'Accesos' });
}

async function topBarReady() {
  return screen.findByRole('navigation', { name: 'Accesos' });
}

describe('Layout · navegación', () => {
  it('shows the mobile bars and the desktop sidebar with every view', async () => {
    server();
    renderApp('/calendario');
    expect(await screen.findByRole('heading', { name: 'Calendario', level: 1 })).toBeInTheDocument();

    const [sidebar, bottom] = screen.getAllByRole('navigation', { name: 'Secciones' });
    expect(within(sidebar!).getAllByRole('link').map((a) => a.textContent)).toEqual([
      'Oficina',
      'Bandeja de entrada',
      'Notificaciones',
      'Calendario',
      'Resultados',
      'Personas',
      'Galería',
      'Ajustes',
    ]);
    expect(within(bottom!).getAllByRole('link').map((a) => a.getAttribute('href'))).toEqual(['/', '/resultados', '/personas', '/galeria']);
    expect(within(topBar()).getAllByRole('link').map((a) => a.getAttribute('href'))).toEqual(['/tu-turno', '/notificaciones', '/calendario', '/ajustes']);

    // The active view sits on its highlight in the top bar and the sidebar.
    expect(within(topBar()).getByRole('link', { name: 'Calendario' })).toHaveAttribute('aria-current', 'page');
    expect(within(sidebar!).getByRole('link', { name: 'Calendario' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByText('LimeZu · Modern Interiors')).toHaveAttribute('href', 'https://limezu.itch.io/moderninteriors');
  });

  it('hides the Tu turno counter at 0 and the bell dot without unread notifications', async () => {
    server(tuTurnoFixture({ count: 0, notifications_unread: 0 }));
    renderApp('/resultados');
    const link = await within(await topBarReady()).findByRole('link', { name: 'Bandeja de entrada' });
    expect(link.querySelector('.navcount')).toBeNull();
    expect(within(topBar()).getByRole('link', { name: 'Notificaciones' }).querySelector('.navdot')).toBeNull();
  });

  it('paints the counter neutral with questions only and puts a dot on the bell', async () => {
    server(tuTurnoFixture({ count: 3, critical: false, questions: [card(), card({ id: 'question:q2' }), card({ id: 'question:q3' })], notifications_unread: 4 }));
    renderApp('/resultados');
    const link = await within(await topBarReady()).findByRole('link', { name: 'Bandeja de entrada, 3 pendientes' });
    const counter = link.querySelector('.navcount');
    expect(counter).toHaveTextContent('3');
    expect(counter).toHaveAttribute('data-tone', 'neutral');
    const bell = within(topBar()).getByRole('link', { name: 'Notificaciones, hay novedades' });
    expect(bell.querySelector('.navdot')).not.toBeNull();
    expect(bell).not.toHaveTextContent('4');
  });

  it('paints the counter red when there is a critical notice', async () => {
    server(
      tuTurnoFixture({
        count: 6,
        critical: true,
        alerts: [card({ id: 'uncertain:a1', type: 'aviso', critical: true, tone: 'bad' }), card({ id: 'linkedin_expiring', type: 'aviso', tone: 'warn' })],
      }),
    );
    renderApp('/resultados');
    const link = await within(await topBarReady()).findByRole('link', { name: 'Bandeja de entrada, 6 pendientes, 1 urgente' });
    expect(link.querySelector('.navcount')).toHaveAttribute('data-tone', 'critical');
    // Same counter in the sidebar.
    const [sidebar] = screen.getAllByRole('navigation', { name: 'Secciones' });
    expect(within(sidebar!).getByRole('link', { name: 'Bandeja de entrada, 6 pendientes, 1 urgente' }).querySelector('.navcount')).toHaveTextContent('6');
  });

  it('opens the capture from the centre button and from the sidebar', async () => {
    server();
    const user = userEvent.setup();
    const { onCapture } = renderApp('/galeria');
    await screen.findByRole('heading', { name: 'Galería', level: 1 });
    await user.click(screen.getByRole('button', { name: 'Capturar: mantén oprimido para grabar audio, o toca para foto o nota' }));
    await user.click(screen.getByRole('button', { name: 'Capturar' }));
    expect(onCapture).toHaveBeenCalledTimes(2);
    expect(onCapture).toHaveBeenCalledWith(undefined);
  });

  it('replaces the logo with a back link on detail views', async () => {
    server();
    renderApp('/calendario/pieza/p1');
    expect(await screen.findByRole('heading', { name: 'Detalle de la pieza', level: 1 })).toBeInTheDocument();
    expect(document.querySelector('.topbar-brand')).toBeNull();
    const back = document.querySelector('.topbar-back');
    expect(back).toHaveAttribute('href', '/calendario');
    expect(back).toHaveTextContent('Calendario');
  });
});

describe('Layout · banners', () => {
  it('shows the pause banner on every view, linking to Ajustes › Máquina', async () => {
    server(tuTurnoFixture(), overviewFixture({ control: { paused: true, reason: 'Reviso los topes', source: 'db', updated_at: null, updated_by: 'gustavo' } }));
    renderApp('/personas');
    const banner = await screen.findByRole('link', { name: /Máquina en pausa/ });
    expect(banner).toHaveTextContent('Máquina en pausa · Reviso los topes');
    expect(banner).not.toHaveTextContent('fijada en el entorno');
    expect(banner).toHaveAttribute('href', '/ajustes#maquina');
  });

  it('says when the stop comes from the environment', async () => {
    server(tuTurnoFixture(), overviewFixture({ control: { paused: true, reason: 'Mantenimiento', source: 'env', updated_at: null, updated_by: null } }));
    renderApp('/personas');
    expect(await screen.findByRole('link', { name: /Máquina en pausa/ })).toHaveTextContent('Mantenimiento · fijada en el entorno');
  });

  it('shows the account-paused variant and links to its Tu turno notice', async () => {
    server(
      tuTurnoFixture(),
      overviewFixture({
        accounts: [
          { id: 'acc-1', label: 'LinkedIn Gustavo', provider: 'unipile', status: 'running', is_locked: false, paused: true, paused_reason: 'LinkedIn limitó las invitaciones', last_checked_at: null },
        ],
      }),
    );
    renderApp('/personas');
    const banner = await screen.findByRole('link', { name: /La cuenta de LinkedIn está en pausa/ });
    expect(banner).toHaveTextContent('LinkedIn limitó las invitaciones');
    expect(banner).toHaveAttribute('href', `/tu-turno#${turnoAnchor('account_paused:acc-1')}`);
  });

  it('shows no banner while the machine runs', async () => {
    server();
    renderApp('/personas');
    await screen.findByRole('heading', { name: 'Personas', level: 1 });
    await waitFor(() => expect(screen.queryByText(/en pausa/)).not.toBeInTheDocument());
  });

  it('shows the offline strip while the device is offline', async () => {
    server();
    const online = Object.getOwnPropertyDescriptor(Navigator.prototype, 'onLine');
    Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => false });
    try {
      renderApp('/personas');
      expect(await screen.findByText('Sin conexión. Mostrando lo último que cargó.')).toBeInTheDocument();
    } finally {
      delete (navigator as { onLine?: boolean }).onLine;
      if (online) Object.defineProperty(Navigator.prototype, 'onLine', online);
    }
  });
});

describe('turnLabel', () => {
  it('names the count and the urgent items', () => {
    expect(turnLabel({ count: 0, critical: false, urgent: 0 })).toBe('Bandeja de entrada');
    expect(turnLabel({ count: 1, critical: false, urgent: 0 })).toBe('Bandeja de entrada, 1 pendiente');
    expect(turnLabel({ count: 4, critical: true, urgent: 2 })).toBe('Bandeja de entrada, 4 pendientes, 2 urgentes');
  });
});
