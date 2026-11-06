import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { fakeServer } from '../test/fakeServer';
import { renderAt } from '../test/render';
import { Oficina } from './Oficina';

vi.mock('../scene/sprites', () => ({
  loadSprites: () => new Promise(() => {}),
  portraitUrl: (n: number) => `/assets/portrait${n}.png`,
}));

describe('Oficina', () => {
  it('shows each role with its real status, detail and the service note', async () => {
    fakeServer({
      'GET /api/v1/oficina/actividad': {
        body: {
          updated_at: new Date().toISOString(),
          roles: {
            operador_cuenta: { status: 'trabajando', detail: 'Ejecutando comentario aprobado', since: new Date().toISOString() },
            relaciones_comunidad: { status: 'en_espera', detail: '', since: null },
            conversaciones_inbox: { status: 'diseno', detail: '', since: null },
          },
        },
      },
    });
    const user = userEvent.setup();
    renderAt('/', [{ path: '/', element: <Oficina /> }]);

    // Default team: Operación.
    const panel = await screen.findByRole('complementary');
    const operator = await within(panel).findByRole('button', { name: /Operador de cuenta/ });
    expect(operator).toHaveTextContent('Trabajando');
    expect(operator).toHaveTextContent('Ejecutando comentario aprobado');

    await user.click(screen.getByRole('button', { name: /Relaciones/, pressed: false }));
    const members = within(panel).getAllByRole('button');
    expect(members.find((b) => b.textContent?.includes('Relaciones con la comunidad'))).toHaveTextContent('En espera');
    expect(members.find((b) => b.textContent?.includes('Conversaciones e inbox'))).toHaveTextContent('En diseño');
    expect(within(panel).getByText(/0 trabajando · 1 en espera · 1 en diseño/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Operación/, pressed: false }));
    await user.click(within(panel).getByRole('button', { name: /Operador de cuenta/ }));
    expect(within(panel).getByRole('heading', { name: 'Operador de cuenta' })).toBeInTheDocument();
    expect(within(panel).getByText(/no un agente de IA/)).toBeInTheDocument();
  });

  it('says so when activity is unavailable instead of inventing it', async () => {
    fakeServer({ 'GET /api/v1/oficina/actividad': { status: 503, body: { detail: 'Servicio no disponible' } } });
    renderAt('/', [{ path: '/', element: <Oficina /> }]);
    expect(await screen.findByText(/la oficina no simula trabajo/)).toBeInTheDocument();
    const panel = screen.getByRole('complementary');
    expect(within(panel).getByRole('button', { name: /Operador de cuenta/ })).toHaveTextContent('Sin datos');
  });
});
