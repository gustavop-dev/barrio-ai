// A fake backend for the tests: global fetch answers per «METHOD /path» and records every request
// (absolute URL, headers, JSON body or multipart parts). Nothing leaves the process.

export interface FakeReply {
  status?: number;
  body?: unknown;
}

export type FakeHandler = FakeReply | ((request: SentRequest) => FakeReply);

export interface SentRequest {
  method: string;
  url: string;
  path: string;
  headers: Record<string, string>;
  /** Parsed JSON, or the multipart parts as [name, value] pairs. */
  body: unknown;
}

function reply({ status = 200, body = null }: FakeReply) {
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

export function fakeServer(routes: Record<string, FakeHandler> = {}) {
  const table = new Map(Object.entries(routes));
  const requests: SentRequest[] = [];
  const fetchMock = jest.fn(async (input: string, init: { method?: string; headers?: Record<string, string>; body?: unknown } = {}) => {
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
    const sent: SentRequest = { method, url, path, headers, body };
    requests.push(sent);
    const pathOnly = path.split('?')[0];
    const handler = table.get(`${method} ${path}`) ?? table.get(`${method} ${pathOnly}`);
    if (!handler) return reply({ status: 404, body: { detail: `Sin ruta de prueba para ${method} ${path}` } });
    return reply(typeof handler === 'function' ? handler(sent) : handler);
  });
  (globalThis as unknown as { fetch: unknown }).fetch = fetchMock;
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
