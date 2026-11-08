// MovTuTurno's `roll`: when a counter changes, the old number rises and fades out, then the new one
// comes in from below. Layout animations on a keyed view, so the new value is in the tree at once and
// the whole roll runs on the UI thread. Nothing rolls when the counter first shows or goes away.
import { StyleSheet, View } from 'react-native';
import Animated, { LayoutAnimationConfig } from 'react-native-reanimated';
import { T, type TProps } from '@/components/ui/Text';
import { turnoLayout, useMotion } from '@/theme/motion';

export function RollingNumber({ value, ...text }: { value: string } & Omit<TProps, 'children'>) {
  const { reduced } = useMotion();
  // Reduced motion: the number just changes (a keyed view entering with the system animations off was left blank).
  if (reduced) {
    return (
      <View style={styles.box}>
        <T {...text}>{value}</T>
      </View>
    );
  }
  return (
    <LayoutAnimationConfig skipEntering skipExiting>
      <View style={styles.box}>
        <Animated.View key={value} entering={turnoLayout.rollIn()} exiting={turnoLayout.rollOut()}>
          <T {...text}>{value}</T>
        </Animated.View>
      </View>
    </LayoutAnimationConfig>
  );
}

const styles = StyleSheet.create({ box: { flexDirection: 'row' } });
