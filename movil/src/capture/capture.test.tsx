// The capture: the button (tap, hold, lock, discard with «Recuperar») and the sheet (photo, note,
// «Para qué es», the context chip, the multipart upload with its 5 s «Deshacer», and the microphone
// explained before the system asks).
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import { onlineManager } from '@tanstack/react-query';
import * as Haptics from 'expo-haptics';
import * as ImagePicker from 'expo-image-picker';
import { State } from 'react-native-gesture-handler';
import { createGestureController, fireGestureHandler, getByGestureTestId } from 'react-native-gesture-handler/jest-utils';
import { resetErrorReportsForTests } from '@/api/errorReport';
import '@/api/transport';
import { audio, resetFakeAudio } from '@/test/fakeAudio';
import { renderApp } from '@/test/render';
import { fakeServer } from '@/test/server';
import { captureMotion, captureTimeline, gestures, toastDurations } from '@/theme/motion';
import { CaptureButton } from './CaptureButton';
import { CaptureSheetHost } from './CaptureSheet';
import { checkPhotos, toPickedPhoto } from './photos';
import { discardProgress, holdDecision, holdFollow, isTooShort, lockProgress } from './hold';
import { clipLevels } from './recorder';
import { DRAFT_KEPT } from './sendError';
import { closeCaptureSheet, openCaptureSheet, resetCaptureStoreForTests } from './store';
import type { RecordedAudio } from './types';
import { barHeight, CLIP_BARS, LIVE_BARS } from './Wave';

const CAPTURE = { id: 'c1', state: 'recibida', state_label: 'Recibida', undo_until: new Date(Date.now() + 120_000).toISOString(), can_undo: true };

/** A finished voice note as expo-audio leaves it in the cache (here without its file:// scheme). */
const AUDIO: RecordedAudio = { uri: '/data/user/0/co.projectapp.office/cache/Audio/recording-1.m4a', mime: 'audio/mp4', duration: 4.24, levels: Array.from({ length: 24 }, () => 0.3) };
const AUDIO_PART = { uri: 'file:///data/user/0/co.projectapp.office/cache/Audio/recording-1.m4a', name: 'captura.m4a', type: 'audio/mp4' };

/** A capture of «Lo que enviaste», sent a moment ago (it can still be undone). */
function historyCapture(extra: Record<string, unknown> = {}) {
  return {
    id: 'c9',
    created_at: new Date().toISOString(),
    note: 'Idea para el post del jueves',
    purpose: 'post',
    purpose_label: 'Idea para un post',
    team_decided: null,
    context: null,
    has_audio: false,
    audio_duration_s: null,
    audio_mime: null,
    audio_url: null,
    transcript: '',
    transcript_language: null,
    state: 'recibida',
    state_label: 'Recibida',
    outcome: { kind: 'recibida', text: 'El equipo lo recibió', link: null },
    photos: [],
    error: null,
    undo_until: new Date(Date.now() + 120_000).toISOString(),
    can_undo: true,
    ...extra,
  };
}

function capturaServer(extra: Parameters<typeof fakeServer>[0] = {}) {
  return fakeServer({
    'GET /api/v1/capturas': { body: { count: 0, next: null, previous: null, results: [] } },
    'POST /api/v1/capturas': { status: 201, body: CAPTURE },
    'DELETE /api/v1/capturas/c1': { body: { ...CAPTURE, state: 'deshecha' } },
    'GET /api/v1/preguntas': { body: [] },
    'GET /api/v1/ajustes/preferencias': { body: { gallery_ai_edit: 'auto', updated_at: null } },
    ...extra,
  });
}

async function renderCapture() {
  const result = await renderApp(
    <>
      <CaptureButton />
      <CaptureSheetHost />
    </>,
    { recorder: true },
  );
  // Let the button learn the microphone permission.
  await act(async () => {});
  return result;
}

beforeEach(() => {
  resetFakeAudio();
  resetCaptureStoreForTests(true);
  resetErrorReportsForTests();
});

afterEach(async () => {
  await act(async () => closeCaptureSheet());
});

