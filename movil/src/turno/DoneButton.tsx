// MovTuTurno: the button that resolved a card turns into a check. Same size as the button it replaces
// (48 px, radius 12), filled in 0ff1ce-hondo, its label gives way to a check that grows from checkFrom
// (check, enter). Screen readers still hear the action, now disabled.
import { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';
import { Icon } from '@/components/icons';
import { turnoMotion, turnoTiming } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';

export function DoneButton({ label, block, testID }: { label: string; block?: boolean; testID?: string }) {
  const scale = useSharedValue<number>(turnoMotion.checkFrom);
  useEffect(() => {
    scale.set(withTiming(1, turnoTiming('check')));
  }, [scale]);
  const grow = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  return (
    <View
      testID={testID ?? 'turno-done'}
      accessible
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: true }}
      style={[styles.done, block ? styles.block : null]}
    >
      <Animated.View style={grow}>
        <Icon name="check" size={20} color={colors.paper} />
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  done: {
    minHeight: 48,
    paddingHorizontal: space[4],
    borderWidth: 1,
    borderRadius: radius.md,
    borderColor: colors.brandDeep,
    backgroundColor: colors.brandDeep,
    alignItems: 'center',
    justifyContent: 'center',
  },
  block: { alignSelf: 'stretch' },
});
