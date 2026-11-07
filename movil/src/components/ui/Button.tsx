import type { ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withSpring, withTiming } from 'react-native-reanimated';
import { spring, timing } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import { T } from './Text';

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';

export interface ButtonProps {
  children: ReactNode;
  onPress?: () => void;
  variant?: ButtonVariant;
  /** Full width. */
  block?: boolean;
  size?: 'normal' | 'small';
  disabled?: boolean;
  loading?: boolean;
  /** Read and shown while loading («Guardando…»). */
  loadingLabel?: string;
  /** Ghost in tinta-suave instead of 0ff1ce-hondo. */
  quiet?: boolean;
  icon?: ReactNode;
  accessibilityLabel?: string;
  accessibilityHint?: string;
  testID?: string;
  style?: StyleProp<ViewStyle>;
}

const FILL: Record<ButtonVariant, { bg: string; fg: string; border: string }> = {
  primary: { bg: colors.brand, fg: colors.onBrand, border: colors.brand },
  secondary: { bg: colors.surface, fg: colors.ink, border: colors.inkSoft },
  danger: { bg: colors.surface, fg: colors.alert, border: colors.alert },
  ghost: { bg: 'transparent', fg: colors.brandDeep, border: 'transparent' },
};

/** The design's buttons (48 px, radius 12): primary 0ff1ce, secondary outlined, danger alerta, ghost link. */
export function Button({
  children,
  onPress,
  variant = 'secondary',
  block,
  size = 'normal',
  disabled,
  loading,
  loadingLabel,
  quiet,
  icon,
  accessibilityLabel,
  accessibilityHint,
  testID,
  style,
}: ButtonProps) {
  const scale = useSharedValue(1);
  const animated = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  const inactive = Boolean(disabled || loading);
  const fill = FILL[variant];
  const muted = disabled && !loading && variant !== 'ghost';
  const fg = muted ? colors.inkSoft : variant === 'ghost' && quiet ? colors.inkSoft : fill.fg;
  const label = loading && loadingLabel ? loadingLabel : children;

  return (
    <Animated.View style={[block ? styles.block : null, animated, style]}>
      <Pressable
        testID={testID}
        accessibilityRole="button"
        accessibilityLabel={accessibilityLabel ?? (typeof label === 'string' ? label : undefined)}
        accessibilityHint={accessibilityHint}
        accessibilityState={{ disabled: inactive, busy: Boolean(loading) }}
        disabled={inactive}
        onPress={onPress}
        onPressIn={() => {
          scale.set(withTiming(0.97, timing('press')));
        }}
        onPressOut={() => {
          scale.set(withSpring(1, spring('press')));
        }}
        style={({ pressed }) => [
          styles.base,
          size === 'small' ? styles.small : null,
          variant === 'ghost' ? styles.ghost : null,
          {
            backgroundColor: muted ? colors.line : pressed && variant === 'primary' ? colors.brandPressed : pressed && variant !== 'ghost' ? colors.paper : fill.bg,
            borderColor: muted ? colors.line : fill.border,
          },
        ]}
      >
        {loading ? <ActivityIndicator size="small" color={fg} /> : icon ? <View>{icon}</View> : null}
        {typeof label === 'string' ? (
          <T color={fg} center numberOfLines={2} style={variant === 'ghost' ? styles.ghostText : null}>
            {label}
          </T>
        ) : (
          label
        )}
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  block: { alignSelf: 'stretch' },
  base: {
    minHeight: 48,
    paddingHorizontal: space[4],
    borderWidth: 1,
    borderRadius: radius.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: space[2],
  },
  small: { minHeight: shell.touch },
  ghost: { paddingHorizontal: space[2], minHeight: shell.touch },
  ghostText: { textDecorationLine: 'none' },
});
