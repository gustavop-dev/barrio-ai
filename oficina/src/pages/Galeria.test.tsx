import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { PhotoOutput } from '../api/capturas';
import { fakeServer, SESSION_OK, type Handler, type Reply } from '../test/fakeServer';
import { renderAt } from '../test/render';
import { Galeria } from './Galeria';

function foto(overrides: Partial<PhotoOutput> = {}): PhotoOutput {
  return {
    id: 'f1',
    url: '/api/v1/galeria/f1/imagen',
    created_at: '2026-11-03T15:00:00Z',
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
    width: null,
    height: null,
    ...overrides,
  };
}

const PHOTOS = [
  foto({ id: 'f1', url: '/api/v1/galeria/f1/imagen', display_state: 'nueva', label: 'Nueva', tone: 'info' }),
  foto({
    id: 'f2',
    url: '/api/v1/galeria/f2/imagen',
    state: 'elegida',
    display_state: 'elegida',
    label: 'Elegida · dom 8',
    tone: 'info',
    note: 'Úsala en el post del domingo',
    used_in: { piece_id: 'p8', date: '2026-11-08', text: 'Elegida para el post del domingo 8' },
  }),
  foto({ id: 'f3', url: '/api/v1/galeria/f3/imagen', state: 'publicada', display_state: 'publicada', label: 'Publicada · 2 nov', tone: 'ok', allow_ai_edit: false }),
];

const page = (results: PhotoOutput[]) => ({ count: results.length, next: null, previous: null, results });

function server(extra: Record<string, Handler | Reply> = {}) {
  return fakeServer({
    'GET /api/v1/auth/session': { body: SESSION_OK },
    'GET /api/v1/galeria': (request) => ({ body: page(request.search.get('filtro') === 'publicadas' ? [PHOTOS[2]!] : PHOTOS) }),
    ...extra,
  });
}

const routes = [{ path: '/galeria', element: <Galeria /> }];

