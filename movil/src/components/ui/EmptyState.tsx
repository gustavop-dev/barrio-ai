import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { space } from '@/theme/tokens';
import { IdleLibrarian } from './Sprite';
import { T } from './Text';

/** Empty state: the librarian idling, a sentence and an optional action. */
export function EmptyState({ title, children, action }: { title: ReactNode; children?: ReactNode; action?: ReactNode }) {
  return (
    <View style={styles.empty}>
      <IdleLibrarian />
      <T variant="subtitulo" center accessibilityRole="header">
        {title}
      </T>
      {children ? <View style={styles.text}>{children}</View> : null}
      {action ? <View>{action}</View> : null}
    </View>
  );
}

/** Running text inside an EmptyState (tinta-suave, centred). */
export function EmptyText({ children }: { children: ReactNode }) {
  return (
    <T soft center>
      {children}
    </T>
  );
}

const styles = StyleSheet.create({
  empty: { paddingVertical: space[6], gap: space[3], alignItems: 'center' },
  text: { gap: space[2], maxWidth: 340 },
});