describe('capture rules (motion.ts gestures.capture, MovCaptura)', () => {
  it('slide up 64 to lock, left 110 to discard; up wins', () => {
    expect(holdDecision(0, -64)).toBe('lock');
    expect(holdDecision(-110, 0)).toBe('discard');
    expect(holdDecision(-120, -70)).toBe('lock');
    expect(holdDecision(-50, -30)).toBe('none');
    expect(isTooShort(1000, 1500)).toBe(true);
    expect(isTooShort(1000, 1700)).toBe(false);
  });

  it('the button follows 60 % of the finger, only up and left, and the lock and trash fill on the way', () => {
    expect(holdFollow(-100)).toBe(-60);
    expect(holdFollow(30)).toBe(0);
    expect(lockProgress(holdFollow(-gestures.capture.lockDistance))).toBe(1);
    expect(lockProgress(holdFollow(-32))).toBeCloseTo(0.5);
    expect(discardProgress(holdFollow(-55))).toBeCloseTo(0.5);
    expect(discardProgress(holdFollow(20))).toBe(0);
  });

  it('uses the board values: hold scale, follow, lock and trash, and the two timelines', () => {
    expect(captureMotion).toMatchObject({ holdScale: 1.2, follow: 0.6, lockRise: 12, shackleDrop: 3, shackleMs: 120, lidOpenDeg: -28, dropScale: 0.2, trashLingerMs: 220, sentPulse: 1.18 });
    expect(captureMotion.morph).toEqual({ damping: 14, stiffness: 160, mass: 1 });
    expect(captureTimeline.discard).toMatchObject({ ms: 780, dropAt: 0.55, binBelow: 116, shrinkTo: 22 });
    expect(captureTimeline.send).toMatchObject({ ms: 1000, sealAt: 0.42, closeAt: 0.45, thumbStagger: 0.04 });
  });

  it('keeps JPEG, PNG, WebP or HEIC up to 10 MB, ten per capture', () => {
    const ok = toPickedPhoto({ uri: 'file:///a/IMG_1.HEIC', fileName: null, mimeType: undefined, fileSize: 1000 });
    expect(ok).toMatchObject({ name: 'IMG_1.HEIC', type: 'image/heic' });
    const big = toPickedPhoto({ uri: 'file:///a/big.jpg', fileName: 'big.jpg', mimeType: 'image/jpeg', fileSize: 11 * 1024 * 1024 });
    const gif = toPickedPhoto({ uri: 'file:///a/x.gif', fileName: 'x.gif', mimeType: 'image/gif', fileSize: 10 });
    const result = checkPhotos([ok, big, gif], 9);
    expect(result.kept).toEqual([ok]);
    expect(result.problem).toMatch(/No se añadió big\.jpg, x\.gif/);
    expect(checkPhotos([ok, ok], 9).problem).toMatch(/hasta 10 fotos/);
  });

  it('describes a picked photo as the bytes the picker wrote: a URI with a scheme, the real type and a matching name', () => {
    // Android re-encodes a HEIC into …/ImagePicker/<uuid>.jpeg (quality 0.85) but keeps the source's type and name.
    expect(toPickedPhoto({ uri: 'file:///data/user/0/x/cache/ImagePicker/1.jpeg', fileName: 'IMG_1.heic', mimeType: 'image/heic', fileSize: 1000 })).toMatchObject({
      uri: 'file:///data/user/0/x/cache/ImagePicker/1.jpeg',
      name: 'IMG_1.jpg',
      type: 'image/jpeg',
    });
    expect(toPickedPhoto({ uri: '/data/user/0/x/cache/2.png', fileName: null, mimeType: undefined, fileSize: undefined })).toMatchObject({
      uri: 'file:///data/user/0/x/cache/2.png',
      name: '2.png',
      type: 'image/png',
      size: null,
    });
    expect(toPickedPhoto({ uri: 'content://media/external/images/media/3', fileName: 'IMG_3.webp', mimeType: 'image/webp', fileSize: 5 })).toMatchObject({
      uri: 'content://media/external/images/media/3',
      name: 'IMG_3.webp',
      type: 'image/webp',
    });
    const unnamed = toPickedPhoto({ uri: 'content://media/external/images/media/4', fileName: null, mimeType: undefined, fileSize: 5 });
    expect(unnamed.type).toBe('image/jpeg');
    expect(unnamed.name).toMatch(/^foto-\d+\.jpg$/);
    // Not an image: it keeps its type, so the checks refuse it.
    expect(toPickedPhoto({ uri: 'file:///a/1.jpg', fileName: 'video.mov', mimeType: 'video/quicktime', fileSize: 5 })).toMatchObject({ name: 'video.mov', type: 'video/quicktime' });
  });
});

