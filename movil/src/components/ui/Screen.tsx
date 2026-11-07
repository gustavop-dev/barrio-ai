import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { shell, space } from '@/theme/tokens';
import { T } from './Text';

/** A view's title block (t-titulo) with its optional subtitle (cuerpo, tinta-suave). */
export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string | null; actions?: ReactNode }) {
  return (
    <View style={styles.head}>
      <View style={styles.row}>
        <T variant="titulo" accessibilityRole="header" style={styles.title}>
          {title}
        </T>
        {actions}
      </View>
      {subtitle ? <T soft>{subtitle}</T> : null}
    </View>
  );
}

/** Page padding of the PWA at mobile width: 20 top, 16 sides, 32 bottom, 24 between blocks. */
export const pageContent = { paddingTop: 20, paddingHorizontal: shell.gutter, paddingBottom: 32, gap: space[6] } as const;

const styles = StyleSheet.create({
  head: { gap: space[1] },
  row: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', gap: space[2] },
  title: { flexShrink: 1 },
});
