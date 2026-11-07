import { useState, type ComponentRef, type Ref } from 'react';
import { StyleSheet, TextInput, View, type TextInputProps } from 'react-native';
import { colors, fonts, radius, space } from '@/theme/tokens';
import { T } from './Text';

export interface FieldProps extends Omit<TextInputProps, 'style'> {
  label: string;
  /** « · opcional» after the label. */
  optional?: boolean;
  hint?: string;
  error?: string | null;
  multiline?: boolean;
  ref?: Ref<ComponentRef<typeof TextInput>>;
}

/** Label, input (tinta-suave border, radius 6, 0ff1ce-hondo focus) and help or error under it. */
export function Field({ label, optional, hint, error, multiline, ref, ...input }: FieldProps) {
  const [focused, setFocused] = useState(false);
  return (
    <View style={styles.field}>
      <T variant="detalle">
        {label}
        {optional ? <T variant="detalle" soft>{' · opcional'}</T> : null}
      </T>
      <TextInput
        ref={ref}
        accessibilityLabel={label}
        placeholderTextColor={colors.inkSoft}
        multiline={multiline}
        textAlignVertical={multiline ? 'top' : 'center'}
        {...input}
        onFocus={(event) => {
          setFocused(true);
          input.onFocus?.(event);
        }}
        onBlur={(event) => {
          setFocused(false);
          input.onBlur?.(event);
        }}
        style={[styles.input, multiline ? styles.multiline : null, focused ? styles.focused : null, error ? styles.invalid : null]}
      />
      {error ? (
        <T variant="detalle" color={colors.alert}>
          {error}
        </T>
      ) : hint ? (
        <T variant="detalle" soft>
          {hint}
        </T>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  field: { gap: space[1] },
  input: {
    minHeight: 48,
    paddingHorizontal: space[3],
    paddingVertical: space[2],
    borderWidth: 1,
    borderColor: colors.inkSoft,
    borderRadius: radius.sm,
    backgroundColor: colors.surface,
    color: colors.ink,
    fontFamily: fonts.regular,
    fontSize: 16,
  },
  multiline: { minHeight: 88, maxHeight: 280 },
  focused: { borderColor: colors.brandDeep, borderWidth: 2 },
  invalid: { borderColor: colors.alert },
});
