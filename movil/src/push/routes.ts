// In-app paths (the PWA's: `data.url` of a push, a notification's `link`, a card's `href`) mapped to
// Expo Router. Only relative app paths are accepted; API routes and other origins never open in-app.

export interface AppRoute {
  pathname: string;
  params: Record<string, string>;
}

/** The capture_processed link: «Lo que enviaste» in the capture sheet. */
export const CAPTURE_HISTORY_PARAM = 'enviado';

export function isInAppPath(url: unknown): url is string {
  return typeof url === 'string' && url.startsWith('/') && !url.startsWith('//') && !url.startsWith('/api/');
}

/**
 * «/tu-turno#turno-question-7» → { pathname: '/tu-turno', params: { ancla: 'turno-question-7' } };
 * «/tu-turno/sabe» → the Sabe tab; «/?enviado=1» → Oficina with the capture history. Null when the
 * URL is not an app path.
 */
export function routeForUrl(url: unknown): AppRoute | null {
  if (!isInAppPath(url)) return null;
  const [beforeHash = '', hash = ''] = url.split('#', 2);
  const [rawPath = '/', query = ''] = beforeHash.split('?', 2);
  const params: Record<string, string> = {};
  for (const pair of query.split('&')) {
    if (!pair) continue;
    const [key = '', value = ''] = pair.split('=', 2);
    try {
      params[decodeURIComponent(key)] = decodeURIComponent(value.replace(/\+/g, ' '));
    } catch {
      params[key] = value;
    }
  }
  if (hash) params.ancla = decodeURIComponent(hash);
  let pathname = rawPath.replace(/\/+$/, '') || '/';
  if (pathname === '/conocimiento') pathname = '/';
  if (pathname === '/tu-turno/sabe') {
    pathname = '/tu-turno';
    params.tab = 'sabe';
  }
  const legacy = legacyCalendarRoute(pathname, params);
  if (legacy) return legacy;
  return { pathname, params };
}

/**
 * Old PWA paths that oficina/src/App.tsx redirects (without their query): /editorial/<id> and
 * /contenido/<id> (old piece pushes) open the piece; /contenido, /editorial and /maquina the calendar;
 * /acciones the calendar, or Tu turno for ?state=uncertain (the old target of an uncertain action).
 */
export function legacyCalendarRoute(pathname: string, params: Record<string, string>): AppRoute | null {
  const piece = /^\/(?:editorial|contenido)\/([^/]+)$/.exec(pathname);
  if (piece) return { pathname: `/calendario/pieza/${piece[1]}`, params: {} };
  if (pathname === '/editorial' || pathname === '/contenido' || pathname === '/maquina') return { pathname: '/calendario', params: {} };
  if (pathname === '/acciones') return { pathname: params.state === 'uncertain' ? '/tu-turno' : '/calendario', params: {} };
  return null;
}
