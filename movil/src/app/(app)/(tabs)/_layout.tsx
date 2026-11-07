// The shell at mobile size: the top bar over every view and the bottom bar with the capture button.
// Tu turno, Notificaciones, Calendario and Ajustes are tabs without a button of their own (the top
// bar opens them); Android back goes through the tab history.
import { Tabs } from 'expo-router/js-tabs';
import { BottomBar } from '@/components/shell/BottomBar';
import { TopBar } from '@/components/shell/TopBar';
import { colors } from '@/theme/tokens';

export default function TabsLayout() {
  return (
    <Tabs
      backBehavior="history"
      tabBar={(props) => <BottomBar {...props} />}
      screenOptions={{ header: () => <TopBar />, sceneStyle: { backgroundColor: colors.paper } }}
    >
      <Tabs.Screen name="index" options={{ title: 'Oficina' }} />
      <Tabs.Screen name="resultados" options={{ title: 'Resultados' }} />
      <Tabs.Screen name="personas" options={{ title: 'Personas' }} />
      <Tabs.Screen name="galeria" options={{ title: 'Galería' }} />
      <Tabs.Screen name="tu-turno" options={{ title: 'Tu turno', href: null }} />
      <Tabs.Screen name="notificaciones" options={{ title: 'Notificaciones', href: null }} />
      <Tabs.Screen name="calendario" options={{ title: 'Calendario', href: null }} />
      <Tabs.Screen name="ajustes" options={{ title: 'Ajustes', href: null }} />
    </Tabs>
  );
}
