import { router } from 'expo-router';
import { StyleSheet, View } from 'react-native';
import { Button, EmptyState, EmptyText } from '@/components/ui';
import { colors, space } from '@/theme/tokens';

export default function NotFound() {
  return (
    <View style={styles.screen}>
      <EmptyState
        title="Esta vista no existe"
        action={
          <Button variant="primary" onPress={() => router.replace('/')}>
            Ir a la Oficina
          </Button>
        }
      >
        <EmptyText>El enlace apunta a algo que la app no tiene (o todavía no).</EmptyText>
      </EmptyState>
    </View>
  );
}

const styles = StyleSheet.create({ screen: { flex: 1, justifyContent: 'center', padding: space[4], backgroundColor: colors.paper } });
