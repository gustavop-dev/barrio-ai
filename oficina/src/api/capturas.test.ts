import { describe, expect, it } from 'vitest';
import { fakeServer } from '../test/fakeServer';
import { captureForm, isAcceptedPhoto, listGaleria, sameOrigin, savePreferencias } from './capturas';
import { api } from './client';

describe('captureForm', () => {
  it.each(['no', 'auto', 'si'] as const)('sends only the new ai_edit field (%s)', (ai_edit) => {
    expect([...captureForm({ nota: 'Una idea', ai_edit }).entries()]).toEqual([['nota', 'Una idea'], ['ai_edit', ai_edit]]);
  });

  it('names every multipart field as the contract does', () => {
    const blob = new Blob(['a'], { type: 'audio/webm' });
    const form = captureForm({
      audio: { blob, filename: 'captura.webm', durationS: 42.34 },
      fotos: [new File(['x'], 'uno.jpg', { type: 'image/jpeg' }), new File(['y'], 'dos.jpg', { type: 'image/jpeg' })],
      nota: '  Para el jueves  ',
      para: 'respuesta',
      contexto: { tipo: 'pregunta', id: 'q1' },
      publicUse: false,
    });
    expect((form.get('audio') as File).name).toBe('captura.webm');
    expect(form.get('audio_duration_s')).toBe('42.3');
    expect(form.getAll('fotos')).toHaveLength(2);
    expect(form.get('nota')).toBe('Para el jueves');
    expect(form.get('para')).toBe('respuesta');
    expect(form.get('contexto_tipo')).toBe('pregunta');
    expect(form.get('contexto_id')).toBe('q1');
    expect(form.get('public_use')).toBe('false');
  });

  it('leaves out what is empty, and the visibility outside a question', () => {
    const form = captureForm({ nota: '', para: null, contexto: { tipo: 'persona', id: 'p1' }, publicUse: true });
    expect([...form.keys()]).toEqual(['contexto_tipo', 'contexto_id']);
  });
});

describe('capturas API', () => {
  it('posts multipart with the CSRF header and no JSON content type', async () => {
    document.cookie = 'csrftoken=tok';
    const server = fakeServer({ 'POST /api/v1/x': { status: 201, body: { ok: true } } });
    const form = new FormData();
    form.append('nota', 'hola');
    await expect(api.postForm('/api/v1/x', form)).resolves.toEqual({ ok: true });
    const init = server.fetch.mock.calls[0]![1]!;
    expect(init.body).toBe(form);
    const headers = new Headers(init.headers);
    expect(headers.get('x-csrftoken')).toBe('tok');
    expect(headers.get('content-type')).toBeNull();
    expect(init.credentials).toBe('same-origin');
  });

  it('asks the gallery by filter and patches the preferences', async () => {
    const server = fakeServer({
      'GET /api/v1/galeria': { body: { count: 0, next: null, previous: null, results: [] } },
      'PATCH /api/v1/ajustes/preferencias': (request) => ({ body: { gallery_ai_edit: 'auto', updated_at: null, ...(request.body as object) } }),
    });
    await listGaleria('sin_usar');
    expect(server.requests[0]!.search.get('filtro')).toBe('sin_usar');
    await savePreferencias({ push_disabled: ['piece_published'] });
    expect(server.find('PATCH', '/api/v1/ajustes/preferencias')[0]!.body).toEqual({ push_disabled: ['piece_published'] });
  });

  it('accepts JPEG, PNG, WebP and HEIC photos only, and same-origin media URLs', () => {
    expect(isAcceptedPhoto(new File([''], 'a.jpg', { type: 'image/jpeg' }))).toBe(true);
    expect(isAcceptedPhoto(new File([''], 'a.heic', { type: '' }))).toBe(true);
    expect(isAcceptedPhoto(new File([''], 'a.gif', { type: 'image/gif' }))).toBe(false);
    expect(sameOrigin('/api/v1/galeria/f1/imagen')).toBe('/api/v1/galeria/f1/imagen');
    expect(sameOrigin('https://evil.example/x.jpg')).toBeNull();
    expect(sameOrigin('//evil.example/x.jpg')).toBeNull();
  });
});
