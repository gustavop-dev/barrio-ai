// Native push (Expo): after login the app asks for permission, gets its Expo push token and POSTs it
// to /api/v1/push/expo (registering it again just updates it); logout DELETEs it before revoking the
// device token. The backend sends every web push to these tokens too, with `data.url` set to the
// in-app path (push/routes.ts opens it).
//
// Expo Go cannot receive remote pushes on Android (since SDK 53), and getExpoPushTokenAsync needs an
// EAS project id: both come with Gustavo's development build. Until then registration says why it
// is unavailable instead of failing.
import { registerExpoPush, unregisterExpoPush } from '@compartido/api/endpoints';
import { isRunningInExpoGo } from 'expo';
import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { colors } from '@/theme/tokens';

const TOKEN_KEY = 'oficina.push-expo';
/** The backend sends `channelId: 'default'`. */
export const ANDROID_CHANNEL = 'default';

export type PushUnavailable = 'expo-go-android' | 'simulador' | 'sin-proyecto';

export type PushResult =
  | { status: 'registrado'; token: string }
  | { status: 'no-disponible'; reason: PushUnavailable }
  | { status: 'denegado' }
  | { status: 'error'; error: unknown };

export const PUSH_UNAVAILABLE_TEXT: Record<PushUnavailable, string> = {
  'expo-go-android': 'Expo Go no recibe avisos push en Android: llegan con la build de desarrollo.',
  simulador: 'Los avisos push solo llegan a un teléfono real.',
  'sin-proyecto': 'Falta el proyecto de Expo (EAS) que firma los avisos: se configura con la build de desarrollo.',
};

/** The EAS project id that signs Expo push tokens (app.json › extra.eas.projectId once Gustavo links one). */
export function easProjectId(): string | null {
  const fromConfig = (Constants.expoConfig?.extra as { eas?: { projectId?: string } } | undefined)?.eas?.projectId;
  return fromConfig ?? Constants.easConfig?.projectId ?? null;
}

export function pushUnavailableReason(): PushUnavailable | null {
  if (Platform.OS === 'android' && isRunningInExpoGo()) return 'expo-go-android';
  if (!Device.isDevice) return 'simulador';
  if (!easProjectId()) return 'sin-proyecto';
  return null;
}

/** «Pixel 8 de Gustavo» or the model; the backend shows it in the device list. */
export function deviceName(): string {
  return Device.deviceName || [Device.manufacturer, Device.modelName].filter(Boolean).join(' ') || `0ff1ce ${Platform.OS}`;
}

/** Asks for permission (the OS prompt), gets the Expo token and registers it with the backend. */
export async function registerForPush(): Promise<PushResult> {
  const reason = pushUnavailableReason();
  if (reason) return { status: 'no-disponible', reason };
  try {
    if (Platform.OS === 'android') {
      // The channel must exist before asking for a token (and for the Android 13 permission prompt).
      await Notifications.setNotificationChannelAsync(ANDROID_CHANNEL, {
        name: 'Avisos de 0ff1ce',
        importance: Notifications.AndroidImportance.HIGH,
        lightColor: colors.brand,
      });
    }
    let { status } = await Notifications.getPermissionsAsync();
    if (status !== 'granted') ({ status } = await Notifications.requestPermissionsAsync());
    if (status !== 'granted') return { status: 'denegado' };
    const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId: easProjectId()! });
    await registerExpoPush(token, deviceName());
    await SecureStore.setItemAsync(TOKEN_KEY, token).catch(() => undefined);
    return { status: 'registrado', token };
  } catch (error) {
    return { status: 'error', error };
  }
}

/** On logout, while the device token still works: the backend stops sending to this phone. */
export async function unregisterPush(): Promise<void> {
  const token = await SecureStore.getItemAsync(TOKEN_KEY).catch(() => null);
  if (!token) return;
  try {
    await unregisterExpoPush(token);
  } catch {
    // Best effort: revoking the device token right after also cuts the pushes off server-side.
  }
  await SecureStore.deleteItemAsync(TOKEN_KEY).catch(() => undefined);
}

/** How a push shows while the app is open: banner and list, no sound, no badge. */
export function configureForegroundPushes(): void {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: false, shouldSetBadge: false }),
  });
}
