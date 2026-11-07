import { afterEach, describe, expect, it, vi } from 'vitest';
import { fakeServer, SESSION_NONE, SESSION_OK } from '../test/fakeServer';
import { ApiError, extractDetail, onUnauthorized, readCookie, request } from './client';

afterEach(() => onUnauthorized(() => {}));

describe('readCookie', () => {
  it('reads and decodes one cookie among several', () => {
    expect(readCookie('csrftoken', 'sessionid=abc; csrftoken=tok%3D1; other=x')).toBe('tok=1');
    expect(readCookie('missing', 'a=1')).toBeNull();
  });
});

describe('request', () => {
  it('sends GET same-origin without a CSRF header', async () => {
    document.cookie = 'csrftoken=secret-token';
    const server = fakeServer({ 'GET /api/v1/operador/overview': { body: { ok: true } } });
    await expect(request('/api/v1/operador/overview')).resolves.toEqual({ ok: true });
    const [sent] = server.requests;
    expect(sent?.credentials).toBe('same-origin');
    expect(sent?.headers['x-csrftoken']).toBeUndefined();
  });

  it('adds X-CSRFToken from the csrftoken cookie and a JSON body on POST', async () => {
    document.cookie = 'csrftoken=secret-token';
    const server = fakeServer({ 'POST /api/v1/operador/control': { body: { paused: true } } });
    await request('/api/v1/operador/control', { method: 'POST', body: { paused: true, reason: 'revisión' } });
    const [sent] = server.requests;
    expect(sent?.headers['x-csrftoken']).toBe('secret-token');
    expect(sent?.headers['content-type']).toBe('application/json');
    expect(sent?.credentials).toBe('same-origin');
    expect(sent?.body).toEqual({ paused: true, reason: 'revisión' });
  });

  it('turns a 409 into an ApiError carrying the backend detail', async () => {
    fakeServer({ 'POST /api/v1/operador/control': { status: 409, body: { detail: 'OPERATOR_PAUSED=true está en el entorno' } } });
    const error = await request('/api/v1/operador/control', { method: 'POST', body: {} }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(409);
    expect((error as ApiError).detail).toBe('OPERATOR_PAUSED=true está en el entorno');
  });

  it('flattens DRF field errors into one readable detail', () => {
    expect(extractDetail(400, { note: ['Este campo es requerido.'] })).toBe('note: Este campo es requerido.');
    expect(extractDetail(500, null)).toMatch(/servidor/);
  });

  it('sends the user to login on 401', async () => {
    const unauthorized = vi.fn();
    onUnauthorized(unauthorized);
    fakeServer({ 'GET /api/v1/memory': { status: 401, body: { detail: 'No autenticado' } } });
    await expect(request('/api/v1/memory')).rejects.toMatchObject({ status: 401 });
    expect(unauthorized).toHaveBeenCalledOnce();
  });

  it('treats a 403 as a lost session only when the session check says so', async () => {
    const unauthorized = vi.fn();
    onUnauthorized(unauthorized);
    const server = fakeServer({
      'GET /api/v1/operador/actions': { status: 403, body: { detail: 'Las credenciales no se proveyeron.' } },
      'GET /api/v1/auth/session': { body: SESSION_NONE },
    });
    await expect(request('/api/v1/operador/actions')).rejects.toMatchObject({ status: 401 });
    expect(unauthorized).toHaveBeenCalledOnce();

    unauthorized.mockClear();
    server.on('GET /api/v1/auth/session', { body: SESSION_OK });
    server.on('POST /api/v1/operador/actions/a1/approve', { status: 403, body: { detail: 'Esta decisión requiere una sesión humana con CSRF' } });
    const error = await request('/api/v1/operador/actions/a1/approve', { method: 'POST', body: {} }).catch((e: unknown) => e);
    expect((error as ApiError).status).toBe(403);
    expect((error as ApiError).detail).toMatch(/sesión humana/);
    expect(unauthorized).not.toHaveBeenCalled();
    // A permission refusal is not a CSRF failure: no blind retry of the POST.
    expect(server.find('POST', '/api/v1/operador/actions/a1/approve')).toHaveLength(1);
  });

  it('refreshes the CSRF cookie and retries once after a CSRF failure', async () => {
    document.cookie = 'csrftoken=old';
    let attempts = 0;
    const server = fakeServer({
      'GET /api/v1/auth/session': () => {
        document.cookie = 'csrftoken=fresh';
        return { body: SESSION_OK };
      },
      'POST /api/v1/memory/proposals': () => {
        attempts += 1;
        return attempts === 1 ? { status: 403, body: { detail: 'CSRF Failed: CSRF token incorrect.' } } : { status: 201, body: { id: 'm1', version: 1, status: 'proposed' } };
      },
    });
    await expect(request('/api/v1/memory/proposals', { method: 'POST', body: {} })).resolves.toMatchObject({ id: 'm1' });
    const posts = server.find('POST', '/api/v1/memory/proposals');
    expect(posts.map((p) => p.headers['x-csrftoken'])).toEqual(['old', 'fresh']);
  });
});
