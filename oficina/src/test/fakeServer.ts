// A tiny in-memory backend for tests: routes "METHOD /path" to handlers and
// records every request, standing in for the Django API of CONTRATO-API.md.
import { vi } from 'vitest';

export interface RecordedRequest {
  method: string;
  path: string;
  search: URLSearchParams;
  headers: Record<string, string>;
  credentials: RequestCredentials | undefined;
  body: unknown;
}

export interface Reply {
  status?: number;
  body?: unknown;
}

export type Handler = (request: RecordedRequest) => Reply | Promise<Reply>;

export function fakeServer(routes: Record<string, Handler | Reply>) {
  const requests: RecordedRequest[] = [];
  const table = new Map<string, Handler | Reply>(Object.entries({ 'GET /api/v1/referentes/revisiones': { body: [] }, ...routes }));

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, 'http://localhost');
    const method = (init.method ?? 'GET').toUpperCase();
    const headers: Record<string, string> = {};
    new Headers(init.headers).forEach((value, key) => {
      headers[key.toLowerCase()] = value;
    });
    let body: unknown = undefined;
    if (typeof init.body === 'string') {
      try {
        body = JSON.parse(init.body);
      } catch {
        body = init.body;
      }
    }
    const request: RecordedRequest = { method, path: url.pathname, search: url.searchParams, headers, credentials: init.credentials, body };
    requests.push(request);
    const route = table.get(`${method} ${url.pathname}`);
    if (!route) return json(404, { detail: `Sin ruta simulada: ${method} ${url.pathname}` });
    const reply = typeof route === 'function' ? await route(request) : route;
    return json(reply.status ?? 200, reply.body);
  });

  vi.stubGlobal('fetch', fetchMock);

  return {
    requests,
    fetch: fetchMock,
    on(key: string, handler: Handler | Reply) {
      table.set(key, handler);
    },
    find(method: string, path: string) {
      return requests.filter((r) => r.method === method && r.path === path);
    },
  };
}

function json(status: number, body: unknown): Response {
  if (status === 204 || body === undefined) return new Response(null, { status });
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

export const SESSION_OK = {
  authenticated: true,
  user: { username: 'gustavo', is_superuser: true, permissions: ['approve_actions', 'operate_linkedin'] },
};
export const SESSION_NONE = { authenticated: false, user: null };
