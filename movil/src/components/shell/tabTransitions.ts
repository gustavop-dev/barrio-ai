// How the tab content changes (MovNavegacion `tab`): the old screen fades out in 60 % of TOK.fast
// (EASE_IN) while the new one fades in and rises 8 points (TOK.fast, EASE_OUT). The four screens of
// the top bar (Notificaciones, Calendario, Ajustes) open with the push instead: they slide
// in from the right with the `push` spring while the screen underneath moves left by 30 %.
//
// The scenes are drawn in the navigator's order, whatever the focus: react-native-screens stacks the screens of its
// container in that order and drops their zIndex (Screen.tsx), so the focused tab is not brought to the front. A push
// works only when the new screen comes later in the order than the one it covers. Between two top-bar screens, going to
// an earlier one is therefore the way back: the old screen, drawn on top, slides off to the right and uncovers the new one.
// As a push it slid left over the new one and stayed there, covering it, until the spring settled (Gustavo, 11/11).
//
// These are options of the JS tabs navigator, whose scenes animate with React Native's Animated on
// the native driver (UI thread). Each scene animates with its own spec, so the screen that leaves
// and the one that enters get different ones. With reduced motion nothing animates.
//
// A scene's part in the change (entering, leaving, not involved) depends on the tab focused before
// and the one focused now, and js-tabs reads each scene's options in the very render that changes the
// focus. So the focus must come from that render's state: the tabs layout reads it from the root
// navigation state (`focusedChild`), never from `navigation.getState()`, which during render still
// returns the state of the previous render (it is a callback refreshed after the commit).
import { useState } from 'react';
import { Animated, Easing } from 'react-native';
import type { TabsScreenOptions } from 'expo-router/js-tabs';
import { BEZIER, navSprings, navTimings, navValues } from '@/theme/motion';

/** Routes of the top bar: they open with the push. */
export const TOP_BAR_ROUTES: readonly string[] = ['notificaciones', 'calendario', 'ajustes'];

/** The tabs in the navigator's order: the order they are drawn in, and the side a scene slides from. */
export const TAB_ORDER = ['index', 'resultados', 'personas', 'tu-turno', 'notificaciones', 'calendario', 'ajustes'] as const;

export type TabMove = 'fade' | 'push' | 'pop';

/**
 * The kind of change from the screen that was shown to the one shown now. A top-bar screen earlier in the order than
 * the top-bar screen it replaces is drawn under it, so it comes back with the pop (see the note at the top).
 */
export function tabMove(previous: string | null, current: string, order: readonly string[] = TAB_ORDER): TabMove {
  const fromTopBar = previous !== null && TOP_BAR_ROUTES.includes(previous);
  if (TOP_BAR_ROUTES.includes(current)) return fromTopBar && order.indexOf(current) < order.indexOf(previous) ? 'pop' : 'push';
  return fromTopBar ? 'pop' : 'fade';
}

/** A tab's part in the change: the screen arriving, the one leaving, or one not involved. */
export type TabRole = 'enter' | 'leave' | 'idle';

type SceneStyle = ReturnType<NonNullable<TabsScreenOptions['sceneStyleInterpolator']>>;
type Progress = Animated.Value;

const enter = Easing.bezier(...BEZIER.enter);
const exit = Easing.bezier(...BEZIER.exit);

const pushSpec = { animation: 'spring', config: { ...navSprings.push } } as const;
const tabInSpec = { animation: 'timing', config: { duration: navTimings.tabIn.duration, easing: enter } } as const;
const tabOutSpec = { animation: 'timing', config: { duration: navTimings.tabOut.duration, easing: exit } } as const;

/**
 * How far a scene is from being shown, 0 shown to 1 away: the navigator moves a scene's progress
 * between 0 and ±1 depending on which side of the focused tab it is; `side` is that sign.
 */
function away(progress: Progress, side: 1 | -1) {
  return progress.interpolate({ inputRange: [-1, 1], outputRange: [-side, side] });
}

type Driven = Animated.AnimatedInterpolation<number>;

/** A value that stays put, as an interpolation of the same progress (so it is still a driven prop). */
function fixed(progress: Progress, value: number): Driven {
  return progress.interpolate({ inputRange: [-1, 1], outputRange: [value, value] });
}

/**
 * Every animated scene sets the same three props, opacity, translateX and translateY, driven by its progress, whatever
 * its part in the change. A scene's style changes shape as its part changes (idle, entering, leaving), and the native
 * driver keeps the last value it set for a prop that a new style no longer drives: an idle scene faded to opacity 0 that
 * came back with the push (a style without opacity) stayed invisible. That was the blank screen of Android back from
 * Calendario to Notificaciones (QA run 42451843664, 02-navegacion).
 */
