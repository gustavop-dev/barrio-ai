// The native transport of the shared client (compartido/src/api/client.ts): absolute URLs against
// EXPO_PUBLIC_API_URL and `Authorization: Bearer <device token>`. No cookies and no CSRF: the backend
// treats a bearer request as a human session. Importing this module installs it.
//
// JSON goes through the global fetch (expo/fetch). Multipart bodies (captures with audio or photos,
// gallery uploads) go through React Native's XMLHttpRequest instead: expo/fetch cannot send React
// Native's `{uri, name, type}` file parts (see ./multipart.ts).
import { setTransport, type Transport } from '@compartido/api/client';
import { apiUrl } from './config';
import { sendMultipart } from './multipart';
import { currentToken } from './token';

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
    return fetch(apiUrl(path), { method, headers: all, body, signal });
  },
};

setTransport(nativeTransport);
