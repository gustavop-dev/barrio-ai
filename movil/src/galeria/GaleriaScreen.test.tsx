// Galería: the grid with each photo's state, the filter in the route, the upload ten per request
// with its progress, the photo sheet (only what changed is PATCHed), delete after confirming, the
// full-screen viewer and the empty state.
import type { PhotoOutput } from '@compartido/api/capturas';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import { router } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { StyleSheet } from 'react-native';
import '@/api/transport';
import { saveToken } from '@/api/token';
import { apiImageSource } from '@/components/ui';
import { renderApp } from '@/test/render';
import { fakeServer, type FakeHandler } from '@/test/server';
import { colors } from '@/theme/tokens';
import { GaleriaScreen } from './GaleriaScreen';

const routerState = (jest.requireMock('expo-router') as { __state: { params: Record<string, string> } }).__state;
const mockedRouter = router as unknown as { setParams: jest.Mock };

function photo(id: string, extra: Partial<PhotoOutput> = {}): PhotoOutput {
  return {
    id,
    url: `/media/galeria/${id}.jpg`,
    created_at: '2026-11-03T10:00:00-05:00',
    state: 'sin_usar',
    display_state: 'sin_usar',
    label: 'Sin usar',
    tone: 'muted',
    note: '',
    allow_ai_edit: true,
    used_in: null,
    capture_id: null,
    mime: 'image/jpeg',
    size_bytes: 1000,
    width: 1200,
    height: 900,
    ...extra,
  };
}

const CHOSEN = photo('p2', { state: 'elegida', display_state: 'elegida', label: 'Elegida · jue 12', tone: 'info', used_in: { piece_id: 'pz1', date: '2026-11-12', text: 'Elegida para el post del jueves 12' } });
const PHOTOS = [photo('p1', { label: 'Nueva', tone: 'info', display_state: 'nueva' }), CHOSEN, photo('p3', { label: 'Publicada · 2 nov', tone: 'ok', display_state: 'publicada' })];

function page(results: PhotoOutput[], next: string | null = null) {
  return { count: results.length, next, previous: null, results };
}

async function renderGaleria(routes: Record<string, FakeHandler> = {}) {
  const server = fakeServer({ 'GET /api/v1/galeria': { body: page(PHOTOS) }, ...routes });
  const { client } = await renderApp(<GaleriaScreen />);
  return Object.assign(server, { client });
}

function asset(index: number, extra: Partial<ImagePicker.ImagePickerAsset> = {}): ImagePicker.ImagePickerAsset {
  return { uri: `file:///fotos/${index}.jpg`, fileName: `foto-${index}.jpg`, mimeType: 'image/jpeg', fileSize: 2000, width: 100, height: 100, type: 'image', ...extra } as ImagePicker.ImagePickerAsset;
}

beforeEach(async () => {
  routerState.params = {};
  mockedRouter.setParams = jest.fn();
  await saveToken('0ff1ce_dt_prueba');
});