describe('capture button', () => {
  it('shows the first-use hint, and a tap opens the sheet without recording', async () => {
    capturaServer();
    await renderCapture();
    expect(screen.getByText('Mantén oprimido para grabar. Toca para foto o nota.')).toBeOnTheScreen();
    await act(async () => fireGestureHandler(getByGestureTestId('capture-tap'), [{ state: State.BEGAN }, { state: State.ACTIVE }, { state: State.END }]));
    expect(await screen.findByText('Para el equipo')).toBeOnTheScreen();
    expect(screen.queryByText('Mantén oprimido para grabar. Toca para foto o nota.')).toBeNull();
    expect(audio.recorder.record).not.toHaveBeenCalled();
  });

  it('the first-use hint goes away by itself, so it does not cover the screen until the first capture', async () => {
    jest.replaceProperty(captureMotion as { hintMs: number }, 'hintMs', 200);
    capturaServer();
    await renderCapture();
    expect(screen.getByText('Mantén oprimido para grabar. Toca para foto o nota.')).toBeOnTheScreen();
    await waitFor(() => expect(screen.queryByText('Mantén oprimido para grabar. Toca para foto o nota.')).toBeNull(), { timeout: 2000 });
  });

  /** Starts a hold and lets the recorder open the microphone, as the finger stays down. */
  async function startHold() {
    const hold = createGestureController('capture-hold');
    await act(async () => {
      hold.begin();
      hold.activate();
    });
    await waitFor(() => expect(audio.recorder.record).toHaveBeenCalled());
    return hold;
  }

  it('hold records; releasing opens the sheet with the audio ready', async () => {
    capturaServer();
    await renderCapture();
    const now = jest.spyOn(Date, 'now');
    now.mockReturnValue(10_000);
    const hold = createGestureController('capture-hold');
    await act(async () => {
      hold.begin();
      hold.activate();
    });
    now.mockReturnValue(10_100);
    await act(async () => {});
    expect(audio.recorder.record).toHaveBeenCalled();
    expect(Haptics.impactAsync).toHaveBeenCalledWith('medium');
    expect(screen.getByText('Desliza hacia arriba para bloquear')).toBeOnTheScreen();
    now.mockReturnValue(12_000);
    await act(async () => {
      hold.update({ translationX: 0, translationY: -10 });
      hold.end();
    });
    // waitFor measures its timeout with Date.now.
    now.mockRestore();
    expect(await screen.findByTestId('capture-audio')).toBeOnTheScreen();
    expect(audio.recorder.stop).toHaveBeenCalled();
  });

  it('sliding up locks the recording: it carries on in the sheet', async () => {
    capturaServer();
    await renderCapture();
    const hold = await startHold();
    await act(async () => {
      hold.update({ translationY: -80 });
      hold.end({ translationY: -80 });
    });
    expect(await screen.findByTestId('capture-recording')).toBeOnTheScreen();
    expect(screen.getByText('Grabando · bloqueado')).toBeOnTheScreen();
    expect(audio.recorder.stop).not.toHaveBeenCalled();
    // «HÁPTICO · ÉXITO» at the lock point.
    expect(Haptics.notificationAsync).toHaveBeenCalledWith('success');
  });

  it('«Descartar» in the sheet throws the ball into the bin, then offers to record again', async () => {
    capturaServer();
    await renderCapture();
    const hold = await startHold();
    await act(async () => {
      hold.update({ translationY: -80 });
      hold.end({ translationY: -80 });
    });
    const panel = await screen.findByTestId('capture-recording');
    await fireEvent.press(within(panel).getByText('Descartar'));
    // The panel stays while the ball falls; the recording is already stopped.
    expect(screen.getByTestId('capture-recording')).toBeOnTheScreen();
    expect(await screen.findByText('Grabar un audio', {}, { timeout: 4000 })).toBeOnTheScreen();
    expect(screen.queryByTestId('capture-recording')).toBeNull();
    expect(Haptics.notificationAsync).toHaveBeenCalledWith('warning');
    expect(screen.getByTestId('capture-sheet')).toBeOnTheScreen();
  });

  it('sliding left discards it, and «Recuperar» brings the audio back', async () => {
    capturaServer();
    await renderCapture();
    const hold = await startHold();
    await act(async () => {
      hold.update({ translationX: -130 });
      hold.end({ translationX: -130 });
    });
    // The button falls into the trash first (fast + trashLingerMs), then the toast.
    expect(Haptics.notificationAsync).toHaveBeenCalledWith('warning');
    expect(await screen.findByText('Grabación descartada.', {}, { timeout: 4000 })).toBeOnTheScreen();
    expect(screen.queryByText('Para el equipo')).toBeNull();
    await fireEvent.press(screen.getByText('Recuperar'));
    expect(await screen.findByTestId('capture-audio')).toBeOnTheScreen();
  });

  it('without the microphone permission, a hold explains why before the system asks', async () => {
    audio.permission = { granted: false, canAskAgain: true, status: 'undetermined' };
    capturaServer();
    await renderCapture();
    await act(async () => fireGestureHandler(getByGestureTestId('capture-hold'), [{ state: State.BEGAN }, { state: State.ACTIVE }, { state: State.END }]));
    expect(await screen.findByText('Para grabar, 0ff1ce necesita el micrófono')).toBeOnTheScreen();
    expect(audio.requested).toBe(0);
    expect(audio.recorder.record).not.toHaveBeenCalled();
    audio.permission = { granted: true, canAskAgain: true, status: 'granted' };
    await fireEvent.press(screen.getByText('Permitir el micrófono'));
    expect(audio.requested).toBe(1);
    expect(await screen.findByTestId('capture-recording')).toBeOnTheScreen();
  });
});

