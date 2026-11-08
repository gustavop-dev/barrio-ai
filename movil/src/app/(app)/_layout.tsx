// The session gate and what only signed-in screens need: the shared recorder, the capture sheet,
// the push-tap routing, and the stack (tabs plus the detail views above them). Signed out, it opens the
// login over itself (SignedOut).
import * as Notifications from 'expo-notifications';
import { Stack, router, useFocusEffect } from 'expo-router';
import { useCallback, useEffect } from 'react';
import { View } from 'react-native';
import { useSession } from '@/auth/session';
import { CaptureSheetHost } from '@/capture/CaptureSheet';
import { RecorderProvider } from '@/capture/recorder';
import { loadCaptureUsed } from '@/capture/store';
import { openLink } from '@/navigation';
import { isInAppPath } from '@/push/routes';
import { timings } from '@/theme/motion';
import { colors } from '@/theme/tokens';

/** A tapped push opens its `data.url` in the app (also when the tap launched the app). */
function usePushRouting() {
  useEffect(() => {
    const open = (response: Notifications.NotificationResponse | null) => {
      const url = response?.notification.request.content.data?.url;
      if (!isInAppPath(url)) return;
      openLink(url);
      Notifications.clearLastNotificationResponse();
    };
    open(Notifications.getLastNotificationResponse());
    const subscription = Notifications.addNotificationResponseReceivedListener(open);
    return () => subscription.remove();
  }, []);
}

/**
 * Detail screens draw their own push (components/shell/DetailScreen.tsx, MovNavegacion): the stack
 * shows them as transparent modals without a native animation, so the tabs stay drawn underneath
 * and can move left and darken while the detail slides in.
 */
const PUSHED = { presentation: 'transparentModal', animation: 'none', contentStyle: { backgroundColor: 'transparent' } } as const;

function SignedIn() {
  usePushRouting();
  useEffect(() => {
    void loadCaptureUsed();
  }, []);
  return (
    <RecorderProvider>
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.paper },
          animation: 'slide_from_right',
          animationDuration: timings.screen.duration,
        }}
      >
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="personas/[id]" options={PUSHED} />
        <Stack.Screen name="calendario/pieza/[id]" options={PUSHED} />
      </Stack>
      <CaptureSheetHost />
    </RecorderProvider>
  );
}

/**
 * Signed out, the app stays at the bottom of the root stack and opens the login over itself (a transparent
 * modal). When the session opens, SignedIn mounts here, under the login, and the login fades into the live
 * Oficina (MovEntrada, app/login.tsx). A Redirect would replace the app with the login, which would then be
 * the first screen of its stack: drawn as an opaque card, with nothing under it to fade into.
 */
function SignedOut() {
  useFocusEffect(
    useCallback(() => {
      router.push('/login');
    }, []),
  );
  return <View testID="app-fuera" style={{ flex: 1, backgroundColor: colors.ink }} />;
}

export default function AppLayout() {
  const { status } = useSession();
  if (status === 'fuera') return <SignedOut />;
  if (status === 'cargando') return null;
  return <SignedIn />;
}
