import type { ReactNode } from 'react';
import { ScrollView, StyleSheet } from 'react-native';
import { router } from 'expo-router';
import { Button, EmptyState, EmptyText, PageHeader, pageContent } from '@/components/ui';
import { colors } from '@/theme/tokens';
import { useContentInsets } from './useContentInsets';

/** Phase 1 placeholder of a view the next phase ports from the PWA. */
export function Placeholder({ title, subtitle, children, testID }: { title: string; subtitle?: string; children?: ReactNode; testID?: string }) {
  const { bottom } = useContentInsets();
  return (
    <ScrollView testID={testID} style={styles.screen} contentContainerStyle={[pageContent, { paddingBottom: bottom }]}>
      <PageHeader title={title} subtitle={subtitle} />
      <EmptyState
        title="En construcción"
        action={
          <Button onPress={() => router.navigate('/')} variant="secondary">
            Volver a la Oficina
          </Button>
        }
      >
        <EmptyText>El equipo está montando esta vista en la app. Mientras tanto, la PWA la tiene completa.</EmptyText>
      </EmptyState>
      {children}
    </ScrollView>
  );
}

const styles = StyleSheet.create({ screen: { flex: 1, backgroundColor: colors.paper } });