describe('capture sheet', () => {
  it('sends a photo, a note and «Para qué es» in one multipart POST, then «Deshacer» gives the content back', async () => {
    const server = capturaServer();
    jest.mocked(ImagePicker.launchImageLibraryAsync).mockResolvedValueOnce({
      canceled: false,
      assets: [{ uri: 'file:///cache/foto.jpg', fileName: 'foto.jpg', mimeType: 'image/jpeg', fileSize: 2048, width: 10, height: 10 }],
    } as never);
    await renderCapture();
    await act(async () => openCaptureSheet());
    const sheet = await screen.findByTestId('capture-sheet');
    expect(within(sheet).getByTestId('capture-send')).toBeDisabled();
    await fireEvent.press(within(sheet).getByText('Galería'));
    expect(await within(sheet).findByLabelText('Foto adjunta 1')).toBeOnTheScreen();
    await fireEvent.changeText(within(sheet).getByTestId('capture-note'), 'Para el post del jueves');
    await fireEvent.press(within(sheet).getByText('Idea para un post'));
    expect(within(sheet).getByRole('radio', { name: 'Que decida el equipo' })).toBeChecked();
    await fireEvent.press(within(sheet).getByRole('radio', { name: 'Editar' }));
    await fireEvent.press(within(sheet).getByTestId('capture-send'));

    await waitFor(() => expect(server.find('POST', '/api/v1/capturas')).toHaveLength(1));
    const sent = server.find('POST', '/api/v1/capturas')[0]!;
    expect(sent.headers['content-type']).toBeUndefined();
    expect(sent.body).toEqual([
      ['fotos', { uri: 'file:///cache/foto.jpg', name: 'foto.jpg', type: 'image/jpeg' }],
      ['nota', 'Para el post del jueves'],
      ['para', 'post'],
      ['ai_edit', 'si'],
    ]);
    // The envelope choreography plays first: the sheet goes and the toast comes at its end.
    expect(screen.getByTestId('capture-sheet')).toBeOnTheScreen();
    expect(await screen.findByText('Enviado al equipo.', {}, { timeout: 4000 })).toBeOnTheScreen();
    expect(screen.queryByTestId('capture-sheet')).toBeNull();
    expect(Haptics.notificationAsync).toHaveBeenCalledWith('success');

    await fireEvent.press(screen.getByText('Deshacer'));
    await waitFor(() => expect(server.find('DELETE', '/api/v1/capturas/c1')).toHaveLength(1));
    expect(await screen.findByText('Envío deshecho. Lo tienes otra vez en la hoja.')).toBeOnTheScreen();
    const again = await screen.findByTestId('capture-sheet');
    // The sheet opens again on top: the toast is drawn in its window, where Gustavo sees it, not under it.
    expect(within(screen.getByTestId('capture-sheet-modal')).getByText('Envío deshecho. Lo tienes otra vez en la hoja.')).toBeOnTheScreen();
    expect(within(again).getByDisplayValue('Para el post del jueves')).toBeOnTheScreen();
    expect(within(again).getByLabelText('Foto adjunta 1')).toBeOnTheScreen();
    expect(within(again).getByRole('radio', { name: 'Editar' })).toBeChecked();
  });

  it('«Deshacer» stays for 5 seconds (motion.ts toastDurations)', () => {
    expect(toastDurations.withUndo).toBe(5000);
  });

  it('a question context is the simple sheet (audio, photo, note) and sends contexto with the suggested visibility', async () => {
    const server = capturaServer();
    jest.mocked(ImagePicker.launchImageLibraryAsync).mockResolvedValueOnce({
      canceled: false,
      assets: [{ uri: 'file:///cache/foto.jpg', fileName: 'foto.jpg', mimeType: 'image/jpeg', fileSize: 2048, width: 10, height: 10 }],
    } as never);
    await renderCapture();
    await act(async () => openCaptureSheet({ tipo: 'pregunta', id: 'q1', label: '¿Aceptas proyectos de 3 meses?' }));
    const sheet = await screen.findByTestId('capture-sheet');
    const chip = within(sheet).getByTestId('capture-context');
    expect(within(chip).getByText('¿Aceptas proyectos de 3 meses?')).toBeOnTheScreen();
    expect(within(sheet).getByTestId('capture-grabar')).toBeOnTheScreen();
    expect(within(sheet).getByTestId('capture-camara')).toBeOnTheScreen();
    for (const gone of ['Para qué es (opcional)', 'Visibilidad de tu respuesta', 'Privado', 'Lo verás en «Lo que enviaste», arriba en esta hoja.']) {
      expect(within(sheet).queryByText(gone)).toBeNull();
    }
    expect(screen.queryByTestId('capture-historial')).toBeNull();
    await fireEvent.press(within(sheet).getByText('Galería'));
    expect(await within(sheet).findByLabelText('Foto adjunta 1')).toBeOnTheScreen();
    expect(within(sheet).queryByTestId('capture-ai')).toBeNull();
    await fireEvent.changeText(within(sheet).getByTestId('capture-note'), 'Sí, si el equipo es pequeño.');
    await fireEvent.press(within(sheet).getByTestId('capture-send'));
    await waitFor(() => expect(server.find('POST', '/api/v1/capturas')).toHaveLength(1));
    // No public_use: the question's suggestion applies. No ai_edit choice either: the Ajustes value goes.
    const body = server.find('POST', '/api/v1/capturas')[0]!.body as [string, unknown][];
    expect(body.filter(([field]) => field !== 'ai_edit')).toEqual([
      ['fotos', { uri: 'file:///cache/foto.jpg', name: 'foto.jpg', type: 'image/jpeg' }],
      ['nota', 'Sí, si el equipo es pequeño.'],
      ['contexto_tipo', 'pregunta'],
      ['contexto_id', 'q1'],
    ]);
  });

  it('a loose capture offers no «Propuesta de post» nor «Responde una pregunta»', async () => {
    capturaServer();
    await renderCapture();
    await act(async () => openCaptureSheet());
    const sheet = await screen.findByTestId('capture-sheet');
    expect(within(sheet).getByText('Idea para un post')).toBeOnTheScreen();
    expect(within(sheet).getByText('Dato sobre mí')).toBeOnTheScreen();
    // The Galería left the app (12/11/2026): photos go with a note, so «Foto para la galería» is gone.
    expect(within(sheet).queryByText('Foto para la galería')).toBeNull();
    expect(within(sheet).queryByText('Propuesta de post')).toBeNull();
    expect(within(sheet).queryByText('Responde una pregunta')).toBeNull();
    expect(screen.getByTestId('capture-historial')).toBeOnTheScreen();
  });

  it('removing the context chip sends the capture loose', async () => {
    const server = capturaServer();
    await renderCapture();
    await act(async () => openCaptureSheet({ tipo: 'persona', id: 'c-1', label: 'Lucía Ficticia' }));
    const sheet = await screen.findByTestId('capture-sheet');
    await fireEvent.press(within(sheet).getByLabelText('Quitar el contexto'));
    expect(within(sheet).queryByTestId('capture-context')).toBeNull();
    await fireEvent.changeText(within(sheet).getByTestId('capture-note'), 'Una nota');
    await fireEvent.press(within(sheet).getByTestId('capture-send'));
    await waitFor(() => expect(server.find('POST', '/api/v1/capturas')[0]?.body).toEqual([['nota', 'Una nota']]));
  });

  it('a photo goes with «Idea para un post» and needs no other purpose', async () => {
    capturaServer();
    await renderCapture();
    await act(async () => openCaptureSheet());
    const sheet = await screen.findByTestId('capture-sheet');
    await fireEvent.changeText(within(sheet).getByTestId('capture-note'), 'Mira');
    await fireEvent.press(within(sheet).getByText('Idea para un post'));
    expect(within(sheet).queryByText('Para «Foto para la galería» adjunta al menos una foto.')).toBeNull();
    expect(within(sheet).getByTestId('capture-send')).toBeEnabled();
  });

  it('the close button slides an empty sheet away', async () => {
    capturaServer();
    await renderCapture();
    await act(async () => openCaptureSheet());
    const sheet = await screen.findByTestId('capture-sheet');
    await fireEvent.press(within(sheet).getByLabelText('Cerrar sin enviar'));
    await waitFor(() => expect(screen.queryByTestId('capture-sheet')).toBeNull());
  });

  it('«Deshacer» in «Lo que enviaste» says so over the sheet and takes the capture out of the list at once, even on a slow network', async () => {
    const sent = historyCapture();
    const undone = { ...sent, state: 'deshecha', state_label: 'Deshecha', note: '', can_undo: false, outcome: { kind: 'deshecha', text: 'Deshiciste este envío', link: null } };
    const server = capturaServer({
      'GET /api/v1/capturas': { body: { count: 1, next: null, previous: null, results: [sent] } },
      'GET /api/v1/capturas/c9': { body: sent },
      'DELETE /api/v1/capturas/c9': { body: undone },
    });
    await renderCapture();
    await act(async () => openCaptureSheet(undefined, { view: 'history' }));
    const sheet = await screen.findByTestId('capture-sheet');
    expect(await within(sheet).findByText('Idea para el post del jueves')).toBeOnTheScreen();
    expect(within(sheet).getByText('Lo que enviaste · 1')).toBeOnTheScreen();
    // From the undo on, every read of the captures hangs (a phone on a bad network): the list cannot wait for them.
    const answer = server.fetch.getMockImplementation()!;
    let afterUndo = false;
    server.fetch.mockImplementation((...args: Parameters<typeof answer>) => {
      const [url, init] = args;
      const method = (init?.method ?? 'GET').toUpperCase();
      if (afterUndo && method === 'GET' && String(url).includes('/api/v1/capturas')) return new Promise(() => {});
      if (method === 'DELETE') afterUndo = true;
      return answer(...args);
    });
    await fireEvent.press(within(sheet).getByText('Deshacer'));
    await waitFor(() => expect(server.find('DELETE', '/api/v1/capturas/c9')).toHaveLength(1));
    // The toast is drawn in the sheet's window, above it.
    await waitFor(() => expect(within(screen.getByTestId('capture-sheet-modal')).getByText('Envío deshecho.')).toBeOnTheScreen());
    await waitFor(() => expect(within(screen.getByTestId('capture-sheet')).queryByText('Idea para el post del jueves')).toBeNull());
    expect(within(screen.getByTestId('capture-sheet')).getByText('Lo que enviaste · 0')).toBeOnTheScreen();
    expect(within(screen.getByTestId('capture-sheet')).getByText('Todavía no has enviado nada')).toBeOnTheScreen();
  });

  it('«Deshacer» in «Lo que enviaste» goes away when its 2 minutes run out, with the list still open', async () => {
    const sent = historyCapture({ undo_until: new Date(Date.now() + 1500).toISOString() });
    capturaServer({
      'GET /api/v1/capturas': { body: { count: 1, next: null, previous: null, results: [sent] } },
      'GET /api/v1/capturas/c9': { body: sent },
    });
    await renderCapture();
    await act(async () => openCaptureSheet(undefined, { view: 'history' }));
    const sheet = await screen.findByTestId('capture-sheet');
    expect(await within(sheet).findByText('Deshacer')).toBeOnTheScreen();
    await waitFor(() => expect(within(screen.getByTestId('capture-sheet')).queryByText('Deshacer')).toBeNull(), { timeout: 5000 });
    expect(within(screen.getByTestId('capture-sheet')).getByText('Idea para el post del jueves')).toBeOnTheScreen();
  });

  it('stays open while the send is on its way, and then says it arrived', async () => {
    const server = capturaServer();
    await renderCapture();
    await act(async () => openCaptureSheet());
    const sheet = await screen.findByTestId('capture-sheet');
    await fireEvent.changeText(within(sheet).getByTestId('capture-note'), 'Algo');
    const answer = server.fetch.getMockImplementation()!;
    let release: (() => void) | null = null;
    server.fetch.mockImplementationOnce((...args: Parameters<typeof answer>) => new Promise((resolve) => (release = () => resolve(answer(...args)))));
    await fireEvent.press(within(sheet).getByTestId('capture-send'));
    await waitFor(() => expect(release).not.toBeNull());
    await fireEvent.press(within(sheet).getByLabelText('Cerrar sin enviar'));
    expect(screen.getByTestId('capture-sheet')).toBeOnTheScreen();
    expect(screen.queryByText('¿Cerrar sin enviar?')).toBeNull();
    await act(async () => release?.());
    expect(await screen.findByText('Enviado al equipo.', {}, { timeout: 4000 })).toBeOnTheScreen();
  });

  it('closing with content asks first', async () => {
    capturaServer();
    await renderCapture();
    await act(async () => openCaptureSheet());
    const sheet = await screen.findByTestId('capture-sheet');
    await fireEvent.changeText(within(sheet).getByTestId('capture-note'), 'Algo');
    await fireEvent.press(within(sheet).getByLabelText('Cerrar sin enviar'));
    expect(await screen.findByText('¿Cerrar sin enviar?')).toBeOnTheScreen();
  });

  it('a voice note goes up as a file:// part named captura.m4a of type audio/mp4, through XMLHttpRequest', async () => {
    const server = capturaServer();
    await renderCapture();
    await act(async () => openCaptureSheet(undefined, { audio: AUDIO }));
    const sheet = await screen.findByTestId('capture-sheet');
    await fireEvent.press(within(sheet).getByTestId('capture-send'));
    await waitFor(() => expect(server.find('POST', '/api/v1/capturas')).toHaveLength(1));
    const sent = server.find('POST', '/api/v1/capturas')[0]!;
    expect(sent.via).toBe('xhr');
    expect(sent.headers['content-type']).toBeUndefined();
    expect(sent.body).toEqual([
      ['audio', AUDIO_PART],
      ['audio_duration_s', '4.2'],
    ]);
    expect(await screen.findByText('Enviado al equipo.', {}, { timeout: 4000 })).toBeOnTheScreen();
  });

  it('a locked recording is finished first, and the file the recorder wrote goes up', async () => {
    const server = capturaServer();
    await renderCapture();
    const hold = createGestureController('capture-hold');
    await act(async () => {
      hold.begin();
      hold.activate();
    });
    await waitFor(() => expect(audio.recorder.record).toHaveBeenCalled());
    await act(async () => {
      hold.update({ translationY: -80 });
      hold.end({ translationY: -80 });
    });
    expect(await screen.findByTestId('capture-recording')).toBeOnTheScreen();
    const sheet = screen.getByTestId('capture-sheet');
    audio.recorder.stop.mockImplementationOnce(async () => {
      audio.recorder.isRecording = false;
      audio.recorder.uri = '/data/user/0/co.projectapp.office/cache/Audio/recording-2.m4a';
    });
    await fireEvent.press(within(sheet).getByTestId('capture-send'));
    await waitFor(() => expect(server.find('POST', '/api/v1/capturas')).toHaveLength(1));
    expect(audio.recorder.stop).toHaveBeenCalledTimes(1);
    const [part] = server.find('POST', '/api/v1/capturas')[0]!.body as [string, unknown][];
    expect(part).toEqual(['audio', { uri: 'file:///data/user/0/co.projectapp.office/cache/Audio/recording-2.m4a', name: 'captura.m4a', type: 'audio/mp4' }]);
  });

  it('a send that fails on the phone says why, keeps the audio, the photo and the note, reports only metadata, and «Reintentar» sends it', async () => {
    const server = capturaServer({
      'POST /api/v1/capturas': { networkError: 'Could not retrieve file for uri file:///data/user/0/co.projectapp.office/cache/Audio/recording-1.m4a' },
      'POST /api/v1/app/errores': { status: 201, body: { id: 'e1' } },
    });
    jest.mocked(ImagePicker.launchImageLibraryAsync).mockResolvedValueOnce({
      canceled: false,
      assets: [{ uri: 'file:///cache/foto.jpg', fileName: 'foto.jpg', mimeType: 'image/jpeg', fileSize: 2048, width: 10, height: 10 }],
    } as never);
    await renderCapture();
    await act(async () => openCaptureSheet(undefined, { audio: AUDIO }));
    const sheet = await screen.findByTestId('capture-sheet');
    await fireEvent.press(within(sheet).getByText('Galería'));
    expect(await within(sheet).findByLabelText('Foto adjunta 1')).toBeOnTheScreen();
    await fireEvent.changeText(within(sheet).getByTestId('capture-note'), 'Idea secreta del jueves');
    await fireEvent.press(within(sheet).getByTestId('capture-send'));

    const problem = await within(sheet).findByTestId('capture-send-error');
    expect(within(problem).getByText('El teléfono no pudo leer un archivo')).toBeOnTheScreen();
    expect(within(problem).getByText(DRAFT_KEPT)).toBeOnTheScreen();
    expect(within(problem).getByText(/Detalle: Network request failed: Could not retrieve file for uri/)).toBeOnTheScreen();
    expect(Haptics.notificationAsync).toHaveBeenCalledWith('error');
    // Nothing is lost: the sheet stays open with the audio, the photo and the note.
    expect(screen.getByTestId('capture-sheet')).toBeOnTheScreen();
    expect(within(sheet).getByTestId('capture-audio')).toBeOnTheScreen();
    expect(within(sheet).getByLabelText('Foto adjunta 1')).toBeOnTheScreen();
    expect(within(sheet).getByDisplayValue('Idea secreta del jueves')).toBeOnTheScreen();

    await waitFor(() => expect(server.find('POST', '/api/v1/app/errores')).toHaveLength(1));
    const report = server.find('POST', '/api/v1/app/errores')[0]!.body;
    expect(report).toMatchObject({
      kind: 'captura_envio',
      name: 'UploadNetworkError',
      status: null,
      parts: [
        { field: 'audio', type: 'audio/mp4', scheme: 'file', size: null },
        { field: 'fotos', type: 'image/jpeg', scheme: 'file', size: 2048 },
      ],
    });
    expect(JSON.stringify(report)).not.toMatch(/Idea secreta|recording-1|foto\.jpg|0ff1ce_dt_/);

    server.on('POST /api/v1/capturas', { status: 201, body: CAPTURE });
    await fireEvent.press(within(problem).getByText('Reintentar'));
    await waitFor(() => expect(server.find('POST', '/api/v1/capturas')).toHaveLength(2));
    const [first, second] = server.find('POST', '/api/v1/capturas');
    expect(second!.body).toEqual(first!.body);
    expect(second!.body).toEqual([
      ['audio', AUDIO_PART],
      ['audio_duration_s', '4.2'],
      ['fotos', { uri: 'file:///cache/foto.jpg', name: 'foto.jpg', type: 'image/jpeg' }],
      ['nota', 'Idea secreta del jueves'],
      ['ai_edit', 'auto'],
    ]);
    expect(await screen.findByText('Enviado al equipo.', {}, { timeout: 4000 })).toBeOnTheScreen();
  });

  it('no network says so, and the draft stays', async () => {
    capturaServer({ 'POST /api/v1/capturas': { networkError: 'Unable to resolve host "office.projectapp.co"' } });
    await renderCapture();
    await act(async () => openCaptureSheet(undefined, { audio: AUDIO }));
    const sheet = await screen.findByTestId('capture-sheet');
    await fireEvent.press(within(sheet).getByTestId('capture-send'));
    const problem = await within(sheet).findByTestId('capture-send-error');
    expect(within(problem).getByText('No hay conexión con el servidor')).toBeOnTheScreen();
    expect(within(sheet).getByTestId('capture-audio')).toBeOnTheScreen();
  });

  it('offline, it says so at once instead of waiting with «Enviando…», keeps the draft and sends it again once online', async () => {
    const server = capturaServer();
    await renderCapture();
    await act(async () => openCaptureSheet(undefined, { audio: AUDIO }));
    const sheet = await screen.findByTestId('capture-sheet');
    await fireEvent.changeText(within(sheet).getByTestId('capture-note'), 'Sin red');
    // What NetInfo says through TanStack's onlineManager (only its answer: no online/offline event is fired).
    const offline = jest.spyOn(onlineManager, 'isOnline').mockReturnValue(false);
    await fireEvent.press(within(sheet).getByTestId('capture-send'));
    const problem = await within(sheet).findByTestId('capture-send-error');
    expect(within(problem).getByText('No hay conexión con el servidor')).toBeOnTheScreen();
    expect(within(problem).queryByText(/Detalle:/)).toBeNull();
    expect(server.find('POST', '/api/v1/capturas')).toHaveLength(0);
    expect(within(sheet).getByTestId('capture-audio')).toBeOnTheScreen();
    expect(within(sheet).getByDisplayValue('Sin red')).toBeOnTheScreen();
    offline.mockRestore();
    await fireEvent.press(within(problem).getByText('Reintentar'));
    await waitFor(() => expect(server.find('POST', '/api/v1/capturas')).toHaveLength(1));
    // The envelope choreography ends and the sheet goes (nothing of it is left for the next test).
    await waitFor(() => expect(screen.queryByTestId('capture-sheet')).toBeNull(), { timeout: 6000 });
  });

  it('a 400 shows the server message', async () => {
    capturaServer({ 'POST /api/v1/capturas': { status: 400, body: { detail: 'Tipo de audio no admitido: desconocido.' } } });
    await renderCapture();
    await act(async () => openCaptureSheet(undefined, { audio: AUDIO }));
    const sheet = await screen.findByTestId('capture-sheet');
    await fireEvent.press(within(sheet).getByTestId('capture-send'));
    const problem = await within(sheet).findByTestId('capture-send-error');
    expect(within(problem).getByText('El servidor no aceptó el envío')).toBeOnTheScreen();
    expect(within(problem).getByText('Tipo de audio no admitido: desconocido.')).toBeOnTheScreen();
    expect(within(problem).getByText('Detalle: HTTP 400')).toBeOnTheScreen();
    expect(within(sheet).getByTestId('capture-audio')).toBeOnTheScreen();
  });

  it('a 409 says why it cannot go with that context', async () => {
    capturaServer({ 'POST /api/v1/capturas': { status: 409, body: { detail: 'La pregunta ya no está abierta.' } } });
    await renderCapture();
    await act(async () => openCaptureSheet({ tipo: 'pregunta', id: 'q1', label: '¿Aceptas proyectos de 3 meses?' }));
    const sheet = await screen.findByTestId('capture-sheet');
    await fireEvent.changeText(within(sheet).getByTestId('capture-note'), 'Sí.');
    await fireEvent.press(within(sheet).getByTestId('capture-send'));
    const problem = await within(sheet).findByTestId('capture-send-error');
    expect(within(problem).getByText('No se puede enviar así ahora')).toBeOnTheScreen();
    expect(within(problem).getByText('La pregunta ya no está abierta. Quita el contexto de arriba para enviarlo suelto.')).toBeOnTheScreen();
    expect(within(sheet).getByDisplayValue('Sí.')).toBeOnTheScreen();
  });

  it('a 413 says the upload is too big', async () => {
    capturaServer({ 'POST /api/v1/capturas': { status: 413, body: { detail: 'Demasiado grande.' } } });
    await renderCapture();
    await act(async () => openCaptureSheet());
    const sheet = await screen.findByTestId('capture-sheet');
    await fireEvent.changeText(within(sheet).getByTestId('capture-note'), 'Algo');
    await fireEvent.press(within(sheet).getByTestId('capture-send'));
    expect(await screen.findByText('El envío es demasiado grande')).toBeOnTheScreen();
  });
});


