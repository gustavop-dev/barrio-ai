// A labelled choice, the app's version of the PWA's <select>: the field shows the current option and,
// tapped, lists every option right under it as a radio group (no dialog on top, so it also works inside a
// sheet). Choosing closes the list.
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Icon } from '@/components/icons';
import { haptic } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';
import { FoldIn } from './Fold';
import { T } from './Text';

export interface SelectOption<V extends string> {
  value: V;
  label: string;
}

export interface SelectProps<V extends string> {
  label: string;
  value: V | '';
  options: readonly SelectOption<V>[];
  onChange: (value: V) => void;
  /** Shown while nothing is chosen. */
  placeholder?: string;
  /** Accessible name when it differs from the visible label («Etapa de Marta Inventada»). */
  accessibilityLabel?: string;
  /** Hides the label above the field (the name is still read). */
  hideLabel?: boolean;
  /** « · opcional» after the label. */
  optional?: boolean;
  error?: string | null;
  disabled?: boolean;
  testID?: string;
}

export function Select<V extends string>({
  label,
  value,
  options,
  onChange,
  placeholder = 'Elige…',
  accessibilityLabel,
  hideLabel,
  optional,
  error,
  disabled,
  testID,
}: SelectProps<V>) {
  const [open, setOpen] = useState(false);
  const current = options.find((option) => option.value === value);
  const name = accessibilityLabel ?? label;
  return (
    <View style={styles.field}>
      {hideLabel ? null : (
        <T variant="detalle">
          {label}
          {optional ? <T variant="detalle" soft>{' · opcional'}</T> : null}
        </T>
      )}
      <Pressable
        testID={testID}
        accessibilityRole="button"
        accessibilityLabel={name}
        accessibilityValue={{ text: current?.label ?? placeholder }}
        accessibilityState={{ expanded: open, disabled: Boolean(disabled) }}
        accessibilityHint="Muestra las opciones"
        disabled={disabled}
        onPress={() => setOpen((value) => !value)}
        style={[styles.box, open ? styles.boxOpen : null, error ? styles.invalid : null, disabled ? styles.disabled : null]}
      >
        <T style={styles.value} color={current ? colors.ink : colors.inkSoft} numberOfLines={1}>
          {current?.label ?? placeholder}
        </T>
        <Icon name={open ? 'chevronUp' : 'chevronDown'} size={20} color={colors.inkSoft} />
      </Pressable>
      {open ? (
        // FoldIn, not a layout `entering`: that fade sometimes stayed at opacity 0 (08-resultados, «Modalidad»).
        <FoldIn accessibilityRole="radiogroup" accessibilityLabel={name} style={styles.list}>
          {options.map((option) => {
            const selected = option.value === value;
            return (
              <Pressable
                key={option.value || '__empty'}
                accessibilityRole="radio"
                accessibilityLabel={option.label}
                accessibilityState={{ checked: selected }}
                onPress={() => {
                  haptic('toggle');
                  setOpen(false);
                  if (!selected) onChange(option.value);
                }}
                style={({ pressed }) => [styles.option, selected ? styles.optionOn : null, pressed ? styles.optionPressed : null]}
              >
                <T style={styles.value}>{option.label}</T>
                {selected ? <Icon name="check" size={18} color={colors.brandDeep} /> : null}
              </Pressable>
            );
          })}
        </FoldIn>
      ) : null}
      {error ? (
        <T variant="detalle" color={colors.alert}>
          {error}
        </T>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  field: { gap: space[1] },
  box: {
    minHeight: 48,
    paddingHorizontal: space[3],
    flexDirection: 'row',
    alignItems: 'center',
    gap: space[2],
    borderWidth: 1,
    borderColor: colors.inkSoft,
    borderRadius: radius.sm,
    backgroundColor: colors.surface,
  },
  boxOpen: { borderColor: colors.brandDeep, borderWidth: 2 },
  invalid: { borderColor: colors.alert },
  disabled: { borderColor: colors.line, backgroundColor: colors.paper },
  value: { flex: 1 },
  list: { borderWidth: 1, borderColor: colors.line, borderRadius: radius.sm, backgroundColor: colors.surface, overflow: 'hidden' },
  option: { minHeight: 48, paddingHorizontal: space[3], flexDirection: 'row', alignItems: 'center', gap: space[2], borderTopWidth: 1, borderTopColor: colors.line },
  optionOn: { backgroundColor: colors.brandLight },
  optionPressed: { backgroundColor: colors.paper },
});
