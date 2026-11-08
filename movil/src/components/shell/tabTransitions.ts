// How the tab content changes (MovNavegacion `tab`): the old screen fades out in 60 % of TOK.fast
// (EASE_IN) while the new one fades in and rises 8 points (TOK.fast, EASE_OUT). The four screens of
// the top bar (Tu turno, Notificaciones, Calendario, Ajustes) open with the push instead: they slide
// in from the right with the `push` spring while the screen underneath moves left by 30 %.
//
// These are options of the JS tabs navigator, whose scenes animate with React Native's Animated on
// the native driver (UI thread). Each scene animates with its own spec, so the screen that leaves
// and the one that enters get different ones. With reduced motion nothing animates.
import { Animated, Easing } from 'react-native';
import type { TabsScreenOptions } from 'expo-router/js-tabs';
import { BEZIER, navSprings, navTimings, navValues } from '@/theme/motion';

/** Routes of the top bar: they open with the push. */
export const TOP_BAR_ROUTES: readonly string[] = ['tu-turno', 'notificaciones', 'calendario', 'ajustes'];

export type TabMove = 'fade' | 'push' | 'pop';

/** The kind of change from the screen that was shown to the one shown now. */
export function tabMove(previous: string | null, current: string): TabMove {
  if (TOP_BAR_ROUTES.includes(current)) return 'push';
  if (previous && TOP_BAR_ROUTES.includes(previous)) return 'pop';
  return 'fade';
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

function hidden(progress: Progress): SceneStyle {
  return { sceneStyle: { opacity: progress.interpolate({ inputRange: [-1, 0, 1], outputRange: [0, 1, 0] }) } };
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
        return {
          sceneStyle: {
            opacity: a.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }),
            transform: [{ translateY: a.interpolate({ inputRange: [0, 1], outputRange: [0, navValues.tabRise] }) }],
          },
        };
      },
    };
  }
  if (move === 'fade') {
    return {
      transitionSpec: tabOutSpec,
      sceneStyleInterpolator: ({ current }) => ({ sceneStyle: { opacity: away(current.progress, side).interpolate({ inputRange: [0, 1], outputRange: [1, 0] }) } }),
    };
  }
  // The push and its way back: the top-bar screen moves by the whole width, the other by 30 %.
  const slides = (move === 'push') === (role === 'enter');
  return {
    transitionSpec: pushSpec,
    sceneStyleInterpolator: ({ current }) => {
      const a = away(current.progress, side);
      if (slides) return { sceneStyle: { transform: [{ translateX: a.interpolate({ inputRange: [0, 1], outputRange: [0, width] }) }] } };
      const shift = { translateX: a.interpolate({ inputRange: [0, 1], outputRange: [0, -navValues.pushParallax * width] }) };
      // The tabs draw the focused scene on top, so a screen coming back from under the top-bar screen
      // cannot be revealed by it: it fades in as it moves back.
      if (role === 'enter') return { sceneStyle: { opacity: a.interpolate({ inputRange: [0, 1], outputRange: [1, 0], extrapolate: 'clamp' }), transform: [shift] } };
      return { sceneStyle: { transform: [shift] } };
    },
  };
}

/** Remembers the last two focused tabs across renders of the navigator (the options need both). */
export interface FocusMemory {
  previous: string | null;
  current: string | null;
}

/** Updates `memory` when the focus changed; the same state always gives the same answer. */
export function noteFocus(memory: FocusMemory, focused: string): FocusMemory {
  if (memory.current !== focused) {
    memory.previous = memory.current;
    memory.current = focused;
  }
  return memory;
}

/** The role and side of `route` in the change from `memory.previous` to `memory.current`, given the tab order. */
export function sceneRole(memory: FocusMemory, route: string, order: readonly string[]): { role: TabRole; side: 1 | -1 } {
  const other = route === memory.current ? memory.previous : memory.current;
  const role: TabRole = route === memory.current ? 'enter' : route === memory.previous ? 'leave' : 'idle';
  const side = other !== null && order.indexOf(route) < order.indexOf(other) ? -1 : 1;
  return { role, side };
}
