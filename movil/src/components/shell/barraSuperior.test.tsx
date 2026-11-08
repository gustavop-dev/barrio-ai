// The top bar on the real shell: the root layout, the login, the (app) stack and the tabs layout with
// TopBar and BottomBar, on the real Expo Router (the rest of the suite mocks it). Only the screens are
// minimal. It guards the regression where none of the top-bar destinations opened (Tu turno,
// Notificaciones, Calendario, Ajustes): pressing an icon must focus its screen and leave its content
// visible (no opacity 0, not moved off-screen in the applied style), from any tab and from a detail,
// and back must return. It also checks that the login leaves the tree after signing in.
//
// What these tests cannot see: real touches. fireEvent calls the pressed element's handler directly,
// so a transparent layer drawn over the top bar would not stop a press here. The emulator + Maestro QA
// covers that.
import { turnoFixture } from '@compartido/fixtures/turno';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react-native';
import * as SecureStore from 'expo-secure-store';
import { router } from 'expo-router';
import { ExpoRoot, type ExpoRootProps } from 'expo-router/build/ExpoRoot';
import { getRouteInfoFromState } from 'expo-router/build/global-state/getRouteInfoFromState';
import { navigationRef } from 'expo-router/build/global-state/navigationRef';
import { inMemoryContext } from 'expo-router/build/testing-library/context-stubs';
import { Dimensions, NativeModules, StyleSheet, Text } from 'react-native';
import type { TestInstance } from 'test-renderer';
import TabsLayout from '@/app/(app)/(tabs)/_layout';
import AppLayout from '@/app/(app)/_layout';
import RootLayout from '@/app/_layout';
import Login from '@/app/login';
import { clearToken } from '@/api/token';
import { DetailScreen } from '@/components/shell/DetailScreen';
import { openLink } from '@/navigation';
import { fakeServer } from '@/test/server';
import { navValues } from '@/theme/motion';

jest.unmock('expo-router');

// What expo-router/testing-library mocks for its renderRouter (its Reanimated mock is left out: this
// suite runs the real Reanimated through setUpTests).
jest.mock('expo-linking', () => ({
  ...jest.requireActual('expo-linking'),
  createURL: (path: string) => `barrio://${path}`,
  resolveScheme: () => 'barrio',
  addEventListener: () => ({ remove: () => undefined }),
}));

jest.mock('expo-font', () => ({ ...jest.requireActual('expo-font'), useFonts: () => [true, null] }));

// Only the GPU boundary of the login's pixel door.
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

const store = (SecureStore as unknown as { __store: Map<string, string> }).__store;
const USER = { username: 'gustavo', is_superuser: true, permissions: [] };
const TOP = ['tu-turno', 'notificaciones', 'calendario', 'ajustes'] as const;
const BOTTOM = ['index', 'resultados', 'personas', 'galeria'] as const;
/** A tab change at rest: js-tabs' native-driven animations (ended by the mock below) and its 32 ms tail. */
const TAB_MS = 250;
/** Long enough for every Reanimated spring of the shell (the detail push, the entrance) to come to rest. */
const SETTLE_MS = 1500;

function screenOf(name: string) {
  return function Pantalla() {
    return <Text testID={`pantalla-${name}`}>{name}</Text>;
  };
}

function PersonaStub() {
  return (
    <DetailScreen back="Personas" fallback="/personas">
      <Text testID="pantalla-persona">Ficha</Text>
    </DetailScreen>
  );
}

function PiezaStub() {
  return (
    <DetailScreen back="Calendario" fallback="/calendario">
      <Text testID="pantalla-pieza">Pieza</Text>
    </DetailScreen>
  );
}

const ROUTES = {
  _layout: RootLayout,
  login: Login,
  '(app)/_layout': AppLayout,
  '(app)/(tabs)/_layout': TabsLayout,
  ...Object.fromEntries([...BOTTOM, ...TOP].map((name) => [`(app)/(tabs)/${name}`, screenOf(name)])),
  '(app)/personas/[id]': PersonaStub,
  '(app)/calendario/pieza/[id]': PiezaStub,
};

