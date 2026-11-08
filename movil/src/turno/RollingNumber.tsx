// MovTuTurno's `roll`: when a counter changes, the old number rises and fades out, then the new one comes in from
// below. The old one leaves with a layout animation on its keyed view; the new one rises with a shared value, not with
// Reanimated `entering`: a number that changed right after a sheet's Modal closed stayed at opacity 0 (the group label
// read «URGENTE ·» with no number). Nothing rolls when the counter first shows; with reduced motion the number just changes.
import { useEffect, useState, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, { LayoutAnimationConfig, useAnimatedStyle, useSharedValue, withDelay, withTiming } from 'react-native-reanimated';
import { T, type TProps } from '@/components/ui/Text';
import { timingWith, turnoLayout, turnoMotion, turnoTimings, useMotion } from '@/theme/motion';

/** The new number: from below and transparent, once the old one is gone (it never rolls on the first render). */
function RollIn({ roll, children }: { roll: boolean; children: ReactNode }) {
  const shown = useSharedValue(roll ? 0 : 1);
  useEffect(() => {
    if (!roll) return;
    shown.set(withDelay(turnoTimings.rollOut.duration, withTiming(1, timingWith(turnoTimings.rollIn.duration, turnoTimings.rollIn.easing))));
  }, [roll, shown]);
  const style = useAnimatedStyle(() => ({ opacity: shown.value, transform: [{ translateY: (1 - shown.value) * turnoMotion.rollDistance }] }));
  return <Animated.View style={style}>{children}</Animated.View>;
}

export function RollingNumber({ value, ...text }: { value: string } & Omit<TProps, 'children'>) {
  const { reduced } = useMotion();
  // Rolls from the first change on (derived state: the value it showed first never rolls in).
  const [shownFirst, setShownFirst] = useState(value);
  const [changed, setChanged] = useState(false);
  if (value !== shownFirst) {
    setShownFirst(value);
    setChanged(true);
  }
  if (reduced) {
    return (
      <View style={styles.box}>
        <T {...text}>{value}</T>
      </View>
    );
  }
  return (
    <LayoutAnimationConfig skipExiting>
      <View style={styles.box}>
        <Animated.View key={value} exiting={turnoLayout.rollOut()}>
          <RollIn roll={changed}>
            <T {...text}>{value}</T>
          </RollIn>
        </Animated.View>
      </View>
    </LayoutAnimationConfig>
  );
}

const styles = StyleSheet.create({ box: { flexDirection: 'row' } });
