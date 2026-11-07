// Same-origin JSON client for the Django backend: session cookie + CSRF header.
// The contract-level client (errors, lost session, `api`) lives in compartido/src/api/client.ts and is
// shared with the native app; this module installs the web transport and re-exports it unchanged.
import { isSafeMethod, setTransport, SESSION_PATH, type Transport, type TransportRequest } from '../../../compartido/src/api/client';

export { ApiError, api, extractDetail, LOGIN_PATH, onUnauthorized, request, SESSION_PATH } from '../../../compartido/src/api/client';
export type { RequestOptions } from '../../../compartido/src/api/client';

// Django: "CSRF Failed: CSRF token missing.", "CSRF Failed: Origin checking failed…"
const CSRF_FAILURE = /csrf failed|csrf token|csrf cookie/i;

export function readCookie(name: string, cookieString: string = document.cookie): string | null {
  for (const part of cookieString.split(';')) {
    const [rawKey, ...rest] = part.trim().split('=');
    if (rawKey === name) {
      try {
        return decodeURIComponent(rest.join('='));
      } catch {
        return rest.join('=');
      }
    }
  }
  return null;
}

function send(path: string, { method, headers, body, signal }: TransportRequest): Promise<Response> {
  const withCsrf = { ...headers };
  if (!isSafeMethod(method)) {
    const token = readCookie('csrftoken');
    if (token) withCsrf['X-CSRFToken'] = token;
  }
  return fetch(path, { method, headers: withCsrf, body, credentials: 'same-origin', signal });
}

/** The browser transport: relative URLs, the session cookie, and the CSRF header on unsafe methods. */
export const webTransport: Transport = {
  send,
  // A missing or rotated CSRF cookie: GET the session (which sets it) and retry once.
  async shouldRetry(response, detail, sent) {
    if (response.status !== 403 || isSafeMethod(sent.method) || !CSRF_FAILURE.test(detail)) return false;
    await send(SESSION_PATH, { method: 'GET', headers: { Accept: 'application/json' }, body: undefined, signal: undefined }).catch(() => undefined);
    return true;
  },
};

setTransport(webTransport);
