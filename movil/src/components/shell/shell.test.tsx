// The shell: the top bar counter (alerta when critical) and bell dot from GET /tu-turno, and the
// accessible labels.
import { turnoFixture } from '@compartido/fixtures/turno';
import { screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';
import { fireEvent } from '@testing-library/react-native';
import '@/api/transport';
import { renderApp } from '@/test/render';
import { fakeServer } from '@/test/server';
import { colors } from '@/theme/tokens';
import { TopBar } from './TopBar';
import { turnLabel } from './useTurnCount';

describe('top bar', () => {
  it('shows the Tu turno counter in alerta when critical, and the bell dot with unread notifications', async () => {
    fakeServer({
      'GET /api/v1/tu-turno': { body: turnoFixture({ count: 6, critical: true, urgent_count: 1, notifications_unread: 2 }) },
      'GET /api/v1/operador/overview': { body: { control: { paused: false }, accounts: [] } },
    });
    await renderApp(<TopBar />);
    const counter = await screen.findByTestId('turn-counter');
    expect(counter).toHaveTextContent('6');
    expect(counter).toHaveStyle({ backgroundColor: colors.alert });
    expect(screen.getByTestId('unread-dot')).toBeOnTheScreen();
    expect(screen.getByLabelText('Tu turno, 6 pendientes, 1 urgente')).toBeOnTheScreen();
    expect(screen.getByLabelText('Notificaciones, hay novedades')).toBeOnTheScreen();
    await fireEvent.press(screen.getByTestId('top-calendario'));
    expect(router.navigate).toHaveBeenCalledWith('/calendario');
  });

  it('hides the counter at 0 and shows the pause banner when the machine is paused', async () => {
    fakeServer({
      'GET /api/v1/tu-turno': { body: turnoFixture({ count: 0, notifications_unread: 0 }) },
      'GET /api/v1/operador/overview': { body: { control: { paused: true, reason: 'revisión', source: 'db' }, accounts: [] } },
    });
    await renderApp(<TopBar />);
    expect(await screen.findByText('Máquina en pausa')).toBeOnTheScreen();
    await waitFor(() => expect(screen.queryByTestId('turn-counter')).toBeNull());
    expect(screen.queryByTestId('unread-dot')).toBeNull();
    // From the tabs it focuses Ajustes › Máquina like the top bar does (navigate), never pushing another shell.
    await fireEvent.press(screen.getByRole('link', { name: /Máquina en pausa/ }));
    expect(router.navigate).toHaveBeenCalledWith({ pathname: '/ajustes', params: { ancla: 'maquina' } });
    expect(router.push).not.toHaveBeenCalled();
  });

  it('builds the accessible Tu turno label', () => {
    expect(turnLabel({ count: 0, critical: false, urgent: 0 })).toBe('Tu turno');
    expect(turnLabel({ count: 1, critical: false, urgent: 0 })).toBe('Tu turno, 1 pendiente');
    expect(turnLabel({ count: 3, critical: true, urgent: 0 })).toBe('Tu turno, 3 pendientes, con algo urgente');
  });
});
