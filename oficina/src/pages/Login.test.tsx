import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { RequireAuth } from '../auth/session';
import { fakeServer, SESSION_NONE, SESSION_OK } from '../test/fakeServer';
import { renderAt } from '../test/render';
import { LOCK_MS, Login, safeNext } from './Login';

const routes = [
  { path: '/login', element: <Login /> },
  {
    path: '/calendario',
    element: (
      <RequireAuth>
        <p>El calendario</p>
      </RequireAuth>
    ),
  },
];

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>, password = 'clave-segura') {
  await user.type(await screen.findByLabelText('Usuario'), 'gustavo');
  await user.type(screen.getByLabelText('Contraseña'), password);
  await user.click(screen.getByRole('button', { name: 'Entrar' }));
}

afterEach(() => {
  vi.useRealTimers();
});

describe('Login', () => {
  it('shows «Comprobando sesión…» while the session is being checked', async () => {
    let release: (value: { body: unknown }) => void = () => {};
    fakeServer({ 'GET /api/v1/auth/session': () => new Promise((resolve) => (release = resolve)) });
    renderAt('/login', routes);
    expect(screen.getByText('Comprobando sesión…')).toBeInTheDocument();
    expect(screen.getByAltText('0ff1ce')).toHaveAttribute('src', '/brand/isotipo.svg');
    await act(async () => release({ body: SESSION_NONE }));
    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument();
  });

  it('shows the hero on tinta, the logo and the form', async () => {
    fakeServer({ 'GET /api/v1/auth/session': { body: SESSION_NONE } });
    renderAt('/login', routes);
    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument();
    expect(screen.getByAltText(/La oficina de 0ff1ce de tarde/)).toHaveAttribute('src', '/brand/login-oficina-tarde.png');
    expect(screen.getByAltText('0ff1ce')).toHaveAttribute('src', '/brand/logo-inverso.svg');
    expect(screen.getByText('Usa tu usuario y contraseña de Django.')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('redirects a protected page to /login and back after signing in, showing «Entrando…» meanwhile', async () => {
    let signedIn = false;
    let finishLogin: () => void = () => {};
    const server = fakeServer({
      'GET /api/v1/auth/session': () => {
        document.cookie = 'csrftoken=tok123';
        return { body: signedIn ? SESSION_OK : SESSION_NONE };
      },
      'POST /api/v1/auth/login': (request) =>
        new Promise((resolve) => {
          finishLogin = () => {
            signedIn = true;
            resolve({ body: { user: { ...SESSION_OK.user, username: (request.body as { username: string }).username } } });
          };
        }),
    });
    const user = userEvent.setup();
    renderAt('/calendario', routes);

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/login?next=%2Fcalendario');

    await fillAndSubmit(user);
    const sending = await screen.findByRole('button', { name: 'Entrando…' });
    expect(sending).toBeDisabled();
    await act(async () => finishLogin());

    expect(await screen.findByText('El calendario')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/calendario');
    const [login] = server.find('POST', '/api/v1/auth/login');
    expect(login?.body).toEqual({ username: 'gustavo', password: 'clave-segura' });
    expect(login?.headers['x-csrftoken']).toBe('tok123');
  });

  it('says the credentials are wrong on a 400', async () => {
    fakeServer({
      'GET /api/v1/auth/session': { body: SESSION_NONE },
      'POST /api/v1/auth/login': { status: 400, body: { detail: 'Credenciales inválidas' } },
    });
    const user = userEvent.setup();
    renderAt('/login', routes);
    await fillAndSubmit(user, 'mal');
    expect(await screen.findByRole('alert')).toHaveTextContent('Usuario o contraseña incorrectos.');
    expect(screen.getByTestId('location')).toHaveTextContent('/login');
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeEnabled();
  });

  it('says it could not reach the office when the network fails', async () => {
    const server = fakeServer({ 'GET /api/v1/auth/session': { body: SESSION_NONE } });
    server.on('POST /api/v1/auth/login', () => Promise.reject(new TypeError('Failed to fetch')));
    const user = userEvent.setup();
    renderAt('/login', routes);
    await fillAndSubmit(user);
    expect(await screen.findByRole('alert')).toHaveTextContent('No pudimos conectar con la oficina. Revisa tu conexión e intenta de nuevo.');
  });

  it('locks the button after a 429 and unlocks it later', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fakeServer({
      'GET /api/v1/auth/session': { body: SESSION_NONE },
      'POST /api/v1/auth/login': { status: 429, body: { detail: 'Demasiados intentos.' } },
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderAt('/login', routes);
    await fillAndSubmit(user, 'x');
    expect(await screen.findByRole('alert')).toHaveTextContent('Demasiados intentos. Espera unos minutos.');
    const button = screen.getByRole('button', { name: 'Entrar' });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('data-locked', 'true');

    await act(async () => {
      vi.advanceTimersByTime(LOCK_MS + 10);
    });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Entrar' })).toBeEnabled());
    expect(screen.getByRole('alert')).toHaveTextContent('Demasiados intentos');
  });

  it('shows and hides the password', async () => {
    fakeServer({ 'GET /api/v1/auth/session': { body: SESSION_NONE } });
    const user = userEvent.setup();
    renderAt('/login', routes);
    const password = await screen.findByLabelText('Contraseña');
    expect(password).toHaveAttribute('type', 'password');
    const toggle = screen.getByRole('button', { name: 'Mostrar contraseña' });
    expect(toggle).toHaveAttribute('aria-pressed', 'false');
    await user.click(toggle);
    expect(password).toHaveAttribute('type', 'text');
    expect(screen.getByRole('button', { name: 'Ocultar contraseña' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('does not send an empty form: it focuses the missing field', async () => {
    const server = fakeServer({ 'GET /api/v1/auth/session': { body: SESSION_NONE } });
    const user = userEvent.setup();
    renderAt('/login', routes);
    await user.click(await screen.findByRole('button', { name: 'Entrar' }));
    expect(screen.getByLabelText('Usuario')).toHaveFocus();
    expect(server.find('POST', '/api/v1/auth/login')).toHaveLength(0);
  });

  it('only accepts in-app destinations after login', () => {
    expect(safeNext('/tu-turno?x=1')).toBe('/tu-turno?x=1');
    expect(safeNext('//evil.example')).toBe('/');
    expect(safeNext('https://evil.example')).toBe('/');
    expect(safeNext('/login?next=/x')).toBe('/');
    expect(safeNext(null)).toBe('/');
  });
});
