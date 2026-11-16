// Tu turno › a strategy change of the monthly review (cambio_estrategia), each its own decision: the card, «Aprobar»,
// «Editar y aprobar» (the proposal prefilled, its 600-character count, his text sent as `text`), «Rechazar» with its
// optional reason, «Ver la revisión» (the review's tab in Resultados), a refused decision that keeps the card, and a
// card of a kind this app does not know yet.
import { strategyCardFixture, strategyChangeFixture } from '@compartido/fixtures/revision';
import { cardFixture, turnoFixture } from '@compartido/fixtures/turno';
import type { TurnoCard } from '@compartido/api/types';
import { fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import { router } from 'expo-router';
import '@/api/transport';
import { renderApp } from '@/test/render';
import { fakeServer, type FakeHandler } from '@/test/server';
import { TuTurnoScreen } from './TuTurnoScreen';

const CARD = strategyCardFixture();
const CHANGE = '/api/v1/resultados/revision-mensual/cambios/ch-1';
const PROPOSAL = CARD.strategy_change!.proposal;
const EDITED = 'Publica un caso práctico cada semana, con el problema del cliente arriba.';
const APPROVED = 'Cambio aprobado. El equipo lo usa desde su próxima tarea.';

async function renderCard(extra: Record<string, FakeHandler> = {}, items: TurnoCard[] = [CARD]) {
  const server = fakeServer({
    'GET /api/v1/tu-turno': { body: turnoFixture({ count: items.length, items }) },
    'POST /api/v1/tu-turno/vistos': { body: { count: 1 } },
    ...extra,
  });
  await renderApp(<TuTurnoScreen />);
  await screen.findByTestId(`turno-card-${items[0]!.id}`);
  return server;
}

const card = (id = CARD.id) => within(screen.getByTestId(`turno-card-${id}`));
const sheet = async () => within(await screen.findByTestId('confirm-sheet'));
const approved = () => ({ body: { change: strategyChangeFixture({ state: 'aprobado', state_label: 'Aprobado', final_text: PROPOSAL, can_decide: false, can_revert: true }) } });

describe('Tu turno · cambio de estrategia', () => {
  it('shows the change as its own decision; «Ver más» opens why, the evidence and how it will be measured', async () => {
    await renderCard();
    expect(card().getByText('Cambio de estrategia')).toBeOnTheScreen();
    expect(card().getByText('Analista del barrio')).toBeOnTheScreen();
    expect(card().getByText('Más posts de caso práctico')).toBeOnTheScreen();
    expect(card().getByTestId(`turno-summary-${CARD.id}`)).toHaveTextContent(`“${PROPOSAL}”`);
    for (const label of ['Aprobar', 'Editar y aprobar', 'Rechazar', 'Ver la revisión']) expect(card().getByText(label)).toBeOnTheScreen();

    await fireEvent.press(card().getByTestId(`turno-more-${CARD.id}`));
    const details = within(card().getByTestId('strategy-details-ch-1'));
    expect(details.getByText('Revisión de octubre de 2026 · parcial')).toBeOnTheScreen();
    expect(details.getByText(`“${PROPOSAL}”`)).toBeOnTheScreen();
    expect(details.getByText('Los dos casos prácticos del mes tuvieron el doble de impresiones a las 72 h que el resto.')).toBeOnTheScreen();
    expect(details.getByText('Dato: por_tipo.caso.mediana_impresiones_72h: 1180')).toBeOnTheScreen();
    expect(details.getByText('Comparado con: metricas.mediana_impresiones_72h.mes: 590')).toBeOnTheScreen();
    expect(details.getByText('Que la mediana de impresiones a las 72 h suba el mes que viene.')).toBeOnTheScreen();
    expect(details.getByText('Se medirá con: Mediana de impresiones de los posts a las 72 h')).toBeOnTheScreen();
    // Decided with a tap only: no swipe, not even from a screen reader.
    expect(screen.getByTestId(`turno-card-${CARD.id}`).props.accessibilityActions).toEqual([]);
  });

  it('«Aprobar» approves the proposal as it is', async () => {
    const server = await renderCard({ [`POST ${CHANGE}/aprobar`]: approved() });
    await fireEvent.press(card().getByText('Aprobar'));
    await waitFor(() => expect(server.find('POST', `${CHANGE}/aprobar`)).toHaveLength(1));
    expect(server.find('POST', `${CHANGE}/aprobar`)[0]!.body).toEqual({});
    expect(await screen.findByText(APPROVED)).toBeOnTheScreen();
    expect(screen.queryByTestId('confirm-sheet')).toBeNull();
  });

  it('«Editar y aprobar» opens the proposal to edit, counts its characters and sends his text', async () => {
    const server = await renderCard({ [`POST ${CHANGE}/editar`]: approved() });
    await fireEvent.press(card().getByText('Editar y aprobar'));
    const confirm = await sheet();
    expect(confirm.getByText('Lo que escribas entra tal cual en la orientación del equipo. Podrás revertirlo desde Resultados.')).toBeOnTheScreen();
    const field = confirm.getByTestId('confirm-note');
    expect(field.props.value).toBe(PROPOSAL);
    expect(field.props.maxLength).toBe(600);
    expect(confirm.getByText(`${PROPOSAL.length} de 600 caracteres`)).toBeOnTheScreen();
    await fireEvent.changeText(field, EDITED);
    expect(confirm.getByText(`${EDITED.length} de 600 caracteres`)).toBeOnTheScreen();
    await fireEvent.press(confirm.getByRole('button', { name: 'Aprobar' }));
    await waitFor(() => expect(server.find('POST', `${CHANGE}/editar`)).toHaveLength(1));
    expect(server.find('POST', `${CHANGE}/editar`)[0]!.body).toEqual({ text: EDITED });
    expect(await screen.findByText(APPROVED)).toBeOnTheScreen();
  });

  it('«Editar y aprobar» cannot send an empty text', async () => {
    const server = await renderCard({ [`POST ${CHANGE}/editar`]: approved() });
    await fireEvent.press(card().getByText('Editar y aprobar'));
    const confirm = await sheet();
    await fireEvent.changeText(confirm.getByTestId('confirm-note'), '   ');
    expect(confirm.getByRole('button', { name: 'Aprobar' })).toBeDisabled();
    expect(server.find('POST', `${CHANGE}/editar`)).toHaveLength(0);
  });

  it('«Rechazar» asks for an optional reason and sends it as the note', async () => {
    const rejected = strategyChangeFixture({ state: 'rechazado', state_label: 'Rechazado', can_decide: false });
    const server = await renderCard({ [`POST ${CHANGE}/rechazar`]: { body: { change: rejected } } });
    await fireEvent.press(card().getByText('Rechazar'));
    const confirm = await sheet();
    expect(confirm.getByText('Rechazar el cambio')).toBeOnTheScreen();
    expect(confirm.getByText('No entra en la orientación. El analista no lo volverá a proponer igual en los próximos tres meses.')).toBeOnTheScreen();
    await fireEvent.changeText(confirm.getByTestId('confirm-note'), 'Ya publicamos casos de sobra.');
    await fireEvent.press(confirm.getByRole('button', { name: 'Rechazar' }));
    await waitFor(() => expect(server.find('POST', `${CHANGE}/rechazar`)).toHaveLength(1));
    expect(server.find('POST', `${CHANGE}/rechazar`)[0]!.body).toEqual({ note: 'Ya publicamos casos de sobra.' });
    expect(await screen.findByText('Cambio rechazado')).toBeOnTheScreen();
  });

  it('«Rechazar» without a reason sends no note', async () => {
    const server = await renderCard({ [`POST ${CHANGE}/rechazar`]: { body: { change: strategyChangeFixture({ state: 'rechazado', can_decide: false }) } } });
    await fireEvent.press(card().getByText('Rechazar'));
    await fireEvent.press((await sheet()).getByRole('button', { name: 'Rechazar' }));
    await waitFor(() => expect(server.find('POST', `${CHANGE}/rechazar`)).toHaveLength(1));
    expect(server.find('POST', `${CHANGE}/rechazar`)[0]!.body).toEqual({});
  });

  it('«Ver la revisión» opens the monthly review in Resultados without deciding anything', async () => {
    const server = await renderCard();
    await fireEvent.press(card().getByText('Ver la revisión'));
    expect(router.navigate).toHaveBeenCalledWith({ pathname: '/resultados', params: { pestana: 'mensual' } });
    expect(server.requests.filter((request) => request.method === 'POST' && request.path.startsWith('/api/v1/resultados'))).toEqual([]);
  });

  it('a refused decision keeps the card and says why', async () => {
    const server = await renderCard({ [`POST ${CHANGE}/aprobar`]: { status: 409, body: { detail: 'Este cambio ya se decidió.' } } });
    await fireEvent.press(card().getByText('Aprobar'));
    await waitFor(() => expect(server.find('POST', `${CHANGE}/aprobar`)).toHaveLength(1));
    expect(await card().findByText('Este cambio ya se decidió.')).toBeOnTheScreen();
    expect(card().getByText('No se puede ahora')).toBeOnTheScreen();
    expect(card().getByText('Editar y aprobar')).toBeOnTheScreen();
    expect(screen.queryByText(APPROVED)).toBeNull();
  });

  it('a card of a kind the app does not know yet still shows, with its actions', async () => {
    const future = { ...cardFixture({ id: 'futuro:1', type: 'tipo_futuro', title: 'Algo que aún no existe', body: 'Con un texto corto.', actions: [{ label: 'Entendido', endpoint: '/api/v1/futuro/1/ok' }] }), campo_nuevo: { valor: 1 } } as TurnoCard;
    const older = strategyCardFixture(strategyChangeFixture({ id: 'ch-2' }), { strategy_change: undefined, review: undefined, title: 'Cambio de estrategia: Comentar antes de invitar' });
    await renderCard({}, [future, older]);
    expect(card('futuro:1').getByText('Aviso')).toBeOnTheScreen();
    expect(card('futuro:1').getByText('Algo que aún no existe')).toBeOnTheScreen();
    expect(card('futuro:1').getByText('Entendido')).toBeOnTheScreen();
    expect(card(older.id).getByText('Cambio de estrategia: Comentar antes de invitar')).toBeOnTheScreen();
    expect(card(older.id).getByText('Ver la revisión')).toBeOnTheScreen();
    expect(screen.getByTestId(`turno-card-${older.id}`).props.accessibilityActions).toEqual([]);
  });
});
