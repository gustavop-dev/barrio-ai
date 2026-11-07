// Opening a link from the API (a push's `data.url`, a card's `href`, a notification's `link`):
// app paths open in-app, https opens in the browser, and API routes that need the cookie session
// (the LinkedIn OAuth reconnect) open the PWA's Ajustes in the browser instead.
import { router } from 'expo-router';
import { Linking } from 'react-native';
import { apiUrl } from '@/api/config';
import { openCaptureSheet } from '@/capture/store';
import { CAPTURE_HISTORY_PARAM, routeForUrl } from '@/push/routes';

/** The PWA section where Gustavo reconnects LinkedIn with his cookie session. */
export const PWA_LINKEDIN = '/ajustes#linkedin';

export function isHttps(url: unknown): boolean {
  return typeof url === 'string' && /^https:\/\//i.test(url);
}

export function openLink(url: string | null | undefined): void {
  if (!url) return;
  if (isHttps(url)) {
    void Linking.openURL(url);
    return;
  }
  if (url.startsWith('/api/')) {
    void Linking.openURL(apiUrl(PWA_LINKEDIN));
    return;
  }
  const route = routeForUrl(url);
  if (!route) return;
  if (route.params[CAPTURE_HISTORY_PARAM] === '1') {
    openCaptureSheet(undefined, { view: 'history' });
    return;
  }
  router.push({ pathname: route.pathname as never, params: route.params });
}
