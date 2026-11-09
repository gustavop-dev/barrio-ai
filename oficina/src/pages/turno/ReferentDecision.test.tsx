import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { MONTHLY_CARD } from '../../../../compartido/src/fixtures/referentes';
import { monthlyCountdown, editedProposal, editFields } from '../../../../compartido/src/logic/referentes';
import { fakeServer } from '../../test/fakeServer';
import { ReferentDecision } from './ReferentDecision';
import { ProtectedReferent } from '../personas/ProtectedReferent';

function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<MemoryRouter><QueryClientProvider client={client}>{ui}</QueryClientProvider></MemoryRouter>);
}

describe('Monthly referent decisions', () => {
  it('shows the pair, sources, sample and explicit Bogotá cutoff', () => {
    fakeServer({ 'GET /api/v1/operador/referents': { body: [] } });
    wrap(<ReferentDecision card={MONTHLY_CARD} />);
    expect(screen.getByText('Sale: Alba Variable')).toBeInTheDocument();
    expect(screen.getByText('Entra: Nora Investigación')).toBeInTheDocument();
    expect(screen.getByText(/encaje 5\/8 \(62.5 %\)/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Fuente pública' })).toHaveAttribute('href', 'https://example.org/evidence');
    expect(monthlyCountdown(MONTHLY_CARD.deadline!, Date.parse('2026-11-06T04:00:00Z'))).toContain('America/Bogota');
    expect(monthlyCountdown(MONTHLY_CARD.deadline!, Date.parse('2026-11-06T05:00:00Z'))).toContain('Plazo terminado');
  });

  it('saves and applies the concrete edited pair; a failed request keeps the form open', async () => {
    const user = userEvent.setup();
    let fail = true;
    const server = fakeServer({
      'GET /api/v1/operador/referents': { body: [{ id: 'variable-1', display_name: 'Alba Variable', reason: 'Synthetic' }] },
      'POST /api/v1/referentes/cambios/change-1/decidir': () => fail ? { status: 409, body: { detail: 'Recarga la propuesta' } } : { body: { state: 'approved' } },
    });
    wrap(<ReferentDecision card={MONTHLY_CARD} />);
    await user.click(screen.getByRole('button', { name: 'Editar' }));
    await user.clear(screen.getByRole('textbox', { name: 'Motivo' }));
    await user.type(screen.getByRole('textbox', { name: 'Motivo' }), 'Aporte revisado');
    await user.click(screen.getByRole('button', { name: 'Guardar y aplicar cambios' }));
    expect(await screen.findByText('Recarga la propuesta')).toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole('button', { name: 'Guardar y aplicar cambios' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(server.requests.filter(r => r.method === 'POST').at(-1)?.body).toMatchObject({ version: 3, decision: 'edit_apply', proposal: { kind: 'swap', reason: 'Aporte revisado' } });
  });

  it('leaves protected decisions to Gustavo and preserves the proposal when merely opening edit', () => {
    wrap(<ProtectedReferent referent={{ id: 'main', reason: 'Synthetic', protected: true, can_manage_protected: false }} candidates={[]} />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    const card = MONTHLY_CARD.referent_change!;
    const revised = editedProposal(card, { ...editFields(card), reason: 'New reason' });
    expect(revised.reason).toBe('New reason');
    expect(card.proposal.reason).toBe('Mejor encaje observado');
  });
});