describe('Galería', () => {
  it('shows the header, the note, the filters and a grid with each photo’s state, loading the images with the token', async () => {
    const server = await renderGaleria();
    expect(screen.getByText('Fotos para tus posts.')).toBeOnTheScreen();
    expect(screen.getByText('Para usar la cámara, toca el botón aguamarina y elige «Foto para la galería».')).toBeOnTheScreen();
    expect(screen.getByText('El equipo decide cuándo usarlas y si las edita con IA. Tú puedes dejar una nota o prohibir la edición en cada foto.')).toBeOnTheScreen();
    for (const label of ['Todas', 'Sin usar', 'Elegidas', 'Publicadas']) expect(screen.getByRole('button', { name: label })).toBeOnTheScreen();
    expect(await screen.findByLabelText('Foto del 3 nov, elegida · jue 12')).toBeOnTheScreen();
    expect(screen.getByText('Publicada · 2 nov')).toBeOnTheScreen();
    expect(server.find('GET', '/api/v1/galeria')[0]?.path).toBe('/api/v1/galeria?filtro=todas');
    // Private images: the API origin and the device token; never an absolute URL from elsewhere.
    expect(apiImageSource('/media/galeria/p1.jpg')).toEqual({
      uri: 'https://office.projectapp.co/media/galeria/p1.jpg',
      headers: { Authorization: 'Bearer 0ff1ce_dt_prueba' },
      cacheKey: '/media/galeria/p1.jpg',
    });
    expect(apiImageSource('https://evil.example/x.jpg')).toBeNull();
  });

  it('filters through the API and keeps the filter in the route; a link opens on its filter', async () => {
    const server = await renderGaleria({ 'GET /api/v1/galeria?filtro=elegidas': { body: page([CHOSEN]) } });
    await screen.findByLabelText('Foto del 3 nov, elegida · jue 12');
    await fireEvent.press(screen.getByTestId('filtro-elegidas'));
    await waitFor(() => expect(server.find('GET', '/api/v1/galeria').map((r) => r.path)).toContain('/api/v1/galeria?filtro=elegidas'));
    expect(mockedRouter.setParams).toHaveBeenCalledWith({ filtro: 'elegidas' });
    await waitFor(() => expect(screen.queryByLabelText('Foto del 3 nov, nueva')).toBeNull());
  });

  it('opens on the filter of /galeria?filtro=sin_usar', async () => {
    routerState.params = { filtro: 'sin_usar' };
    const server = await renderGaleria({ 'GET /api/v1/galeria?filtro=sin_usar': { body: page([]) } });
    expect(await screen.findByText('No hay fotos con este filtro.')).toBeOnTheScreen();
    expect(server.find('GET', '/api/v1/galeria')[0]?.path).toBe('/api/v1/galeria?filtro=sin_usar');
    expect(screen.getByTestId('filtro-sin_usar')).toBeSelected();
  });

  it('shows the empty state when there are no photos yet, and «Ver más fotos» when there are more', async () => {
    await renderGaleria({ 'GET /api/v1/galeria': { body: page([]) } });
    expect(await screen.findByText('Todavía no hay fotos')).toBeOnTheScreen();
    expect(screen.getByText('Sube fotos tuyas, de eventos o de tu trabajo. El equipo las usará en tus posts cuando encajen.')).toBeOnTheScreen();
  });

  it('loads the next page with «Ver más fotos»', async () => {
    const server = await renderGaleria({
      'GET /api/v1/galeria?filtro=todas': { body: page(PHOTOS, '/api/v1/galeria?page=2') },
      'GET /api/v1/galeria?filtro=todas&page=2': { body: page([photo('p4', { label: 'Editada con IA', tone: 'ok' })]) },
    });
    await fireEvent.press(await screen.findByText('Ver más fotos'));
    expect(await screen.findByText('Editada con IA')).toBeOnTheScreen();
    expect(server.find('GET', '/api/v1/galeria').map((r) => r.path)).toContain('/api/v1/galeria?filtro=todas&page=2');
  });

  it('uploads 12 photos ten per request, showing each one’s progress, and refuses what does not fit', async () => {
    const picked = [...Array.from({ length: 12 }, (_, i) => asset(i)), asset(99, { fileName: 'video.mov', mimeType: 'video/quicktime' })];
    jest.mocked(ImagePicker.launchImageLibraryAsync).mockResolvedValueOnce({ canceled: false, assets: picked });
    let release: (() => void) | null = null;
    const created = (n: number) => Array.from({ length: n }, (_, i) => photo(`n${i}`));
    let calls = 0;
    const server = await renderGaleria({
      'POST /api/v1/galeria': () => {
        calls += 1;
        return { status: 201, body: created(calls === 1 ? 10 : 2) };
      },
    });
    await screen.findByLabelText('Foto del 3 nov, nueva');
    // Hold the first request to see the progress on its way.
    const realFetch = global.fetch as jest.Mock;
    const held = realFetch.getMockImplementation()!;
    realFetch.mockImplementationOnce((...args: unknown[]) => new Promise((resolve) => (release = () => resolve(held(...(args as [string, object]))))));
    await fireEvent.press(screen.getByTestId('gallery-upload'));
    expect(await screen.findByText('No se subió video.mov: solo JPEG, PNG, WebP o HEIC de hasta 10 MB.')).toBeOnTheScreen();
    expect(await screen.findByText('Subiendo 10 de 12 fotos…')).toBeOnTheScreen();
    expect(screen.getByTestId('upload-0-subiendo')).toBeOnTheScreen();
    expect(screen.getByTestId('upload-11-esperando')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Subiendo…' })).toBeDisabled();
    await act(async () => release?.());
    expect(await screen.findByText('12 fotos subidas. El equipo las verá en su próxima ronda.')).toBeOnTheScreen();
    const posts = server.find('POST', '/api/v1/galeria');
    expect(posts).toHaveLength(2);
    expect((posts[0]!.body as [string, unknown][]).filter(([name]) => name === 'fotos')).toHaveLength(10);
    expect((posts[1]!.body as [string, unknown][]).filter(([name]) => name === 'fotos')).toHaveLength(2);
    expect((posts[0]!.body as [string, unknown][])[0]).toEqual(['fotos', { uri: 'file:///fotos/0.jpg', name: 'foto-0.jpg', type: 'image/jpeg' }]);
    expect(posts[0]!.headers.authorization).toBe('Bearer 0ff1ce_dt_prueba');
    await waitFor(() => expect(screen.queryByTestId('upload-title')).toBeNull());
  });

  it('retries only the photos that did not get in', async () => {
    jest.mocked(ImagePicker.launchImageLibraryAsync).mockResolvedValueOnce({ canceled: false, assets: Array.from({ length: 12 }, (_, i) => asset(i)) });
    let calls = 0;
    const server = await renderGaleria({
      'POST /api/v1/galeria': () => {
        calls += 1;
        return calls === 2 ? { status: 413, body: { detail: 'La foto supera 10 MB.' } } : { status: 201, body: [photo(`n${calls}`)] };
      },
    });
    await screen.findByLabelText('Foto del 3 nov, nueva');
    await fireEvent.press(screen.getByTestId('gallery-upload'));
    expect(await screen.findByText('La foto supera 10 MB.')).toBeOnTheScreen();
    expect(screen.getByText('10 de 12 fotos subidas')).toBeOnTheScreen();
    expect(screen.getByTestId('upload-9-subida')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Reintentar'));
    await waitFor(() => expect(server.find('POST', '/api/v1/galeria')).toHaveLength(3));
    expect((server.find('POST', '/api/v1/galeria')[2]!.body as [string, unknown][]).map(([, part]) => (part as { name: string }).name)).toEqual(['foto-10.jpg', 'foto-11.jpg']);
  });

  it('opens a photo and PATCHes only what changed: the note', async () => {
    const server = await renderGaleria({ 'PATCH /api/v1/galeria/p2': (request) => ({ body: { ...CHOSEN, ...(request.body as object) } }) });
    await fireEvent.press(await screen.findByLabelText('Foto del 3 nov, elegida · jue 12'));
    const sheet = await screen.findByTestId('photo-sheet');
    expect(within(sheet).getByText('Elegida para el post del jueves 12')).toBeOnTheScreen();
    expect(within(sheet).getByRole('button', { name: 'Guardar' })).toBeDisabled();
    await fireEvent.changeText(within(sheet).getByTestId('photo-note'), '  Recórtala para que no se lean nombres.  ');
    await fireEvent.press(within(sheet).getByRole('button', { name: 'Guardar' }));
    await waitFor(() => expect(server.find('PATCH', '/api/v1/galeria/p2')[0]?.body).toEqual({ note: 'Recórtala para que no se lean nombres.' }));
    expect(await screen.findByText('Foto guardada.')).toBeOnTheScreen();
  });

  it('PATCHes only the AI switch when only it changed', async () => {
    const server = await renderGaleria({ 'PATCH /api/v1/galeria/p1': { body: PHOTOS[0] } });
    await fireEvent.press(await screen.findByLabelText('Foto del 3 nov, nueva'));
    const sheet = await screen.findByTestId('photo-sheet');
    const ai = within(sheet).getByRole('switch', { name: 'El equipo puede editarla con IA' });
    expect(ai).toBeChecked();
    await fireEvent.press(ai);
    await fireEvent.press(within(sheet).getByRole('button', { name: 'Guardar' }));
    await waitFor(() => expect(server.find('PATCH', '/api/v1/galeria/p1')[0]?.body).toEqual({ allow_ai_edit: false }));
  });

  it('a photo opened again before the gallery reloads shows what was just saved', async () => {
    const server = await renderGaleria({ 'PATCH /api/v1/galeria/p1': (request) => ({ body: { ...PHOTOS[0], ...(request.body as object) } }) });
    await fireEvent.press(await screen.findByLabelText('Foto del 3 nov, nueva'));
    let sheet = await screen.findByTestId('photo-sheet');
    // From here on the gallery reloads slowly (a phone on a bad network): its list stays the old one for a while.
    const answer = server.fetch.getMockImplementation()!;
    server.fetch.mockImplementation((...args: Parameters<typeof answer>) => {
      const [url, init] = args;
      if ((init?.method ?? 'GET').toUpperCase() === 'GET' && String(url).includes('/api/v1/galeria')) return new Promise(() => {});
      return answer(...args);
    });
    await fireEvent.changeText(within(sheet).getByTestId('photo-note'), 'Sin nombres de clientes');
    await fireEvent.press(within(sheet).getByRole('switch', { name: 'El equipo puede editarla con IA' }));
    await fireEvent.press(within(sheet).getByRole('button', { name: 'Guardar' }));
    expect(await screen.findByText('Foto guardada.')).toBeOnTheScreen();
    await waitFor(() => expect(screen.queryByTestId('photo-sheet')).toBeNull());
    await fireEvent.press(screen.getByLabelText('Foto del 3 nov, nueva'));
    sheet = await screen.findByTestId('photo-sheet');
    expect(within(sheet).getByTestId('photo-note')).toHaveDisplayValue('Sin nombres de clientes');
    expect(within(sheet).getByRole('switch', { name: 'El equipo puede editarla con IA' })).not.toBeChecked();
    expect(within(sheet).getByRole('button', { name: 'Guardar' })).toBeDisabled();
    expect(within(sheet).getByLabelText('Foto: Sin nombres de clientes')).toBeOnTheScreen();
  });

  it('an open photo follows a fresher copy from the server while its fields are untouched', async () => {
    const server = await renderGaleria();
    await fireEvent.press(await screen.findByLabelText('Foto del 3 nov, nueva'));
    const sheet = await screen.findByTestId('photo-sheet');
    expect(within(sheet).getByTestId('photo-note')).toHaveDisplayValue('');
    server.on('GET /api/v1/galeria', { body: page([{ ...PHOTOS[0]!, note: 'Desde la PWA', allow_ai_edit: false }, ...PHOTOS.slice(1)]) });
    await act(async () => server.client.invalidateQueries({ queryKey: ['galeria'] }));
    await waitFor(() => expect(within(screen.getByTestId('photo-sheet')).getByTestId('photo-note')).toHaveDisplayValue('Desde la PWA'));
    expect(within(screen.getByTestId('photo-sheet')).getByRole('switch', { name: 'El equipo puede editarla con IA' })).not.toBeChecked();
    expect(within(screen.getByTestId('photo-sheet')).getByRole('button', { name: 'Guardar' })).toBeDisabled();
  });

  it('removes a photo after confirming, warning where it is used', async () => {
    const server = await renderGaleria({ 'DELETE /api/v1/galeria/p2': { status: 204 } });
    await fireEvent.press(await screen.findByLabelText('Foto del 3 nov, elegida · jue 12'));
    await fireEvent.press(within(await screen.findByTestId('photo-sheet')).getByLabelText('Quitar de la galería: Foto del 3 nov, elegida · jue 12'));
    const confirm = await screen.findByTestId('confirm-sheet');
    expect(within(confirm).getByText('Se borran la foto y su archivo; el equipo ya no podrá usarla.')).toBeOnTheScreen();
    expect(within(confirm).getByText('Ojo: elegida para el post del jueves 12.')).toBeOnTheScreen();
    expect(server.find('DELETE', '/api/v1/galeria/p2')).toHaveLength(0);
    await fireEvent.press(within(confirm).getByRole('button', { name: 'Quitar la foto' }));
    await waitFor(() => expect(server.find('DELETE', '/api/v1/galeria/p2')).toHaveLength(1));
    expect(await screen.findByText('Foto quitada de la galería.')).toBeOnTheScreen();
  });

  it('shows the photo on ink in the viewer: nothing light around it, so «N de M» and the caption read in white', async () => {
    await renderGaleria();
    await fireEvent.press(await screen.findByLabelText('Foto del 3 nov, nueva'));
    await fireEvent.press(within(await screen.findByTestId('photo-sheet')).getByTestId('photo-sheet-image'));
    const viewer = await screen.findByTestId('photo-viewer');
    expect(StyleSheet.flatten(viewer.props.style).backgroundColor).toBe(colors.ink);
    expect(StyleSheet.flatten(within(viewer).getByTestId('photo-viewer-count').props.style).color).toBe(colors.paper);
    // The fitted photo fills the whole page: a placeholder colour on it would cover the ink around the picture.
    const image = within(viewer).getByLabelText('Foto del 3 nov, nueva');
    expect(StyleSheet.flatten(image.props.style).backgroundColor ?? 'transparent').toBe('transparent');
  });

  it('opens the full-screen viewer from the sheet and moves between photos', async () => {
    await renderGaleria();
    await fireEvent.press(await screen.findByLabelText('Foto del 3 nov, elegida · jue 12'));
    await fireEvent.press(within(await screen.findByTestId('photo-sheet')).getByTestId('photo-sheet-image'));
    const viewer = await screen.findByTestId('photo-viewer');
    expect(within(viewer).getByTestId('photo-viewer-count')).toHaveTextContent('2 de 3');
    const pager = within(viewer).getByRole('adjustable');
    await fireEvent(pager, 'accessibilityAction', { nativeEvent: { actionName: 'increment' } });
    expect(within(viewer).getByTestId('photo-viewer-count')).toHaveTextContent('3 de 3');
    await fireEvent.press(within(viewer).getByRole('button', { name: 'Cerrar' }));
    // The sheet follows the photo seen last.
    await waitFor(() => expect(screen.queryByTestId('photo-viewer')).toBeNull());
    expect(within(screen.getByTestId('photo-sheet')).getByText('Publicada · 2 nov')).toBeOnTheScreen();
  });
});