function scene(progress: Progress, { opacity, x, y }: { opacity?: Driven; x?: Driven; y?: Driven }): SceneStyle {
  return {
    sceneStyle: {
      opacity: opacity ?? fixed(progress, 1),
      transform: [{ translateX: x ?? fixed(progress, 0) }, { translateY: y ?? fixed(progress, 0) }],
    },
  };
}

function hidden(progress: Progress): SceneStyle {
  return scene(progress, { opacity: progress.interpolate({ inputRange: [-1, 0, 1], outputRange: [0, 1, 0] }) });
}

/**
 * The options of one tab for the change in course. `side` is +1 when the tab sits after the other
 * screen of the change in the navigator, −1 before (it decides the sign of its progress).
 */
export function tabSceneOptions(move: TabMove, role: TabRole, side: 1 | -1, width: number, reduced: boolean): TabsScreenOptions {
  if (reduced) return { animation: 'none' };
  if (role === 'idle') return { transitionSpec: tabInSpec, sceneStyleInterpolator: ({ current }) => hidden(current.progress) };
  if (move === 'fade' && role === 'enter') {
    return {
      transitionSpec: tabInSpec,
      sceneStyleInterpolator: ({ current }) => {
        const a = away(current.progress, side);
        return scene(current.progress, {
          opacity: a.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }),
          y: a.interpolate({ inputRange: [0, 1], outputRange: [0, navValues.tabRise] }),
        });
      },
    };
  }
  if (move === 'fade') {
    return {
      transitionSpec: tabOutSpec,
      sceneStyleInterpolator: ({ current }) => scene(current.progress, { opacity: away(current.progress, side).interpolate({ inputRange: [0, 1], outputRange: [1, 0] }) }),
    };
  }
  // The push and its way back: the screen on top moves by the whole width, the one under it by 30 %. The push brings a
  // screen later in the order (drawn on top) and the pop uncovers an earlier one, so the screen that slides is always
  // the one drawn on top and the one under it is uncovered as it moves back.
  const slides = (move === 'push') === (role === 'enter');
  return {
    transitionSpec: pushSpec,
    sceneStyleInterpolator: ({ current }) => {
      const a = away(current.progress, side);
      if (slides) return scene(current.progress, { x: a.interpolate({ inputRange: [0, 1], outputRange: [0, width] }) });
      return scene(current.progress, { x: a.interpolate({ inputRange: [0, 1], outputRange: [0, -navValues.pushParallax * width] }) });
    },
  };
}

/** The last two focused tabs (the options need both). */
export interface FocusMemory {
  previous: string | null;
  current: string | null;
}

/** The memory once `focused` is the focused tab: the same object when nothing changed (null: not known). */
export function nextFocus(memory: FocusMemory, focused: string | null): FocusMemory {
  if (focused === null || memory.current === focused) return memory;
  return { previous: memory.current, current: focused };
}

/**
 * Keeps the last two focused tabs across renders. It updates during render (React's «storing
 * information from previous renders»), so the options computed in the same render already know the
 * change in course.
 */
export function useFocusMemory(focused: string | null): FocusMemory {
  const [memory, setMemory] = useState<FocusMemory>(() => ({ previous: null, current: focused }));
  const next = nextFocus(memory, focused);
  if (next !== memory) setMemory(next);
  return next;
}

interface NavNode {
  index?: number;
  routes?: readonly { key?: string; name?: string; state?: NavNode }[];
}

/**
 * The name of the route focused inside the navigator of the route `routeKey`, searched from the root
 * navigation state (null when that route or its navigator state is not there yet).
 */
export function focusedChild(root: unknown, routeKey: string): string | null {
  for (const route of (root as NavNode | null | undefined)?.routes ?? []) {
    if (route.key === routeKey) {
      const child = route.state;
      if (!child) return null;
      return child.routes?.[child.index ?? 0]?.name ?? null;
    }
    const found = focusedChild(route.state, routeKey);
    if (found !== null) return found;
  }
  return null;
}

/** The role and side of `route` in the change from `memory.previous` to `memory.current`, given the tab order. */
export function sceneRole(memory: FocusMemory, route: string, order: readonly string[]): { role: TabRole; side: 1 | -1 } {
  const other = route === memory.current ? memory.previous : memory.current;
  const role: TabRole = route === memory.current ? 'enter' : route === memory.previous ? 'leave' : 'idle';
  const side = other !== null && order.indexOf(route) < order.indexOf(other) ? -1 : 1;
  return { role, side };
}
