import type { ReactNode } from 'react';
import { Pressable, StyleSheet } from 'react-native';
import { haptic } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import { T } from './Text';

/** ui.css .chip-filter.solid: a toggle chip, tinta when pressed. */
export function FilterChip({ pressed, onPress, children, testID }: { pressed: boolean; onPress: () => void; children: ReactNode; testID?: string }) {
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityState={{ selected: pressed }}
      onPress={() => {
        haptic('toggle');
        onPress();
      }}
      style={[styles.chip, pressed ? styles.on : null]}
    >
      <T variant="detalle" color={pressed ? colors.paper : colors.ink}>
        {children}
      </T>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    minHeight: shell.touch,
    paddingHorizontal: space[3],
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
  },
  on: { backgroundColor: colors.ink, borderColor: colors.ink },
});
