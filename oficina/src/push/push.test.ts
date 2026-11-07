import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fakeServer } from '../test/fakeServer';
import { parsePushPayload, safeTargetUrl } from './payload';
import { detectPush, disablePush, enablePush, PushError, urlBase64ToUint8Array } from './push';

// A 65-byte P-256 public key in base64url, as the backend serves it.
const KEY_BYTES = Uint8Array.from({ length: 65 }, (_, i) => (i * 37 + 4) % 256);
const PUBLIC_KEY = btoa(String.fromCharCode(...KEY_BYTES)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

const SUBSCRIPTION_JSON = {
  endpoint: 'https://push.example/endpoint/123',
  expirationTime: null,
  keys: { p256dh: 'BPublicClientKey', auth: 'authSecret' },
};

function makeSubscription() {
  return {
    endpoint: SUBSCRIPTION_JSON.endpoint,
    options: { applicationServerKey: KEY_BYTES.buffer, userVisibleOnly: true },
    toJSON: () => SUBSCRIPTION_JSON,
    unsubscribe: vi.fn(async () => true),
  };
}

function installBrowser({ permission = 'granted' as NotificationPermission, existing = null as ReturnType<typeof makeSubscription> | null, userAgent = 'Mozilla/5.0 (X11; Linux x86_64) Chrome/140' } = {}) {
  const created = makeSubscription();
  const pushManager = {
    getSubscription: vi.fn(async () => existing),
    subscribe: vi.fn(async () => created),
  };
  const registration = { pushManager };
  Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: { ready: Promise.resolve(registration) } });
  Object.defineProperty(navigator, 'userAgent', { configurable: true, value: userAgent });
  vi.stubGlobal('PushManager', function PushManager() {});
  const requestPermission = vi.fn(async () => permission);
  vi.stubGlobal('Notification', Object.assign(function Notification() {}, { permission: 'default', requestPermission }));
  return { pushManager, created, requestPermission };
}

beforeEach(() => {
  document.cookie = 'csrftoken=tok';
});

afterEach(() => {
  Reflect.deleteProperty(navigator, 'serviceWorker');
  Reflect.deleteProperty(navigator, 'userAgent');
});

describe('push subscription', () => {
  it('decodes the base64url VAPID key', () => {
    expect(Array.from(urlBase64ToUint8Array(PUBLIC_KEY))).toEqual(Array.from(KEY_BYTES));
  });

  it('asks permission first, subscribes with the backend VAPID key and sends the subscription', async () => {
    const browser = installBrowser();
    const server = fakeServer({
      'GET /api/v1/push/key': { body: { public_key: PUBLIC_KEY } },
      'POST /api/v1/push/subscriptions': { status: 201, body: { ok: true } },
    });

    await enablePush();

    expect(browser.requestPermission).toHaveBeenCalledOnce();
    // Permission is requested before any network call (iOS needs the user gesture).
    expect(browser.requestPermission.mock.invocationCallOrder[0]!).toBeLessThan(server.fetch.mock.invocationCallOrder[0]!);
    expect(browser.pushManager.subscribe).toHaveBeenCalledOnce();
    const options = browser.pushManager.subscribe.mock.calls[0] as unknown as [PushSubscriptionOptionsInit];
    expect(options[0].userVisibleOnly).toBe(true);
    expect(Array.from(options[0].applicationServerKey as Uint8Array)).toEqual(Array.from(KEY_BYTES));
    const [saved] = server.find('POST', '/api/v1/push/subscriptions');
    expect(saved?.body).toEqual(SUBSCRIPTION_JSON);
    expect(saved?.headers['x-csrftoken']).toBe('tok');
  });

  it('reuses an existing subscription made with the same key', async () => {
    const browser = installBrowser({ existing: makeSubscription() });
    const server = fakeServer({
      'GET /api/v1/push/key': { body: { public_key: PUBLIC_KEY } },
      'POST /api/v1/push/subscriptions': { status: 200, body: {} },
    });
    await enablePush();
    expect(browser.pushManager.subscribe).not.toHaveBeenCalled();
    expect(server.find('POST', '/api/v1/push/subscriptions')).toHaveLength(1);
  });

  it('stops without subscribing when permission is denied', async () => {
    const browser = installBrowser({ permission: 'denied' });
    const server = fakeServer({});
    await expect(enablePush()).rejects.toBeInstanceOf(PushError);
    expect(browser.pushManager.subscribe).not.toHaveBeenCalled();
    expect(server.requests).toHaveLength(0);
  });

  it('requires the home-screen app on iPhone', async () => {
    const browser = installBrowser({ userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Safari/604.1' });
    expect(detectPush()).toMatchObject({ ios: true, standalone: false, needsInstall: true });
    await expect(enablePush()).rejects.toThrow(/pantalla de inicio/);
    expect(browser.requestPermission).not.toHaveBeenCalled();
  });

  it('unsubscribes on the backend and in the browser', async () => {
    const existing = makeSubscription();
    installBrowser({ existing });
    const server = fakeServer({ 'POST /api/v1/push/unsubscribe': { status: 204 } });
    await disablePush();
    const [sent] = server.find('POST', '/api/v1/push/unsubscribe');
    expect(sent?.body).toEqual({ endpoint: SUBSCRIPTION_JSON.endpoint });
    expect(existing.unsubscribe).toHaveBeenCalledOnce();
  });
});

describe('push payload (service worker)', () => {
  it('reads title, body, url and tag', () => {
    expect(parsePushPayload(JSON.stringify({ title: 'Máquina en pausa', body: '429 de LinkedIn', url: '/maquina', tag: 'pause' }))).toEqual({
      title: 'Máquina en pausa',
      body: '429 de LinkedIn',
      url: '/maquina',
      tag: 'pause',
    });
    expect(parsePushPayload('texto plano')).toMatchObject({ title: 'Barrio AI', body: 'texto plano', url: '/' });
    expect(parsePushPayload(null)).toMatchObject({ title: 'Barrio AI', url: '/' });
  });

  it('opens only same-origin URLs', () => {
    const origin = 'https://barrio.example';
    expect(safeTargetUrl('/acciones?state=uncertain', origin)).toBe('https://barrio.example/acciones?state=uncertain');
    expect(safeTargetUrl('https://evil.example/x', origin)).toBe('https://barrio.example/');
    expect(safeTargetUrl(undefined, origin)).toBe('https://barrio.example/');
  });
});
