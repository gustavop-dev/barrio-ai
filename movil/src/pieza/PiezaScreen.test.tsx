// Detalle de una pieza: the cuts and the missing-data rules, the veto with «Deshacer», the preparation
// steps, the final text with Copiar, the comments for the team, the folds and the variant tabs.
import { CAROUSEL_IMAGES, pieceImage } from '@compartido/fixtures/imagenes';
import type { PieceDetailFull } from '@compartido/api/calendario';
import { piece, shellOverview } from '@compartido/fixtures/calendario';
import { fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import * as Clipboard from 'expo-clipboard';
import { Text } from 'react-native';
import '@/api/transport';
import { flushVetoes } from '@/calendario/pendingVeto';
import { useCaptureSheet } from '@/capture/store';
import { renderApp } from '@/test/render';
import { fakeServer, type FakeHandler, type FakeReply } from '@/test/server';
import * as motion from '@/theme/motion';
import { PiezaScreen } from './PiezaScreen';

jest.mock('expo-clipboard', () => ({ setStringAsync: jest.fn(async () => true) }));

const expoRouter = jest.requireMock('expo-router') as { router: Record<string, jest.Mock> };

const PUBLISHED = piece({
  snapshots: [{ kind: '24h', impressions: 1210, reactions: 31, comments: 9, reposts: null, engagement_pct: 3.5, captured_at: '2026-11-08T14:00:00Z', age_hours: 24 }],
  commenters: [
    { provider_user_id: 'u1', name: 'Ana', substantive: true, role: 'comprador', fit: true },
    { provider_user_id: 'u2', name: 'Beto', substantive: false, role: 'comprador', fit: true },
    { provider_user_id: 'u3', name: 'Ciro', substantive: true, role: 'par', fit: true },
    { provider_user_id: 'u4', name: 'Dani', substantive: false, role: null, fit: null },
  ],
});

const SCHEDULED = piece({
  id: 'p8',
  slot_date: '2026-11-08',
  scheduled_for: '2026-11-08T14:00:00Z',
  status: 'scheduled',
  action: { id: 'act-8', state: 'approved', payload_hash: 'h' },
  metrics: null,
  external_url: null,
});

function server(detail: PieceDetailFull | FakeReply, extra: Record<string, FakeHandler> = {}) {
  const id = 'id' in detail ? detail.id : 'p7';
  return fakeServer({
    'GET /api/v1/operador/overview': { body: shellOverview() },
    [`GET /api/v1/editorial/pieces/${id}`]: 'id' in detail ? { body: detail } : detail,
    ...extra,
  });
}

function useFakeNow(iso: string) {
  jest.useFakeTimers({
    now: new Date(iso),
    doNotFake: ['hrtime', 'nextTick', 'performance', 'queueMicrotask', 'requestAnimationFrame', 'cancelAnimationFrame', 'requestIdleCallback', 'cancelIdleCallback', 'setImmediate', 'clearImmediate', 'setInterval', 'clearInterval', 'setTimeout', 'clearTimeout'],
  });
}

/** What the capture sheet would open with (CaptureSheetHost lives in the app layout). */
function CaptureProbe() {
  const { open, context } = useCaptureSheet();
  return <Text testID="captura">{JSON.stringify({ open, context })}</Text>;
}
const captureState = () => JSON.parse(String(screen.getByTestId('captura').props.children));

async function renderPieza(id = 'p7') {
  return renderApp(
    <>
      <PiezaScreen pieceId={id} />
      <CaptureProbe />
    </>,
  );
}

beforeEach(() => useFakeNow('2026-11-08T20:00:00Z')); // 15:00 on Sunday 8 in Bogotá
afterEach(async () => {
  await flushVetoes();
  jest.useRealTimers();
});

describe('Detalle de una pieza', () => {
  it('shows a published piece: its cuts, who commented, the final text and the post on LinkedIn', async () => {
    const { Linking } = require('react-native');
    const open = jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
    server(PUBLISHED);
    await renderPieza();
    expect(await screen.findByText('Pieza del sábado 7 de noviembre')).toBeOnTheScreen();
    expect(screen.getByText('Publicada')).toBeOnTheScreen();
    expect(screen.getByText('Salió a las 09:00')).toBeOnTheScreen();
    expect(screen.getByText('Interacción = (reacciones + comentarios + republicaciones) / impresiones.')).toBeOnTheScreen();

    const day = screen.getByTestId('corte-24h');
    expect(within(day).getByText('A las 24 h')).toBeOnTheScreen();
    expect(within(day).getByText('Interacción 3,5 %')).toBeOnTheScreen();
    expect(screen.getByLabelText('Impresiones: 1.210')).toBeOnTheScreen();
    // A missing metric is «—», never 0.
    expect(screen.getByLabelText('Republicaciones: —')).toBeOnTheScreen();
    expect(within(screen.getByTestId('corte-72h')).getByText('Aún no')).toBeOnTheScreen();
    expect(screen.getByText('Llega el martes 10 de noviembre a las 09:00.')).toBeOnTheScreen();
    expect(screen.getByText('Llega el sábado 14 de noviembre a las 09:00.')).toBeOnTheScreen();

    expect(screen.getByText('Comprador · 2')).toBeOnTheScreen();
    expect(screen.getByText('Par · 1')).toBeOnTheScreen();
    expect(screen.getByText('Sin clasificar · 1')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Ver el post en LinkedIn'));
    expect(open).toHaveBeenCalledWith('https://www.linkedin.com/feed/update/urn:li:share:7/');

    expect(screen.getByText('Most feature requests arrive as a solution.')).toBeOnTheScreen();
    expect(screen.getByText('Se publicó tal cual, en inglés.')).toBeOnTheScreen(); // backlog #13: it already went out
    expect(screen.queryByText('Veto')).toBeNull();
  });

  it('says «Sin dato» once a cut’s hour has passed, the last reading, and that comments were never read', async () => {
    useFakeNow('2026-11-12T20:00:00Z');
    server(piece({ snapshots: [], commenters: null }));
    await renderPieza();
    expect(await screen.findByText('Pieza del sábado 7 de noviembre')).toBeOnTheScreen();
    expect(within(screen.getByTestId('corte-24h')).getByText('Sin dato')).toBeOnTheScreen();
    expect(within(screen.getByTestId('corte-72h')).getByText('Sin dato')).toBeOnTheScreen();
    expect(screen.getAllByText('El corte no se pudo leer a tiempo.')).toHaveLength(2);
    expect(within(screen.getByTestId('corte-7d')).getByText('Aún no')).toBeOnTheScreen();
    expect(screen.getByText(/^Última lectura: 1\.210 impresiones, /)).toBeOnTheScreen();
    expect(screen.getByText('Los comentarios aún no se han leído.')).toBeOnTheScreen();
  });

  it('shows the conversation on the post: each comment, what the team did, and its replies', async () => {
    server(
      piece({
        comments: {
          count: 2,
          read_at: '2026-11-07T18:00:00Z',
          threads: [
            {
              id: 'pc-1',
              comment: {
                id: 'pc-1',
                author: { name: 'Marta Ejemplo', profile_url: null, contact_id: 'c-9', headline: 'Head of Product', role: 'par' },
                text: 'We ask customers for the problem first.',
                at: '2026-11-07T15:00:00Z',
                own: false,
                status: 'respondido',
                status_label: 'Respondido',
                reply: null,
                turn: 1,
              },
              answers: [
                {
                  id: 'pc-2',
                  author: { name: 'Gustavo', profile_url: null, contact_id: null, headline: '', role: null },
                  text: 'That list is still useful: we read it as symptoms.',
                  at: '2026-11-07T16:00:00Z',
                  own: true,
                  status: 'equipo',
                  status_label: 'Del equipo',
                  reply: null,
                  turn: null,
                },
              ],
            },
            {
              id: 'pc-3',
              comment: {
                id: 'pc-3',
                author: { name: 'Beto Prueba', profile_url: null, contact_id: null, headline: '', role: null },
                text: 'Great post!',
                at: '2026-11-07T17:00:00Z',
                own: false,
                status: 'reaccion',
                status_label: 'Reacción',
                reply: { text: null, reaction: 'linkedin_like', state: 'confirmed' },
                turn: null,
              },
              answers: [],
            },
          ],
        },
      }),
    );
    await renderPieza();
    expect(await screen.findByText('Conversación en el post')).toBeOnTheScreen();
    expect(screen.getByText(/^2 comentarios · el equipo respondió 1 · reaccionó a 1/)).toBeOnTheScreen();
    const first = screen.getByTestId('comentario-pc-1');
    expect(within(first).getByText('Respondido')).toBeOnTheScreen();
    expect(within(screen.getByTestId('comentario-pc-2')).getByText('Tú')).toBeOnTheScreen();
    expect(within(screen.getByTestId('comentario-pc-3')).getByText('El equipo reaccionó a este comentario')).toBeOnTheScreen();
    await fireEvent.press(within(first).getByText('Marta Ejemplo'));
    expect(expoRouter.router.push).toHaveBeenCalledWith({ pathname: '/personas/[id]', params: { id: 'c-9' } });
  });

  it('copies the final text and counts its characters', async () => {
    server(PUBLISHED);
    await renderPieza();
    expect(await screen.findByText('178 caracteres')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Copiar'));
    expect(Clipboard.setStringAsync).toHaveBeenCalledWith(PUBLISHED.final_text);
    expect(await screen.findByText('Copiado')).toBeOnTheScreen();
  });

  it('says the final text comes after the selection while it is not there', async () => {
    useFakeNow('2026-11-07T08:00:00Z');
    server(piece({ status: 'preparing', state: 'preparing', stage: 'lectores', action: null, final_text: '', selection: {}, snapshots: [], metrics: null }));
    await renderPieza();
    expect(await screen.findByText('Etapa: panel de lectores')).toBeOnTheScreen();
    expect(screen.getByText('El texto final aparece cuando termine la selección.')).toBeOnTheScreen();
    expect(screen.getByLabelText('Etapas de la preparación')).toBeOnTheScreen();
    expect(screen.getByLabelText('1. Director: idea y brief, hecho')).toBeOnTheScreen();
    expect(screen.getByLabelText('2. Redactores: variantes A y B, hecho')).toBeOnTheScreen();
    expect(screen.getByLabelText('3. Panel de lectores, ahora')).toBeOnTheScreen();
    expect(screen.getByLabelText('5. Verificador, pendiente')).toBeOnTheScreen();
    expect(screen.getByText('Sale hoy a las 09:00. Puedes vetarla cuando esté lista.')).toBeOnTheScreen();
    expect(screen.queryByText('Resultado')).toBeNull();
  });

  it('opens the capture sheet tied to the piece and lists what Gustavo already told the team, with its audio', async () => {
    server(
      piece({
        team_comments: [
          { id: 'cap-1', text: '', note: 'Usa el ejemplo de la llamada del martes', transcript: '', has_audio: true, audio_url: '/api/v1/capturas/cap-1/audio', created_at: '2026-11-08T18:00:00Z', by: 'gustavo' },
        ],
      }),
    );
    await renderPieza();
    expect(await screen.findByText('Tus comentarios para el equipo')).toBeOnTheScreen();
    expect(screen.getByText('Usa el ejemplo de la llamada del martes')).toBeOnTheScreen();
    expect(screen.getByText('hace 2 h')).toBeOnTheScreen();
    expect(screen.getByText('Escuchar')).toBeOnTheScreen();

    await fireEvent.press(screen.getByText('Comentario para el equipo'));
    expect(captureState()).toEqual({ open: true, context: { tipo: 'pieza', id: 'p7', label: 'Scope features from the decision they support.' } });
  });

  it('keeps every fold of «Cómo se escribió» closed, and shows the variants as tabs you can swipe', async () => {
    server(PUBLISHED);
    await renderPieza();
    await screen.findByText('Cómo se escribió');
    for (const fold of ['Brief', 'Variantes A y B', 'Panel de lectores', 'Selección', 'Verificador', 'Fuentes y coste']) expect(screen.getByText(fold)).toBeOnTheScreen();
    expect(screen.queryByText('Ronda de reparación')).toBeNull();
    expect(screen.queryByText('Lector comprador')).toBeNull();

    await fireEvent.press(screen.getByText('Brief'));
    expect(screen.getByText('Lector comprador')).toBeOnTheScreen();
    expect(screen.getByText('LI-05-M001-K02')).toBeOnTheScreen();
    expect(screen.getByText('Solo texto')).toBeOnTheScreen();

    await fireEvent.press(screen.getByText('Variantes A y B'));
    const tabA = screen.getByRole('tab', { name: 'Variante A · Elegida' });
    const tabB = screen.getByRole('tab', { name: 'Variante B' });
    expect(tabA).toBeSelected();
    expect(within(screen.getByTestId('variante-A')).getByText('Elegida')).toBeOnTheScreen();
    // The other variant waits beside it, hidden from screen readers until its tab is chosen.
    expect(screen.queryByText('Everyone wants AI everywhere.')).toBeNull();
    await fireEvent.press(tabB);
    expect(screen.getByRole('tab', { name: 'Variante B' })).toBeSelected();
    expect(screen.getByText('Everyone wants AI everywhere.')).toBeOnTheScreen();
    // Swiping the card back to A selects its tab.
    await fireEvent(screen.getByTestId('variantes').parent!, 'layout', { nativeEvent: { layout: { x: 0, y: 0, width: 300, height: 200 } } });
    await fireEvent(screen.getByTestId('variantes'), 'momentumScrollEnd', { nativeEvent: { contentOffset: { x: 0, y: 0 } } });
    expect(screen.getByRole('tab', { name: 'Variante A · Elegida' })).toBeSelected();

    await fireEvent.press(screen.getByText('Panel de lectores'));
    expect(screen.getByText('Faltan datos')).toBeOnTheScreen();
    expect(screen.getByText('Objeción menor')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Verificador'));
    expect(screen.getByText('Aprobada')).toBeOnTheScreen();
    expect(screen.getByText('Sin correcciones de las guardas')).toBeOnTheScreen();
    expect(screen.getByText('2 de 3')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Fuentes y coste'));
    expect(screen.getByText('LI-04-M005-K01 · LI-06-M002-K09')).toBeOnTheScreen();
    expect(screen.getByText('0,14 USD')).toBeOnTheScreen();
    expect(screen.getByText('0,26 USD')).toBeOnTheScreen();
  });

  it('shows the repair round when the rules asked for one', async () => {
    server(
      piece({
        verification: {
          verdict: 'ready_for_execution',
          model_verdict: 'ready_for_execution',
          blocking_reasons: [],
          rules: [],
          repair: {
            trigger: 'reglas',
            findings: [{ source: 'reglas', issue: 'regla', quote: '', detail: 'Contiene enlaces' }],
            original_text: 'Most feature requests arrive as a solution. More at https://example.com',
            changes: [{ finding: 'Contiene enlaces', change: 'Quité el enlace del cierre.' }],
            outcome: 'reparada',
          },
        },
      }),
    );
    await renderPieza();
    await fireEvent.press(await screen.findByText('Ronda de reparación'));
    expect(screen.getByText('Reparada y verificada')).toBeOnTheScreen();
    expect(screen.getByText('La pidieron las reglas de publicación')).toBeOnTheScreen();
    expect(screen.getByText('Contiene enlaces')).toBeOnTheScreen();
    expect(screen.getByText('Quité el enlace del cierre.')).toBeOnTheScreen();
    expect(screen.getByText('Most feature requests arrive as a solution. More at https://example.com')).toBeOnTheScreen();
  });

  it('explains a blocked piece and an uncertain one', async () => {
    server(piece({ status: 'blocked', state: 'blocked', action: null, verification: { verdict: 'blocked', model_verdict: 'ready_for_execution', blocking_reasons: ['Afirma una experiencia que no está en tu memoria confirmada.'] } }));
    await renderPieza();
    expect(await screen.findByText('El verificador bloqueó la pieza')).toBeOnTheScreen();
    // The reasons are folded under the title: they show only when he opens them.
    expect(screen.queryByText('Afirma una experiencia que no está en tu memoria confirmada.')).toBeNull();
    await fireEvent.press(screen.getByText('Por qué se bloqueó'));
    expect(screen.getByText('Afirma una experiencia que no está en tu memoria confirmada.')).toBeOnTheScreen();
    expect(screen.getByText('Iba a salir a las 09:00')).toBeOnTheScreen();
  });

  // EDI-23: on a block he sees why and decides.
  it('on a block he asks for a change with a comment or dismisses it with an optional note', async () => {
    const blocked = piece({
      status: 'blocked',
      state: 'blocked',
      action: null,
      images: [],
      verification: { verdict: 'blocked', blocking_reasons: ['Contiene pitch agresivo o petición de contacto'] } as PieceDetailFull['verification'],
      rescue: { kind: 'verificador', override: true, change: true, why_not: '' },
    });
    const api = server(blocked, { 'POST /api/v1/editorial/pieces/p7/desestimar': { status: 202, body: { job: { id: 'job-1' } } } });
    await renderPieza();
    // The two ways out come first; the reason is one tap away.
    expect(await screen.findByText('Desestimar el bloqueo')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Por qué se bloqueó'));
    expect(screen.getByText('Contiene pitch agresivo o petición de contacto')).toBeOnTheScreen();

    await fireEvent.press(screen.getByText('Pedir un cambio'));
    expect(captureState()).toEqual({ open: true, context: { tipo: 'pieza', id: 'p7', label: 'Pieza del sábado 7 de noviembre' } });

    await fireEvent.press(screen.getByText('Desestimar el bloqueo'));
    const confirm = await screen.findByTestId('confirm-sheet');
    expect(within(confirm).getByText(/sin pasar por el líder\. Antes, el equipo le prepara la imagen/)).toBeOnTheScreen();
    await fireEvent.changeText(within(confirm).getByTestId('confirm-note'), 'Sale así');
    await fireEvent.press(within(confirm).getByText('Desestimar'));
    await waitFor(() => expect(api.find('POST', '/api/v1/editorial/pieces/p7/desestimar')).toHaveLength(1));
    const body = api.find('POST', '/api/v1/editorial/pieces/p7/desestimar')[0]!.body as { request_id: string; note: string };
    expect(body.note).toBe('Sale así');
    expect(body.request_id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect(within(await screen.findByTestId('toast')).getByText('Bloqueo desestimado: el equipo la deja lista para salir con tu aprobación.')).toBeOnTheScreen();
  });

  it('says why a block has no way out, without its buttons', async () => {
    server(
      piece({
        status: 'blocked',
        state: 'blocked',
        action: null,
        rescue: { kind: 'verificador', override: false, change: false, why_not: 'Ese día ya tiene otra pieza programada.' },
      }),
    );
    await renderPieza();
    expect(await screen.findByText('Ese día ya tiene otra pieza programada.')).toBeOnTheScreen();
    expect(screen.queryByText('Desestimar el bloqueo')).toBeNull();
    expect(screen.queryByText('Pedir un cambio')).toBeNull();
  });

  it('sends Gustavo to Tu turno to resolve an uncertain piece', async () => {
    server(piece({ status: 'uncertain', action_detail: { id: 'act-7' } as PieceDetailFull['action_detail'] }));
    await renderPieza();
    expect(await screen.findByText('No se sabe si salió')).toBeOnTheScreen();
    // From the piece (a detail over the tabs) it goes back down to the tabs instead of stacking another shell.
    (expoRouter.router.canDismiss as jest.Mock).mockReturnValueOnce(true);
    await fireEvent.press(screen.getByText('Resuélvela en la Bandeja'));
    expect(expoRouter.router.dismissTo).toHaveBeenCalledWith({ pathname: '/tu-turno', params: { ancla: 'turno-uncertain-act-7' } });
    expect(expoRouter.router.push).not.toHaveBeenCalled();
  });

  it('shows the error with a retry', async () => {
    const api = server({ status: 404, body: { detail: 'No encontrado.' } });
    await renderPieza();
    expect(await screen.findByText('No se pudo cargar la pieza')).toBeOnTheScreen();
    expect(screen.getByText('No encontrado.')).toBeOnTheScreen();
    expect(screen.getByText('Detalle de la pieza')).toBeOnTheScreen();
    api.on('GET /api/v1/editorial/pieces/p7', { body: PUBLISHED });
    await fireEvent.press(screen.getByText('Reintentar'));
    expect(await screen.findByText('Pieza del sábado 7 de noviembre')).toBeOnTheScreen();
  });
});

describe('Detalle de una pieza · veto con «Deshacer»', () => {
  beforeEach(() => useFakeNow('2026-11-07T15:00:00Z'));

  it('asks for a note, then gives 5 s to undo before sending anything', async () => {
    const api = server(SCHEDULED, { 'POST /api/v1/operador/actions/act-8/reject': { body: {} } });
    await renderPieza('p8');
    expect(await screen.findByText('Sale mañana a las 09:00')).toBeOnTheScreen();
    expect(screen.getByText('El equipo publica solo. Si no quieres que salga, vétala antes de las 09:00: ese día quedará sin publicación.')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Vetar'));
    const confirm = await screen.findByTestId('confirm-sheet');
    expect(within(confirm).getByText('Vetar la pieza')).toBeOnTheScreen();
    // Why «Vetar» does nothing yet: the note is marked as required, as in the PWA.
    expect(within(confirm).getByText('Nota · obligatoria')).toBeOnTheScreen();
    const send = within(confirm).getAllByText('Vetar').at(-1)!;
    await fireEvent.press(send);
    expect(screen.getByTestId('confirm-sheet')).toBeOnTheScreen();
    await fireEvent.changeText(within(confirm).getByTestId('confirm-note'), 'No es el momento');
    await fireEvent.press(within(confirm).getAllByText('Vetar').at(-1)!);

    const toast = await screen.findByTestId('toast');
    expect(within(toast).getByText('Vetada')).toBeOnTheScreen();
    await fireEvent.press(within(toast).getByText('Deshacer'));
    await flushVetoes();
    expect(api.find('POST', '/api/v1/operador/actions/act-8/reject')).toHaveLength(0);
    expect(await screen.findByText('Vetar')).toBeOnTheScreen();
  });

  it('sends the veto when nobody undoes it, and refreshes the piece', async () => {
    jest.replaceProperty(motion.toastDurations as { withUndo: number }, 'withUndo', 30);
    const api = server(SCHEDULED, { 'POST /api/v1/operador/actions/act-8/reject': { body: {} } });
    await renderPieza('p8');
    await fireEvent.press(await screen.findByText('Vetar'));
    const confirm = await screen.findByTestId('confirm-sheet');
    await fireEvent.changeText(within(confirm).getByTestId('confirm-note'), 'No es el momento');
    await fireEvent.press(within(confirm).getAllByText('Vetar').at(-1)!);
    await waitFor(() => expect(api.find('POST', '/api/v1/operador/actions/act-8/reject')[0]?.body).toEqual({ note: 'No es el momento' }));
    await waitFor(() => expect(api.find('GET', '/api/v1/editorial/pieces/p8').length).toBeGreaterThan(1));
  });

  // E2E wave, E4 bug 1: the veto had its own 5 s timer, started before its toast appeared, so «Deshacer» was still on
  // screen when the veto had already gone (tapping it then said «El veto ya se había enviado»).
  it('sends the veto only once its «Deshacer» has left the screen', async () => {
    jest.replaceProperty(motion.toastDurations as { withUndo: number }, 'withUndo', 30);
    const undoOnScreenAtSend: boolean[] = [];
    const api = server(SCHEDULED, {
      'POST /api/v1/operador/actions/act-8/reject': () => {
        undoOnScreenAtSend.push(screen.queryByText('Deshacer') !== null);
        return { body: {} };
      },
    });
    await renderPieza('p8');
    await fireEvent.press(await screen.findByText('Vetar'));
    const confirm = await screen.findByTestId('confirm-sheet');
    await fireEvent.changeText(within(confirm).getByTestId('confirm-note'), 'No es el momento');
    await fireEvent.press(within(confirm).getAllByText('Vetar').at(-1)!);
    expect(within(await screen.findByTestId('toast')).getByText('Deshacer')).toBeOnTheScreen();
    await waitFor(() => expect(api.find('POST', '/api/v1/operador/actions/act-8/reject')).toHaveLength(1));
    expect(undoOnScreenAtSend).toEqual([false]);
  });

  it('sends a pending veto at once when the app goes to the background', async () => {
    const api = server(SCHEDULED, { 'POST /api/v1/operador/actions/act-8/reject': { body: {} } });
    const { AppState } = require('react-native');
    const listen = jest.spyOn(AppState, 'addEventListener');
    await renderPieza('p8');
    await fireEvent.press(await screen.findByText('Vetar'));
    const confirm = await screen.findByTestId('confirm-sheet');
    await fireEvent.changeText(within(confirm).getByTestId('confirm-note'), 'No');
    await fireEvent.press(within(confirm).getAllByText('Vetar').at(-1)!);
    const handler = listen.mock.calls.find(([type]) => type === 'change')?.[1] as (state: string) => void;
    handler('background');
    await waitFor(() => expect(api.find('POST', '/api/v1/operador/actions/act-8/reject')).toHaveLength(1));
  });
});


describe('IMG-11 · imágenes de la pieza', () => {
  async function measureImage() {
    await screen.findByTestId('piece-images');
    await fireEvent(screen.getByTestId('piece-images-pager').parent!, 'layout', { nativeEvent: { layout: { x: 0, y: 0, width: 300, height: 375 } } });
  }

  it('shows the original photo and reason, and keeps the existing veto for the whole piece', async () => {
    useFakeNow('2026-11-07T15:00:00Z');
    server({ ...SCHEDULED, images: [pieceImage()], image_kind: 'foto' as const });
    await renderPieza('p8');
    await measureImage();
    expect(screen.getByLabelText('People sharing a product demonstration.')).toBeOnTheScreen();
    expect(screen.getByText('Se publica tal cual')).toBeOnTheScreen();
    expect(screen.getByText('Instrucción de Gustavo: úsala tal cual')).toBeOnTheScreen();
    expect(screen.getByText('Vetar')).toBeOnTheScreen();
    expect(screen.queryByText('Ver original')).toBeNull();
  });

  it('compares an AI edit with its authenticated original and retries a failed image', async () => {
    server({ ...PUBLISHED, images: [pieceImage({ edited: true, ai_edit: 'si', reason: 'Más luz', review: { ok: true } })] });
    await renderPieza();
    await measureImage();
    expect(screen.getByText('Editada con IA')).toBeOnTheScreen();
    expect(screen.getByText('Comprobación aprobada')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Ver original'));
    expect(JSON.stringify(screen.getByTestId('piece-image-original').props.source)).toContain('/galeria/f1/imagen');
    await fireEvent.press(screen.getByText('Ver editada'));
    await fireEvent(screen.getByTestId('piece-image-1'), 'error', { nativeEvent: { error: '404' } });
    expect(screen.getByText('No se pudo cargar la imagen')).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Reintentar'));
    expect(screen.getByTestId('piece-image-1')).toBeOnTheScreen();
    expect(screen.queryByText('Vetar')).toBeNull();
  });

  it('marks a plain crop without AI apart from an AI edit and compares it with the original', async () => {
    const reason = 'Decisión del equipo: adaptar el encuadre para LinkedIn; sale recortada a 1080×1350, centrada y sin IA';
    server({ ...PUBLISHED, images: [pieceImage({ cropped: true, ai_edit: 'auto', width: 1080, height: 1350, mime: 'image/jpeg', reason })] });
    await renderPieza();
    await measureImage();
    expect(screen.getByText('Recortada, sin IA')).toBeOnTheScreen();
    expect(screen.queryByText('Editada con IA')).toBeNull();
    expect(screen.queryByText('Se publica tal cual')).toBeNull();
    expect(screen.getByText(reason)).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Ver original'));
    expect(JSON.stringify(screen.getByTestId('piece-image-original').props.source)).toContain('/galeria/f1/imagen');
    await fireEvent.press(screen.getByText('Ver recortada'));
    expect(screen.getByTestId('piece-image-1')).toBeOnTheScreen();
  });

  it('shows an infographic, its template, alt and review', async () => {
    server({ ...PUBLISHED, image_kind: 'infografia' as const, images: [pieceImage({ ...CAROUSEL_IMAGES[1]!, kind: 'infografia' })] });
    await renderPieza();
    await measureImage();
    expect(screen.getByText('Infografía')).toBeOnTheScreen();
    expect(screen.getByText('Plantilla: Pasos')).toBeOnTheScreen();
    expect(screen.getByText('1. Correcto: Texto legible')).toBeOnTheScreen();
    expect(screen.getByLabelText(CAROUSEL_IMAGES[1]!.alt)).toBeOnTheScreen();
  });

  it('orders carousel slides, swipes them and exposes only the active alt to screen readers', async () => {
    server({ ...PUBLISHED, image_kind: 'carrusel' as const, images: [...CAROUSEL_IMAGES].reverse() });
    await renderPieza();
    await measureImage();
    expect(screen.getByText('1/3')).toBeOnTheScreen();
    expect(screen.getByLabelText(CAROUSEL_IMAGES[0]!.alt)).toBeOnTheScreen();
    expect(screen.queryByLabelText(CAROUSEL_IMAGES[1]!.alt)).toBeNull();
    await fireEvent(screen.getByTestId('piece-images-pager'), 'momentumScrollEnd', { nativeEvent: { contentOffset: { x: 300, y: 0 } } });
    expect(screen.getByText('2/3')).toBeOnTheScreen();
    expect(screen.getByLabelText(CAROUSEL_IMAGES[1]!.alt)).toBeOnTheScreen();
    await fireEvent.press(screen.getByText('Siguiente'));
    expect(screen.getByText('3/3')).toBeOnTheScreen();
    expect(screen.getByText('Plantilla: Cierre')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Siguiente' })).toBeDisabled();
  });

  it('does not call a fixed brand card a dynamic visual verification', async () => {
    server({ ...PUBLISHED, image_kind: 'tarjeta' as const, images: [pieceImage({ kind: 'tarjeta', review: { ok: true, mode: 'fixed_brand_card' } })] });
    await renderPieza();
    expect(await screen.findByText('Plantilla fija de marca; sin revisión visual dinámica.')).toBeOnTheScreen();
    expect(screen.queryByText('Comprobación aprobada')).toBeNull();
  });

  it('explains that the image is still being prepared', async () => {
    server(piece({ status: 'preparing', images: [], image_kind: null }));
    await renderPieza();
    expect(await screen.findByText('La imagen aparece cuando el equipo la prepare')).toBeOnTheScreen();
  });
});


it('approves text and images using the received hash without changing the manifest', async () => {
  useFakeNow('2026-11-07T15:00:00Z');
  const api = server({ ...SCHEDULED, status: 'awaiting_approval', action: { id: 'act-8', state: 'proposed', payload_hash: 'frozen-text-and-images' }, images: CAROUSEL_IMAGES }, {
    'POST /api/v1/operador/actions/act-8/approve': { body: {} },
  });
  await renderPieza('p8');
  await fireEvent.press(await screen.findByText('Aprobar'));
  await waitFor(() => expect(api.find('POST', '/api/v1/operador/actions/act-8/approve')[0]?.body).toEqual({ expected_hash: 'frozen-text-and-images', note: '' }));
});

it('hides the veto after the scheduled time even if the last response still says approved', async () => {
  server({ ...SCHEDULED, images: [pieceImage()] });
  await renderPieza('p8');
  await screen.findByTestId('piece-images');
  expect(screen.queryByText('Vetar')).toBeNull();
});


it('explains a rejected edit while showing the original that will be published', async () => {
  server({ ...PUBLISHED, images: [pieceImage({ reason: 'Se conserva el original: la edición cambió un rostro', review: { ok: false, reasons: ['La edición cambió un rostro'] } })] });
  await renderPieza();
  expect(await screen.findByText('Se conserva el original: la edición cambió un rostro')).toBeOnTheScreen();
  expect(screen.getByText('Se publica tal cual')).toBeOnTheScreen();
  expect(screen.getByText('Comprobación no aprobada')).toBeOnTheScreen();
  expect(screen.queryByText('Editada con IA')).toBeNull();
  expect(screen.queryByText('Ver original')).toBeNull();
});

it('shows the AI edit the check rejected, with why, next to the original that goes out', async () => {
  const rejected = { url: '/api/v1/editorial/pieces/p7/images/img-1/descartada?v=abc', reasons: ['La edición cambió un rostro'], width: 1080, height: 1350 };
  server({ ...PUBLISHED, images: [pieceImage({ reason: 'Instrucción de Gustavo; edición descartada', review: { ok: false, reasons: ['La edición cambió un rostro'] }, rejected_edit: rejected })] });
  await renderPieza();
  const block = await screen.findByTestId('piece-image-rejected');
  expect(within(block).getByText('Edición con IA descartada')).toBeOnTheScreen();
  expect(within(block).getByText('No se publica')).toBeOnTheScreen();
  expect(within(block).getByText('• La edición cambió un rostro')).toBeOnTheScreen();
  expect(JSON.stringify(within(block).getByLabelText(/^Edición con IA descartada\./).props.source)).toContain('/descartada?v=abc');
  expect(screen.getByText('Se publica tal cual')).toBeOnTheScreen();
});
