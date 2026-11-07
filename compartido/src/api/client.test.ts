// The shared client with a fake transport: the rules both apps rely on, whatever carries the request.
import { api, ApiError, extractDetail, onUnauthorized, request, setTransport, type Transport, type TransportRequest } from './client';

type Reply = { status: number; body?: unknown };

function response({ status, body }: Reply): Response {
  const text = body === undefined ? '' : JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name: string) => (name.toLowerCase() === 'content-type' && text ? 'application/json' : null) },
    text: async () => text,
  } as unknown as Response;
}

function fakeTransport(routes: Record<string, Reply | (() => Reply)>, extra: Partial<Transport> = {}) {
  const sent: { path: string; request: TransportRequest }[] = [];
  const transport: Transport = {
    send: async (path, req) => {
      sent.push({ path, request: req });
      const route = routes[`${req.method} ${path}`];
      if (!route) return response({ status: 404, body: { detail: 'No encontrado.' } });
      return response(typeof route === 'function' ? route() : route);
    },
    ...extra,
  };
  setTransport(transport);
  return sent;
}

afterEach(() => onUnauthorized(() => {}));

describe('shared API client', () => {
  it('encodes JSON bodies and asks for JSON, leaving authentication to the transport', async () => {
    const sent = fakeTransport({ 'POST /api/v1/operador/control': { status: 200, body: { paused: true } } });
    await expect(api.post('/api/v1/operador/control', { paused: true, reason: 'revisión' })).resolves.toEqual({ paused: true });
    expect(sent[0]!.request).toEqual({
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ paused: true, reason: 'revisión' }),
      signal: undefined,
    });
  });

  it('sends multipart bodies untouched and without a JSON Content-Type', async () => {
    const sent = fakeTransport({ 'POST /api/v1/capturas': { status: 201, body: { id: 'c1' } } });
    const form = new FormData();
    form.append('nota', 'hola');
    await api.postForm('/api/v1/capturas', form);
    expect(sent[0]!.request.body).toBe(form);
    expect(sent[0]!.request.headers['Content-Type']).toBeUndefined();
  });

  it('sends DELETE with a JSON body when given one (unregistering an Expo push token)', async () => {
    const sent = fakeTransport({ 'DELETE /api/v1/push/expo': { status: 204 } });
    await expect(api.delete('/api/v1/push/expo', { token: 'ExponentPushToken[x]' })).resolves.toBeNull();
    expect(sent[0]!.request.body).toBe(JSON.stringify({ token: 'ExponentPushToken[x]' }));
  });

  it('turns an error into an ApiError carrying the backend detail', async () => {
    fakeTransport({ 'POST /api/v1/operador/control': { status: 409, body: { detail: 'OPERATOR_PAUSED=true está en el entorno' } } });
    const error = await request('/api/v1/operador/control', { method: 'POST', body: {} }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, detail: 'OPERATOR_PAUSED=true está en el entorno' });
    expect(extractDetail(400, { note: ['Este campo es requerido.'] })).toBe('note: Este campo es requerido.');
  });

  it('calls the unauthorized handler on a 401, but not for the login endpoints', async () => {
    const unauthorized = jest.fn();
    onUnauthorized(unauthorized);
    fakeTransport({
      'GET /api/v1/tu-turno': { status: 401, body: { detail: 'Token inválido.' } },
      'POST /api/v1/auth/token': { status: 400, body: { detail: 'Credenciales incorrectas.' } },
    });
    await expect(api.get('/api/v1/tu-turno')).rejects.toMatchObject({ status: 401 });
    expect(unauthorized).toHaveBeenCalledTimes(1);
    await expect(api.post('/api/v1/auth/token', { username: 'g', password: 'x' })).rejects.toMatchObject({ status: 400 });
    expect(unauthorized).toHaveBeenCalledTimes(1);
  });

  it('treats a 403 as a lost session only when GET /auth/session says so', async () => {
    const unauthorized = jest.fn();
    onUnauthorized(unauthorized);
    let authenticated = false;
    fakeTransport({
      'GET /api/v1/operador/actions': { status: 403, body: { detail: 'Las credenciales no se proveyeron.' } },
      'GET /api/v1/auth/session': () => ({ status: 200, body: { authenticated, user: null } }),
    });
    await expect(api.get('/api/v1/operador/actions')).rejects.toMatchObject({ status: 401 });
    expect(unauthorized).toHaveBeenCalledTimes(1);
    authenticated = true;
    await expect(api.get('/api/v1/operador/actions')).rejects.toMatchObject({ status: 403 });
    expect(unauthorized).toHaveBeenCalledTimes(1);
  });

  it('lets the transport repeat a failed request once (the web CSRF refresh)', async () => {
    let attempts = 0;
    const shouldRetry = jest.fn(async (r: Response) => r.status === 403);
    fakeTransport(
      {
        'POST /api/v1/memory/proposals': () => {
          attempts += 1;
          return attempts === 1 ? { status: 403, body: { detail: 'CSRF Failed' } } : { status: 201, body: { id: 'm1' } };
        },
      },
      { shouldRetry },
    );
    await expect(api.post('/api/v1/memory/proposals', {})).resolves.toEqual({ id: 'm1' });
    expect(shouldRetry).toHaveBeenCalledTimes(1);
    expect(attempts).toBe(2);
  });
});
