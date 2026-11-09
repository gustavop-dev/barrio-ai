import { fireEvent, screen, waitFor } from '@testing-library/react-native';
import { PROFILE_PROPOSAL } from '@compartido/fixtures/perfil';
import '@/api/transport';
import { saveToken } from '@/api/token';
import { renderApp } from '@/test/render';
import { fakeServer } from '@/test/server';
import { ProfileProposal } from './ProfileProposal';

it('queues photos and banner once and keeps the existing copy visible', async () => {
  await saveToken('0ff1ce_dt_perfil_fake');
  let proposal = { ...PROFILE_PROPOSAL, can_prepare_assets: true, assets_pending: false };
  const server = fakeServer({
    'GET /api/v1/perfil/profile-qa': () => ({ body: proposal }),
    'POST /api/v1/perfil/profile-qa/decision': () => {
      proposal = { ...proposal, assets_pending: true };
      return { body: proposal };
    },
  });
  await renderApp(<ProfileProposal id="profile-qa" />);
  await fireEvent.press(screen.getByTestId('profile-open'));
  await fireEvent.press(await screen.findByTestId('profile-prepare-assets'));
  expect(await screen.findByText('Preparando fotos y banner; el texto se conserva.')).toBeOnTheScreen();
  expect(screen.getByTestId('profile-prepare-assets')).toBeDisabled();
  expect(server.find('POST', '/api/v1/perfil/profile-qa/decision').map((r) => r.body)).toEqual([
    { revision: 1, action: 'prepare_assets' },
  ]);
  await fireEvent.press(screen.getByTestId('profile-section-headline'));
  expect(screen.getByText(PROFILE_PROPOSAL.sections[0]!.copy)).toBeOnTheScreen();
});

it('opens a private proposal, cites each recommendation and distinguishes manual application', async () => {
  await saveToken('0ff1ce_dt_perfil_fake');
  let proposal = JSON.parse(JSON.stringify(PROFILE_PROPOSAL)) as typeof PROFILE_PROPOSAL;
  const server = fakeServer({ 'GET /api/v1/perfil/profile-qa': () => ({ body: proposal }),
    'POST /api/v1/perfil/profile-qa/decision': (request) => {
      const data = request.body as { action: string };
      proposal = { ...proposal, revision: proposal.revision + 1, sections: proposal.sections.map((row) => ({ ...row,
        decision: 'accepted' as const, application: data.action === 'applied' ? 'applied' as const : 'pending' as const })) };
      return { body: proposal };
    } });
  await renderApp(<ProfileProposal id="profile-qa" />);
  await fireEvent.press(screen.getByTestId('profile-open'));
  await fireEvent.press(await screen.findByTestId('profile-section-headline'));
  expect(screen.getByText(/\[LI-02-V015-K03\]/)).toBeOnTheScreen();
  await fireEvent.press(screen.getByTestId('profile-headline-accept'));
  await fireEvent.press(await screen.findByTestId('profile-headline-applied'));
  await waitFor(() => expect(screen.getByText('Aplicado por Gustavo, pendiente de comprobar')).toBeOnTheScreen());
  expect(screen.queryByText(/^Comprobado$/)).not.toBeOnTheScreen();
  expect(server.find('POST', '/api/v1/perfil/profile-qa/decision').map((r) => (r.body as { action: string }).action)).toEqual(['accept', 'applied']);
});

it('keeps the note and the pending state after a failed decision', async () => {
  await saveToken('0ff1ce_dt_perfil_fake');
  fakeServer({ 'GET /api/v1/perfil/profile-qa': { body: PROFILE_PROPOSAL },
    'POST /api/v1/perfil/profile-qa/decision': { status: 409, body: { detail: 'La propuesta cambió.' } } });
  await renderApp(<ProfileProposal id="profile-qa" />);
  await fireEvent.press(screen.getByTestId('profile-open'));
  await fireEvent.press(await screen.findByTestId('profile-section-headline'));
  await fireEvent.changeText(screen.getByTestId('profile-note-headline'), 'Please shorten it');
  await fireEvent.press(screen.getByTestId('profile-headline-adjust'));
  expect(await screen.findByText('La propuesta cambió.')).toBeOnTheScreen();
  expect(screen.getByTestId('profile-note-headline').props.value).toBe('Please shorten it');
  expect(screen.getByText('Pendiente de revisar')).toBeOnTheScreen();
});

it('keeps ready sections usable and shows pending questions with placeholder copy', async () => {
  await saveToken('0ff1ce_dt_perfil_fake');
  const proposal = JSON.parse(JSON.stringify(PROFILE_PROPOSAL)) as typeof PROFILE_PROPOSAL;
  const [first] = proposal.sections;
  if (!first) throw new Error('PROFILE_PROPOSAL needs a section');
  proposal.sections.push({ ...first, id: 'experience', title: 'Experiencia', readiness: 'needs_input',
    copy: '[exact title] — Built useful software.',
    missing: [{ key: 'perfil.experience.title', question: '¿Cuál fue el cargo exacto?', purpose: 'Completar el cargo.' }] });
  fakeServer({ 'GET /api/v1/perfil/profile-qa': { body: proposal } });
  await renderApp(<ProfileProposal id="profile-qa" />);
  await fireEvent.press(screen.getByTestId('profile-open'));
  expect(await screen.findByText('Secciones listas: 1 · Assets descargables: 0')).toBeOnTheScreen();
  expect(screen.getByText('Preguntas pendientes')).toBeOnTheScreen();
  expect(screen.getByText('Experiencia: ¿Cuál fue el cargo exacto?')).toBeOnTheScreen();
  await fireEvent.press(screen.getByTestId('profile-section-experience'));
  expect(screen.getByText('[exact title] — Built useful software.')).toBeOnTheScreen();
  expect(screen.queryByTestId('profile-experience-accept')).not.toBeOnTheScreen();
  await fireEvent.press(screen.getByTestId('profile-section-headline'));
  expect(screen.getByTestId('profile-headline-accept')).toBeOnTheScreen();
});
