// A fake backend for the tests: global fetch answers per «METHOD /path» and records every request
// (absolute URL, headers, JSON body or multipart parts). Nothing leaves the process.
//
// Multipart uploads travel through React Native's XMLHttpRequest on the phone (src/api/multipart.ts),
// so a fake XMLHttpRequest is installed too. It hands each request to the same fetch mock (tests that
// hold a request with `fetch.mockImplementationOnce` hold an upload as well) and records `via: 'xhr'`.
// A route can answer `{ networkError: 'reason' }`: fetch rejects with a TypeError and the XHR fires
// `error` with that reason in `responseText`, as React Native's does. `{ fetchError: 'reason' }` is what
// the phone really does without a connection since `expo/fetch` became the global fetch: it rejects with
// expo's FetchError, a plain Error whose message is «fetch failed: <reason>» (not a TypeError).

export interface FakeReply {
  status?: number;
  body?: unknown;
  /** No HTTP answer: the request fails on the phone with this native reason. */
  networkError?: string;
  /** No HTTP answer, as expo/fetch fails on the phone: a FetchError («fetch failed: <reason>»). */
  fetchError?: string;
}

export type FakeHandler = FakeReply | ((request: SentRequest) => FakeReply);

export interface SentRequest {
  method: string;
  url: string;
  path: string;
  headers: Record<string, string>;
  /** Parsed JSON, or the multipart parts as [name, value] pairs. */
  body: unknown;
  /** How the app sent it: the global fetch, or XMLHttpRequest (multipart uploads). */
  via: 'fetch' | 'xhr';
}

interface FakeResponse {
  ok: boolean;
  status: number;
  headers: { get: (name: string) => string | null };
  text: () => Promise<string>;
}

class FakeNetworkError extends TypeError {
  readonly reason: string;
  constructor(reason: string) {
    super('Network request failed');
    this.reason = reason;
  }
}

/** expo/src/winter/fetch/FetchErrors.ts: `class FetchError extends Error`, message «fetch failed: …». */
class FakeFetchError extends Error {
  constructor(reason: string) {
    super(`fetch failed: ${reason}`);
  }
}

function reply({ status = 200, body = null, networkError, fetchError }: FakeReply, via: 'fetch' | 'xhr' = 'fetch'): FakeResponse {
  if (networkError !== undefined) throw new FakeNetworkError(networkError);
  if (fetchError !== undefined) throw via === 'xhr' ? new FakeNetworkError(fetchError) : new FakeFetchError(fetchError);
  const text = body === null || body === undefined || status === 204 ? '' : JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name: string) => (name.toLowerCase() === 'content-type' && text ? 'application/json' : null) },
    text: async () => text,
  };
}

function partsOf(form: FormData): [string, unknown][] {
  const withParts = form as unknown as { getParts?: () => { fieldName: string; string?: string; uri?: string; name?: string; type?: string }[]; _parts?: [string, unknown][] };
  if (typeof withParts.getParts === 'function') {
    return withParts.getParts().map((part) => [part.fieldName, part.uri ? { uri: part.uri, name: part.name, type: part.type } : part.string]);
  }
  return withParts._parts ?? [];
}

type FetchInit = { method?: string; headers?: Record<string, string>; body?: unknown; via?: 'xhr' };

/** React Native's XMLHttpRequest as src/api/multipart.ts uses it, answered by the fake fetch. */
class FakeXMLHttpRequest {
  status = 0;
  statusText = '';
  responseText = '';
  readyState = 0;
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  onabort: (() => void) | null = null;
  private method = 'GET';
  private url = '';
  private headers: Record<string, string> = {};
  private contentType: string | null = null;
  private aborted = false;

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
    this.readyState = 1;
  }

  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }

  getAllResponseHeaders() {
    return this.contentType ? `content-type: ${this.contentType}\r\n` : '';
  }

  getResponseHeader(name: string) {
    return name.toLowerCase() === 'content-type' ? this.contentType : null;
  }

  abort() {
    if (this.readyState === 4) return;
    this.aborted = true;
    this.readyState = 4;
    this.onabort?.();
  }

  send(body: unknown) {
    const fetchFn = (globalThis as unknown as { fetch: (url: string, init: FetchInit) => Promise<FakeResponse> }).fetch;
    void Promise.resolve()
      .then(() => fetchFn(this.url, { method: this.method, headers: this.headers, body, via: 'xhr' }))
      .then(
        async (response) => {
          const text = await response.text();
          if (this.aborted) return;
          this.status = response.status;
          this.responseText = text;
          this.contentType = response.headers.get('content-type');
          this.readyState = 4;
          this.onload?.();
        },
        (error: unknown) => {
          if (this.aborted) return;
          this.responseText = error instanceof FakeNetworkError ? error.reason : '';
          this.readyState = 4;
          this.onerror?.();
        },
      );
  }
}

export function fakeServer(routes: Record<string, FakeHandler> = {}) {
  const table = new Map(Object.entries({ 'GET /api/v1/referentes/revisiones': { body: [] }, ...routes }));
  const requests: SentRequest[] = [];
  const fetchMock = jest.fn(async (input: string, init: FetchInit = {}) => {
    const url = String(input);
    const path = url.replace(/^https?:\/\/[^/]+/, '');
    const method = (init.method ?? 'GET').toUpperCase();
    const headers = Object.fromEntries(Object.entries(init.headers ?? {}).map(([k, v]) => [k.toLowerCase(), String(v)]));
    let body: unknown = init.body ?? null;
    if (typeof body === 'string') {
      try {
        body = JSON.parse(body);
      } catch {
        // keep the text
      }
    } else if (body && typeof FormData !== 'undefined' && body instanceof FormData) {
      body = partsOf(body);
    }
    const sent: SentRequest = { method, url, path, headers, body, via: init.via ?? 'fetch' };
    requests.push(sent);
    const pathOnly = path.split('?')[0];
    const handler = table.get(`${method} ${path}`) ?? table.get(`${method} ${pathOnly}`);
    if (!handler) return reply({ status: 404, body: { detail: `Sin ruta de prueba para ${method} ${path}` } });
    return reply(typeof handler === 'function' ? handler(sent) : handler, sent.via);
  });
  (globalThis as unknown as { fetch: unknown }).fetch = fetchMock;
  (globalThis as unknown as { XMLHttpRequest: unknown }).XMLHttpRequest = FakeXMLHttpRequest;
  return {
    requests,
    fetch: fetchMock,
    on(route: string, handler: FakeHandler) {
      table.set(route, handler);
    },
    find(method: string, path: string) {
      return requests.filter((r) => r.method === method && r.path.split('?')[0] === path);
    },
  };
}
