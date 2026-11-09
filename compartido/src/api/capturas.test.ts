// captureForm with React Native file parts (run from movil/ with React Native's FormData, as on the
// phone): every part goes with a URI that has a scheme, a name and a type, which Android's networking
// needs to open and send it. The PWA's Blob parts are covered in oficina/src/api/capturas.test.ts.
import { captureForm, nativePart, nativeUri, typeFromName } from './capturas';

type Part = { fieldName: string; string?: string; uri?: string; name?: string; type?: string; headers: Record<string, string> };

function partsOf(form: FormData): Part[] {
  return (form as unknown as { getParts: () => Part[] }).getParts();
}

describe('native file parts', () => {
  it('gives a bare path the file:// scheme and keeps file:// and content://', () => {
    expect(nativeUri('/data/user/0/co.projectapp.office/cache/Audio/recording-1.m4a')).toBe('file:///data/user/0/co.projectapp.office/cache/Audio/recording-1.m4a');
    expect(nativeUri('file:///data/user/0/a.m4a')).toBe('file:///data/user/0/a.m4a');
    expect(nativeUri('content://media/external/images/media/12')).toBe('content://media/external/images/media/12');
    expect(nativeUri('  file:///x.jpg ')).toBe('file:///x.jpg');
  });

  it('knows the contract types by extension', () => {
    expect(typeFromName('IMG_1.HEIC')).toBe('image/heic');
    expect(typeFromName('file:///cache/ImagePicker/a.jpeg?x=1')).toBe('image/jpeg');
    expect(typeFromName('captura.m4a')).toBe('audio/mp4');
    expect(typeFromName('content://media/external/images/media/12')).toBeNull();
    expect(typeFromName('x.gif')).toBeNull();
  });

  it('always has a type and a name: declared, else from the name, else from the URI', () => {
    expect(nativePart({ uri: '/cache/a.m4a', name: '', type: '' }, 'captura.m4a')).toEqual({ uri: 'file:///cache/a.m4a', name: 'captura.m4a', type: 'audio/mp4' });
    expect(nativePart({ uri: 'file:///cache/f.png', name: '', type: '' })).toEqual({ uri: 'file:///cache/f.png', name: 'f.png', type: 'image/png' });
    expect(nativePart({ uri: 'content://media/12', name: 'IMG_2.heic', type: '' })).toEqual({ uri: 'content://media/12', name: 'IMG_2.heic', type: 'image/heic' });
    expect(nativePart({ uri: 'content://media/12', name: '', type: 'IMAGE/JPEG' })).toEqual({ uri: 'content://media/12', name: '12', type: 'image/jpeg' });
    expect(nativePart({ uri: 'content://media/13', name: '', type: '' }).type).toBe('application/octet-stream');
  });
});

describe('captureForm with React Native parts', () => {
  it.each(['no', 'auto', 'si'] as const)('sends ai_edit=%s without boolean aliases or writable urgency', (ai_edit) => {
    expect(partsOf(captureForm({ nota: 'Una idea', ai_edit })).map((part) => [part.fieldName, part.string])).toEqual([
      ['nota', 'Una idea'], ['ai_edit', ai_edit],
    ]);
  });

  it('sends the audio and photos with scheme, name and type, each part with its content-type header', () => {
    const form = captureForm({
      audio: { blob: { uri: '/data/user/0/co.projectapp.office/cache/Audio/recording-1.m4a', name: 'captura.m4a', type: '' }, filename: 'captura.m4a', durationS: 12.345 },
      fotos: [
        { uri: 'file:///cache/ImagePicker/a.jpeg', name: 'IMG_1.jpg', type: 'image/jpeg' },
        { uri: 'content://media/external/images/media/7', name: 'IMG_2.HEIC', type: '' },
      ],
      nota: 'Para el jueves',
    });
    const parts = partsOf(form);
    expect(parts.map((part) => [part.fieldName, part.uri ? { uri: part.uri, name: part.name, type: part.type } : part.string])).toEqual([
      ['audio', { uri: 'file:///data/user/0/co.projectapp.office/cache/Audio/recording-1.m4a', name: 'captura.m4a', type: 'audio/mp4' }],
      ['audio_duration_s', '12.3'],
      ['fotos', { uri: 'file:///cache/ImagePicker/a.jpeg', name: 'IMG_1.jpg', type: 'image/jpeg' }],
      ['fotos', { uri: 'content://media/external/images/media/7', name: 'IMG_2.HEIC', type: 'image/heic' }],
      ['nota', 'Para el jueves'],
    ]);
    // Android refuses a binary part without a content-type («Binary FormData part needs a content-type header»).
    for (const part of parts.filter((p) => p.uri)) {
      expect(part.headers['content-type']).toMatch(/^(audio|image)\//);
      expect(part.headers['content-disposition']).toMatch(/filename="/);
    }
  });

  it('sends only the three fields of a part, whatever else the app object carries', () => {
    const photo = { id: 'f1', uri: 'file:///cache/f.jpg', name: 'f.jpg', type: 'image/jpeg', size: 2048 };
    const [part] = partsOf(captureForm({ fotos: [photo] }));
    expect(part).toMatchObject({ fieldName: 'fotos', uri: 'file:///cache/f.jpg', name: 'f.jpg', type: 'image/jpeg' });
    expect(part).not.toHaveProperty('size');
    expect(part).not.toHaveProperty('id');
  });
});
