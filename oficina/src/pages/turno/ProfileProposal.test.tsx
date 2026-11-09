import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { PROFILE_PROPOSAL } from '../../../../compartido/src/fixtures/perfil';
import { fakeServer, SESSION_OK } from '../../test/fakeServer';
import { renderAt } from '../../test/render';
import { ProfileProposal } from './ProfileProposal';

describe('Private profile proposal', () => {
  it('shows per-section citations and records applied without claiming checked', async () => {
    const user = userEvent.setup();
    let proposal = structuredClone(PROFILE_PROPOSAL);
    const server = fakeServer({
      'GET /api/v1/auth/session': { body: SESSION_OK },
      'GET /api/v1/perfil/profile-qa': () => ({ body: proposal }),
      'POST /api/v1/perfil/profile-qa/decision': (request) => {
        const data = request.body as { action: string };
        proposal = { ...proposal, revision: proposal.revision + 1, sections: proposal.sections.map((row) => ({ ...row,
          decision: 'accepted' as const, application: data.action === 'applied' ? 'applied' as const : 'pending' as const })) };
        return { body: proposal };
      },
    });
    renderAt('/perfil', [{ path: '/perfil', element: <ProfileProposal id="profile-qa" /> }]);
    await user.click(screen.getByRole('button', { name: 'Abrir propuesta de perfil' }));
    await user.click(await screen.findByText(/Titular · Pendiente de revisar/));
    expect(screen.getByText(/^\[LI-02-V015-K03\]/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Descargar Markdown' })).toHaveAttribute('href', '/api/v1/perfil/profile-qa/documento');
    await user.click(screen.getByRole('button', { name: 'Aceptar propuesta' }));
    await user.click(await screen.findByRole('button', { name: 'Hecho, lo apliqué' }));
    await waitFor(() => expect(screen.getByText(/Titular · Aplicado por Gustavo, pendiente de comprobar/)).toBeInTheDocument());
    expect(screen.queryByText(/^Comprobado$/)).not.toBeInTheDocument();
    expect(server.requests.filter((r) => r.method === 'POST').map((r) => (r.body as { action: string }).action)).toEqual(['accept', 'applied']);
  });
  it('retains a written adjustment when saving fails', async () => {
    const user = userEvent.setup();
    fakeServer({ 'GET /api/v1/auth/session': { body: SESSION_OK }, 'GET /api/v1/perfil/profile-qa': { body: PROFILE_PROPOSAL },
      'POST /api/v1/perfil/profile-qa/decision': { status: 409, body: { detail: 'La propuesta cambió; revisa la versión vigente.' } } });
    renderAt('/perfil', [{ path: '/perfil', element: <ProfileProposal id="profile-qa" /> }]);
    await user.click(screen.getByRole('button', { name: 'Abrir propuesta de perfil' }));
    await user.click(await screen.findByText(/Titular · Pendiente/));
    await user.type(screen.getByLabelText('Nota · Titular'), 'Shorten this headline');
    await user.click(screen.getByRole('button', { name: 'Pedir ajuste' }));
    expect(await screen.findByText('La propuesta cambió; revisa la versión vigente.')).toBeInTheDocument();
    expect(screen.getByLabelText('Nota · Titular')).toHaveValue('Shorten this headline');
  });
  it('shows available copy and downloads separately from pending questions in a partial proposal', async () => {
    const user = userEvent.setup();
    const proposal = structuredClone(PROFILE_PROPOSAL);
    const [first] = proposal.sections;
    if (!first) throw new Error('PROFILE_PROPOSAL needs a section');
    proposal.sections.push({ ...first, id: 'experience', title: 'Experiencia', readiness: 'needs_input',
      copy: '[exact title] — Built useful software.',
      missing: [{ key: 'perfil.experience.title', question: '¿Cuál fue el cargo exacto?', purpose: 'Completar el cargo.' }] });
    const asset = { id: 'asset-a', kind: 'A', width: 800, height: 800, url: '/api/v1/perfil/profile-qa/assets/asset-a', review: { ok: true } } as const;
    proposal.assets = [asset];
    fakeServer({ 'GET /api/v1/auth/session': { body: SESSION_OK }, 'GET /api/v1/perfil/profile-qa': { body: proposal } });
    renderAt('/perfil', [{ path: '/perfil', element: <ProfileProposal id="profile-qa" /> }]);
    await user.click(screen.getByRole('button', { name: 'Abrir propuesta de perfil' }));
    expect(await screen.findByText('Secciones listas: 1 · Assets descargables: 1')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Preguntas pendientes' })).toHaveTextContent('¿Cuál fue el cargo exacto?');
    await user.click(screen.getByText('Fotos, banner y previews'));
    expect(screen.getByRole('link', { name: 'Descargar Foto A · grises' })).toHaveAttribute('href', asset.url);
    await user.click(screen.getByText(/Experiencia · Copy preparado/));
    expect(screen.getByText('[exact title] — Built useful software.')).toBeInTheDocument();
    expect(screen.getByText('Completa los placeholders con tus datos antes de pegar.')).toBeInTheDocument();
    await user.click(screen.getByText(/Titular · Pendiente de revisar/));
    expect(screen.getByRole('button', { name: 'Aceptar propuesta' })).toBeEnabled();
  });
});
