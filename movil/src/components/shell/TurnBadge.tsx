// The Bandeja de entrada counter (formerly in the top bar's «Tu turno» access, now on the bottom bar's Bandeja tab)
// and `useChange`, shared with the top bar's bell.
//
// Motion (MovTuTurno `badge`): the counter rolls to its new number and pops (SOFT) when it changes.
import { useEffect, useRef } from 'react';
import { StyleSheet, type StyleProp, type ViewStyle } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from 'react-native-reanimated';
import { turnoMotion, turnoSpring } from '@/theme/motion';
import { colors, radius } from '@/theme/tokens';
import { RollingNumber } from '@/turno/RollingNumber';

/**
 * Calls `onChange` when a value of GET /tu-turno changes. Its first answer is not a change: `onFirst`
 * gets it instead (and the value a bar finds when it mounts).
 */
export function useChange<V>(value: V, loaded: boolean, onChange: (before: V, now: V) => void, onFirst?: (now: V) => void) {
  const previous = useRef<{ value: V } | null>(null);
  const handlers = useRef({ onChange, onFirst });
  useEffect(() => {
    handlers.current = { onChange, onFirst };
  });
  useEffect(() => {
    if (!loaded) return;
    const before = previous.current;
    previous.current = { value };
    if (!before) handlers.current.onFirst?.(value);
    else if (before.value !== value) handlers.current.onChange(before.value, value);
  }, [value, loaded]);
}

/** The Bandeja counter (MovTuTurno `badge`): a new number rolls in and the badge pops back from badgePop. */
export function Counter({ count, critical, loaded, style }: { count: number; critical: boolean; loaded: boolean; style?: StyleProp<ViewStyle> }) {
  const scale = useSharedValue(1);
  useChange(count, loaded, () => {
    scale.set(turnoMotion.badgePop);
    scale.set(withSpring(1, turnoSpring('badge')));
  });
  const pop = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  if (count <= 0) return null;
  return (
    <Animated.View style={[styles.counter, critical ? styles.counterCritical : null, style, pop]} testID="turn-counter">
      <RollingNumber value={count > 99 ? '99+' : String(count)} variant="etiqueta" color={critical ? colors.onAlert : colors.paper} style={styles.counterText} />
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  counter: { position: 'absolute', minWidth: 18, height: 18, paddingHorizontal: 5, borderRadius: radius.pill, backgroundColor: colors.ink, alignItems: 'center', justifyContent: 'center' },
  counterCritical: { backgroundColor: colors.alert },
  counterText: { letterSpacing: 0, lineHeight: 18 },
});
