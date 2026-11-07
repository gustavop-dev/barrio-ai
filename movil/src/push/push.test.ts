// Native push: in-app routes for `data.url`, and registration with POST /api/v1/push/expo.
import * as Notifications from 'expo-notifications';
import * as SecureStore from 'expo-secure-store';
import '@/api/transport';
import { fakeServer } from '@/test/server';
import { ANDROID_CHANNEL, registerForPush } from './register';
import { routeForUrl } from './routes';

jest.mock('expo', () => ({ isRunningInExpoGo: jest.fn(() => false) }));
jest.mock('expo-constants', () => ({ __esModule: true, default: { expoConfig: { extra: { eas: { projectId: 'proyecto-prueba' } } }, easConfig: null } }));

describe('routes for data.url', () => {
  it('maps app paths, query and anchors; refuses API routes and other origins', () => {
    expect(routeForUrl('/tu-turno')).toEqual({ pathname: '/tu-turno', params: {} });
    expect(routeForUrl('/tu-turno#turno-question-7')).toEqual({ pathname: '/tu-turno', params: { ancla: 'turno-question-7' } });
    expect(routeForUrl('/tu-turno/sabe')).toEqual({ pathname: '/tu-turno', params: { tab: 'sabe' } });
    expect(routeForUrl('/calendario/pieza/p-9')).toEqual({ pathname: '/calendario/pieza/p-9', params: {} });
    expect(routeForUrl('/?enviado=1')).toEqual({ pathname: '/', params: { enviado: '1' } });
    expect(routeForUrl('/resultados#resumen')).toEqual({ pathname: '/resultados', params: { ancla: 'resumen' } });
    expect(routeForUrl('/api/v1/linkedin/oauth/start')).toBeNull();
    expect(routeForUrl('//evil.example/x')).toBeNull();
    expect(routeForUrl('https://www.linkedin.com/')).toBeNull();
    expect(routeForUrl(undefined)).toBeNull();
  });
});

describe('push registration', () => {
  beforeEach(() => (SecureStore as unknown as { __store: Map<string, string> }).__store.clear());

  it('creates the «default» channel, asks permission and registers the Expo token', async () => {
    const server = fakeServer({ 'POST /api/v1/push/expo': { status: 201, body: { id: 'p1' } } });
    await expect(registerForPush()).resolves.toEqual({ status: 'registrado', token: 'ExponentPushToken[prueba]' });
    expect(ANDROID_CHANNEL).toBe('default');
    expect(Notifications.getExpoPushTokenAsync).toHaveBeenCalledWith({ projectId: 'proyecto-prueba' });
    expect(server.find('POST', '/api/v1/push/expo')[0]?.body).toEqual({ token: 'ExponentPushToken[prueba]', device_name: 'Pixel de prueba' });
    expect(await SecureStore.getItemAsync('oficina.push-expo')).toBe('ExponentPushToken[prueba]');
  });

  it('says when the person said no', async () => {
    jest.mocked(Notifications.getPermissionsAsync).mockResolvedValueOnce({ status: 'denied' } as never);
    jest.mocked(Notifications.requestPermissionsAsync).mockResolvedValueOnce({ status: 'denied' } as never);
    const server = fakeServer();
    await expect(registerForPush()).resolves.toEqual({ status: 'denegado' });
    expect(server.requests).toHaveLength(0);
  });

  it('fails gracefully in Expo Go on Android (no remote pushes since SDK 53)', async () => {
    const expo = jest.requireMock('expo') as { isRunningInExpoGo: jest.Mock };
    const { Platform } = require('react-native');
    const os = Platform.OS;
    Platform.OS = 'android';
    expo.isRunningInExpoGo.mockReturnValueOnce(true);
    const server = fakeServer();
    await expect(registerForPush()).resolves.toEqual({ status: 'no-disponible', reason: 'expo-go-android' });
    expect(server.requests).toHaveLength(0);
    Platform.OS = os;
  });
});
