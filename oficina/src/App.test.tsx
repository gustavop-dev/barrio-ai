import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { overviewFixture, renderApp, tuTurnoFixture } from './test/app';
import { fakeServer, SESSION_NONE, SESSION_OK } from './test/fakeServer';

function signedIn() {
  return fakeServer({
    'GET /api/v1/auth/session': { body: SESSION_OK },
    'GET /api/v1/tu-turno': { body: tuTurnoFixture() },
    'GET /api/v1/operador/overview': { body: overviewFixture() },
  });
}

describe('rutas', () => {
  it.each([
    ['/editorial/p-1', '/calendario/pieza/p-1'],
    ['/contenido/p-2', '/calendario/pieza/p-2'],
    ['/contenido', '/calendario'],
    ['/editorial', '/calendario'],
    ['/acciones', '/calendario'],
    ['/acciones?state=uncertain', '/tu-turno'],
    ['/maquina', '/calendario'],
    ['/red', '/personas'],
    ['/red?etapa=fit', '/personas?etapa=fit'],
    ['/referentes', '/personas?pestana=referentes'],
    ['/memoria', '/tu-turno/sabe'],
    ['/una-ruta-que-no-existe', '/'],
  ])('redirects %s to %s', async (from, to) => {
    signedIn();
    renderApp(from);
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(new RegExp(`^${to.replace(/[?]/g, '\\?')}$`)));
  });

  it('sends /conocimiento to the office', async () => {
    signedIn();
    renderApp('/conocimiento');
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/'));
  });

  it.each([
    ['/calendario', 'Calendario'],
    ['/calendario/pieza/p-1', 'Detalle de la pieza'],
  ])('renders %s', async (path, title) => {
    signedIn();
    renderApp(path);
    expect(await screen.findByRole('heading', { name: title, level: 1 })).toBeInTheDocument();
  });

  it('nests the person card inside Personas', async () => {
    signedIn();
    renderApp('/personas/c-9');
    expect(await screen.findByRole('heading', { name: 'Personas', level: 1 })).toBeInTheDocument();
    // The card is the nested route: the shell keeps the Personas page around it (no mock: the person is not found).
    expect(await screen.findByText('No encontramos a esta persona')).toBeInTheDocument();
  });
});

describe('sesión caducada', () => {
  it('sends a 401 to /login?next=<path> and comes back after signing in', async () => {
    document.cookie = 'csrftoken=tok';
    let session: typeof SESSION_OK | typeof SESSION_NONE = SESSION_OK;
    let expired = true;
    fakeServer({
      'GET /api/v1/auth/session': () => ({ body: session }),
      'GET /api/v1/tu-turno': () => {
        if (expired) {
          session = SESSION_NONE;
          return { status: 401, body: { detail: 'Las credenciales no se proveyeron.' } };
        }
        return { body: tuTurnoFixture() };
      },
      'GET /api/v1/operador/overview': { body: overviewFixture() },
      'POST /api/v1/auth/login': () => {
        session = SESSION_OK;
        expired = false;
        return { body: { user: SESSION_OK.user } };
      },
    });
    const user = userEvent.setup();
    renderApp('/calendario?vista=mes');

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/login?next=%2Fcalendario%3Fvista%3Dmes');

    await user.type(screen.getByLabelText('Usuario'), 'gustavo');
    await user.type(screen.getByLabelText('Contraseña'), 'clave');
    await user.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(await screen.findByRole('heading', { name: 'Calendario', level: 1 })).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/calendario?vista=mes');
  });

  it('treats a 403 as expired only when the session check says so', async () => {
    let session: typeof SESSION_OK | typeof SESSION_NONE = SESSION_OK;
    fakeServer({
      'GET /api/v1/auth/session': () => ({ body: session }),
      'GET /api/v1/tu-turno': () => {
        session = SESSION_NONE;
        return { status: 403, body: { detail: 'Las credenciales no se proveyeron.' } };
      },
      'GET /api/v1/operador/overview': { body: overviewFixture() },
    });
    renderApp('/resultados');
    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/login?next=%2Fresultados');
  });
});
