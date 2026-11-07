// The native transport: absolute URLs, the bearer token, no cookies and no CSRF.
import { api, onUnauthorized } from '@compartido/api/client';
import { captureForm } from '@compartido/api/capturas';
import { fakeServer } from '@/test/server';
import { API_URL, apiUrl } from './config';
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
    await api.postForm('/api/v1/capturas', form);
    const [sent] = server.requests;
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

  it('a 401 (revoked or unknown token) reaches the unauthorized handler', async () => {
    await saveToken('0ff1ce_dt_revocado');
    const unauthorized = jest.fn();
    onUnauthorized(unauthorized);
    fakeServer({ 'GET /api/v1/tu-turno': { status: 401, body: { detail: 'Token inválido.' } } });
    await expect(api.get('/api/v1/tu-turno')).rejects.toMatchObject({ status: 401 });
    expect(unauthorized).toHaveBeenCalledTimes(1);
  });
});
