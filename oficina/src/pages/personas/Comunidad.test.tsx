import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { communityFixture, emptyCommunity } from '../../../../compartido/src/fixtures/comunidad';
import { renderApp, overviewFixture, tuTurnoFixture } from '../../test/app';
import { fakeServer, SESSION_OK } from '../../test/fakeServer';
import { accountFixture } from '../../test/fixtures/personas';

describe('Personas · Comunidad', () => {
  it('shows minimized patterns, opens restricted sources and withdraws without editing contacts', async () => {
    let report = communityFixture();
    const server = fakeServer({
      'GET /api/v1/auth/session': { body: SESSION_OK },
      'GET /api/v1/tu-turno': { body: tuTurnoFixture() },
      'GET /api/v1/operador/overview': { body: overviewFixture() },
      'GET /api/v1/operador/accounts': { body: [accountFixture()] },
      'GET /api/v1/comunidad': () => ({ body: report }),
      'POST /api/v1/comunidad/fuentes/source-synthetic/retirar': () => { report = emptyCommunity; return { body: { status: 'retirada' } }; },
    });
    renderApp('/personas?pestana=comunidad');
    expect(await screen.findByText('medición del resultado')).toBeInTheDocument();
    expect(screen.queryByText('How do you measure delivery cost?')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Fuentes públicas' }));
    expect(screen.getByText('How do you measure delivery cost?')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Retirar fuente 1' }));
    expect(await screen.findByText('Sin estudio vigente')).toBeInTheDocument();
    await waitFor(() => expect(server.requests.filter((r) => r.method === 'POST').map((r) => r.path))
      .toEqual(['/api/v1/comunidad/fuentes/source-synthetic/retirar']));
  });
});
