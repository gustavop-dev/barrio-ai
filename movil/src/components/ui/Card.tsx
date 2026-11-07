import type { ReactNode } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { colors, radius, space } from '@/theme/tokens';

export type CardTone = 'bad' | 'warn' | 'ok' | 'info' | 'dashed' | null;

const BORDER: Record<Exclude<CardTone, null>, string> = {
  bad: colors.alert,
  warn: colors.postIt,
  ok: colors.brandDeep,
  info: colors.spriteBlue,
  dashed: colors.inkSoft,
};

/** ui.css .card: superficie, 1px linea border (or the tone's), radius 12, 16 padding, 12 gap. */
export function Card({ tone = null, compact, children, style }: { tone?: CardTone; compact?: boolean; children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return (
    <View
      style={[
        styles.card,
        compact ? styles.compact : null,
        tone ? { borderColor: BORDER[tone] } : null,
        tone === 'dashed' ? styles.dashed : null,
        style,
      ]}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { padding: space[4], gap: space[3], backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: radius.md },
  compact: { padding: space[3], gap: space[2] },
  dashed: { borderStyle: 'dashed', backgroundColor: 'transparent' },
});
