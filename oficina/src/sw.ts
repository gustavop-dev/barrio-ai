/// <reference lib="webworker" />
// Service worker of the office: app-shell precache, Web Push and notification clicks.
// Responses from /api/ are never cached.

import { clientsClaim } from 'workbox-core';
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching';
import { NavigationRoute, registerRoute } from 'workbox-routing';
import { NetworkOnly } from 'workbox-strategies';
import { parsePushPayload, safeTargetUrl } from './push/payload';

declare const self: ServiceWorkerGlobalScope & { __WB_MANIFEST: (string | { url: string; revision: string | null })[] };

const BACKEND = /^\/(api|admin|static)(\/|$)|^\/health$/;

self.skipWaiting();
clientsClaim();
cleanupOutdatedCaches();

// Build output only (JS, CSS, HTML, icons, sprites). Nothing from the backend.
precacheAndRoute(self.__WB_MANIFEST);

// Backend reads always go to the network, explicitly and without a cache. Writes
// (POST…) never match a Workbox route, so the browser sends them untouched.
registerRoute(({ url }) => url.origin === self.location.origin && BACKEND.test(url.pathname), new NetworkOnly(), 'GET');

// Client-side routes (/maquina, /acciones…) open the cached shell, even offline.
registerRoute(new NavigationRoute(createHandlerBoundToURL('index.html'), { denylist: [BACKEND] }));

self.addEventListener('push', (event: PushEvent) => {
  let raw: string | null;
  try {
    raw = event.data ? event.data.text() : null;
  } catch {
    raw = null;
  }
  const payload = parsePushPayload(raw);
  const url = safeTargetUrl(payload.url, self.location.origin);
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      tag: payload.tag,
      data: { url },
      icon: '/icons/icon-192.png',
      badge: '/icons/badge-96.png',
      lang: 'es',
    }),
  );
});

self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close();
  const data = event.notification.data as { url?: unknown } | null;
  const url = safeTargetUrl(data?.url, self.location.origin);
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      const exact = windows.find((client) => client.url === url);
      if (exact) return exact.focus();
      const sameApp = windows.find((client) => new URL(client.url).origin === self.location.origin);
      if (sameApp) {
        const navigated = await sameApp.navigate(url).catch(() => null);
        return (navigated ?? sameApp).focus();
      }
      return self.clients.openWindow(url);
    })(),
  );
});
