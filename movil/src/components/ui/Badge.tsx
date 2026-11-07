import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { colors, radius, type Tone } from '@/theme/tokens';
import { T } from './Text';

/** Status chip colours (ui.css .badge): ok, info, warn, bad (outline, or solid), muted and ink. */
const TONES: Record<Tone | 'ink', { fg: string; bg: string; border: string }> = {
  ok: { fg: colors.brandDeep, bg: colors.brandLight, border: colors.brandLight },
  info: { fg: colors.info, bg: colors.infoLight, border: colors.infoLight },
  warn: { fg: colors.ink, bg: colors.postIt, border: colors.postIt },
  bad: { fg: colors.alert, bg: colors.surface, border: colors.alert },
  muted: { fg: colors.inkSoft, bg: colors.surface, border: colors.line },
  ink: { fg: colors.paper, bg: colors.ink, border: colors.ink },
};

export function Badge({ tone = 'muted', solid, dot, children }: { tone?: Tone | 'ink'; solid?: boolean; dot?: boolean; children: ReactNode }) {
  const t = solid && tone === 'bad' ? { fg: colors.onAlert, bg: colors.alert, border: colors.alert } : TONES[tone];
  return (
    <View style={[styles.badge, { backgroundColor: t.bg, borderColor: t.border }]}>
      {dot ? <View style={[styles.dot, { backgroundColor: t.fg }]} /> : null}
      <T variant="etiqueta" color={t.fg} numberOfLines={1}>
        {children}
      </T>
    </View>
  );
}

/** Pill label (ui.css .chip-label): role and modality of a person. */
export function LabelChip({ tone = 'muted', children }: { tone?: 'info' | 'muted' | 'ok' | 'warn'; children: ReactNode }) {
  const t = TONES[tone];
  return (
    <View style={[styles.label, { backgroundColor: t.bg, borderColor: t.border }]}>
      <T variant="etiqueta" color={t.fg} numberOfLines={1}>
        {children}
      </T>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 9, paddingVertical: 3, borderWidth: 1, borderRadius: radius.pill },
  dot: { width: 6, height: 6, borderRadius: radius.pill },
  label: { paddingHorizontal: 8, paddingVertical: 2, borderWidth: 1, borderRadius: radius.pill, alignSelf: 'flex-start' },
});