describe('Galería', () => {
  it('shows the header, the note, the filters and a grid with each photo’s state', async () => {
    server();
    renderAt('/galeria', routes);
    expect(screen.getByRole('heading', { name: 'Galería', level: 1 })).toBeInTheDocument();
    expect(screen.getByText('Fotos para tus posts.')).toBeInTheDocument();
    expect(screen.getByText(/El equipo decide cuándo usarlas y si las edita con IA/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Subir fotos/)).toHaveAttribute('multiple');
    const filters = screen.getByRole('group', { name: 'Filtrar fotos' });
    expect(within(filters).getAllByRole('button').map((b) => b.textContent)).toEqual(['Todas', 'Sin usar', 'Elegidas', 'Publicadas']);
    expect(within(filters).getByRole('button', { name: 'Todas' })).toHaveAttribute('aria-pressed', 'true');

    const grid = await screen.findByRole('list', { name: 'Fotos' });
    const tiles = within(grid).getAllByRole('button');
    expect(tiles).toHaveLength(3);
    expect(tiles[1]).toHaveAccessibleName('Foto del 3 nov, elegida · dom 8');
    expect(within(tiles[1]!).getByText('Elegida · dom 8')).toHaveClass('badge', 'info');
    expect(within(tiles[2]!).getByText('Publicada · 2 nov')).toHaveClass('badge', 'ok');
    expect(tiles[0]!.querySelector('img')).toHaveAttribute('src', '/api/v1/galeria/f1/imagen');
  });

  it('filters through the API and keeps the filter in the URL', async () => {
    const api = server();
    const user = userEvent.setup();
    renderAt('/galeria', routes);
    await screen.findByRole('list', { name: 'Fotos' });
    await user.click(screen.getByRole('button', { name: 'Publicadas' }));
    await waitFor(() => expect(within(screen.getByRole('list', { name: 'Fotos' })).getAllByRole('button')).toHaveLength(1));
    expect(api.requests.some((r) => r.path === '/api/v1/galeria' && r.search.get('filtro') === 'publicadas')).toBe(true);
    expect(screen.getByTestId('location')).toHaveTextContent('/galeria?filtro=publicadas');
  });

  it('opens a photo, saves its note and the AI switch', async () => {
    const api = server({ 'PATCH /api/v1/galeria/f2': (request) => ({ body: { ...PHOTOS[1], ...(request.body as object) } }) });
    const user = userEvent.setup();
    renderAt('/galeria', routes);
    await user.click(await screen.findByRole('button', { name: 'Foto del 3 nov, elegida · dom 8' }));

    const sheet = screen.getByRole('dialog', { name: 'Foto' });
    expect(within(sheet).getByRole('img')).toHaveAttribute('src', '/api/v1/galeria/f2/imagen');
    expect(within(sheet).getByText('Elegida para el post del domingo 8')).toBeInTheDocument();
    const save = within(sheet).getByRole('button', { name: 'Guardar' });
    expect(save).toBeDisabled();
    const note = within(sheet).getByLabelText('Nota para el equipo (opcional)');
    expect(note).toHaveValue('Úsala en el post del domingo');
    await user.clear(note);
    await user.type(note, 'Recórtala sin nombres');
    const ai = within(sheet).getByRole('switch', { name: 'El equipo puede editarla con IA' });
    expect(ai).toBeChecked();
    await user.click(ai);
    await user.click(save);

    expect(await screen.findByText('Foto guardada.')).toBeInTheDocument();
    expect(api.find('PATCH', '/api/v1/galeria/f2')[0]?.body).toEqual({ note: 'Recórtala sin nombres', allow_ai_edit: false });
    expect(screen.queryByRole('dialog', { name: 'Foto' })).not.toBeInTheDocument();
  });

  it('removes a photo after confirming', async () => {
    const api = server({ 'DELETE /api/v1/galeria/f3': { status: 204 } });
    const user = userEvent.setup();
    renderAt('/galeria', routes);
    await user.click(await screen.findByRole('button', { name: /Foto del 3 nov, publicada/ }));
    expect(within(screen.getByRole('dialog', { name: 'Foto' })).getByText('Todavía sin usar')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Quitar de la galería' }));
    const confirm = screen.getByRole('dialog', { name: '¿Quitar esta foto de la galería?' });
    await user.click(within(confirm).getByRole('button', { name: 'Quitar la foto' }));
    expect(await screen.findByText('Foto quitada de la galería.')).toBeInTheDocument();
    expect(api.find('DELETE', '/api/v1/galeria/f3')).toHaveLength(1);
  });

  it('uploads several photos at once as multipart', async () => {
    document.cookie = 'csrftoken=tok';
    const api = server({ 'POST /api/v1/galeria': { status: 201, body: [foto({ id: 'n1' }), foto({ id: 'n2' })] } });
    const user = userEvent.setup();
    renderAt('/galeria', routes);
    await screen.findByRole('list', { name: 'Fotos' });
    await user.upload(screen.getByLabelText(/Subir fotos/), [new File(['a'], 'a.jpg', { type: 'image/jpeg' }), new File(['b'], 'b.png', { type: 'image/png' })]);
    expect(await screen.findByText('2 fotos subidas. El equipo las verá en su próxima ronda.')).toBeInTheDocument();
    const call = api.fetch.mock.calls.find(([input, init]) => String(input) === '/api/v1/galeria' && init?.method === 'POST');
    const form = call![1]!.body as FormData;
    expect(form.getAll('fotos').map((f) => (f as File).name)).toEqual(['a.jpg', 'b.png']);
    expect(new Headers(call![1]!.headers).get('content-type')).toBeNull();
    expect(new Headers(call![1]!.headers).get('x-csrftoken')).toBe('tok');
  });

  it('shows the empty state when there are no photos yet', async () => {
    fakeServer({ 'GET /api/v1/auth/session': { body: SESSION_OK }, 'GET /api/v1/galeria': { body: page([]) } });
    renderAt('/galeria', routes);
    expect(await screen.findByText(/Sube fotos tuyas, de eventos o de tu trabajo/)).toBeInTheDocument();
  });
});
