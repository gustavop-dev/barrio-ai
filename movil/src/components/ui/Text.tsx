import { Text as RNText, type TextProps } from 'react-native';
import { colors, type TypeVariant, type as typeScale } from '@/theme/tokens';

export interface TProps extends TextProps {
  /** Type scale of tokens.json; cuerpo by default. */
  variant?: TypeVariant;
  color?: string;
  /** detalle and subtitles go in tinta-suave. */
  soft?: boolean;
  center?: boolean;
}

/** All text of the app goes through here: Ubuntu, the type scale and tinta by default. */
export function T({ variant = 'cuerpo', color, soft, center, style, ...rest }: TProps) {
  return (
    <RNText
      {...rest}
      style={[typeScale[variant], { color: color ?? (soft ? colors.inkSoft : colors.ink) }, center ? { textAlign: 'center' } : null, style]}
    />
  );
}
