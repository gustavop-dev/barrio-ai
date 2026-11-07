// The capture: the button (tap, hold, lock, discard with «Recuperar») and the sheet (photo, note,
// «Para qué es», the context chip, the multipart upload with its 5 s «Deshacer», and the microphone
// explained before the system asks).
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import * as ImagePicker from 'expo-image-picker';
import { State } from 'react-native-gesture-handler';
import { createGestureController, fireGestureHandler, getByGestureTestId } from 'react-native-gesture-handler/jest-utils';
import '@/api/transport';
import { audio, resetFakeAudio } from '@/test/fakeAudio';
import { renderApp } from '@/test/render';
import { fakeServer } from '@/test/server';
import { toastDurations } from '@/theme/motion';
import { CaptureButton } from './CaptureButton';
import { CaptureSheetHost } from './CaptureSheet';
import { checkPhotos, toPickedPhoto } from './photos';
import { holdDecision, holdLift, isTooShort } from './hold';
import { closeCaptureSheet, openCaptureSheet, resetCaptureStoreForTests } from './store';

const CAPTURE = { id: 'c1', state: 'recibida', state_label: 'Recibida', undo_until: new Date(Date.now() + 120_000).toISOString(), can_undo: true };

function capturaServer(extra: Parameters<typeof fakeServer>[0] = {}) {
  return fakeServer({
    'GET /api/v1/capturas': { body: { count: 0, next: null, previous: null, results: [] } },
    'POST /api/v1/capturas': { status: 201, body: CAPTURE },
    'DELETE /api/v1/capturas/c1': { body: { ...CAPTURE, state: 'deshecha' } },
    'GET /api/v1/preguntas': { body: [] },
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
});

afterEach(async () => {
  await act(async () => closeCaptureSheet());
});

describe('capture rules (motion.ts gestures.capture)', () => {
  it('slide up 64 to lock, left 110 to discard; up wins', () => {
    expect(holdDecision(0, -65)).toBe('lock');
    expect(holdDecision(-111, 0)).toBe('discard');
    expect(holdDecision(-120, -70)).toBe('lock');
    expect(holdDecision(-50, -30)).toBe('none');
    expect(holdLift(-200)).toBe(-60);
    expect(holdLift(30)).toBe(0);
    expect(isTooShort(1000, 1500)).toBe(true);
    expect(isTooShort(1000, 1700)).toBe(false);
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
  });

  it('sliding left discards it, and «Recuperar» brings the audio back', async () => {
    capturaServer();
    await renderCapture();
    const hold = await startHold();
    await act(async () => {
      hold.update({ translationX: -130 });
      hold.end({ translationX: -130 });
    });
    expect(await screen.findByText('Grabación descartada.')).toBeOnTheScreen();
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
    await fireEvent.press(within(sheet).getByTestId('capture-send'));

    await waitFor(() => expect(server.find('POST', '/api/v1/capturas')).toHaveLength(1));
    const sent = server.find('POST', '/api/v1/capturas')[0]!;
    expect(sent.headers['content-type']).toBeUndefined();
    expect(sent.body).toEqual([
      ['fotos', { uri: 'file:///cache/foto.jpg', name: 'foto.jpg', type: 'image/jpeg' }],
      ['nota', 'Para el post del jueves'],
      ['para', 'post'],
    ]);
    expect(await screen.findByText('Enviado al equipo.')).toBeOnTheScreen();
    expect(screen.queryByTestId('capture-sheet')).toBeNull();

    await fireEvent.press(screen.getByText('Deshacer'));
    await waitFor(() => expect(server.find('DELETE', '/api/v1/capturas/c1')).toHaveLength(1));
    expect(await screen.findByText('Envío deshecho. Lo tienes otra vez en la hoja.')).toBeOnTheScreen();
    const again = await screen.findByTestId('capture-sheet');
    expect(within(again).getByDisplayValue('Para el post del jueves')).toBeOnTheScreen();
    expect(within(again).getByLabelText('Foto adjunta 1')).toBeOnTheScreen();
  });

  it('«Deshacer» stays for 5 seconds (motion.ts toastDurations)', () => {
    expect(toastDurations.withUndo).toBe(5000);
  });

  it('a question context shows its chip and sends contexto and the visibility chosen', async () => {
    const server = capturaServer();
    await renderCapture();
    await act(async () => openCaptureSheet({ tipo: 'pregunta', id: 'q1', label: '¿Aceptas proyectos de 3 meses?' }));
    const sheet = await screen.findByTestId('capture-sheet');
    const chip = within(sheet).getByTestId('capture-context');
    expect(within(chip).getByText('¿Aceptas proyectos de 3 meses?')).toBeOnTheScreen();
    await fireEvent.changeText(within(sheet).getByTestId('capture-note'), 'Sí, si el equipo es pequeño.');
    await fireEvent.press(within(sheet).getByText('Privado'));
    await fireEvent.press(within(sheet).getByTestId('capture-send'));
    await waitFor(() => expect(server.find('POST', '/api/v1/capturas')).toHaveLength(1));
    expect(server.find('POST', '/api/v1/capturas')[0]!.body).toEqual([
      ['nota', 'Sí, si el equipo es pequeño.'],
      ['contexto_tipo', 'pregunta'],
      ['contexto_id', 'q1'],
      ['public_use', 'false'],
    ]);
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

  it('«Foto para la galería» needs a photo', async () => {
    capturaServer();
    await renderCapture();
    await act(async () => openCaptureSheet());
    const sheet = await screen.findByTestId('capture-sheet');
    await fireEvent.changeText(within(sheet).getByTestId('capture-note'), 'Mira');
    await fireEvent.press(within(sheet).getByText('Foto para la galería'));
    expect(within(sheet).getByText('Para «Foto para la galería» adjunta al menos una foto.')).toBeOnTheScreen();
    expect(within(sheet).getByTestId('capture-send')).toBeDisabled();
  });

  it('closing with content asks first', async () => {
    capturaServer();
    await renderCapture();
    await act(async () => openCaptureSheet());
    const sheet = await screen.findByTestId('capture-sheet');
    await fireEvent.changeText(within(sheet).getByTestId('capture-note'), 'Algo');
    await fireEvent.press(within(sheet).getByLabelText('Cerrar sin guardar'));
    expect(await screen.findByText('¿Cerrar sin enviar?')).toBeOnTheScreen();
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
