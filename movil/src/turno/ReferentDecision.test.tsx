import { fireEvent, screen, waitFor } from '@testing-library/react-native';
import { INDUSTRY_CARD, MONTHLY_CARD } from '@compartido/fixtures/referentes';
import { editedProposal, editFields, industryLines, monthlyCountdown, proposalTitle } from '@compartido/logic/referentes';
import '@/api/transport';
import { renderApp } from '@/test/render';
import { fakeServer } from '@/test/server';
import { ReferentDecision, ReferentDetails } from './ReferentDecision';
import { ProtectedReferent } from '@/personas/ProtectedReferent';

it('keeps a swap paired and counts the first five Bogotá days across UTC midnight', () => {
  expect(proposalTitle(MONTHLY_CARD.referent_change!.proposal, 'Alba Variable')).toBe(MONTHLY_CARD.title);
  expect(monthlyCountdown(MONTHLY_CARD.deadline!, Date.parse('2026-11-01T05:00:00Z'))).toContain('Quedan 5 días');
  expect(monthlyCountdown(MONTHLY_CARD.deadline!, Date.parse('2026-11-06T04:59:00Z'))).toContain('Queda 1 hora');
  expect(monthlyCountdown(MONTHLY_CARD.deadline!, Date.parse('2026-11-06T05:00:00Z'))).toContain('Plazo terminado');
});

it('requires a source for a changed candidate and clears an unverified badge', () => {
  const card = MONTHLY_CARD.referent_change!;
  const fields = { ...editFields(card), url: 'https://www.linkedin.com/in/another/' };
  expect(() => editedProposal(card, fields)).toThrow('fuente pública');
  const saved = editedProposal(card, { ...fields, source: 'https://example.org/new-evidence' });
  expect(saved.incoming).toMatchObject({ identifier: 'another', top_voice: false });
  expect(saved.outgoing).toBe('variable-1');
});

it('shows evidence and saves an edit with the version, keeping errors visible', async () => {
  let conflict = true;
  const server = fakeServer({
    'GET /api/v1/operador/referents': { body: [{ id: 'variable-1', display_name: 'Alba Variable', reason: 'Synthetic', active: true }] },
    'POST /api/v1/referentes/cambios/change-1/decidir': () => conflict ? { status: 409, body: { detail: 'La propuesta cambió' } } : { body: { state: 'edited', version: 4 } },
  });
  await renderApp(<><ReferentDetails card={MONTHLY_CARD} /><ReferentDecision card={MONTHLY_CARD} /></>);
  expect(screen.getByText(/cobertura 8\/12; encaje 5\/8/)).toBeOnTheScreen();
  expect(screen.getByText(/5 main protegidos/)).toBeOnTheScreen();
  await fireEvent.press(screen.getByText('Editar'));
  await fireEvent.changeText(screen.getByTestId('referent-edit-reason'), 'Hipótesis revisada');
  await fireEvent.press(screen.getByText('Guardar cambios'));
  expect(await screen.findByText('La propuesta cambió')).toBeOnTheScreen();
  expect(screen.getByTestId('referent-edit')).toBeOnTheScreen();
  conflict = false;
  await fireEvent.press(screen.getByText('Guardar cambios'));
  await waitFor(() => expect(screen.queryByTestId('referent-edit')).toBeNull());
  const writes = server.requests.filter(r => r.method === 'POST');
  expect(writes.at(-1)?.body).toMatchObject({ version: 3, decision: 'edit', proposal: { kind: 'swap', reason: 'Hipótesis revisada' } });
});

it('shows an industry candidate with every criterion and never counts an unmeasured audience as met', async () => {
  const card = INDUSTRY_CARD.referent_change!;
  expect(proposalTitle(card.proposal)).toBe(INDUSTRY_CARD.title);
  const lines = industryLines(card.proposal.incoming);
  expect(lines).toHaveLength(9);
  expect(lines.find(l => l.includes('Su audiencia es el barrio'))).toMatch(/^\? .*Sin medir \(no cuenta como cumplido\)/);
  expect(lines.at(-1)).toMatch(/nunca se copian sus textos/);
  expect(industryLines(MONTHLY_CARD.referent_change!.proposal.incoming)).toEqual([]);
  await renderApp(<ReferentDetails card={INDUSTRY_CARD} />);
  expect(screen.getByText(/✓ Es grande — Cumple\. 24\.000 seguidores/)).toBeOnTheScreen();
  expect(screen.getByText(/referente de industria/)).toBeOnTheScreen();
});

it('drops the industry evaluation when the edit points to another profile', () => {
  const card = INDUSTRY_CARD.referent_change!;
  const same = editedProposal(card, { ...editFields(card), reason: 'Mismo perfil' });
  expect(same.incoming?.industria?.slug).toBe('lia-constructora-test');
  const other = editedProposal(card, { ...editFields(card), url: 'https://www.linkedin.com/in/otra-persona-test/', source: 'https://example.org/otra' });
  expect(other.incoming?.industria).toBeUndefined();
});

it('does not offer protection controls to a different user', async () => {
  await renderApp(<ProtectedReferent referent={{ id: 'main', reason: 'Protected', protected: true, can_manage_protected: false }} candidates={[]} />);
  expect(screen.queryByText(/Gestionar protección/)).toBeNull();
});
