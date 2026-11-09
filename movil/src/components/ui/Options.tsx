import { Pressable, StyleSheet, View } from 'react-native';
import { haptic } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import { T } from './Text';

export interface Option<V> {
  value: V;
  label: string;
  hint?: string;
}

/** A radio group: one row per option (label and hint), a ring that fills when chosen. */
export function Options<V extends string | boolean>({
  legend,
  options,
  value,
  onChange,
  disabled,
  horizontal,
  testID,
}: {
  legend: string;
  options: readonly Option<V>[];
  value: V | null;
  onChange: (value: V) => void;
  disabled?: boolean;
  horizontal?: boolean;
  testID?: string;
}) {
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel={legend} style={styles.group} testID={testID} collapsable={false}>
      <T variant="etiqueta" soft>
        {legend}
      </T>
      <View style={horizontal ? styles.row : styles.column}>
        {options.map((option) => {
          const selected = option.value === value;
          return (
            <Pressable
              key={String(option.value)}
              testID={testID ? `${testID}-${String(option.value)}` : undefined}
              accessibilityRole="radio"
              accessibilityState={{ checked: selected, disabled: Boolean(disabled) }}
              accessibilityLabel={option.hint ? `${option.label}. ${option.hint}` : option.label}
              disabled={disabled}
              onPress={() => {
                haptic('toggle');
                onChange(option.value);
              }}
              style={[styles.option, horizontal ? styles.pill : null, selected && horizontal ? styles.pillOn : null]}
            >
              {horizontal ? null : (
                <View style={[styles.ring, selected ? styles.ringOn : null]}>{selected ? <View style={styles.dot} /> : null}</View>
              )}
              <View style={styles.texts}>
                <T color={selected && horizontal ? colors.paper : colors.ink}>{option.label}</T>
                {option.hint ? (
                  <T variant="detalle" soft>
                    {option.hint}
                  </T>
                ) : null}
              </View>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  group: { gap: space[2] },
  column: { gap: space[2] },
  row: { flexDirection: 'row', gap: space[2] },
  option: { minHeight: shell.touch, flexDirection: 'row', alignItems: 'center', gap: space[3] },
  pill: { paddingHorizontal: space[4], borderWidth: 1, borderColor: colors.inkSoft, borderRadius: radius.pill, backgroundColor: colors.surface },
  pillOn: { backgroundColor: colors.ink, borderColor: colors.ink },
  ring: { width: 22, height: 22, borderRadius: radius.pill, borderWidth: 2, borderColor: colors.inkSoft, alignItems: 'center', justifyContent: 'center' },
  ringOn: { borderColor: colors.brandDeep },
  dot: { width: 10, height: 10, borderRadius: radius.pill, backgroundColor: colors.brandDeep },
  texts: { flexShrink: 1, gap: 2 },
});
