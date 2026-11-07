// Root: the native transport, fonts and splash, and the providers every screen shares.
import '@/api/transport';
// Only the two weights the design uses (the package index would bundle all eight).
import { Ubuntu_400Regular } from '@expo-google-fonts/ubuntu/400Regular';
import { Ubuntu_700Bold } from '@expo-google-fonts/ubuntu/700Bold';
import { QueryClientProvider } from '@tanstack/react-query';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState, type ReactNode } from 'react';
import { LogBox } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { createQueryClient, wireQueryManagers } from '@/api/queryClient';
import { SessionProvider, useSession } from '@/auth/session';
import { ToastProvider } from '@/components/ui';
import { configureForegroundPushes } from '@/push/register';
import { timings } from '@/theme/motion';
import { colors } from '@/theme/tokens';

// Expo Go on Android has no remote pushes (since SDK 53): registration says so in Ajustes instead.
LogBox.ignoreLogs(['`expo-notifications` functionality is not fully supported in Expo Go', '[expo-notifications] Push notifications (remote notifications) are unavailable in Expo Go']);

void SplashScreen.preventAutoHideAsync().catch(() => undefined);
wireQueryManagers();
configureForegroundPushes();

/** Keeps the splash up until the fonts are in and the session is known. */
function SplashGate({ fontsReady, children }: { fontsReady: boolean; children: ReactNode }) {
  const { status } = useSession();
  const ready = fontsReady && status !== 'cargando';
  useEffect(() => {
    if (ready) void SplashScreen.hideAsync().catch(() => undefined);
  }, [ready]);
  return ready ? <>{children}</> : null;
}

export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts({ Ubuntu_400Regular, Ubuntu_700Bold });
  const [client] = useState(createQueryClient);
  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: colors.paper }}>
      <SafeAreaProvider>
        <QueryClientProvider client={client}>
          <SessionProvider>
            <ToastProvider>
              <StatusBar style="dark" />
              <SplashGate fontsReady={fontsLoaded || Boolean(fontError)}>
                <Stack
                  screenOptions={{
                    headerShown: false,
                    contentStyle: { backgroundColor: colors.paper },
                    animation: 'slide_from_right',
                    animationDuration: timings.screen.duration,
                  }}
                />
              </SplashGate>
            </ToastProvider>
          </SessionProvider>
        </QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
