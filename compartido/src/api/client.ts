// JSON client for the Django backend, shared by the PWA (oficina/) and the native app (movil/).
// It knows the contract (JSON in and out, `{detail}` errors, what a lost session looks like) but not
// how a request travels: each app installs a Transport with `setTransport` before the first request.
// - Web (oficina/src/api/client.ts): same-origin fetch with the session cookie and the CSRF header.
// - Native (movil/src/api/transporte.ts): absolute URL with `Authorization: Bearer <device token>`.

export const SESSION_PATH = '/api/v1/auth/session';
export const LOGIN_PATH = '/api/v1/auth/login';
export const TOKEN_PATH = '/api/v1/auth/token';
const AUTH_PATHS = new Set([SESSION_PATH, LOGIN_PATH, TOKEN_PATH]);

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

export function isSafeMethod(method: string): boolean {
  return SAFE_METHODS.has(method.toUpperCase());
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly data: unknown;

  constructor(status: number, detail: string, data: unknown = null) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.data = data;
  }
}

/** What the core hands the transport: method in upper case, the JSON headers and the encoded body. */
export interface TransportRequest {
  method: string;
  headers: Record<string, string>;
  body: string | FormData | undefined;
  signal: AbortSignal | undefined;
}

export interface Transport {
  /** Sends one request to an API path (`/api/v1/...`), adding whatever authenticates it. */
  send(path: string, request: TransportRequest): Promise<Response>;
  /**
   * Called once for a failed response before the usual handling. Returning true repeats the request
   * one time (the web transport uses it to refresh a missing or rotated CSRF cookie).
   */
  shouldRetry?(response: Response, detail: string, request: TransportRequest): Promise<boolean>;
}

let transport: Transport | null = null;

/** Each app installs its transport once, at start-up, before any request. */
export function setTransport(next: Transport): void {
  transport = next;
}

function currentTransport(): Transport {
  if (!transport) throw new Error('No hay transporte HTTP configurado: llama a setTransport() al arrancar la app.');
  return transport;
}

let unauthorizedHandler: () => void = () => {};

/** The auth provider registers how a lost session sends the user to the login. */
export function onUnauthorized(handler: () => void): () => void {
  unauthorizedHandler = handler;
  return () => {
    if (unauthorizedHandler === handler) unauthorizedHandler = () => {};
  };
}

const FALLBACK: Record<number, string> = {
  400: 'Los datos enviados no son válidos.',
  401: 'Tu sesión ha caducado. Vuelve a entrar.',
  403: 'No tienes permiso para esta acción.',
  404: 'No encontrado.',
  409: 'La acción entra en conflicto con el estado actual.',
  429: 'Demasiadas peticiones. Espera un momento y vuelve a intentarlo.',
};

/** `{detail}` per the contract; DRF validation errors arrive as `{field: [msg]}`. */
export function extractDetail(status: number, data: unknown): string {
  if (data && typeof data === 'object') {
    const record = data as Record<string, unknown>;
    if (typeof record.detail === 'string' && record.detail) return record.detail;
    const parts: string[] = [];
    for (const [field, value] of Object.entries(record)) {
      const messages = Array.isArray(value) ? value.map(String) : [String(value)];
      parts.push(field === 'non_field_errors' ? messages.join(' ') : `${field}: ${messages.join(' ')}`);
    }
    if (parts.length) return parts.join(' · ');
  }
  if (typeof data === 'string' && data.trim() && !data.trim().startsWith('<')) return data.trim();
  return FALLBACK[status] ?? (status >= 500 ? 'El servidor no pudo completar la petición.' : `Error ${status}.`);
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
}

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204 || response.status === 205) return null;
  const text = await response.text();
  if (!text) return null;
  const type = response.headers.get('content-type') ?? '';
  if (type.includes('json')) {
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  }
  return text;
}

/** A multipart body: the platform writes its Content-Type with the boundary, so the client must not set one. */
function isFormData(body: unknown): body is FormData {
  return typeof FormData !== 'undefined' && body instanceof FormData;
}

function encode({ method = 'GET', body, signal }: RequestOptions): TransportRequest {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined && !isFormData(body)) headers['Content-Type'] = 'application/json';
  return {
    method: method.toUpperCase(),
    headers,
    body: body === undefined ? undefined : isFormData(body) ? body : JSON.stringify(body),
    signal,
  };
}

function send(path: string, options: RequestOptions): Promise<Response> {
  return currentTransport().send(path, encode(options));
}

/** A 403 is either "no session" (go to login) or "no permission" (show detail). */
async function sessionIsGone(): Promise<boolean> {
  try {
    const response = await send(SESSION_PATH, {});
    if (!response.ok) return response.status === 401 || response.status === 403;
    const data = (await parseBody(response)) as { authenticated?: boolean } | null;
    return !data?.authenticated;
  } catch {
    return false;
  }
}

export async function request<T>(path: string, options: RequestOptions = {}, retried = false): Promise<T> {
  const encoded = encode(options);
  const active = currentTransport();
  const response = await active.send(path, encoded);
  const data = await parseBody(response);
  if (response.ok) return data as T;

  const detail = extractDetail(response.status, data);
  const error = new ApiError(response.status, detail, data);

  if (!retried && active.shouldRetry && (await active.shouldRetry(response, detail, encoded))) {
    return request<T>(path, options, true);
  }
  if (AUTH_PATHS.has(path)) throw error;

  if (response.status === 401) {
    unauthorizedHandler();
    throw error;
  }
  if (response.status === 403 && (await sessionIsGone())) {
    unauthorizedHandler();
    throw new ApiError(401, FALLBACK[401]!, data);
  }
  throw error;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body: body ?? {} }),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: 'PUT', body }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: 'PATCH', body }),
  /** DELETE, with an optional JSON body (`DELETE /api/v1/push/expo` takes `{token}`). */
  delete: <T = null>(path: string, body?: unknown) => request<T>(path, body === undefined ? { method: 'DELETE' } : { method: 'DELETE', body }),
  /** multipart/form-data upload (captures, gallery photos): no JSON Content-Type. */
  postForm: <T>(path: string, form: FormData) => request<T>(path, { method: 'POST', body: form }),
};
