import { useEffect, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';
import { Icon } from '@/components/icons';
import { durations, haptic, microMotion, timingWith } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import { T } from './Text';

/** The check's room: the 16 px icon and the space before the label. */
const CHECK_ICON = 16;
const CHECK_ROOM = CHECK_ICON + 6;

/**
 * ui.css .chip-filter.solid: a toggle chip, tinta when pressed. MovMicro: chosen, it fills with ink at
 * once and its check slides in from the left (fast, EASE_OUT; EASE_IN when it goes), with a selection haptic.
 */
export function FilterChip({ pressed, onPress, children, testID }: { pressed: boolean; onPress: () => void; children: ReactNode; testID?: string }) {
  const shown = useSharedValue(pressed ? 1 : 0);
  useEffect(() => {
    shown.set(withTiming(pressed ? 1 : 0, timingWith(durations.fast, pressed ? 'enter' : 'exit')));
  }, [pressed, shown]);
  const check = useAnimatedStyle(() => ({
    width: CHECK_ROOM * shown.value,
    opacity: shown.value,
    transform: [{ translateX: -microMotion.chipCheckShift * (1 - shown.value) }],
  }));
  const tone = pressed ? colors.paper : colors.ink;
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityState={{ selected: pressed }}
      onPress={() => {
        haptic('chipToggle');
        onPress();
      }}
      style={[styles.chip, pressed ? styles.on : null]}
    >
      <Animated.View style={[styles.check, check]} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
        <View style={styles.checkIcon}>
          <Icon name="check" size={CHECK_ICON} color={tone} />
        </View>
      </Animated.View>
      <T variant="detalle" color={tone}>
        {children}
      </T>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    minHeight: shell.touch,
    paddingHorizontal: space[3],
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    overflow: 'hidden',
  },
  on: { backgroundColor: colors.ink, borderColor: colors.ink },
  check: { overflow: 'hidden' },
  checkIcon: { width: CHECK_ROOM },
});