/** What the shell asks for once signed in. */
const SHELL_API = {
  'GET /api/v1/tu-turno': { body: turnoFixture({ count: 3, notifications_unread: 1 }) },
  'GET /api/v1/operador/overview': { body: { control: { paused: false }, accounts: [] } },
  'GET /api/v1/capturas': { body: { count: 0, next: null, previous: null, results: [] } },
  'GET /api/v1/preguntas': { body: [] },
};

async function advance(ms: number) {
  await act(async () => {
    await jest.advanceTimersByTimeAsync(ms);
  });
}

async function renderShell() {
  const view = await render(<ExpoRoot context={inMemoryContext(ROUTES) as unknown as ExpoRootProps['context']} location="/" />);
  await advance(SETTLE_MS);
  return view;
}

async function renderSignedIn() {
  store.set('oficina.token-dispositivo', '0ff1ce_dt_guardado');
  fakeServer({ ...SHELL_API, 'GET /api/v1/auth/session': { body: { authenticated: true, user: USER } } });
  const view = await renderShell();
  await waitFor(() => expect(screen.getByTestId('pantalla-index')).toBeOnTheScreen());
  return view;
}

function rootState() {
  return navigationRef.getRootState() as unknown as Parameters<typeof getRouteInfoFromState>[0];
}

function pathname(): string {
  return getRouteInfoFromState(rootState()).pathname;
}

/** The routes of the root stack (Expo Router 58 wraps it in a `__root` route). */
function rootStackNames(): string[] {
  type Node = { routes?: { name: string; state?: Node }[] };
  let state = navigationRef.getRootState() as unknown as Node;
  while (state.routes?.length === 1 && state.routes[0]?.name === '__root' && state.routes[0].state) state = state.routes[0].state;
  return state.routes?.map((route) => route.name) ?? [];
}

const pathOf = (name: string) => (name === 'index' ? '/' : `/${name}`);

/** A view's style as applied now: its props, with what Reanimated applied under Jest on top (`jestAnimatedStyle`). */
function liveStyle(node: TestInstance): { opacity?: unknown; transform?: unknown } {
  const style = StyleSheet.flatten(node.props.style) ?? {};
  const live = (node.props.jestAnimatedStyle as { value?: Record<string, unknown> } | undefined)?.value ?? {};
  return { ...style, ...live };
}

/** The opacity and horizontal offset an element ends up with, through its own style and every ancestor's. */
function appliedFrame(element: TestInstance): { opacity: number; translateX: number } {
  let opacity = 1;
  let translateX = 0;
  for (let node: TestInstance | null = element; node; node = node.parent) {
    const style = liveStyle(node);
    if (typeof style.opacity === 'number') opacity *= style.opacity;
    if (Array.isArray(style.transform)) {
      for (const step of style.transform as Record<string, unknown>[]) {
        if (typeof step.translateX === 'number') translateX += step.translateX;
      }
    }
  }
  return { opacity, translateX };
}

/** The route `name` is focused and its content is on the screen: visible, opaque and in place. */
function expectShown(name: string, path = pathOf(name)) {
  expect(pathname()).toBe(path);
  const content = screen.getByTestId(`pantalla-${name}`);
  expect(content).toBeVisible();
  const frame = appliedFrame(content);
  expect(frame.opacity).toBeCloseTo(1, 2);
  expect(Math.abs(frame.translateX)).toBeLessThan(1);
}

async function press(testID: string, settle = TAB_MS) {
  await fireEvent.press(screen.getByTestId(testID));
  await advance(settle);
}

async function back(settle = TAB_MS) {
  await act(async () => {
    router.back();
  });
  await advance(settle);
}

beforeAll(() => {
  // As renderRouter does: the routes load synchronously.
  process.env.EXPO_ROUTER_IMPORT_MODE = 'sync';
});

beforeEach(async () => {
  jest.useFakeTimers();
  store.clear();
  await clearToken();
  // React Native's jest mock ends a native-driven animation without telling JS its final value, so a
  // scene would keep the value it started from. The phone reports it; so does this mock.
  (NativeModules.NativeAnimatedModule.startAnimatingNode as jest.Mock).mockImplementation(
    (_id: number, _tag: number, config: { toValue?: number }, end?: (result: { finished: boolean; value?: number; offset?: number }) => void) => {
      setTimeout(() => end?.({ finished: true, value: config.toValue, offset: 0 }), 16);
    },
  );
});

