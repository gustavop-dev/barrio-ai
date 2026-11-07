import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { Control, Overview } from '../api/types';
import { PauseBanner } from '../components/Layout';
import { fakeServer } from '../test/fakeServer';
import { renderAt } from '../test/render';
import { Maquina } from './Maquina';

function overview(control: Partial<Control> = {}): Overview {
  return {
    autopilot: { enabled: true, policy_version: 'autonomia-v1' },
    control: { paused: false, reason: '', source: 'none', updated_at: null, updated_by: null, ...control },
    window: { start: '07:00', end: '21:00', timezone: 'America/Bogota', open_now: true, min_spacing_seconds: 1200 },
    accounts: [
      {
        id: 'acc-1',
        label: 'LinkedIn Gustavo',
        provider: 'unipile',
        status: 'running',
        is_locked: false,
        paused: true,
        paused_reason: '429 de LinkedIn',
        last_checked_at: null,
        capacity: { 'INT-03': { daily: 3, weekly: 12, daily_used: 1, weekly_used: 4, left: 2 } },
      },
    ],
    today: { proposals: { approved: 1, discarded: 2 }, llm_spent_usd: '0.42', llm_daily_cap_usd: '1', drafts: 3, drafts_daily_cap: 6 },
    counts: { referents: 7, posts: 31, uncertain: 1 },
  };
}

const routes = [
  {
    path: '/maquina',
    element: (
      <>
        <PauseBanner />
        <Maquina />
      </>
    ),
  },
];

describe('Máquina · parada total', () => {
  it('asks for a reason, POSTs the stop and shows the paused machine everywhere', async () => {
    document.cookie = 'csrftoken=tok';
    let current = overview();
    const server = fakeServer({
      'GET /api/v1/operador/overview': () => ({ body: current }),
      'GET /api/v1/operador/feed': { body: [] },
      'POST /api/v1/operador/control': (request) => {
        const body = request.body as { paused: boolean; reason: string };
        current = overview({ paused: body.paused, reason: body.reason, source: 'db', updated_by: 'gustavo', updated_at: '2026-11-06T20:00:00Z' });
        return { body: current.control };
      },
    });
    const user = userEvent.setup();
    renderAt('/maquina', routes);

    await user.click(await screen.findByRole('button', { name: 'PARADA TOTAL' }));
    const dialog = screen.getByRole('dialog', { name: 'Parada total' });
    const submit = within(dialog).getByRole('button', { name: 'Detener la máquina' });
    expect(submit).toBeDisabled();
    await user.type(within(dialog).getByLabelText('Motivo de la parada'), 'Reviso los comentarios');
    await user.click(submit);

    expect(await screen.findByRole('heading', { name: 'La máquina está detenida' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'REANUDAR' })).toBeEnabled();
    expect(await screen.findByText('Máquina en pausa')).toBeInTheDocument();
    const [post] = server.find('POST', '/api/v1/operador/control');
    expect(post?.body).toEqual({ paused: true, reason: 'Reviso los comentarios' });
    expect(post?.headers['x-csrftoken']).toBe('tok');
  });

  it('cannot resume a stop that comes from the environment', async () => {
    fakeServer({
      'GET /api/v1/operador/overview': { body: overview({ paused: true, reason: 'Mantenimiento', source: 'env' }) },
      'GET /api/v1/operador/feed': { body: [] },
    });
    renderAt('/maquina', routes);
    expect(await screen.findByRole('button', { name: 'REANUDAR' })).toBeDisabled();
    expect(screen.getByText(/viene del entorno del servidor/)).toBeInTheDocument();
    expect(screen.getByText(/fijada en el entorno/)).toBeInTheDocument();
  });

  it('shows the 409 detail when the backend refuses to resume', async () => {
    fakeServer({
      'GET /api/v1/operador/overview': { body: overview({ paused: true, reason: 'x', source: 'db' }) },
      'GET /api/v1/operador/feed': { body: [] },
      'POST /api/v1/operador/control': { status: 409, body: { detail: 'OPERATOR_PAUSED=true en el entorno: no se puede reanudar desde la app.' } },
    });
    const user = userEvent.setup();
    renderAt('/maquina', routes);
    await user.click(await screen.findByRole('button', { name: 'REANUDAR' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Reanudar' }));
    expect(await within(screen.getByRole('dialog')).findByRole('alert')).toHaveTextContent('no se puede reanudar desde la app');
  });

  it('shows the editorial budget and the own-publication cap only when the backend reports them', async () => {
    const base = overview();
    const withEditorial: Overview = {
      ...base,
      accounts: [
        {
          ...base.accounts[0]!,
          id: 'acc-li',
          label: 'LinkedIn oficial',
          provider: 'linkedin',
          paused: false,
          paused_reason: '',
          capacity: { 'CONT-09': { daily: 1, weekly: 7, daily_used: 0, weekly_used: 3, left: 1 } },
        },
      ],
      today: { ...base.today, editorial_llm_spent_usd: '0.43', editorial_llm_daily_cap_usd: '1' },
    };
    fakeServer({ 'GET /api/v1/operador/overview': { body: withEditorial }, 'GET /api/v1/operador/feed': { body: [] } });
    renderAt('/maquina', routes);
    expect(await screen.findByRole('meter', { name: 'Gasto editorial del día' })).toHaveAttribute('aria-valuetext', expect.stringContaining('0,43'));
    expect(screen.getByRole('link', { name: 'Ver el calendario de contenido' })).toHaveAttribute('href', '/contenido');
    expect(screen.getByRole('meter', { name: 'Publicación propia esta semana' })).toHaveAttribute('aria-valuenow', '3');
  });

  it('invents no editorial data when the overview has none', async () => {
    fakeServer({ 'GET /api/v1/operador/overview': { body: overview() }, 'GET /api/v1/operador/feed': { body: [] } });
    renderAt('/maquina', routes);
    expect(await screen.findByRole('meter', { name: 'Gasto LLM del día' })).toBeInTheDocument();
    expect(screen.queryByRole('meter', { name: 'Gasto editorial del día' })).not.toBeInTheDocument();
    expect(screen.queryByText(/calendario de contenido/)).not.toBeInTheDocument();
  });

  it('shows capacity, LLM spend against its cap and resumes a paused account', async () => {
    const server = fakeServer({
      'GET /api/v1/operador/overview': { body: overview() },
      'GET /api/v1/operador/feed': { body: [{ id: 1, action: 'operator.account_paused', target: 'acc-1', created_at: '2026-11-06T19:00:00Z', actor: null, metadata: {} }] },
      'POST /api/v1/operador/accounts/acc-1/pause': { body: {} },
    });
    const user = userEvent.setup();
    renderAt('/maquina', routes);
    expect(await screen.findByRole('meter', { name: 'Gasto LLM del día' })).toHaveAttribute('aria-valuetext', expect.stringContaining('0,42'));
    expect(screen.getByRole('meter', { name: 'Comentario hoy' })).toHaveAttribute('aria-valuenow', '1');
    expect(screen.getByText('Abierta ahora')).toBeInTheDocument();
    expect(await screen.findByText('operator.account_paused')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reanudar la cuenta' }));
    const [pause] = server.find('POST', '/api/v1/operador/accounts/acc-1/pause');
    expect(pause?.body).toEqual({ paused: false, reason: '' });
  });
});
