// Ajustes › Fotos de perfil: the profile photos in role order, the empty state, the upload as category «perfil» with
// Perfil's permission, the photo sheet (only what changed is PATCHed: the instructions, the role), delete after
// confirming and the full-screen viewer. Brought over from the Galería's tests when it left the app (12/11/2026).
import type { PhotoOutput } from '@compartido/api/capturas';
import { fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import * as ImagePicker from 'expo-image-picker';
import { StyleSheet } from 'react-native';
import '@/api/transport';
import { saveToken } from '@/api/token';
import { renderApp } from '@/test/render';
import { fakeServer, type FakeHandler } from '@/test/server';
import { colors } from '@/theme/tokens';
import { FotosPerfilSection, byRole, profileRoleLabel } from './FotosPerfil';

function photo(id: string, extra: Partial<PhotoOutput> = {}): PhotoOutput {
  return {
    id,
    url: `/media/galeria/${id}.jpg`,
    created_at: '2026-11-03T10:00:00-05:00',
    state: 'sin_usar',
    display_state: 'sin_usar',
    label: 'Sin usar',
    tone: 'muted',
    note: '',
    ai_edit: 'auto',
    used_in: null,
    capture_id: null,
    mime: 'image/jpeg',
    size_bytes: 1000,
    width: 1200,
    height: 900,
    category: 'perfil',
    profile_edit: true,
    profile_role: '',
    ...extra,
  };
}

const PHOTOS = [
  photo('p0'),
  photo('p3', { profile_role: '03', note: 'Con gafas claras' }),
  photo('p1', { profile_role: '01' }),
  photo('p2', { profile_role: '02' }),
];

function page(results: PhotoOutput[], next: string | null = null) {
  return { count: results.length, next, previous: null, results };
}

function asset(index: number): ImagePicker.ImagePickerAsset {
  return { uri: `file:///fotos/${index}.jpg`, fileName: `foto-${index}.jpg`, mimeType: 'image/jpeg', fileSize: 2000, width: 100, height: 100, type: 'image' } as ImagePicker.ImagePickerAsset;
}

async function renderFotos(routes: Record<string, FakeHandler> = {}) {
  const server = fakeServer({ 'GET /api/v1/galeria': { body: page(PHOTOS) }, ...routes });
  await renderApp(<FotosPerfilSection />);
  return server;
}

beforeEach(async () => {
  await saveToken('0ff1ce_dt_prueba');
});

it('orders the photos by role, the unassigned ones last, and names each role', () => {
  expect(byRole(PHOTOS).map((item) => item.id)).toEqual(['p1', 'p2', 'p3', 'p0']);
  expect(profileRoleLabel({ profile_role: '02' })).toBe('02 · Cuerpo del banner');
  expect(profileRoleLabel({ profile_role: '' })).toBe('Sin asignar');
});

it('shows only the profile photos, in role order and each with its role', async () => {
  const server = await renderFotos();
  expect(await screen.findByLabelText('01 · Pose y sonrisa. Foto del 3 nov, sin usar')).toBeOnTheScreen();
  expect(screen.getByText('Sin asignar')).toBeOnTheScreen();
  expect(screen.getAllByTestId(/^foto-perfil-p/).map((tile) => tile.props.testID)).toEqual(['foto-perfil-p1', 'foto-perfil-p2', 'foto-perfil-p3', 'foto-perfil-p0']);
  expect(server.find('GET', '/api/v1/galeria')[0]!.path).toContain('filtro=perfil');
});

it('says what to upload when there are no profile photos yet', async () => {
  await renderFotos({ 'GET /api/v1/galeria': { body: page([]) } });
  expect(await screen.findByText(/Todavía no hay fotos de perfil/)).toBeOnTheScreen();
});

it('uploads the chosen photos as profile photos Perfil may edit', async () => {
  jest.mocked(ImagePicker.launchImageLibraryAsync).mockResolvedValueOnce({ canceled: false, assets: [asset(1), asset(2)] });
  const server = await renderFotos({ 'POST /api/v1/galeria': { status: 201, body: [photo('n1'), photo('n2')] } });
  await screen.findByTestId('foto-perfil-p1');
  await fireEvent.press(screen.getByTestId('fotos-perfil-subir'));
  expect(await screen.findByText('Fotos subidas a Perfil.')).toBeOnTheScreen();
  const parts = server.find('POST', '/api/v1/galeria')[0]!.body as [string, unknown][];
  expect(parts.filter(([name]) => name === 'fotos')).toHaveLength(2);
  expect(parts).toEqual(expect.arrayContaining([['category', 'perfil'], ['profile_edit', 'true']]));
});

it('opens a photo without offering «Posts» and PATCHes only what changed: the instructions for Perfil', async () => {
  const server = await renderFotos({ 'PATCH /api/v1/galeria/p1': (request) => ({ body: { ...PHOTOS[2], ...(request.body as object) } }) });
  await fireEvent.press(await screen.findByTestId('foto-perfil-p1'));
  const sheet = await screen.findByTestId('photo-sheet');
  expect(within(sheet).queryByText('Posts')).toBeNull();
  expect(within(sheet).getByRole('button', { name: 'Guardar' })).toBeDisabled();
  await fireEvent.changeText(within(sheet).getByTestId('photo-note'), '  Sonrisa abierta, sin gafas.  ');
  await fireEvent.press(within(sheet).getByRole('button', { name: 'Guardar' }));
  await waitFor(() => expect(server.find('PATCH', '/api/v1/galeria/p1')[0]?.body).toEqual({ note: 'Sonrisa abierta, sin gafas.' }));
  expect(await screen.findByText('Foto guardada.')).toBeOnTheScreen();
});

it('changes the reference role and PATCHes only it', async () => {
  const server = await renderFotos({ 'PATCH /api/v1/galeria/p0': (request) => ({ body: { ...PHOTOS[0], ...(request.body as object) } }) });
  await fireEvent.press(await screen.findByTestId('foto-perfil-p0'));
  const sheet = await screen.findByTestId('photo-sheet');
  await fireEvent.press(within(sheet).getByText('02 · Cuerpo del banner'));
  await fireEvent.press(within(sheet).getByTestId('photo-save'));
  await waitFor(() => expect(server.find('PATCH', '/api/v1/galeria/p0')[0]?.body).toEqual({ profile_role: '02' }));
});

it('removes a photo only after confirming', async () => {
  const server = await renderFotos({ 'DELETE /api/v1/galeria/p1': { status: 204 } });
  await fireEvent.press(await screen.findByTestId('foto-perfil-p1'));
  await fireEvent.press(within(await screen.findByTestId('photo-sheet')).getByLabelText('Quitar la foto: Foto del 3 nov, sin usar'));
  const confirm = await screen.findByTestId('confirm-sheet');
  expect(within(confirm).getByText('Se borran la foto y su archivo; el equipo ya no podrá usarla.')).toBeOnTheScreen();
  expect(server.find('DELETE', '/api/v1/galeria/p1')).toHaveLength(0);
  await fireEvent.press(within(confirm).getByRole('button', { name: 'Quitar la foto' }));
  await waitFor(() => expect(server.find('DELETE', '/api/v1/galeria/p1')).toHaveLength(1));
  expect(await screen.findByText('Foto quitada.')).toBeOnTheScreen();
});

it('opens the viewer on ink from the sheet and moves between the photos in role order', async () => {
  await renderFotos();
  await fireEvent.press(await screen.findByTestId('foto-perfil-p2'));
  await fireEvent.press(within(await screen.findByTestId('photo-sheet')).getByTestId('photo-sheet-image'));
  const viewer = await screen.findByTestId('photo-viewer');
  expect(StyleSheet.flatten(viewer.props.style).backgroundColor).toBe(colors.ink);
  expect(within(viewer).getByTestId('photo-viewer-count')).toHaveTextContent('2 de 4');
  await fireEvent(within(viewer).getByRole('adjustable'), 'accessibilityAction', { nativeEvent: { actionName: 'increment' } });
  expect(within(viewer).getByTestId('photo-viewer-count')).toHaveTextContent('3 de 4');
  await fireEvent.press(within(viewer).getByRole('button', { name: 'Cerrar' }));
  await waitFor(() => expect(screen.queryByTestId('photo-viewer')).toBeNull());
  // The sheet follows the photo seen last: 03 · Identidad y gafas.
  expect(within(screen.getByTestId('photo-sheet')).getByLabelText('Foto: Con gafas claras')).toBeOnTheScreen();
});
