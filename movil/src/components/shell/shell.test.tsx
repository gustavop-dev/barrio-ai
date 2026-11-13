// The shell's top bar: the bell dot from GET /tu-turno, the pause banner and the accessible labels. The Bandeja de
// entrada counter moved to the bottom bar on 12/11/2026 (navegacion.test.tsx, «BottomBar»).
import { turnoFixture } from '@compartido/fixtures/turno';
import { screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';
import { fireEvent } from '@testing-library/react-native';
import '@/api/transport';
import { renderApp } from '@/test/render';
import { fakeServer } from '@/test/server';
import { TopBar } from './TopBar';
import { turnLabel } from './useTurnCount';

describe('top bar', () => {
  it('shows the bell dot with unread notifications; the Bandeja and its counter are no longer up here', async () => {
    fakeServer({
      'GET /api/v1/tu-turno': { body: turnoFixture({ count: 6, critical: true, urgent_count: 1, notifications_unread: 2 }) },
      'GET /api/v1/operador/overview': { body: { control: { paused: false }, accounts: [] } },
    });
    await renderApp(<TopBar />);
    expect(await screen.findByTestId('unread-dot')).toBeOnTheScreen();
    expect(screen.getByLabelText('Notificaciones, hay novedades')).toBeOnTheScreen();
    expect(screen.queryByTestId('top-tu-turno')).toBeNull();
    expect(screen.queryByTestId('turn-counter')).toBeNull();
    expect(screen.queryByLabelText(/Bandeja de entrada/)).toBeNull();
    await fireEvent.press(screen.getByTestId('top-calendario'));
    expect(router.navigate).toHaveBeenCalledWith('/calendario');
  });

  it('shows the pause banner when the machine is paused', async () => {
    fakeServer({
      'GET /api/v1/tu-turno': { body: turnoFixture({ count: 0, notifications_unread: 0 }) },
      'GET /api/v1/operador/overview': { body: { control: { paused: true, reason: 'revisión', source: 'db' }, accounts: [] } },
    });
    await renderApp(<TopBar />);
    expect(await screen.findByText('Máquina en pausa')).toBeOnTheScreen();
    await waitFor(() => expect(screen.queryByTestId('unread-dot')).toBeNull());
    // From the tabs it focuses Ajustes › Máquina like the top bar does (navigate), never pushing another shell.
    await fireEvent.press(screen.getByRole('link', { name: /Máquina en pausa/ }));
    expect(router.navigate).toHaveBeenCalledWith({ pathname: '/ajustes', params: { ancla: 'maquina' } });
    expect(router.push).not.toHaveBeenCalled();
  });

  it('builds the accessible Bandeja de entrada label', () => {
    expect(turnLabel({ count: 0, critical: false, urgent: 0 })).toBe('Bandeja de entrada');
    expect(turnLabel({ count: 1, critical: false, urgent: 0 })).toBe('Bandeja de entrada, 1 pendiente');
    expect(turnLabel({ count: 3, critical: true, urgent: 0 })).toBe('Bandeja de entrada, 3 pendientes, con algo urgente');
  });
});
