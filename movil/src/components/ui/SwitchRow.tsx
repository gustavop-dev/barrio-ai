import { Pressable, StyleSheet, Switch, View } from 'react-native';
import { haptic } from '@/theme/motion';
import { colors, space } from '@/theme/tokens';
import { T } from './Text';

/**
 * A switch row (Ajustes, the photo sheet): label and optional hint on the left, the switch on the
 * right, a 1 px line on top. The whole row (48 dp) is the control.
 */
export function SwitchRow({
  label,
  hint,
  value,
  disabled,
  onChange,
  divider = true,
  testID,
}: {
  label: string;
  hint?: string;
  value: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
  /** The line on top; off for the first row of a card. */
  divider?: boolean;
  testID?: string;
}) {
  const toggle = () => {
    if (disabled) return;
    haptic('switchToggle');
    onChange(!value);
  };
  return (
    <Pressable
      testID={testID}
      accessibilityRole="switch"
      accessibilityLabel={label}
      accessibilityHint={hint}
      accessibilityState={{ checked: value, disabled: Boolean(disabled) }}
      disabled={disabled}
      onPress={toggle}
      style={[styles.row, divider ? styles.divider : null]}
    >
      <View style={styles.text}>
        <T color={disabled ? colors.inkSoft : colors.ink}>{label}</T>
        {hint ? (
          <T variant="detalle" soft>
            {hint}
          </T>
        ) : null}
      </View>
      <View pointerEvents="none" importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
        <Switch
          value={value}
          disabled={disabled}
          trackColor={{ false: colors.line, true: colors.brandDeep }}
          thumbColor={colors.surface}
          ios_backgroundColor={colors.line}
        />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { minHeight: 48, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space[3], paddingVertical: space[1] },
  divider: { borderTopWidth: 1, borderTopColor: colors.line },
  text: { flex: 1, gap: 2 },
});
