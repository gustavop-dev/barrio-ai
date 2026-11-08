// Multipart uploads (a capture with audio or photos, «Subir fotos») go through React Native's own
// XMLHttpRequest, not the global fetch.
//
// Why: since SDK 52 Expo installs `expo/fetch` as the global fetch on Android and iOS
// (docs.expo.dev/versions/v58.0.0/sdk/expo: «On Android and iOS, `expo/fetch` is also installed as the
// global `fetch`»). expo/fetch turns a FormData into bytes in JavaScript and does not support React
// Native's `{uri, name, type}` file parts: `expo/src/winter/fetch/convertFormData.ts` says «`uri` is not
// supported for React Native's FormData» and throws `Unsupported FormDataPart implementation` before
// the request starts. So every capture with a voice note or a photo failed on the phone and never
// reached the server, while text-only captures (string parts) went through.
//
// React Native's XMLHttpRequest hands the parts to the native networking module, which streams each
// `file://` or `content://` part from disk (no copy of the audio in JavaScript memory). On a network
// failure it leaves the native reason in `responseText` («Could not retrieve file for uri …», «Unable
// to resolve host …»): UploadNetworkError carries it so the sheet can show it and the app can report it.

import { onlineManager } from '@tanstack/react-query';

/** The reason of an upload refused because the phone has no network (NetInfo, through TanStack's onlineManager). */
export const OFFLINE_REASON = 'offline';

/** The request the shared client hands the transport, with a multipart body. */
export interface MultipartRequest {
  method: string;
  headers: Record<string, string>;
  body: FormData;
  signal?: AbortSignal;
}

/** The upload never got an HTTP answer: no network, or the phone could not read a file part. */
export class UploadNetworkError extends TypeError {
  /** What the native networking said, if anything (no file contents, at most a local path). */
  readonly reason: string;

  constructor(reason: string) {
    super(reason ? `Network request failed: ${reason}` : 'Network request failed');
    this.name = 'UploadNetworkError';
    this.reason = reason;
  }
}

/** The native side failed before sending: it could not open or type a file part. */
export function isFilePartFailure(error: unknown): boolean {
  return error instanceof UploadNetworkError && /retrieve file|content-type header|FormData part|valid file uri|ENOENT|No such file|FileNotFound/i.test(error.reason);
}

function abortError(): Error {
  const error = new Error('Aborted');
  error.name = 'AbortError';
  return error;
}

/** The response text (on a network failure, React Native puts the native reason there). */
function textOf(xhr: XMLHttpRequest): string {
  try {
    return typeof xhr.responseText === 'string' ? xhr.responseText : '';
  } catch {
    return '';
  }
}

function headersOf(xhr: XMLHttpRequest): Map<string, string> {
  const headers = new Map<string, string>();
  for (const line of (xhr.getAllResponseHeaders() || '').split(/\r?\n/)) {
    const at = line.indexOf(':');
    if (at > 0) headers.set(line.slice(0, at).trim().toLowerCase(), line.slice(at + 1).trim());
  }
  return headers;
}

/** What the shared client reads from a response (ok, status, a header and the text), from an XHR. */
function toResponse(xhr: XMLHttpRequest): Response {
  const text = textOf(xhr);
  const headers = headersOf(xhr);
  return {
    ok: xhr.status >= 200 && xhr.status < 300,
    status: xhr.status,
    statusText: xhr.statusText,
    headers: { get: (name: string) => headers.get(name.toLowerCase()) ?? null },
    text: async () => text,
    json: async () => JSON.parse(text),
  } as unknown as Response;
}

/** Sends a multipart request with React Native's XMLHttpRequest and resolves with its response. */
export function sendMultipart(url: string, { method, headers, body, signal }: MultipartRequest): Promise<Response> {
  return new Promise<Response>((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortError());
      return;
    }
    // Without network the native request can wait for one indefinitely: say so at once instead.
    if (!onlineManager.isOnline()) {
      reject(new UploadNetworkError(OFFLINE_REASON));
      return;
    }
    const xhr = new XMLHttpRequest();
    const onAbort = () => xhr.abort();
    const settle = () => signal?.removeEventListener('abort', onAbort);
    signal?.addEventListener('abort', onAbort);
    xhr.onload = () => {
      settle();
      resolve(toResponse(xhr));
    };
    xhr.onerror = () => {
      settle();
      reject(new UploadNetworkError(textOf(xhr).slice(0, 300)));
    };
    xhr.ontimeout = () => {
      settle();
      reject(new UploadNetworkError('timeout'));
    };
    xhr.onabort = () => {
      settle();
      reject(abortError());
    };
    xhr.open(method, url, true);
    // No Content-Type: the native side writes multipart/form-data with its boundary.
    for (const [name, value] of Object.entries(headers)) {
      if (name.toLowerCase() !== 'content-type') xhr.setRequestHeader(name, value);
    }
    xhr.send(body);
  });
}
