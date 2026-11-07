// Same-origin JSON client for the Django backend: session cookie + CSRF header.

export const SESSION_PATH = '/api/v1/auth/session';
export const LOGIN_PATH = '/api/v1/auth/login';
const AUTH_PATHS = new Set([SESSION_PATH, LOGIN_PATH]);

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);
// Django: "CSRF Failed: CSRF token missing.", "CSRF Failed: Origin checking failed…"
const CSRF_FAILURE = /csrf failed|csrf token|csrf cookie/i;

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

let unauthorizedHandler: () => void = () => {};

/** The auth provider registers how a lost session sends the user to /login. */
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

/** A multipart body: the browser writes its Content-Type with the boundary, so the client must not set one. */
function isFormData(body: unknown): body is FormData {
  return typeof FormData !== 'undefined' && body instanceof FormData;
}

function send(path: string, { method = 'GET', body, signal }: RequestOptions): Promise<Response> {
  const upper = method.toUpperCase();
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined && !isFormData(body)) headers['Content-Type'] = 'application/json';
  if (!SAFE_METHODS.has(upper)) {
    const token = readCookie('csrftoken');
    if (token) headers['X-CSRFToken'] = token;
  }
  return fetch(path, {
    method: upper,
    headers,
    body: body === undefined ? undefined : isFormData(body) ? body : JSON.stringify(body),
    credentials: 'same-origin',
    signal,
  });
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
  const response = await send(path, options);
  const data = await parseBody(response);
  if (response.ok) return data as T;

  const detail = extractDetail(response.status, data);
  const error = new ApiError(response.status, detail, data);
  const unsafe = !SAFE_METHODS.has((options.method ?? 'GET').toUpperCase());

  // A missing or rotated CSRF cookie: GET the session (which sets it) and retry once.
  if (response.status === 403 && unsafe && !retried && CSRF_FAILURE.test(detail)) {
    await send(SESSION_PATH, {}).catch(() => undefined);
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
  delete: <T = null>(path: string) => request<T>(path, { method: 'DELETE' }),
  /** multipart/form-data upload (captures, gallery photos): CSRF header, no JSON Content-Type. */
  postForm: <T>(path: string, form: FormData) => request<T>(path, { method: 'POST', body: form }),
};
