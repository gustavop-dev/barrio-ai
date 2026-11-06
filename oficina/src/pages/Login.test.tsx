import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { RequireAuth } from '../auth/session';
import { fakeServer, SESSION_NONE, SESSION_OK } from '../test/fakeServer';
import { renderAt } from '../test/render';
import { Login, safeNext } from './Login';

const routes = [
  { path: '/login', element: <Login /> },
  {
    path: '/maquina',
    element: (
      <RequireAuth>
        <p>Panel de la máquina</p>
      </RequireAuth>
    ),
  },
];

describe('Login', () => {
  it('redirects a protected page to /login and back after signing in', async () => {
    let signedIn = false;
    const server = fakeServer({
      'GET /api/v1/auth/session': () => {
        document.cookie = 'csrftoken=tok123';
        return { body: signedIn ? SESSION_OK : SESSION_NONE };
      },
      'POST /api/v1/auth/login': (request) => {
        signedIn = true;
        return { body: { user: { ...SESSION_OK.user, username: (request.body as { username: string }).username } } };
      },
    });
    const user = userEvent.setup();
    renderAt('/maquina', routes);

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/login?next=%2Fmaquina');

    await user.type(screen.getByLabelText('Usuario'), 'gustavo');
    await user.type(screen.getByLabelText('Contraseña'), 'clave-segura');
    await user.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(await screen.findByText('Panel de la máquina')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/maquina');
    const [login] = server.find('POST', '/api/v1/auth/login');
    expect(login?.body).toEqual({ username: 'gustavo', password: 'clave-segura' });
    expect(login?.headers['x-csrftoken']).toBe('tok123');
  });

  it('shows the backend detail when the credentials are wrong', async () => {
    fakeServer({
      'GET /api/v1/auth/session': { body: SESSION_NONE },
      'POST /api/v1/auth/login': { status: 400, body: { detail: 'Usuario o contraseña incorrectos.' } },
    });
    const user = userEvent.setup();
    renderAt('/login', routes);
    await user.type(await screen.findByLabelText('Usuario'), 'gustavo');
    await user.type(screen.getByLabelText('Contraseña'), 'mal');
    await user.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Usuario o contraseña incorrectos.');
    expect(screen.getByTestId('location')).toHaveTextContent('/login');
  });

  it('explains a 429 lockout', async () => {
    fakeServer({
      'GET /api/v1/auth/session': { body: SESSION_NONE },
      'POST /api/v1/auth/login': { status: 429, body: { detail: 'Demasiados intentos.' } },
    });
    const user = userEvent.setup();
    renderAt('/login', routes);
    await user.type(await screen.findByLabelText('Usuario'), 'gustavo');
    await user.type(screen.getByLabelText('Contraseña'), 'x');
    await user.click(screen.getByRole('button', { name: 'Entrar' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Espera unos minutos'));
  });

  it('only accepts in-app destinations after login', () => {
    expect(safeNext('/acciones?state=uncertain')).toBe('/acciones?state=uncertain');
    expect(safeNext('//evil.example')).toBe('/');
    expect(safeNext('https://evil.example')).toBe('/');
    expect(safeNext(null)).toBe('/');
  });
});
