import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { colors, radius, space } from '@/theme/tokens';
import { T } from './Text';

export type NoteTone = 'info' | 'ok' | 'warn' | 'error';

const TONES: Record<NoteTone, { bg: string; fg: string; border: string; title: string }> = {
  info: { bg: colors.infoLight, fg: colors.info, border: colors.infoLight, title: colors.info },
  ok: { bg: colors.brandLight, fg: colors.brandDeep, border: colors.brandLight, title: colors.brandDeep },
  warn: { bg: colors.postIt, fg: colors.ink, border: colors.postIt, title: colors.ink },
  error: { bg: colors.surface, fg: colors.ink, border: colors.alert, title: colors.alert },
};

/** ui.css .note: info, ok, warn (post-it) and error (alerta border and title on superficie). */
export function Note({ tone = 'info', title, children, actions }: { tone?: NoteTone; title?: ReactNode; children?: ReactNode; actions?: ReactNode }) {
  const t = TONES[tone];
  return (
    <View
      style={[styles.note, { backgroundColor: t.bg, borderColor: t.border }]}
      accessibilityRole={tone === 'error' || tone === 'warn' ? 'alert' : 'summary'}
      accessibilityLiveRegion={tone === 'error' || tone === 'warn' ? 'assertive' : 'polite'}
    >
      {title ? <T color={t.title}>{title}</T> : null}
      {typeof children === 'string' ? (
        <T variant="detalle" color={t.fg}>
          {children}
        </T>
      ) : (
        children
      )}
      {actions ? <View style={styles.actions}>{actions}</View> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  note: { paddingVertical: space[3], paddingHorizontal: space[4], borderWidth: 1, borderRadius: radius.sm, gap: space[1] },
  actions: { marginTop: space[2], flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
});
