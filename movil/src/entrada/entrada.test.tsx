// MovEntrada: after a successful login the door opens (the app is already under the login), the picture
// zooms to 3× in integer steps and the login fades out and leaves; with reduced motion it only
// crossfades; a failed login stays put.
import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';
import { useEffect } from 'react';
import { StyleSheet } from 'react-native';
import Login from '@/app/login';
import '@/api/transport';
import { clearToken } from '@/api/token';
import { renderApp } from '@/test/render';
import { fakeServer } from '@/test/server';
import { entrada, navTimings } from '@/theme/motion';
import { useEntrada, type Entrada } from './useEntrada';

// Only the GPU boundary is mocked.
jest.mock('@shopify/react-native-skia', () => {
  const { View } = require('react-native');
  const Nothing = () => null;
  return {
    Canvas: View,
    Group: Nothing,
    Image: Nothing,
    Rect: Nothing,
    rect: (x: number, y: number, width: number, height: number) => ({ x, y, width, height }),
    useImage: () => null,
    FilterMode: { Nearest: 0, Linear: 1 },
    MipmapMode: { None: 0 },
  };
});

const expoRouter = jest.requireMock('expo-router') as Record<string, unknown>;
const USER = { username: 'gustavo', is_superuser: true, permissions: [] };

function Probe({ reduced, onDone, onApi }: { reduced: boolean; onDone: () => void; onApi: (api: Entrada) => void }) {
  const api = useEntrada({ reduced, onDone });
  useEffect(() => {
    onApi(api);
  });
  return null;
}

describe('the entrance timeline', () => {
  it('opens the door, zooms to 3× and fades the login out, in the board order', async () => {
    const seen: { api: Entrada | null } = { api: null };
    const onDone = jest.fn();
    await renderApp(<Probe reduced={false} onDone={onDone} onApi={(value) => (seen.api = value)} />);
    await act(async () => seen.api!.start());
    expect(onDone).not.toHaveBeenCalled();
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1), { timeout: 3000 });
    const api = seen.api!;
    expect(api.door.hole.get()).toBe(1);
    expect(api.door.leaf.get()).toBe(entrada.leafOpen);
    expect(api.door.zoom.get()).toBe(entrada.zoom3);
    expect(api.leaving.get()).toBe(1);
    expect(api.shown.get()).toBe(0);
    expect(api.running).toBe(true);
  });

  it('with reduced motion only crossfades into the Oficina', async () => {
    const seen: { api: Entrada | null } = { api: null };
    const onDone = jest.fn();
    await renderApp(<Probe reduced onDone={onDone} onApi={(value) => (seen.api = value)} />);
    await act(async () => seen.api!.start());
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1), { timeout: 3000 });
    const api = seen.api!;
    expect(api.shown.get()).toBe(0);
    expect(api.door.zoom.get()).toBe(1);
    expect(api.door.leaf.get()).toBe(1);
    expect(api.door.hole.get()).toBe(0);
    expect(api.leaving.get()).toBe(0);
  });

  it('uses the design steps and tokens', () => {
    expect([entrada.leafHalf, entrada.leafOpen, entrada.leafStepMs]).toEqual([0.5, 0.125, 80]);
    expect([entrada.zoom2Ms, entrada.zoom2, entrada.zoom3Ms, entrada.zoom3]).toEqual([160, 2, 310, 3]);
    expect([entrada.formOutMs, entrada.formDrop, entrada.fadeMs]).toEqual([160, 16, 460]);
    expect(navTimings.entradaFormOut).toEqual({ duration: 180, easing: 'exit' });
    expect(navTimings.entradaFade).toEqual({ duration: 260, easing: 'enter' });
  });
});

describe('login → Oficina', () => {
  const navigation = {
    getState: () => ({ index: 0, routes: [{ key: 'login-1', name: 'login' }] }),
    dispatch: jest.fn(),
    canGoBack: () => true,
    goBack: jest.fn(),
  };

  beforeEach(async () => {
    expoRouter.useNavigation = () => navigation;
    // No token left by another test: with one, the start-up keeps the session (only a 401 logs out) and the login redirects.
    await clearToken();
  });

  async function fillAndEnter() {
    await fireEvent.changeText(screen.getByTestId('login-usuario'), 'gustavo');
    await fireEvent.changeText(screen.getByTestId('login-clave'), 'secreto');
    await fireEvent.press(screen.getByTestId('login-entrar'));
  }

  it('opens the door after a successful login and leaves once faded, without resetting the stack', async () => {
    fakeServer({ 'POST /api/v1/auth/token': { status: 201, body: { token: '0ff1ce_dt_nuevo', user: USER, device: { id: 'd1', name: 'Pixel de prueba', created_at: '2026-11-07T10:00:00Z' } } } });
    await renderApp(<Login />, { session: true });
    await fillAndEnter();
    expect(screen.queryByTestId('redirect')).toBeNull();
    await waitFor(() => expect(navigation.goBack).toHaveBeenCalledTimes(1), { timeout: 3000 });
    // The app is already under the login (the (app) layout opened it over itself): no RESET, which Expo Router 58 rejects.
    expect(navigation.dispatch).not.toHaveBeenCalled();
  });

  it('stays on the login when the credentials are wrong', async () => {
    fakeServer({ 'POST /api/v1/auth/token': { status: 400, body: { detail: 'Credenciales inválidas.' } } });
    await renderApp(<Login />, { session: true });
    await fillAndEnter();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Entrar' })).toBeEnabled());
    expect(navigation.dispatch).not.toHaveBeenCalled();
    expect(navigation.goBack).not.toHaveBeenCalled();
  });

  // The keyboard covers the lower half of the screen: while a field is focused the content is shifted up (a transform,
  // part of the render) until the form's heading sits under the status bar, whatever height the keyboard reports.
  it('lifts the form above the keyboard while a field is focused', async () => {
    fakeServer({});
    await renderApp(<Login />, { session: true });
    const shift = () => {
      const style = StyleSheet.flatten(screen.getByTestId('login-scroll').props.contentContainerStyle) as { transform?: { translateY?: number }[] };
      return style.transform?.[0]?.translateY ?? 0;
    };
    await fireEvent(screen.getByTestId('login-form'), 'layout', { nativeEvent: { layout: { x: 0, y: 400, width: 390, height: 420 } } });
    expect(shift()).toBeCloseTo(0);
    await fireEvent(screen.getByTestId('login-clave'), 'focus');
    expect(shift()).toBeLessThan(-300);
    expect(shift()).toBeGreaterThanOrEqual(-400);
  });
});