afterEach(() => {
  jest.useRealTimers();
});

describe('the top bar on the real shell', () => {
  it('opens Tu turno, Notificaciones, Calendario and Ajustes from every bottom tab, and back returns', async () => {
    await renderSignedIn();
    for (const tab of BOTTOM) {
      if (tab !== 'index') await press(`tab-${tab}`);
      expectShown(tab);
      for (const destination of TOP) {
        await press(`top-${destination}`);
        expectShown(destination);
        expect(screen.getByTestId(`top-${destination}`)).toBeSelected();
        // The screen it came from is no longer the one shown.
        expect(screen.queryByTestId(`pantalla-${tab}`)).toBeNull();
        await back();
        expectShown(tab);
      }
    }
  }, 60_000);

  it('goes from one top-bar screen to another and back through them; a second press stays', async () => {
    await renderSignedIn();
    await press('top-tu-turno');
    expectShown('tu-turno');
    await press('top-tu-turno');
    expectShown('tu-turno');
    await press('top-notificaciones');
    expectShown('notificaciones');
    await press('top-ajustes');
    expectShown('ajustes');
    await press('top-calendario');
    expectShown('calendario');
    await back();
    expectShown('ajustes');
    await back();
    expectShown('notificaciones');
    await back();
    expectShown('tu-turno');
    await back();
    expectShown('index');
  });

  it('pushes a top-bar screen in from the right over the screen underneath, and pops it back (MovNavegacion)', async () => {
    await renderSignedIn();
    const { width } = Dimensions.get('window');
    const parallax = navValues.pushParallax * width;
    // First frame of the push: Tu turno starts beyond the right edge, opaque (not a fade).
    await fireEvent.press(screen.getByTestId('top-tu-turno'));
    const entering = appliedFrame(screen.getByTestId('pantalla-tu-turno'));
    expect(entering.translateX).toBeCloseTo(width, 0);
    expect(entering.opacity).toBeCloseTo(1, 2);
    await advance(TAB_MS);
    expectShown('tu-turno');
    // The Oficina underneath ended 30 % to the left.
    expect(appliedFrame(screen.getByTestId('pantalla-index', { includeHiddenElements: true })).translateX).toBeCloseTo(-parallax, 0);

    // First frame of the way back: the Oficina comes from 30 % to the left, from transparent.
    await act(async () => {
      router.back();
    });
    const returning = appliedFrame(screen.getByTestId('pantalla-index'));
    expect(returning.translateX).toBeCloseTo(-parallax, 0);
    expect(returning.opacity).toBeCloseTo(0, 2);
    await advance(TAB_MS);
    expectShown('index');
    // Tu turno left through the right edge.
    expect(appliedFrame(screen.getByTestId('pantalla-tu-turno', { includeHiddenElements: true })).translateX).toBeCloseTo(width, 0);

    // A bottom tab still crossfades: Resultados starts transparent, in place horizontally.
    await fireEvent.press(screen.getByTestId('tab-resultados'));
    const fading = appliedFrame(screen.getByTestId('pantalla-resultados'));
    expect(fading.opacity).toBeCloseTo(0, 2);
    expect(fading.translateX).toBeCloseTo(0, 0);
    await advance(TAB_MS);
    expectShown('resultados');
  });

  it('opens a top-bar screen from an in-app link (a push, a card) too', async () => {
    await renderSignedIn();
    await act(async () => openLink('/ajustes'));
    await advance(TAB_MS);
    expectShown('ajustes');
    await act(async () => openLink('/tu-turno'));
    await advance(TAB_MS);
    expectShown('tu-turno');
  });

  it('keeps the bottom tabs working, and back walks the tab history', async () => {
    await renderSignedIn();
    for (const [tab, label] of [
      ['resultados', 'Resultados'],
      ['personas', 'Personas'],
      ['galeria', 'Galería'],
    ] as const) {
      await press(`tab-${tab}`);
      expectShown(tab);
      expect(screen.getByRole('tab', { name: label })).toBeSelected();
    }
    await press('top-tu-turno');
    expectShown('tu-turno');
    for (const label of ['Oficina', 'Resultados', 'Personas', 'Galería']) expect(screen.getByRole('tab', { name: label })).not.toBeSelected();
    await press('tab-index');
    expectShown('index');
    await back();
    expectShown('tu-turno');
    await back();
    expectShown('galeria');
    await back();
    expectShown('personas');
  });

  it('opens the top-bar destinations from a detail screen, after its push back', async () => {
    await renderSignedIn();
    await press('tab-personas');
    await act(async () => {
      router.push('/personas/7');
    });
    await advance(SETTLE_MS);
    expect(pathname()).toBe('/personas/7');
    expect(screen.getByTestId('pantalla-persona')).toBeVisible();
    expect(Math.abs(appliedFrame(screen.getByTestId('pantalla-persona')).translateX)).toBeLessThan(1);
    // Under the detail, the whole shell (top bar and tabs) moved 30 % to the left.
    const { width } = Dimensions.get('window');
    expect(appliedFrame(screen.getByTestId('shell-tabs', { includeHiddenElements: true })).translateX).toBeCloseTo(-navValues.pushParallax * width, 0);
    await back(SETTLE_MS);
    expectShown('personas');
    expect(appliedFrame(screen.getByTestId('shell-tabs')).translateX).toBeCloseTo(0, 0);

    await act(async () => {
      router.push('/personas/7');
    });
    await advance(SETTLE_MS);
    await fireEvent.press(within(screen.getByTestId('detail-panel')).getByTestId('top-tu-turno'));
    // The detail first runs its push back to rest (FIRM) and only then lets the navigation go on: that
    // commit lands when the act() ends, so the tab's own push needs a second act to run.
    await advance(SETTLE_MS);
    await advance(TAB_MS);
    expectShown('tu-turno');
    // The detail went (after its push back), and no second shell was stacked over it.
    expect(screen.queryByTestId('pantalla-persona', { includeHiddenElements: true })).toBeNull();
    expect(screen.getAllByTestId('shell-tabs', { includeHiddenElements: true })).toHaveLength(1);
    expect(appliedFrame(screen.getByTestId('shell-tabs')).translateX).toBeCloseTo(0, 0);
    // Back returns to the tab the detail was opened from.
    await back();
    expectShown('personas');
  });
});

