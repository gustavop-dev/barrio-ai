import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { space } from '@/theme/tokens';
import { T } from './Text';

/** A block of a view: UPPERCASE etiqueta label, optional intro, content with 12 px gaps. */
export function Section({ label, intro, children }: { label: ReactNode; intro?: ReactNode; children?: ReactNode }) {
  return (
    <View style={styles.section}>
      <T variant="etiqueta" soft accessibilityRole="header">
        {label}
      </T>
      {intro ? (
        <T variant="detalle" soft>
          {intro}
        </T>
      ) : null}
      {children}
    </View>
  );
}

const styles = StyleSheet.create({ section: { gap: space[3] } });
