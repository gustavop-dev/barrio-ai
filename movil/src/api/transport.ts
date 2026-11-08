// The native transport of the shared client (compartido/src/api/client.ts): absolute URLs against
// EXPO_PUBLIC_API_URL and `Authorization: Bearer <device token>`. No cookies and no CSRF: the backend
// treats a bearer request as a human session. Importing this module installs it.
//
// JSON goes through the global fetch (expo/fetch). Multipart bodies (captures with audio or photos,
// gallery uploads) go through React Native's XMLHttpRequest instead: expo/fetch cannot send React
// Native's `{uri, name, type}` file parts (see ./multipart.ts).
//
// A request that gets no HTTP answer (no connection, host unreachable) rejects with NetworkError, a
// TypeError, like React Native's own fetch did. expo/fetch rejects with its FetchError instead, a plain
// Error whose message is «fetch failed: <the system's reason in English>»: every screen showed that text,
// the login did not say «no connection» and an offline start logged Gustavo out, because the shared
// client, the login and the session tell «no connection» by `instanceof TypeError` (APP-08, ACC-06).
import { setTransport, type Transport } from '@compartido/api/client';
import { apiUrl } from './config';
import { sendMultipart } from './multipart';
import { currentToken } from './token';

/** A request that never got an HTTP answer. The system's reason is kept for diagnosis, never shown. */
export class NetworkError extends TypeError {
  readonly reason: string;

  constructor(reason: string) {
    super('Network request failed');
    this.name = 'NetworkError';
    this.reason = reason;
  }
}

/** What fetch rejected with, as the app tells it apart: a cancellation stays itself, anything else is no answer. */
export function asNetworkError(error: unknown, signal: AbortSignal | undefined): unknown {
  if (signal?.aborted || (error instanceof Error && error.name === 'AbortError')) return error;
  if (error instanceof TypeError) return error;
  return new NetworkError(error instanceof Error ? error.message : String(error));
}

/** Headers that authenticate a request outside the client (images, audio). */
export function authHeaders(): Record<string, string> {
  const token = currentToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function isFormData(body: unknown): body is FormData {
  return typeof FormData !== 'undefined' && body instanceof FormData;
}

export const nativeTransport: Transport = {
  send(path, { method, headers, body, signal }) {
    const all = { ...headers, ...authHeaders() };
    if (isFormData(body)) return sendMultipart(apiUrl(path), { method, headers: all, body, signal });
    return fetch(apiUrl(path), { method, headers: all, body, signal }).catch((error: unknown) => {
      throw asNetworkError(error, signal);
    });
  },
};

setTransport(nativeTransport);
