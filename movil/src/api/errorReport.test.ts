// Client error reports: only metadata reaches POST /api/v1/app/errores, never the note, a file, a
// path or a token; the same failure is reported once per 30 s; reporting never throws.
import { ApiError } from '@compartido/api/client';
import { fakeServer } from '@/test/server';
import { clientErrorReport, localPart, reportError, resetErrorReportsForTests, withoutPaths } from './errorReport';
import { UploadNetworkError } from './multipart';
import { clearToken, saveToken } from './token';
import './transport';

beforeEach(() => resetErrorReportsForTests());
afterEach(async () => {
  await clearToken();
});

describe('client error reports', () => {
  it('describes the failure, the parts by type, scheme and size, the platform and the app version', () => {
    const report = clientErrorReport('captura_envio', new UploadNetworkError('Could not retrieve file for uri file:///data/user/0/co.projectapp.office/cache/Audio/recording-1.m4a'), [
      localPart('audio', { uri: 'file:///data/user/0/co.projectapp.office/cache/Audio/recording-1.m4a', type: 'audio/mp4' }),
      localPart('fotos', { uri: 'content://media/external/images/media/7', type: 'image/heic', size: 2048 }),
      localPart('fotos', { uri: '/cache/a.jpg', type: 'image/jpeg', size: 10 }),
    ]);
    expect(report).toMatchObject({
      kind: 'captura_envio',
      name: 'UploadNetworkError',
      status: null,
      detail: '',
      parts: [
        { field: 'audio', type: 'audio/mp4', scheme: 'file', size: null },
        { field: 'fotos', type: 'image/heic', scheme: 'content', size: 2048 },
        { field: 'fotos', type: 'image/jpeg', scheme: 'file', size: 10 },
      ],
    });
    expect(report.message).toBe('Network request failed: Could not retrieve file for uri file://….m4a');
    expect(typeof report.platform).toBe('string');
    expect(report.platform).not.toBe('');
    expect(JSON.stringify(report)).not.toMatch(/recording-1|co\.projectapp|media\/7/);
  });

  it('keeps the HTTP status and the server detail', () => {
    const report = clientErrorReport('captura_envio', new ApiError(400, 'Tipo de audio no admitido: desconocido.'));
    expect(report).toMatchObject({ name: 'ApiError', status: 400, detail: 'Tipo de audio no admitido: desconocido.' });
  });

  it('drops local paths but keeps the scheme, the extension and web URLs', () => {
    expect(withoutPaths('No such file: /data/user/0/x/cache/a.jpeg (ENOENT)')).toBe('No such file: ….jpeg (ENOENT)');
    expect(withoutPaths('content://media/external/images/media/7 failed')).toBe('content://… failed');
    expect(withoutPaths('Unable to resolve host https://office.projectapp.co/api')).toBe('Unable to resolve host https://office.projectapp.co/api');
  });

  it('posts it with the session, never the note or the token in the body, once per failure and window', async () => {
    await saveToken('0ff1ce_dt_prueba');
    const server = fakeServer({ 'POST /api/v1/app/errores': { status: 201, body: { id: 'e1' } } });
    const error = new ApiError(413, 'El envío es demasiado grande.');
    reportError('captura_envio', error, [localPart('fotos', { uri: 'file:///cache/f.jpg', type: 'image/jpeg', size: 9_000_000 })]);
    reportError('captura_envio', error, []);
    await new Promise((resolve) => setTimeout(resolve, 0));
    const sent = server.find('POST', '/api/v1/app/errores');
    expect(sent).toHaveLength(1);
    expect(sent[0]!.headers.authorization).toBe('Bearer 0ff1ce_dt_prueba');
    expect(sent[0]!.body).toMatchObject({ kind: 'captura_envio', status: 413, parts: [{ field: 'fotos', type: 'image/jpeg', scheme: 'file', size: 9_000_000 }] });
    expect(JSON.stringify(sent[0]!.body)).not.toContain('0ff1ce_dt_prueba');
  });

  it('skips a lost session and an abort, and never throws when the report fails', async () => {
    const server = fakeServer({ 'POST /api/v1/app/errores': { networkError: 'offline' } });
    const abort = new Error('Aborted');
    abort.name = 'AbortError';
    reportError('captura_envio', new ApiError(401, 'Tu sesión ha caducado.'));
    reportError('captura_envio', abort);
    expect(() => reportError('captura_envio', new TypeError('Network request failed'))).not.toThrow();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(server.find('POST', '/api/v1/app/errores')).toHaveLength(1);
  });
});
