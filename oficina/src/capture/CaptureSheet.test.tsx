import { QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { CaptureOutput } from '../api/capturas';
import { AppRoutes } from '../App';
import { SessionBridge } from '../auth/session';
import { ToastProvider } from '../components/ui/Toast';
import { overviewFixture, tuTurnoFixture } from '../test/app';
import { fakeServer, SESSION_OK, type Handler, type Reply } from '../test/fakeServer';
import { LocationProbe, testQueryClient } from '../test/render';
import { CAPTURE_LABEL, CaptureProvider } from './CaptureContext';
import { installFakeMedia, removeFakeMedia } from './fakeMedia';
import { resetMicStateForTests } from './recorder';
import { openCaptureSheet, resetCaptureStoreForTests } from './store';

/** The whole app with the real capture wiring of App.tsx. */
function renderWithCapture(path = '/galeria') {
  const client = testQueryClient();
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <CaptureProvider onCapture={openCaptureSheet}>
          <MemoryRouter initialEntries={[path]}>
            <SessionBridge>
              <AppRoutes />
              <LocationProbe />
            </SessionBridge>
          </MemoryRouter>
        </CaptureProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { client };
}

export function captureFixture(overrides: Partial<CaptureOutput> = {}): CaptureOutput {
  return {
    id: 'c1',
    created_at: new Date().toISOString(),
    note: '',
    purpose: null,
    purpose_label: null,
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
    ...overrides,
  };
}

const EMPTY_PAGE = { count: 0, next: null, previous: null, results: [] };

function server(extra: Record<string, Handler | Reply> = {}) {
  return fakeServer({
    'GET /api/v1/auth/session': { body: SESSION_OK },
    'GET /api/v1/tu-turno': { body: tuTurnoFixture() },
    'GET /api/v1/operador/overview': { body: overviewFixture() },
    'GET /api/v1/galeria': { body: EMPTY_PAGE },
    'GET /api/v1/capturas': { body: EMPTY_PAGE },
    ...extra,
  });
}

/** The FormData sent with the last POST to `path`. */
function sentForm(fetchMock: ReturnType<typeof fakeServer>['fetch'], path: string): FormData {
  const call = [...fetchMock.mock.calls].reverse().find(([input, init]) => String(input) === path && (init?.method ?? 'GET').toUpperCase() === 'POST');
  if (!call) throw new Error(`No POST to ${path}`);
  return call[1]!.body as FormData;
}

function postHeaders(fetchMock: ReturnType<typeof fakeServer>['fetch'], path: string): Headers {
  const call = [...fetchMock.mock.calls].reverse().find(([input, init]) => String(input) === path && (init?.method ?? 'GET').toUpperCase() === 'POST');
  return new Headers(call?.[1]?.headers);
}

const dialog = () => screen.getByRole('dialog', { name: 'Captura para el equipo' });
const photo = (name: string) => new File(['img'], name, { type: 'image/jpeg' });

beforeEach(() => {
  resetCaptureStoreForTests();
  resetMicStateForTests();
});
afterEach(() => removeFakeMedia());

describe('Captura · hoja', () => {
  it('sends a note, a purpose and two photos in one multipart POST, then undoes it and gives the content back', async () => {
    document.cookie = 'csrftoken=tok';
    const api = server({
      'POST /api/v1/capturas': { status: 201, body: captureFixture({ id: 'c9' }) },
      'DELETE /api/v1/capturas/c9': { body: captureFixture({ id: 'c9', state: 'deshecha' }) },
    });
    const user = userEvent.setup();
    renderWithCapture();
    await screen.findByRole('heading', { name: 'Galería', level: 1 });

    await user.click(screen.getByRole('button', { name: CAPTURE_LABEL }));
    const sheet = dialog();
    const send = within(sheet).getByRole('button', { name: 'Guardar y enviar al equipo' });
    expect(send).toBeDisabled();
    expect(within(sheet).getByRole('button', { name: 'Grabar un audio' })).toBeInTheDocument();
    expect(within(sheet).getByText('Si no eliges, el equipo lo transcribe y decide.')).toBeInTheDocument();

    await user.type(within(sheet).getByLabelText('Nota para el equipo (opcional)'), 'Para el post del jueves');
    expect(send).toBeEnabled();
    await user.click(within(sheet).getByRole('button', { name: 'Idea para un post' }));
    expect(within(sheet).getByRole('button', { name: 'Idea para un post' })).toHaveAttribute('aria-pressed', 'true');
    await user.upload(within(sheet).getByLabelText('Galería'), [photo('pizarra.jpg'), photo('evento.jpg')]);
    expect(within(sheet).getAllByRole('img', { name: /Foto adjunta/ })).toHaveLength(2);
    await user.click(within(sheet).getByRole('button', { name: 'Quitar la foto 2' }));
    await user.upload(within(sheet).getByLabelText('Galería'), [photo('evento.jpg')]);

    await user.click(send);
    expect(await screen.findByText('Enviado al equipo.')).toBeInTheDocument();
    expect(screen.queryByRole('dialog', { name: 'Captura para el equipo' })).not.toBeInTheDocument();

    const form = sentForm(api.fetch, '/api/v1/capturas');
    expect(form.get('nota')).toBe('Para el post del jueves');
    expect(form.get('para')).toBe('post');
    expect(form.getAll('fotos').map((f) => (f as File).name)).toEqual(['pizarra.jpg', 'evento.jpg']);
    expect(form.has('audio')).toBe(false);
    expect(form.has('contexto_tipo')).toBe(false);
    const headers = postHeaders(api.fetch, '/api/v1/capturas');
    expect(headers.get('x-csrftoken')).toBe('tok');
    expect(headers.get('content-type')).toBeNull();

    await user.click(screen.getByRole('button', { name: 'Deshacer' }));
    expect(await screen.findByText(/Envío deshecho/)).toBeInTheDocument();
    expect(api.find('DELETE', '/api/v1/capturas/c9')).toHaveLength(1);
    // The sheet comes back with what was sent.
    const again = await screen.findByRole('dialog', { name: 'Captura para el equipo' });
    expect(within(again).getByLabelText('Nota para el equipo (opcional)')).toHaveValue('Para el post del jueves');
    expect(within(again).getAllByRole('img', { name: /Foto adjunta/ })).toHaveLength(2);
  });

  it('shows the question as a removable chip with its visibility, and sends both', async () => {
    const api = server({
      'GET /api/v1/preguntas': {
        body: [{ id: 'q1', agent: 'director_editorial', agent_label: 'Director editorial', question: '¿Has liderado una migración?', suggested_public: false }],
      },
      'POST /api/v1/capturas': { status: 201, body: captureFixture() },
    });
    const user = userEvent.setup();
    renderWithCapture();
    await screen.findByRole('heading', { name: 'Galería', level: 1 });
    act(() => openCaptureSheet({ tipo: 'pregunta', id: 'q1', label: '¿Has liderado una migración?' }));

    const sheet = dialog();
    expect(await within(sheet).findByText('Responde a Director editorial')).toBeInTheDocument();
    expect(within(sheet).getByText('¿Has liderado una migración?')).toBeInTheDocument();
    expect(within(sheet).getByRole('radio', { name: /Privado/ })).toBeChecked();
    await user.click(within(sheet).getByRole('radio', { name: /Público/ }));
    await user.type(within(sheet).getByLabelText('Nota para el equipo (opcional)'), 'Sí, por partes.');
    await user.click(within(sheet).getByRole('button', { name: 'Guardar y enviar al equipo' }));
    await screen.findByText('Enviado al equipo.');

    const form = sentForm(api.fetch, '/api/v1/capturas');
    expect(form.get('contexto_tipo')).toBe('pregunta');
    expect(form.get('contexto_id')).toBe('q1');
    expect(form.get('public_use')).toBe('true');
  });

  it('lets the context go: the capture then goes loose', async () => {
    const api = server({ 'POST /api/v1/capturas': { status: 201, body: captureFixture() } });
    const user = userEvent.setup();
    renderWithCapture();
    await screen.findByRole('heading', { name: 'Galería', level: 1 });
    act(() => openCaptureSheet({ tipo: 'persona', id: 'p4', label: 'Lucía Ficticia · Huerta Labs' }));

    const sheet = dialog();
    expect(within(sheet).getByText('Nota sobre')).toBeInTheDocument();
    expect(within(sheet).getByText('Lucía Ficticia · Huerta Labs')).toBeInTheDocument();
    await user.click(within(sheet).getByRole('button', { name: 'Quitar el contexto' }));
    expect(within(sheet).queryByText('Lucía Ficticia · Huerta Labs')).not.toBeInTheDocument();
    await user.type(within(sheet).getByLabelText('Nota para el equipo (opcional)'), 'Me escribió ayer');
    await user.click(within(sheet).getByRole('button', { name: 'Guardar y enviar al equipo' }));
    await screen.findByText('Enviado al equipo.');
    expect(sentForm(api.fetch, '/api/v1/capturas').has('contexto_tipo')).toBe(false);
  });

  it('asks before closing a capture with content', async () => {
    server();
    const user = userEvent.setup();
    renderWithCapture();
    await screen.findByRole('heading', { name: 'Galería', level: 1 });
    await user.click(screen.getByRole('button', { name: CAPTURE_LABEL }));
    await user.type(within(dialog()).getByLabelText('Nota para el equipo (opcional)'), 'Algo');
    await user.click(within(dialog()).getByRole('button', { name: 'Cerrar sin enviar' }));
    const confirm = screen.getByRole('dialog', { name: '¿Cerrar sin enviar?' });
    await user.click(within(confirm).getByRole('button', { name: 'Seguir aquí' }));
    expect(dialog()).toBeInTheDocument();
    await user.click(within(dialog()).getByRole('button', { name: 'Cerrar sin enviar' }));
    await user.click(within(screen.getByRole('dialog', { name: '¿Cerrar sin enviar?' })).getByRole('button', { name: 'Cerrar sin enviar' }));
    expect(screen.queryByRole('dialog', { name: 'Captura para el equipo' })).not.toBeInTheDocument();
  });

  it('shows the first-use hint until the first use', async () => {
    server();
    const user = userEvent.setup();
    renderWithCapture();
    await screen.findByRole('heading', { name: 'Galería', level: 1 });
    expect(screen.getByText('Mantén oprimido para grabar. Toca para foto o nota.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: CAPTURE_LABEL }));
    await user.click(within(dialog()).getByRole('button', { name: 'Cerrar sin enviar' }));
    expect(screen.queryByText('Mantén oprimido para grabar. Toca para foto o nota.')).not.toBeInTheDocument();
  });
});

describe('Captura · audio y micrófono', () => {
  it('explains the microphone first, then records, finishes and sends the audio', async () => {
    installFakeMedia();
    resetMicStateForTests('prompt');
    const api = server({ 'POST /api/v1/capturas': { status: 201, body: captureFixture() } });
    const user = userEvent.setup();
    renderWithCapture();
    await screen.findByRole('heading', { name: 'Galería', level: 1 });
    await user.click(screen.getByRole('button', { name: CAPTURE_LABEL }));

    await user.click(within(dialog()).getByRole('button', { name: 'Grabar un audio' }));
    expect(within(dialog()).getByText('Para grabar, 0ff1ce necesita el micrófono')).toBeInTheDocument();
    await user.click(within(dialog()).getByRole('button', { name: 'Permitir el micrófono' }));
    expect(await within(dialog()).findByText('Grabando')).toBeInTheDocument();
    expect(within(dialog()).getByRole('button', { name: 'Pausar' })).toBeEnabled();
    await user.click(within(dialog()).getByRole('button', { name: 'Pausar' }));
    expect(within(dialog()).getByText('En pausa')).toBeInTheDocument();
    await user.click(within(dialog()).getByRole('button', { name: 'Seguir' }));
    await user.click(within(dialog()).getByRole('button', { name: 'Terminar' }));

    expect(await within(dialog()).findByRole('button', { name: 'Escuchar el audio' })).toBeInTheDocument();
    expect(within(dialog()).getByRole('button', { name: 'Quitar el audio' })).toBeInTheDocument();
    await user.click(within(dialog()).getByRole('button', { name: 'Guardar y enviar al equipo' }));
    await screen.findByText('Enviado al equipo.');

    const form = sentForm(api.fetch, '/api/v1/capturas');
    expect((form.get('audio') as File).name).toBe('captura.webm');
    expect(form.get('audio_duration_s')).not.toBeNull();
  });

  it('opens without audio and points to Ajustes when the microphone is blocked', async () => {
    server();
    const user = userEvent.setup();
    renderWithCapture();
    await screen.findByRole('heading', { name: 'Galería', level: 1 });
    act(() => openCaptureSheet(undefined, { mic: 'denied' }));
    expect(within(dialog()).getByText('El micrófono está bloqueado')).toBeInTheDocument();
    expect(within(dialog()).queryByRole('button', { name: 'Grabar un audio' })).not.toBeInTheDocument();
    await user.click(within(dialog()).getByRole('button', { name: 'Ir a Ajustes › Captura y galería' }));
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/ajustes'));
    expect(screen.queryByRole('dialog', { name: 'Captura para el equipo' })).not.toBeInTheDocument();
  });

  it('opens with a recording locked from the button, on the pulsing ball', async () => {
    installFakeMedia();
    server();
    renderWithCapture();
    await screen.findByRole('heading', { name: 'Galería', level: 1 });
    const { Recorder } = await import('./recorder');
    act(() => openCaptureSheet(undefined, { recorder: Recorder.start() }));
    expect(await within(dialog()).findByText('Grabando · bloqueado')).toBeInTheDocument();
    expect(dialog().querySelector('.cap-ball.cap-pulse')).not.toBeNull();
    expect(within(dialog()).getByRole('button', { name: 'Descartar' })).toBeInTheDocument();
    await userEvent.setup().click(within(dialog()).getByRole('button', { name: 'Descartar' }));
    expect(within(dialog()).getByRole('button', { name: 'Grabar un audio' })).toBeInTheDocument();
  });
});

describe('Captura · Lo que enviaste', () => {
  const HISTORY = {
    count: 3,
    next: null,
    previous: null,
    results: [
      captureFixture({
        id: 'h1',
        has_audio: true,
        audio_duration_s: 42,
        audio_url: '/api/v1/capturas/h1/audio',
        photos: [{ id: 'f1', url: '/api/v1/galeria/f1/imagen' }],
        purpose: 'post',
        purpose_label: 'Idea para un post',
        transcript: 'Hoy en una llamada salió algo bueno',
        state: 'procesando',
        state_label: 'Procesando',
        outcome: { kind: 'procesando', text: 'Mesa editorial lo está leyendo', link: null },
      }),
      captureFixture({
        id: 'h2',
        created_at: new Date(Date.now() - 86_400_000).toISOString(),
        note: 'Prefiero no nombrar clientes en público.',
        team_decided: { purpose: 'dato', label: 'Dato sobre mí', reason: 'Cuenta una preferencia suya.' },
        state: 'dato_guardado',
        state_label: 'Dato guardado',
        outcome: { kind: 'dato_guardado', text: 'Está en Lo que el equipo sabe de ti · Privado', link: '/tu-turno/sabe' },
        can_undo: false,
      }),
      captureFixture({ id: 'h3', note: 'Una idea', state: 'sin_usar', state_label: 'Sin usar', outcome: { kind: 'sin_usar', text: 'Pasaron 14 días sin que encajara en un brief', link: null }, can_undo: false }),
    ],
  };

  it('opens from the header link with its counter and shows what each capture became', async () => {
    const api = server({
      'GET /api/v1/capturas': { body: HISTORY },
      'GET /api/v1/capturas/h1': { body: HISTORY.results[0] },
    });
    const user = userEvent.setup();
    renderWithCapture();
    await screen.findByRole('heading', { name: 'Galería', level: 1 });
    await user.click(screen.getByRole('button', { name: CAPTURE_LABEL }));
    await user.click(await within(dialog()).findByRole('button', { name: 'Lo que enviaste · 3' }));

    const cards = within(dialog()).getAllByRole('listitem');
    expect(cards).toHaveLength(3);
    expect(within(cards[0]!).getByText('Audio 0:42')).toBeInTheDocument();
    expect(within(cards[0]!).getByText('1 foto')).toBeInTheDocument();
    expect(within(cards[0]!).getByText(/^Hoy, .* · Idea para un post$/)).toBeInTheDocument();
    expect(within(cards[0]!).getByText('«Hoy en una llamada salió algo bueno»')).toBeInTheDocument();
    expect(within(cards[0]!).getByText('Procesando')).toBeInTheDocument();
    expect(within(cards[0]!).getByRole('button', { name: 'Escuchar' })).toBeInTheDocument();
    expect(within(cards[0]!).getByRole('button', { name: 'Deshacer' })).toBeInTheDocument();
    expect(within(cards[1]!).getByText(/^Ayer, .* · Dato sobre mí · lo decidió el equipo$/)).toBeInTheDocument();
    expect(within(cards[1]!).getByText('Nota')).toBeInTheDocument();
    expect(within(cards[2]!).getByText('Sin usar')).toBeInTheDocument();
    // A capture being processed is polled by id.
    await waitFor(() => expect(api.find('GET', '/api/v1/capturas/h1').length).toBeGreaterThan(0), { timeout: 4000 });

    await user.click(within(cards[1]!).getByRole('link', { name: 'Está en Lo que el equipo sabe de ti · Privado' }));
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/tu-turno/sabe'));
    expect(screen.queryByRole('dialog', { name: 'Captura para el equipo' })).not.toBeInTheDocument();
  });

  it('opens on the history from the notification link (?enviado=1) and cleans the URL', async () => {
    server({ 'GET /api/v1/capturas': { body: HISTORY } });
    renderWithCapture('/galeria?enviado=1');
    expect(await screen.findByRole('button', { name: 'Volver a la captura' })).toBeInTheDocument();
    expect(await within(dialog()).findAllByRole('listitem')).toHaveLength(3);
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/galeria'));
  });

  it('says so when nothing was sent yet', async () => {
    server();
    renderWithCapture();
    await screen.findByRole('heading', { name: 'Galería', level: 1 });
    act(() => openCaptureSheet(undefined, { view: 'history' }));
    expect(await within(dialog()).findByText('Todavía no has enviado nada')).toBeInTheDocument();
  });
});
