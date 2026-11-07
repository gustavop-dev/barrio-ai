// The native transport of the shared client (compartido/src/api/client.ts): absolute URLs against
// EXPO_PUBLIC_API_URL and `Authorization: Bearer <device token>`. No cookies and no CSRF: the backend
// treats a bearer request as a human session. Importing this module installs it.
import { setTransport, type Transport } from '@compartido/api/client';
import { apiUrl } from './config';
import { currentToken } from './token';

/** Headers that authenticate a request outside the client (images, audio). */
export function authHeaders(): Record<string, string> {
  const token = currentToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export const nativeTransport: Transport = {
  send(path, { method, headers, body, signal }) {
    return fetch(apiUrl(path), { method, headers: { ...headers, ...authHeaders() }, body, signal });
  },
};

setTransport(nativeTransport);
