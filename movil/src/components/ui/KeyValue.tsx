import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { space } from '@/theme/tokens';
import { T } from './Text';

/** A key/value row (ui.css .kv): «Origen · Desde la app», the label in tinta-suave and the value on the right. */
export function KeyValue({ label, children, testID }: { label: string; children: ReactNode; testID?: string }) {
  return (
    <View style={styles.row} testID={testID} accessible accessibilityLabel={typeof children === 'string' ? `${label}: ${children}` : undefined}>
      <T variant="detalle" soft style={styles.label}>
        {label}
      </T>
      {typeof children === 'string' ? (
        <T variant="detalle" style={styles.value}>
          {children}
        </T>
      ) : (
        <View style={styles.valueBox}>{children}</View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'flex-start', gap: space[2] },
  label: { flexShrink: 0, maxWidth: '45%' },
  value: { flex: 1, textAlign: 'right' },
  valueBox: { flex: 1, alignItems: 'flex-end' },
});
