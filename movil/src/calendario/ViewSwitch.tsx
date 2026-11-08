// Semana ↔ Mes (MovCalendario, «la semana se va, el mes entra fila por fila»): the view that leaves stays
// drawn under the new one, without its selection, and fades out in 120 ms; the new view enters by itself
// (Grids.tsx) while the selection travels to its cell (Selection.tsx) and the calendar's height eases to
// the new view's (Pager.tsx). Lista is not part of the choreography: it changes the whole screen.
import type { Vista } from '@compartido/logic/events';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { StyleSheet } from 'react-native';
import Animated, { runOnJS, useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';
import { calendarTiming } from '@/theme/motion';

export type GridVista = Exclude<Vista, 'lista'>;

function isGrid(vista: Vista): vista is GridVista {
  return vista !== 'lista';
}

export interface ViewSwitchState {
  /** The view that is leaving (null: none, or no choreography). */
  from: GridVista | null;
  /** The leaving view has gone. */
  done: () => void;
}

/** Follows the view: going between Semana and Mes starts a switch, unless motion is reduced. */
export function useViewSwitch(vista: Vista, reduced: boolean): ViewSwitchState {
  const [memory, setMemory] = useState<{ vista: Vista; from: GridVista | null }>({ vista, from: null });
  let current = memory;
  if (memory.vista !== vista) {
    current = { vista, from: !reduced && isGrid(memory.vista) && isGrid(vista) ? memory.vista : null };
    setMemory(current);
  }
  const done = useCallback(() => setMemory((value) => (value.from ? { ...value, from: null } : value)), []);
  return { from: current.from, done };
}

/** The leaving view, laid under the new one, fading out. */
export function LeavingView({ onDone, children }: { onDone: () => void; children: ReactNode }) {
  const opacity = useSharedValue(1);
  useEffect(() => {
    opacity.set(
      withTiming(0, calendarTiming('viewOut'), (finished) => {
        if (finished) runOnJS(onDone)();
      }),
    );
  }, [opacity, onDone]);
  const style = useAnimatedStyle(() => ({ opacity: opacity.value }));
  return (
    <Animated.View testID="vista-saliente" style={[styles.leaving, style]} pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      {children}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  leaving: { position: 'absolute', top: 0, left: 0, right: 0 },
});
