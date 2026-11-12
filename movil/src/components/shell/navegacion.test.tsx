// MovNavegacion: the push of detail screens (thresholds, projection, reduced motion, every way back
// waiting for the spring), the tab content change and the top-bar push, and the bottom bar's pill and
// haptic.
import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';
import * as Haptics from 'expo-haptics';
import { router } from 'expo-router';
import type { BottomTabBarProps } from 'expo-router/js-tabs';
import { Animated, Dimensions, Text } from 'react-native';
import { State } from 'react-native-gesture-handler';
import { fireGestureHandler, getByGestureTestId } from 'react-native-gesture-handler/jest-utils';
import '@/api/transport';
import { renderApp } from '@/test/render';
import { fakeServer } from '@/test/server';
import { durations, FIRM, navGestures, navSprings, navTimings, navValues } from '@/theme/motion';
import { BottomBar, pillLeft } from './BottomBar';
import { DetailScreen } from './DetailScreen';
import { backLabel, baseFrame, canGrab, dragProgress, edgeRelease, panelFrame, stackLevel, stackOf } from './push';
import { focusedChild, nextFocus, sceneRole, tabMove, tabSceneOptions, useFocusMemory, type FocusMemory } from './tabTransitions';

const expoRouter = jest.requireMock('expo-router') as Record<string, unknown>;

/** Hands over what useFocusMemory returns in every render. */
function FocusProbe({ focused, onMemory }: { focused: string | null; onMemory: (memory: FocusMemory) => void }) {
  onMemory(useFocusMemory(focused));
  return null;
}

describe('push (MovNavegacion)', () => {
  it('follows the finger from where the detail was grabbed, between 0 and 1', () => {
    expect(dragProgress(1, 0, 390)).toBe(1);
    expect(dragProgress(1, 195, 390)).toBeCloseTo(0.5);
    expect(dragProgress(1, -40, 390)).toBe(1);
    expect(dragProgress(0.8, 500, 390)).toBe(0);
  });

  it('settles a released drag with the board projection: below 0.6 it goes back', () => {
    expect(navGestures.stayOpen).toBe(0.6);
    expect(navGestures.velocityProjection).toBe(0.25);
    // Dragged 39 % of the way, no speed: projected 0.61, it stays.
    expect(edgeRelease(0.61, 0)).toBe(1);
    // Dragged 41 %: it goes back.
    expect(edgeRelease(0.59, 0)).toBe(0);
    // A short drag flicked right at 1 pt/ms (1000 pt/s) loses 0.25 more: 0.8 → 0.55, it goes back.
    expect(edgeRelease(0.8, 1000)).toBe(0);
    // A flick back to the left keeps it.
    expect(edgeRelease(0.5, -1000)).toBe(1);
  });

  it('only grabs a detail that is at least half in', () => {
    expect(canGrab(0.5)).toBe(true);
    expect(canGrab(0.49)).toBe(false);
  });

  it('slides the detail in from beyond the edge and moves the screen underneath by 30 % and 8 % tinta', () => {
    expect(panelFrame(0, 0, 390, 391, false)).toEqual({ translateX: 391, opacity: 1 });
    expect(panelFrame(1, 0, 390, 391, false)).toEqual({ translateX: 0, opacity: 1 });
    expect(baseFrame(1, 390, false)).toEqual({ translateX: -navValues.pushParallax * 390, dim: navValues.pushDim });
    expect(baseFrame(0.5, 390, false).dim).toBeCloseTo(0.04);
  });

  it('with reduced motion only fades the detail and darkens the screen underneath, without moving', () => {
    expect(panelFrame(0.4, 0, 390, 391, true)).toEqual({ translateX: 0, opacity: 0.4 });
    expect(baseFrame(1, 390, true)).toEqual({ translateX: 0, dim: navValues.pushDim });
  });

  it('finds the level of a route in its stack', () => {
    expect(stackLevel({ routes: [{ key: 'tabs' }, { key: 'detail' }] }, 'detail')).toBe(1);
    expect(stackLevel(undefined, 'detail')).toBe(0);
  });

  // E2E wave: a piece opened from Tu turno said «‹ Calendario» and went back to Tu turno.
  it('names «‹» after the screen it goes back to', () => {
    const tabs = (focused: string) => ({ key: 'tabs', name: '(tabs)', state: { index: 1, routes: [{ name: 'index' }, { name: focused }] } });
    expect(backLabel({ routes: [tabs('tu-turno'), { key: 'detail', name: 'calendario/pieza/[id]' }] }, 'detail', 'Calendario')).toBe('Tu turno');
    expect(backLabel({ routes: [tabs('resultados'), { key: 'detail', name: 'personas/[id]' }] }, 'detail', 'Personas')).toBe('Resultados');
    expect(backLabel({ routes: [tabs('calendario'), { key: 'detail', name: 'calendario/pieza/[id]' }] }, 'detail', 'Calendario')).toBe('Calendario');
    expect(backLabel({ routes: [tabs('personas'), { key: 'p', name: 'personas/[id]' }, { key: 'detail', name: 'calendario/pieza/[id]' }] }, 'detail', 'Calendario')).toBe('Persona');
    // Opened straight from a notification: nothing underneath, «‹» goes to the fallback section.
    expect(backLabel({ routes: [{ key: 'detail', name: 'calendario/pieza/[id]' }] }, 'detail', 'Calendario')).toBe('Calendario');
    expect(backLabel(undefined, 'detail', 'Personas')).toBe('Personas');
  });

  it('finds the stack of a route in the root navigation state (where a just-pushed screen already is)', () => {
    const app = { index: 1, routes: [{ key: 'tabs', state: { index: 0, routes: [{ key: 'index-1' }] } }, { key: 'detail' }] };
    const root = { index: 0, routes: [{ key: 'root', name: '__root', state: { index: 0, routes: [{ key: 'app', state: app }] } }] };
    expect(stackOf(root, 'detail')).toBe(app);
    expect(stackLevel(stackOf(root, 'detail'), 'detail')).toBe(1);
    expect(stackLevel(stackOf(root, 'tabs'), 'tabs')).toBe(0);
    expect(stackOf(root, 'nope')).toBeUndefined();
    expect(stackOf(undefined, 'detail')).toBeUndefined();
  });

  it('uses the design springs', () => {
    expect(navSprings.push).toBe(FIRM);
    expect(navSprings.pill).toBe(FIRM);
    expect(navSprings.tabIcon).toEqual({ damping: 14, stiffness: 160, mass: 1 });
  });
});

