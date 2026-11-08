// The native transport: absolute URLs, the bearer token, no cookies and no CSRF.
import { api, onUnauthorized } from '@compartido/api/client';
import { captureForm } from '@compartido/api/capturas';
import { errorMessage } from '@compartido/api/errors';
import { problemOf } from '@/auth/loginProblems';
import { fakeServer } from '@/test/server';
import { API_URL, apiUrl } from './config';
import { isFilePartFailure, UploadNetworkError } from './multipart';
import { clearToken, saveToken } from './token';
import './transport';

afterEach(async () => {
  onUnauthorized(() => {});
  await clearToken();
});

describe('native transport', () => {
  it('calls the production API by default (EXPO_PUBLIC_API_URL unset)', () => {
    expect(API_URL).toBe('https://office.projectapp.co');
    expect(apiUrl('/api/v1/tu-turno')).toBe('https://office.projectapp.co/api/v1/tu-turno');
  });

  it('sends the device token as a bearer token and never a CSRF header', async () => {
    await saveToken('0ff1ce_dt_prueba');
    const server = fakeServer({ 'POST /api/v1/preguntas/q1/mas-tarde': { body: { id: 'q1' } } });
    await api.post('/api/v1/preguntas/q1/mas-tarde');
    const [sent] = server.requests;
    expect(sent?.url).toBe('https://office.projectapp.co/api/v1/preguntas/q1/mas-tarde');
    expect(sent?.headers.authorization).toBe('Bearer 0ff1ce_dt_prueba');
    expect(sent?.headers['x-csrftoken']).toBeUndefined();
    expect(sent?.headers['content-type']).toBe('application/json');
  });

  it('sends no Authorization header before login', async () => {
    const server = fakeServer({ 'GET /api/v1/auth/session': { body: { authenticated: false, user: null } } });
    await api.get('/api/v1/auth/session');
    expect(server.requests[0]?.headers.authorization).toBeUndefined();
  });

  it('uploads a capture as multipart with React Native file parts', async () => {
    await saveToken('0ff1ce_dt_prueba');
    const server = fakeServer({ 'POST /api/v1/capturas': { status: 201, body: { id: 'c1' } } });
    const form = captureForm({
      audio: { blob: { uri: 'file:///cache/a.m4a', name: 'captura.m4a', type: 'audio/mp4' }, filename: 'captura.m4a', durationS: 4.24 },
      fotos: [{ uri: 'file:///cache/f.jpg', name: 'f.jpg', type: 'image/jpeg' }],
      nota: '  una idea  ',
      para: 'post',
    });
    await expect(api.postForm('/api/v1/capturas', form)).resolves.toEqual({ id: 'c1' });
    const [sent] = server.requests;
    // React Native's XMLHttpRequest, not expo/fetch (which throws on `{uri}` parts).
    expect(sent?.via).toBe('xhr');
    expect(sent?.url).toBe('https://office.projectapp.co/api/v1/capturas');
    expect(sent?.headers['content-type']).toBeUndefined();
    expect(sent?.headers.authorization).toBe('Bearer 0ff1ce_dt_prueba');
    expect(sent?.body).toEqual([
      ['audio', { uri: 'file:///cache/a.m4a', name: 'captura.m4a', type: 'audio/mp4' }],
      ['audio_duration_s', '4.2'],
      ['fotos', { uri: 'file:///cache/f.jpg', name: 'f.jpg', type: 'image/jpeg' }],
      ['nota', 'una idea'],
      ['para', 'post'],
    ]);
  });

  it('JSON keeps going through fetch', async () => {
    const server = fakeServer({ 'POST /api/v1/preguntas/q1/mas-tarde': { body: { id: 'q1' } } });
    await api.post('/api/v1/preguntas/q1/mas-tarde');
    expect(server.requests[0]?.via).toBe('fetch');
  });

  it('a multipart error answer reaches the client as an ApiError with the server detail', async () => {
    await saveToken('0ff1ce_dt_prueba');
    fakeServer({ 'POST /api/v1/capturas': { status: 400, body: { detail: 'Tipo de audio no admitido: desconocido.' } } });
    const form = captureForm({ audio: { blob: { uri: 'file:///cache/a.m4a', name: 'captura.m4a', type: 'audio/mp4' }, filename: 'captura.m4a', durationS: 1 } });
    await expect(api.postForm('/api/v1/capturas', form)).rejects.toMatchObject({ name: 'ApiError', status: 400, detail: 'Tipo de audio no admitido: desconocido.' });
  });

  it('an upload that never left the phone carries the native reason', async () => {
    await saveToken('0ff1ce_dt_prueba');
    fakeServer({ 'POST /api/v1/capturas': { networkError: 'Could not retrieve file for uri /cache/a.m4a' } });
    const form = captureForm({ audio: { blob: { uri: 'file:///cache/a.m4a', name: 'captura.m4a', type: 'audio/mp4' }, filename: 'captura.m4a', durationS: 1 } });
    const error = await api.postForm('/api/v1/capturas', form).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(UploadNetworkError);
    expect(error).toBeInstanceOf(TypeError);
    expect((error as UploadNetworkError).reason).toBe('Could not retrieve file for uri /cache/a.m4a');
    expect(isFilePartFailure(error)).toBe(true);
    expect(isFilePartFailure(new UploadNetworkError('Unable to resolve host "office.projectapp.co"'))).toBe(false);
  });

  it('a 401 (revoked or unknown token) reaches the unauthorized handler', async () => {
    await saveToken('0ff1ce_dt_revocado');
    const unauthorized = jest.fn();
    onUnauthorized(unauthorized);
    fakeServer({ 'GET /api/v1/tu-turno': { status: 401, body: { detail: 'Token inválido.' } } });
    await expect(api.get('/api/v1/tu-turno')).rejects.toMatchObject({ status: 401 });
    expect(unauthorized).toHaveBeenCalledTimes(1);
  });

  // APP-08: since expo/fetch is the global fetch, a request without a connection rejects with expo's FetchError
  // («fetch failed: …», a plain Error). Every screen used to show that English text, and the login and the start-up
  // did not recognise it as «no connection».
  it('a request without a connection reaches the app as a network failure, in Spanish (not «fetch failed»)', async () => {
    await saveToken('0ff1ce_dt_prueba');
    fakeServer({ 'GET /api/v1/tu-turno': { fetchError: 'Failed to connect to /10.0.2.2:8787' } });
    const error = await api.get('/api/v1/tu-turno').catch((e: unknown) => e);
    expect(error).toBeInstanceOf(TypeError);
    expect(errorMessage(error)).toBe('No hay conexión con el servidor. Comprueba tu red.');
    expect(problemOf(error)).toBe('offline');
    expect(String((error as Error).message)).not.toMatch(/^fetch failed/);
  });

  it('a request the app cancelled stays a cancellation, not «no connection»', async () => {
    fakeServer({ 'GET /api/v1/tu-turno': { fetchError: 'The operation was aborted.' } });
    const controller = new AbortController();
    controller.abort();
    const error = await api.get('/api/v1/tu-turno', controller.signal).catch((e: unknown) => e);
    expect(error).not.toBeInstanceOf(TypeError);
  });
});
