// The day panel changing day (MovCalendario, «el panel entra desde el lado hacia el que avanzas»): the old
// panel fades and slides 12 px away while the new one comes in from the side the date moved to, rising
// 8 px, 60 ms later. The old panel stays laid over the new one until it has left, hidden from screen
// readers and touches. With reduced motion the panel simply changes.
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, { runOnJS, useAnimatedStyle, useSharedValue, withDelay, withTiming } from 'react-native-reanimated';
import { calendarChoreography, calendarTiming } from '@/theme/motion';

/** 1: the date moved forward (the new panel comes from the right); -1: backwards. */
export type Direction = 1 | -1;

export interface DaySwapState {
  /** The panel that is leaving, if any, and which way the date moved. */
  leaving: { date: string; dir: Direction } | null;
  /** Which way the date last moved (0: it has not moved since the panel appeared). */
  dir: Direction | 0;
  /** The leaving panel has gone. */
  done: (date: string) => void;
}

interface SwapMemory {
  shown: string | null;
  leaving: DaySwapState['leaving'];
  dir: Direction | 0;
}

/** Which way a date moved: ISO days compare as text. */
export function directionOf(from: string, to: string): Direction {
  return to > from ? 1 : -1;
}

/**
 * Follows the panel's date. A change from one day to another starts a swap; appearing (null → day) or
 * going away (day → null) does not: coming back from Lista, or leaving for it, changes the whole screen.
 */
export function useDaySwap(date: string | null, reduced: boolean): DaySwapState {
  const [memory, setMemory] = useState<SwapMemory>({ shown: date, leaving: null, dir: 0 });
  let current = memory;
  if (memory.shown !== date) {
    const moved = memory.shown !== null && date !== null && !reduced;
    const dir = moved ? directionOf(memory.shown!, date!) : 0;
    current = { shown: date, leaving: moved && dir ? { date: memory.shown!, dir } : null, dir };
    setMemory(current);
  }
  const done = useCallback((day: string) => setMemory((value) => (value.leaving?.date === day ? { ...value, leaving: null } : value)), []);
  return { leaving: current.leaving, dir: current.dir, done };
}

interface SlotProps {
  date: string;
  /** Entering from this side when it mounts (0: already there). */
  enter: Direction | 0;
  /** Leaving: away from this side. */
  leave?: Direction;
  onLeft?: (date: string) => void;
  children: ReactNode;
}

function PanelSlot({ date, enter, leave, onLeft, children }: SlotProps) {
  const { panelShift, panelRise, panelInDelayMs } = calendarChoreography;
  const opacity = useSharedValue(enter ? 0 : 1);
  const x = useSharedValue(enter ? panelShift * enter : 0);
  const y = useSharedValue(enter ? panelRise : 0);

  useEffect(() => {
    if (!enter) return;
    const config = calendarTiming('panelIn');
    opacity.set(withDelay(panelInDelayMs, withTiming(1, config), config.reduceMotion));
    x.set(withDelay(panelInDelayMs, withTiming(0, config), config.reduceMotion));
    y.set(withDelay(panelInDelayMs, withTiming(0, config), config.reduceMotion));
  }, [enter, opacity, x, y, panelInDelayMs]);

  useEffect(() => {
    if (!leave) return;
    const config = calendarTiming('panelOut');
    opacity.set(
      withTiming(0, config, (finished) => {
        if (finished && onLeft) runOnJS(onLeft)(date);
      }),
    );
    x.set(withTiming(-panelShift * leave, config));
  }, [leave, onLeft, date, opacity, x, panelShift]);

  const style = useAnimatedStyle(() => ({ opacity: opacity.value, transform: [{ translateX: x.value }, { translateY: y.value }] }));
  return (
    <Animated.View
      testID={leave ? 'panel-saliente' : 'panel-entrante'}
      style={[leave ? styles.leaving : null, style]}
      pointerEvents={leave ? 'none' : 'auto'}
      accessibilityElementsHidden={Boolean(leave)}
      importantForAccessibility={leave ? 'no-hide-descendants' : 'auto'}
    >
      {children}
    </Animated.View>
  );
}

/** The panel of `date`, with the panel that is leaving laid over it. `render` draws a day's panel. */
export function DaySwap({ date, swap, render }: { date: string; swap: DaySwapState; render: (date: string, leaving: boolean) => ReactNode }) {
  const slots = [
    ...(swap.leaving && swap.leaving.date !== date ? [{ date: swap.leaving.date, leave: swap.leaving.dir }] : []),
    { date, leave: undefined },
  ];
  // One keyed list: the panel that starts leaving keeps its instance (and its state) while it leaves.
  return (
    <View>
      {slots.map((slot) => (
        <PanelSlot key={slot.date} date={slot.date} enter={slot.leave ? 0 : swap.dir} leave={slot.leave} onLeft={swap.done}>
          {render(slot.date, Boolean(slot.leave))}
        </PanelSlot>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  leaving: { position: 'absolute', top: 0, left: 0, right: 0 },
});
