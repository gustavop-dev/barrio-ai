// A Tu turno card in the list, as it leaves (MovTuTurno). «Más tarde» with its button slides it right
// and down while it fades (laterSlide); then, however it was resolved, its height closes and it fades
// (the `collapse` exiting animation) while the list's item layout animation closes the gap. A card on
// its way out clips its content, so the collapse cuts it like the board does.
import { useEffect, type ReactNode } from 'react';
import { StyleSheet } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';
import { layout, turnoLayout, turnoMotion, turnoTiming } from '@/theme/motion';
import type { CardExit } from './exits';

export function ExitRow({ exit, children }: { exit: CardExit | undefined; children: ReactNode }) {
  const slid = useSharedValue(0);
  const sliding = exit?.lead === 'slide' && exit.phase !== 'acting';

  useEffect(() => {
    if (sliding) slid.set(withTiming(1, turnoTiming('laterSlide')));
  }, [sliding, slid]);

  const slide = useAnimatedStyle(() => ({
    opacity: 1 - slid.value,
    transform: [{ translateX: turnoMotion.laterShift.x * slid.value }, { translateY: turnoMotion.laterShift.y * slid.value }],
  }));

  return (
    <Animated.View
      entering={layout.listEnter()}
      exiting={exit?.lead === 'slide' ? turnoLayout.collapseSpace() : turnoLayout.collapse()}
      style={[exit ? styles.clip : null, slide]}
    >
      {children}
    </Animated.View>
  );
}

const styles = StyleSheet.create({ clip: { overflow: 'hidden' } });
