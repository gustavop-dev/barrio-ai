// Jest setup: native modules are mocked here (no device, no network, no paid calls).
import 'react-native-gesture-handler/jestSetup';

// React Native's FormData (file parts as {uri, name, type}), not Node's, as on the phone.
(globalThis as unknown as { FormData: unknown }).FormData = require('react-native/Libraries/Network/FormData').default;

// Worklets' own mock (its web build refuses the UI runtime that Gesture Handler asks for).
jest.mock('react-native-worklets', () => require('react-native-worklets/src/mock'));
require('react-native-reanimated').setUpTests();

jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);
jest.mock('@react-native-community/netinfo', () => require('@react-native-community/netinfo/jest/netinfo-mock'));

// The keystore, in memory.
jest.mock('expo-secure-store', () => {
  const store = new Map<string, string>();
  return {
    __store: store,
    getItemAsync: jest.fn(async (key: string) => store.get(key) ?? null),
    setItemAsync: jest.fn(async (key: string, value: string) => {
      store.set(key, value);
    }),
    deleteItemAsync: jest.fn(async (key: string) => {
      store.delete(key);
    }),
  };
});

jest.mock('expo-haptics', () => ({
  selectionAsync: jest.fn(async () => undefined),
  impactAsync: jest.fn(async () => undefined),
  notificationAsync: jest.fn(async () => undefined),
  ImpactFeedbackStyle: { Light: 'light', Medium: 'medium', Heavy: 'heavy', Soft: 'soft', Rigid: 'rigid' },
  NotificationFeedbackType: { Success: 'success', Warning: 'warning', Error: 'error' },
}));

jest.mock('expo-device', () => ({ isDevice: true, deviceName: 'Pixel de prueba', manufacturer: 'Google', modelName: 'Pixel 8' }));

jest.mock('expo-notifications', () => ({
  setNotificationHandler: jest.fn(),
  setNotificationChannelAsync: jest.fn(async () => null),
  getPermissionsAsync: jest.fn(async () => ({ status: 'granted', granted: true, canAskAgain: true })),
  requestPermissionsAsync: jest.fn(async () => ({ status: 'granted', granted: true, canAskAgain: true })),
  getExpoPushTokenAsync: jest.fn(async () => ({ type: 'expo', data: 'ExponentPushToken[prueba]' })),
  getLastNotificationResponse: jest.fn(() => null),
  addNotificationResponseReceivedListener: jest.fn(() => ({ remove: jest.fn() })),
  clearLastNotificationResponse: jest.fn(),
  // A push received with the app open (MovNotificaciones: the top bar refreshes the bell).
  addNotificationReceivedListener: jest.fn(() => ({ remove: jest.fn() })),
  AndroidImportance: { HIGH: 4, MAX: 5 },
}));

jest.mock('expo-image-picker', () => ({
  requestCameraPermissionsAsync: jest.fn(async () => ({ granted: true, status: 'granted', canAskAgain: true })),
  launchCameraAsync: jest.fn(async () => ({ canceled: true, assets: null })),
  launchImageLibraryAsync: jest.fn(async () => ({ canceled: true, assets: null })),
}));

// expo-audio: a recorder that records nothing but behaves like the real one.
jest.mock('expo-audio', () => require('./src/test/fakeAudio').expoAudioMock);

// expo-router: screens are rendered on their own; navigation calls are recorded.
jest.mock('expo-router', () => {
  const router = { push: jest.fn(), navigate: jest.fn(), dismissTo: jest.fn(), replace: jest.fn(), back: jest.fn(), canGoBack: jest.fn(() => true), setParams: jest.fn() };
  const state = { params: {} as Record<string, string>, pathname: '/', root: undefined as unknown };
  return {
    router,
    useRouter: () => router,
    useLocalSearchParams: () => state.params,
    usePathname: () => state.pathname,
    useIsFocused: () => state.pathname === '/',
    // No root state by default: screens fall back to useNavigation().getState(), which the tests set.
    useRootNavigationState: () => state.root,
    Redirect: ({ href }: { href: string }) => {
      const { Text } = require('react-native');
      return <Text testID="redirect">{String(href)}</Text>;
    },
    __state: state,
  };
});