describe('DetailScreen', () => {
  type Blocked = (options: { data: { action: { type: string } }; repeat: () => void }) => void;
  const blocked: { current: Blocked | null; guarded: boolean | null } = { current: null, guarded: null };
  const navigation = { getState: () => ({ index: 1, routes: [{ key: 'tabs' }, { key: 'detail' }] }) };

  beforeEach(() => {
    expoRouter.useNavigation = () => navigation;
    expoRouter.useRoute = () => ({ key: 'detail', name: 'personas/[id]' });
    expoRouter.usePreventRemove = (guarded: boolean, callback: Blocked) => {
      blocked.guarded = guarded;
      blocked.current = callback;
      return () => undefined;
    };
    fakeServer({});
  });

  async function renderDetail() {
    await renderApp(
      <DetailScreen back="Personas" fallback="/personas">
        <Text>La ficha</Text>
      </DetailScreen>,
    );
    expect(screen.getByText('La ficha')).toBeOnTheScreen();
  }

  it('waits for the push back before Android back (or «‹») removes it', async () => {
    await renderDetail();
    expect(blocked.guarded).toBe(true);
    const repeat = jest.fn();
    await act(async () => blocked.current?.({ data: { action: { type: 'GO_BACK' } }, repeat }));
    expect(repeat).not.toHaveBeenCalled();
    await waitFor(() => expect(repeat).toHaveBeenCalledTimes(1), { timeout: 3000 });
    await waitFor(() => expect(blocked.guarded).toBe(false));
  });

  it('lets a replace go at once (nothing underneath to reveal)', async () => {
    await renderDetail();
    const repeat = jest.fn();
    await act(async () => blocked.current?.({ data: { action: { type: 'REPLACE' } }, repeat }));
    expect(repeat).toHaveBeenCalledTimes(1);
  });

  it('«‹» goes back through the router', async () => {
    await renderDetail();
    await fireEvent.press(screen.getByRole('button', { name: 'Personas' }));
    expect(router.back).toHaveBeenCalled();
  });

  it('a drag from the left edge past 40 % goes back; a short one stays', async () => {
    const { width } = Dimensions.get('window');
    await renderDetail();
    // Let the push finish so the strip can grab it.
    await act(async () => new Promise((resolve) => setTimeout(resolve, 1000)));
    await act(async () => {
      fireGestureHandler(getByGestureTestId('detail-edge'), [
        { state: State.BEGAN, translationX: 0, velocityX: 0 },
        { state: State.ACTIVE, translationX: 0, velocityX: 0 },
        { state: State.ACTIVE, translationX: width * 0.1, velocityX: 0 },
        { state: State.END, translationX: width * 0.1, velocityX: 0 },
      ]);
    });
    await act(async () => new Promise((resolve) => setTimeout(resolve, 1000)));
    expect(router.back).not.toHaveBeenCalled();

    await act(async () => {
      fireGestureHandler(getByGestureTestId('detail-edge'), [
        { state: State.BEGAN, translationX: 0, velocityX: 0 },
        { state: State.ACTIVE, translationX: 0, velocityX: 0 },
        { state: State.ACTIVE, translationX: width * 0.5, velocityX: 0 },
        { state: State.END, translationX: width * 0.5, velocityX: 0 },
      ]);
    });
    await waitFor(() => expect(router.back).toHaveBeenCalled(), { timeout: 3000 });
  });
});