describe('login → app', () => {
  it('takes the login out of the tree once inside, with the top bar working right away', async () => {
    fakeServer({
      ...SHELL_API,
      'POST /api/v1/auth/token': { status: 201, body: { token: '0ff1ce_dt_nuevo', user: USER, device: { id: 'd1', name: 'Pixel de prueba', created_at: '2026-11-07T10:00:00Z' } } },
    });
    await renderShell();
    await waitFor(() => expect(screen.getByTestId('login')).toBeOnTheScreen());
    expect(pathname()).toBe('/login');

    await fireEvent.changeText(screen.getByTestId('login-usuario'), 'gustavo');
    await fireEvent.changeText(screen.getByTestId('login-clave'), 'secreto');
    await fireEvent.press(screen.getByTestId('login-entrar'));
    await waitFor(() => expect(screen.queryByTestId('login', { includeHiddenElements: true })).toBeNull(), { timeout: 5000 });
    await advance(SETTLE_MS);

    // Nothing of the login is left: not in the tree, not in the root stack.
    expect(screen.queryByTestId('login-entrar', { includeHiddenElements: true })).toBeNull();
    expect(rootStackNames()).toEqual(['(app)']);
    expectShown('index');

    // The top bar is not under anything: none of its ancestors turns touches off.
    const icon = screen.getByTestId('top-tu-turno');
    for (let node: TestInstance | null = icon; node; node = node.parent) expect(['none', 'box-only']).not.toContain(node.props.pointerEvents);

    await press('top-tu-turno');
    expectShown('tu-turno');
    await back();
    expectShown('index');
  });
});