describe('IMG-16 / CAP-16 · opciones e intención', () => {
  it('takes the saved photo default and lets a new capture choose all three states', async () => {
    capturaServer({ 'GET /api/v1/ajustes/preferencias': { body: { gallery_ai_edit: 'no', updated_at: null } } });
    await renderCapture();
    await act(async () => openCaptureSheet(undefined, { draft: { audio: null, fotos: [{ id: 'f1', uri: 'file:///f.jpg', name: 'f.jpg', type: 'image/jpeg', size: 10 }], nota: '', para: null, publicUse: null } }));
    await waitFor(() => expect(screen.getByRole('radio', { name: 'No editar' })).toBeChecked());
    for (const name of ['Que decida el equipo', 'Editar', 'No editar']) {
      await fireEvent.press(screen.getByRole('radio', { name }));
      expect(screen.getByRole('radio', { name })).toBeChecked();
    }
  });

  it('shows the interpreted priority, expected date in Bogotá, evidence and conditions', async () => {
    capturaServer({ 'GET /api/v1/capturas': { body: [historyCapture({
      state: 'usado', publish_asap: true, publish_asap_expected_slot: '2026-11-10T01:30:00Z',
      publish_asap_evidence: 'Publícalo lo antes posible.', publish_asap_reason: 'Sujeto a verificación y veto.',
    })] } });
    await renderCapture();
    await act(async () => openCaptureSheet(undefined, { view: 'history' }));
    expect(await screen.findByText(/Saldrá lo antes posible.*lunes.*9.*20:30/)).toBeOnTheScreen();
    expect(screen.getByText('«Publícalo lo antes posible.»')).toBeOnTheScreen();
    expect(screen.getByText('Sujeto a verificación y veto.')).toBeOnTheScreen();
  });
});

describe('the wave, like WhatsApp', () => {
  it('draws thin bars from 3 to 28 px; live keeps LIVE_BARS levels and a finished recording fits into CLIP_BARS', () => {
    expect([barHeight(0), barHeight(0.5), barHeight(1), barHeight(3), barHeight(Number.NaN)]).toEqual([3, 16, 28, 28, 3]);
    expect(LIVE_BARS).toBeGreaterThan(CLIP_BARS);
    // A short recording keeps the levels it has; a long one is drawn with CLIP_BARS (each the loudest of its slice).
    expect(clipLevels([0.1, 0.5])).toEqual([0.1, 0.5]);
    const long = clipLevels(Array.from({ length: 900 }, (_, i) => (i === 899 ? 1 : 0.2)));
    expect(long).toHaveLength(CLIP_BARS);
    expect(long[CLIP_BARS - 1]).toBe(1);
  });
});