describe('tab content and the top-bar push (MovNavegacion)', () => {
  it('tells a tab change from a push into a top-bar screen and the way back', () => {
    expect(tabMove('index', 'resultados')).toBe('fade');
    expect(tabMove('index', 'tu-turno')).toBe('push');
    expect(tabMove('tu-turno', 'calendario')).toBe('push');
    expect(tabMove('ajustes', 'galeria')).toBe('pop');
    // An earlier top-bar screen is drawn under the one it replaces: it comes back with the pop, never pushed under it.
    expect(tabMove('notificaciones', 'tu-turno')).toBe('pop');
    expect(tabMove('ajustes', 'calendario')).toBe('pop');
    expect(tabMove('tu-turno', 'notificaciones')).toBe('push');
    expect(tabMove(null, 'index')).toBe('fade');
  });

  it('remembers the last two focused tabs and gives each scene its part', () => {
    const order = ['index', 'resultados', 'personas', 'galeria', 'tu-turno'];
    const start: FocusMemory = { previous: null, current: null };
    const first = nextFocus(start, 'index');
    const memory = nextFocus(first, 'tu-turno');
    expect(nextFocus(memory, 'tu-turno')).toBe(memory);
    expect(nextFocus(memory, null)).toBe(memory);
    expect(memory).toEqual({ previous: 'index', current: 'tu-turno' });
    expect(start).toEqual({ previous: null, current: null });
    expect(sceneRole(memory, 'tu-turno', order)).toEqual({ role: 'enter', side: 1 });
    expect(sceneRole(memory, 'index', order)).toEqual({ role: 'leave', side: -1 });
    expect(sceneRole(memory, 'galeria', order).role).toBe('idle');
  });

  it('knows the new focus in the same render that changes it', async () => {
    const seen: FocusMemory[] = [];
    const onMemory = (memory: FocusMemory) => seen.push(memory);
    const view = await renderApp(<FocusProbe focused="index" onMemory={onMemory} />);
    expect(seen.at(-1)).toEqual({ previous: null, current: 'index' });
    const before = seen.length;
    await view.rerender(<FocusProbe focused="tu-turno" onMemory={onMemory} />);
    // Every render with the new focus already has the change in course: none is a render behind.
    const after = seen.slice(before);
    expect(after.length).toBeGreaterThan(0);
    for (const memory of after) expect(memory).toEqual({ previous: 'index', current: 'tu-turno' });
    const settled = seen.at(-1);
    await view.rerender(<FocusProbe focused="tu-turno" onMemory={onMemory} />);
    expect(seen.at(-1)).toBe(settled);
  });

  it('reads the focused tab from the root navigation state, not from a stale getState()', () => {
    const root = {
      index: 0,
      routes: [
        {
          key: 'app-1',
          name: '(app)',
          state: {
            index: 1,
            routes: [
              { key: 'tabs-1', name: '(tabs)', state: { index: 4, routes: ['index', 'resultados', 'personas', 'galeria', 'tu-turno'].map((name) => ({ key: `${name}-1`, name })) } },
              { key: 'persona-1', name: 'personas/[id]' },
            ],
          },
        },
      ],
    };
    expect(focusedChild(root, 'tabs-1')).toBe('tu-turno');
    expect(focusedChild(root, 'app-1')).toBe('personas/[id]');
    expect(focusedChild(root, 'persona-1')).toBeNull();
    expect(focusedChild(root, 'nope')).toBeNull();
    expect(focusedChild(undefined, 'tabs-1')).toBeNull();
  });

  it('fades the new content in (TOK.fast, EASE_OUT) and the old one out in 60 % of it (EASE_IN)', () => {
    const entering = tabSceneOptions('fade', 'enter', 1, 390, false);
    const leaving = tabSceneOptions('fade', 'leave', -1, 390, false);
    expect(entering.transitionSpec).toEqual(expect.objectContaining({ animation: 'timing', config: expect.objectContaining({ duration: durations.fast }) }));
    expect(leaving.transitionSpec).toEqual(expect.objectContaining({ animation: 'timing', config: expect.objectContaining({ duration: navTimings.tabOut.duration }) }));
    expect(navTimings.tabOut.duration).toBeCloseTo(durations.fast * 0.6);
    expect(navValues.tabRise).toBe(8);
  });

  it('pushes the top-bar screens with the FIRM spring', () => {
    for (const role of ['enter', 'leave'] as const) {
      expect(tabSceneOptions('push', role, 1, 390, false).transitionSpec).toEqual({ animation: 'spring', config: { ...FIRM } });
      expect(tabSceneOptions('pop', role, 1, 390, false).transitionSpec).toEqual({ animation: 'spring', config: { ...FIRM } });
    }
  });

  // Back from Calendario to Notificaciones left a blank screen on the phone (QA run 42451843664, 02-navegacion): a scene
  // that was idle (faded out by its opacity) came back with the push, whose style had no opacity, and kept the stale 0
  // the native driver had set. Every animated scene now sets the same props, so a role change rewrites all of them.
  it('gives every animated scene the same props (opacity, translateX, translateY), all at rest when shown', () => {
    // Rounded, and -0 counted as 0.
    const value = (node: unknown) => Math.round((typeof node === 'number' ? node : (node as { __getValue: () => number }).__getValue()) * 1000) / 1000 + 0;
    for (const move of ['fade', 'push', 'pop'] as const) {
      for (const role of ['enter', 'leave', 'idle'] as const) {
        for (const side of [1, -1] as const) {
          const options = tabSceneOptions(move, role, side, 390, false);
          for (const at of [0, side]) {
            const progress = new Animated.Value(at);
            const { sceneStyle } = options.sceneStyleInterpolator!({ current: { progress } } as never) as unknown as {
              sceneStyle: { opacity: unknown; transform: Record<string, unknown>[] };
            };
            const label = `${move} ${role} ${side} at ${at}`;
            expect(sceneStyle.transform.map((step) => Object.keys(step)[0])).toEqual(['translateX', 'translateY']);
            expect(sceneStyle.opacity).toBeDefined();
            if (at === 0) {
              // Shown: opaque and in place, whatever its part in the change.
              expect([label, value(sceneStyle.opacity)]).toEqual([label, 1]);
              expect([label, value(sceneStyle.transform[0]!.translateX), value(sceneStyle.transform[1]!.translateY)]).toEqual([label, 0, 0]);
            }
          }
        }
      }
    }
  });

  it('does not animate with reduced motion', () => {
    expect(tabSceneOptions('push', 'enter', 1, 390, true)).toEqual({ animation: 'none' });
    expect(tabSceneOptions('fade', 'leave', 1, 390, true)).toEqual({ animation: 'none' });
  });
});

