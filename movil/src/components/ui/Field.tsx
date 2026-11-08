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

/** The input's border, and its width while focused (the padding gives the extra pixel back, so the text stays put). */
const BORDER = 1;
const FOCUS_BORDER = 2;

/**
 * Label, input (tinta-suave border, radius 6) and help or error under it. MovMicro: focused, the border
 * turns 2 px 0ff1ce-hondo and so does the label.
 */
export function Field({ label, optional, hint, error, multiline, ref, ...input }: FieldProps) {
  const [focused, setFocused] = useState(false);
  return (
    <View style={styles.field}>
      <T variant="detalle" color={focused ? colors.brandDeep : undefined}>
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
    borderWidth: BORDER,
    borderColor: colors.inkSoft,
    borderRadius: radius.sm,
    backgroundColor: colors.surface,
    color: colors.ink,
    fontFamily: fonts.regular,
    fontSize: 16,
  },
  multiline: { minHeight: 88, maxHeight: 280 },
  focused: {
    borderColor: colors.brandDeep,
    borderWidth: FOCUS_BORDER,
    paddingHorizontal: space[3] - (FOCUS_BORDER - BORDER),
    paddingVertical: space[2] - (FOCUS_BORDER - BORDER),
  },
  invalid: { borderColor: colors.alert },
});
