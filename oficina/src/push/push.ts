// Web Push subscription with the backend's VAPID key.

import { deletePushSubscription, getPushKey, savePushSubscription } from '../api/endpoints';

export interface PushSupport {
  /** Service worker, PushManager and Notification are all available. */
  supported: boolean;
  ios: boolean;
  /** Running as an installed app (home screen). */
  standalone: boolean;
  /** iPhone/iPad Safari: Web Push only works once added to the home screen. */
  needsInstall: boolean;
  permission: NotificationPermission | 'unsupported';
}

export class PushError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'PushError';
  }
}

export function detectPush(): PushSupport {
  const nav = navigator as Navigator & { standalone?: boolean };
  const ua = nav.userAgent ?? '';
  const ios = /iPad|iPhone|iPod/.test(ua) || (/Macintosh/.test(ua) && (nav.maxTouchPoints ?? 0) > 1);
  const standalone =
    (typeof window.matchMedia === 'function' && window.matchMedia('(display-mode: standalone)').matches) || nav.standalone === true;
  const supported = 'serviceWorker' in nav && 'PushManager' in window && 'Notification' in window;
  return {
    supported,
    ios,
    standalone,
    needsInstall: ios && !standalone,
    permission: 'Notification' in window ? Notification.permission : 'unsupported',
  };
}

export function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const normalized = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(normalized);
  const output = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) output[i] = raw.charCodeAt(i);
  return output;
}

function sameKey(current: ArrayBuffer | null | undefined, wanted: Uint8Array): boolean {
  if (!current) return false;
  const bytes = new Uint8Array(current);
  return bytes.length === wanted.length && bytes.every((b, i) => b === wanted[i]);
}

export async function getRegistration(timeoutMs = 10_000): Promise<ServiceWorkerRegistration> {
  if (!('serviceWorker' in navigator)) throw new PushError('Este navegador no admite service workers.');
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(
      () => reject(new PushError('El service worker no está activo. Abre la app instalada (no el modo de desarrollo) y vuelve a intentarlo.')),
      timeoutMs,
    );
  });
  try {
    return await Promise.race([navigator.serviceWorker.ready, timeout]);
  } finally {
    clearTimeout(timer);
  }
}

export async function currentSubscription(): Promise<PushSubscription | null> {
  if (!detectPush().supported) return null;
  const registration = await getRegistration();
  return registration.pushManager.getSubscription();
}

/**
 * Must run from a click: iOS only shows the permission prompt inside a user
 * gesture, so permission is requested before any network round trip.
 */
export async function enablePush(): Promise<PushSubscription> {
  const support = detectPush();
  if (support.needsInstall) throw new PushError('En iPhone, primero añade Barrio a la pantalla de inicio y ábrela desde allí.');
  if (!support.supported) throw new PushError('Este navegador no admite notificaciones push.');
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') {
    throw new PushError(
      permission === 'denied'
        ? 'Las notificaciones están bloqueadas. Actívalas en los ajustes del navegador o del sistema para Barrio.'
        : 'No se concedió el permiso de notificaciones.',
    );
  }
  const registration = await getRegistration();
  const { public_key: publicKey } = await getPushKey();
  if (!publicKey) throw new PushError('El servidor no tiene clave VAPID configurada.');
  const applicationServerKey = urlBase64ToUint8Array(publicKey);
  let subscription = await registration.pushManager.getSubscription();
  if (subscription && !sameKey(subscription.options?.applicationServerKey, applicationServerKey)) {
    await subscription.unsubscribe();
    subscription = null;
  }
  subscription ??= await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey });
  await savePushSubscription(subscription.toJSON());
  return subscription;
}

export async function disablePush(): Promise<void> {
  const registration = await getRegistration();
  const subscription = await registration.pushManager.getSubscription();
  if (!subscription) return;
  try {
    await deletePushSubscription(subscription.endpoint);
  } finally {
    await subscription.unsubscribe();
  }
}
