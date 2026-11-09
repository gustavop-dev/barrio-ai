import { fireEvent, screen, waitFor } from '@testing-library/react-native';
import { accountFixture } from '@compartido/fixtures/personas';
import { communityFixture, emptyCommunity } from '@compartido/fixtures/comunidad';
import '@/api/transport';
import { renderApp } from '@/test/render';
import { fakeServer } from '@/test/server';
import { Comunidad } from './Comunidad';

it('shows the same study and removes dependent evidence on withdrawal', async () => {
  let report = communityFixture();
  fakeServer({
    'GET /api/v1/operador/accounts': { body: [accountFixture()] },
    'GET /api/v1/comunidad': () => ({ body: report }),
    'POST /api/v1/comunidad/fuentes/source-synthetic/retirar': () => { report = emptyCommunity; return { body: { status: 'retirada' } }; },
  });
  await renderApp(<Comunidad header={null} />);
  expect(await screen.findByText('medición del resultado')).toBeOnTheScreen();
  expect(screen.queryByText('How do you measure delivery cost?')).toBeNull();
  await fireEvent.press(screen.getByTestId('community-sources'));
  expect(screen.getByText('How do you measure delivery cost?')).toBeOnTheScreen();
  expect(screen.getByRole('button', { name: 'Retirar fuente 1' })).toBeOnTheScreen();
  expect(screen.getByRole('button', { name: 'Excluir persona de fuente 1' })).toBeOnTheScreen();
  expect(screen.getByRole('button', { name: 'Marcar fuente 1 incorrecta' })).toBeOnTheScreen();
  await fireEvent.press(screen.getByTestId('community-withdraw-0'));
  expect(await screen.findByText('Sin estudio vigente')).toBeOnTheScreen();
  await waitFor(() => expect(screen.queryByText('How do you measure delivery cost?')).toBeNull());
});
