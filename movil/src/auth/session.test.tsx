// Device-token session: login keeps the token in SecureStore, start-up restores it, a 401 or a
// revoked token goes back to login, and logout unregisters the push token before revoking.
import { getTuTurno } from '@compartido/api/endpoints';
import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';
import { onlineManager } from '@tanstack/react-query';
import * as SecureStore from 'expo-secure-store';
import { Pressable, Text } from 'react-native';
import { clearToken, currentToken } from '@/api/token';
import '@/api/transport';
import { renderApp } from '@/test/render';
import { fakeServer } from '@/test/server';
import { useSession } from './session';

const store = (SecureStore as unknown as { __store: Map<string, string> }).__store;
const USER = { username: 'gustavo', is_superuser: true, permissions: [] };

function Probe() {
  const session = useSession();
  return (
    <>
      <Text testID="status">{session.status}</Text>
      <Text testID="user">{session.user?.username ?? ''}</Text>
      <Pressable testID="login" onPress={() => void session.login(' gustavo ', 'secreto').catch(() => undefined)} />
      <Pressable testID="logout" onPress={() => void session.logout()} />
    </>
  );
}

beforeEach(async () => {
  store.clear();
  await clearToken();
});

describe('session', () => {
  it('starts signed out without a stored token, and logs in with a device token', async () => {
    const server = fakeServer({
      'POST /api/v1/auth/token': { status: 201, body: { token: '0ff1ce_dt_nuevo', user: USER, device: { id: 'd1', name: 'Pixel de prueba', created_at: '2026-11-07T10:00:00Z' } } },
    });
    await renderApp(<Probe />, { session: true });
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('fuera'));
    await fireEvent.press(screen.getByTestId('login'));
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('dentro'));
    expect(screen.getByTestId('user')).toHaveTextContent('gustavo');
    expect(server.find('POST', '/api/v1/auth/token')[0]?.body).toEqual({ username: 'gustavo', password: 'secreto', device_name: 'Pixel de prueba' });
    expect(store.get('oficina.token-dispositivo')).toBe('0ff1ce_dt_nuevo');
    expect(currentToken()).toBe('0ff1ce_dt_nuevo');
  });

  it('restores a stored token when GET /auth/session accepts it', async () => {
    store.set('oficina.token-dispositivo', '0ff1ce_dt_guardado');
    const server = fakeServer({ 'GET /api/v1/auth/session': { body: { authenticated: true, user: USER } } });
    await renderApp(<Probe />, { session: true });
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('dentro'));
    expect(server.requests[0]?.headers.authorization).toBe('Bearer 0ff1ce_dt_guardado');
  });

  it('forgets a revoked token (session answers authenticated:false)', async () => {
    store.set('oficina.token-dispositivo', '0ff1ce_dt_revocado');
    fakeServer({ 'GET /api/v1/auth/session': { body: { authenticated: false, user: null } } });
    await renderApp(<Probe />, { session: true });
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('fuera'));
    expect(store.has('oficina.token-dispositivo')).toBe(false);
  });

  // ACC-06: only a 401 or `authenticated:false` logs out at start-up. Offline (expo/fetch's FetchError) or with the
  // server failing (a 5xx while it restarts) the phone keeps its token and stays inside.
  it('stays inside when the phone opens the app without a connection (expo/fetch FetchError)', async () => {
    store.set('oficina.token-dispositivo', '0ff1ce_dt_guardado');
    fakeServer({ 'GET /api/v1/auth/session': { fetchError: 'Unable to resolve host "office.projectapp.co"' } });
    await renderApp(<Probe />, { session: true });
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('dentro'));
    expect(store.get('oficina.token-dispositivo')).toBe('0ff1ce_dt_guardado');
    expect(currentToken()).toBe('0ff1ce_dt_guardado');
  });

  it('stays inside when the server answers 502 at start-up', async () => {
    store.set('oficina.token-dispositivo', '0ff1ce_dt_guardado');
    fakeServer({ 'GET /api/v1/auth/session': { status: 502, body: '<html>Bad Gateway</html>' } });
    await renderApp(<Probe />, { session: true });
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('dentro'));
    expect(store.get('oficina.token-dispositivo')).toBe('0ff1ce_dt_guardado');
  });

  it('forgets the token when the session answers 401 at start-up', async () => {
    store.set('oficina.token-dispositivo', '0ff1ce_dt_desconocido');
    fakeServer({ 'GET /api/v1/auth/session': { status: 401, body: { detail: 'Token inválido.' } } });
    await renderApp(<Probe />, { session: true });
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('fuera'));
    expect(store.has('oficina.token-dispositivo')).toBe(false);
  });

  it('recovers the user once the network is back after an offline start (ACC-06.6)', async () => {
    store.set('oficina.token-dispositivo', '0ff1ce_dt_guardado');
    const server = fakeServer({ 'GET /api/v1/auth/session': { fetchError: 'Failed to connect' } });
    await renderApp(<Probe />, { session: true });
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('dentro'));
    expect(screen.getByTestId('user')).toHaveTextContent('');
    server.on('GET /api/v1/auth/session', { body: { authenticated: true, user: USER } });
    await act(async () => {
      onlineManager.setOnline(false);
      onlineManager.setOnline(true);
    });
    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('gustavo'));
    expect(screen.getByTestId('status')).toHaveTextContent('dentro');
  });

  it('goes back to login when any request gets a 401', async () => {
    store.set('oficina.token-dispositivo', '0ff1ce_dt_guardado');
    fakeServer({
      'GET /api/v1/auth/session': { body: { authenticated: true, user: USER } },
      'GET /api/v1/tu-turno': { status: 401, body: { detail: 'Token inválido.' } },
    });
    await renderApp(<Probe />, { session: true });
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('dentro'));
    await act(async () => {
      await getTuTurno().catch(() => undefined);
    });
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('fuera'));
    expect(currentToken()).toBeNull();
  });

  it('logout: DELETE /push/expo first, then POST /auth/token/revocar, then forgets the token', async () => {
    store.set('oficina.token-dispositivo', '0ff1ce_dt_guardado');
    store.set('oficina.push-expo', 'ExponentPushToken[prueba]');
    const server = fakeServer({
      'GET /api/v1/auth/session': { body: { authenticated: true, user: USER } },
      'DELETE /api/v1/push/expo': { status: 204 },
      'POST /api/v1/auth/token/revocar': { status: 204 },
    });
    await renderApp(<Probe />, { session: true });
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('dentro'));
    await fireEvent.press(screen.getByTestId('logout'));
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('fuera'));
    const calls = server.requests.map((r) => `${r.method} ${r.path}`);
    expect(calls.slice(-2)).toEqual(['DELETE /api/v1/push/expo', 'POST /api/v1/auth/token/revocar']);
    expect(server.find('DELETE', '/api/v1/push/expo')[0]?.body).toEqual({ token: 'ExponentPushToken[prueba]' });
    expect(server.find('POST', '/api/v1/auth/token/revocar')[0]?.headers.authorization).toBe('Bearer 0ff1ce_dt_guardado');
    expect(store.has('oficina.token-dispositivo')).toBe(false);
    expect(store.has('oficina.push-expo')).toBe(false);
  });
});