describe('BottomBar (MovNavegacion)', () => {
  const routes = ['index', 'resultados', 'personas', 'galeria', 'tu-turno'].map((name) => ({ key: `${name}-k`, name }));

  async function renderBar(index: number) {
    fakeServer({ 'GET /api/v1/capturas': { body: { count: 0, next: null, previous: null, results: [] } }, 'GET /api/v1/preguntas': { body: [] } });
    const navigateToTab = jest.fn();
    const props = { state: { index, routes }, descriptors: {}, emitter: {}, navigateToTab, insets: { top: 0, right: 0, bottom: 0, left: 0 } };
    const view = await renderApp(<BottomBar {...(props as unknown as BottomTabBarProps)} />, { recorder: true });
    await act(async () => {});
    return { navigateToTab, ...view };
  }

  it('changing tab ticks once (selection) and navigates; the active tab does not tick', async () => {
    const { navigateToTab } = await renderBar(0);
    await fireEvent.press(screen.getByTestId('tab-personas'));
    expect(Haptics.selectionAsync).toHaveBeenCalledTimes(1);
    expect(navigateToTab).toHaveBeenCalledWith('personas-k');
    await fireEvent.press(screen.getByTestId('tab-index'));
    expect(Haptics.selectionAsync).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('tab', { name: 'Oficina' })).toBeSelected();
  });

  it('puts the pill under the centre of the active tab', async () => {
    expect(pillLeft(39)).toBe(11);
    expect(pillLeft(351)).toBe(323);
    await renderBar(4);
    expect(screen.getByTestId('tab-pill')).toBeOnTheScreen();
    for (const label of ['Oficina', 'Resultados', 'Personas', 'Galería']) expect(screen.getByRole('tab', { name: label })).not.toBeSelected();
  });
});
