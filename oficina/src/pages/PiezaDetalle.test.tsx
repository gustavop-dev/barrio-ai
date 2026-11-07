import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fakeServer, SESSION_OK, type Reply } from '../test/fakeServer';
import { piece, shellOverview, shellTurno } from '../test/fixtures/calendario';
import { renderCalendario } from '../test/fixtures/calendarioRender';
import type { PieceDetailFull } from './calendario/types';

function server(detail: PieceDetailFull | Reply, extra: Record<string, Reply> = {}) {
  return fakeServer({
    'GET /api/v1/auth/session': { body: SESSION_OK },
    'GET /api/v1/tu-turno': { body: shellTurno() },
    'GET /api/v1/operador/overview': { body: shellOverview() },
    [`GET /api/v1/editorial/pieces/${'id' in detail ? detail.id : 'p7'}`]: 'id' in detail ? { body: detail } : detail,
    ...extra,
  });
}

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

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-11-08T20:00:00Z')); // 15:00 on Sunday 8 in Bogotá
});
afterEach(() => {
  vi.useRealTimers();
});

describe('Detalle de una pieza', () => {
  it('shows a published piece: result by cut, who commented, the final text and the way back to its day', async () => {
    server(PUBLISHED);
    renderCalendario('/calendario/pieza/p7');

    expect(await screen.findByRole('heading', { name: 'Pieza del sábado 7 de noviembre', level: 1 })).toBeInTheDocument();
    expect(screen.getByText('Publicada')).toBeInTheDocument();
    expect(screen.getByText('Salió a las 09:00')).toBeInTheDocument();
    await waitFor(() => expect(document.querySelector('.topbar-back')).toHaveAttribute('href', '/calendario?fecha=2026-11-07'));
    expect(document.querySelector('.pz-back')).toHaveAttribute('href', '/calendario?fecha=2026-11-07');

    const result = screen.getByRole('region', { name: 'Resultado' });
    expect(within(result).getByText('Interacción = (reacciones + comentarios + republicaciones) / impresiones.')).toBeInTheDocument();
    expect(within(result).getByText('Interacción 3,5 %')).toBeInTheDocument();
    expect(within(result).getByText('1.210')).toBeInTheDocument();
    expect(within(result).getByText('—')).toBeInTheDocument(); // reposts missing: never 0
    expect(within(result).getAllByText('Aún no')).toHaveLength(2);
    expect(within(result).getByText('Llega el martes 10 de noviembre a las 09:00.')).toBeInTheDocument();
    expect(within(result).getByText('Llega el sábado 14 de noviembre a las 09:00.')).toBeInTheDocument();
    const who = within(result).getByRole('list', { name: 'Quién comentó, por rol' });
    expect(within(who).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['Comprador · 2', 'Par · 1', 'Sin clasificar · 1']);
    expect(within(result).getByRole('link', { name: /Ver el post en LinkedIn/ })).toHaveAttribute('href', 'https://www.linkedin.com/feed/update/urn:li:share:7/');

    expect(screen.queryByRole('region', { name: 'Veto' })).toBeNull();
    const text = screen.getByRole('region', { name: 'Texto final' });
    expect(within(text).getByText('Most feature requests arrive as a solution.')).toBeInTheDocument();
    expect(within(text).getByText('178 caracteres')).toBeInTheDocument();
    expect(within(text).getByRole('button', { name: 'Copiar' })).toBeInTheDocument();
    expect(within(text).getByText('Se publica tal cual, en inglés.')).toBeInTheDocument();
  });

  it('says the comments were never read and shows the last reading when there are no cuts yet', async () => {
    server(piece());
    renderCalendario('/calendario/pieza/p7');
    const result = await screen.findByRole('region', { name: 'Resultado' });
    expect(within(result).getAllByText('Aún no')).toHaveLength(2);
    expect(within(result).getByText('Sin dato')).toBeInTheDocument();
    expect(within(result).getByText('El corte no se pudo leer a tiempo.')).toBeInTheDocument();
    expect(within(result).getByText(/Última lectura: 1\.210 impresiones/)).toBeInTheDocument();
    expect(within(result).getByText('Los comentarios aún no se han leído.')).toBeInTheDocument();
  });

  it('vetoes a scheduled piece from its detail', async () => {
    const api = server(SCHEDULED, { 'POST /api/v1/operador/actions/act-8/reject': { body: {} } });
    const user = userEvent.setup();
    vi.setSystemTime(new Date('2026-11-07T15:00:00Z'));
    renderCalendario('/calendario/pieza/p8');

    expect(await screen.findByRole('heading', { name: 'Pieza del domingo 8 de noviembre' })).toBeInTheDocument();
    expect(screen.getByText('Programada')).toBeInTheDocument();
    expect(screen.getByText('Sale mañana a las 09:00')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Resultado' })).toBeNull();
    const veto = screen.getByRole('region', { name: 'Veto' });
    expect(within(veto).getByText('El equipo publica solo. Si no quieres que salga, vétala antes de las 09:00: ese día quedará sin publicación.')).toBeInTheDocument();

    await user.click(within(veto).getByRole('button', { name: 'Vetar' }));
    const dialog = screen.getByRole('dialog', { name: 'Vetar la pieza' });
    await user.type(within(dialog).getByLabelText(/Nota/), 'Prefiero otro tema');
    await user.click(within(dialog).getByRole('button', { name: 'Vetar' }));
    await waitFor(() => expect(api.find('POST', '/api/v1/operador/actions/act-8/reject')).toHaveLength(1));
    expect(api.find('POST', '/api/v1/operador/actions/act-8/reject')[0]!.body).toEqual({ note: 'Prefiero otro tema' });
    expect(await screen.findByText('Vetada')).toBeInTheDocument();
  });

  it('shows the 5 preparation steps while the piece is being prepared', async () => {
    server(piece({ status: 'preparing', state: 'preparing', stage: 'lectores', action: null, final_text: '', selection: {}, verification: {}, panel: {}, metrics: null }));
    vi.setSystemTime(new Date('2026-11-07T08:00:00Z'));
    renderCalendario('/calendario/pieza/p7');

    expect(await screen.findByText('Etapa: panel de lectores')).toBeInTheDocument();
    const steps = within(screen.getByRole('region', { name: 'Preparándose' })).getByRole('list', { name: 'Etapas de la preparación' });
    const items = within(steps).getAllByRole('listitem');
    expect(items).toHaveLength(5);
    expect(items[2]).toHaveAttribute('aria-current', 'step');
    expect(items[2]).toHaveTextContent('Panel de lectores');
    expect(within(items[0]!).getByText('Hecho')).toBeInTheDocument();
    expect(screen.getByText('Sale hoy a las 09:00. Puedes vetarla cuando esté lista.')).toBeInTheDocument();
    expect(screen.getByText('El texto final aparece cuando termine la selección.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Vetar' })).toBeNull();
  });

  it('opens the capture sheet tied to the piece and lists what Gustavo already told the team', async () => {
    server(
      piece({
        team_comments: [
          { id: 'cap-1', text: '', note: 'Usa el ejemplo de la llamada del martes', transcript: '', has_audio: true, audio_url: '/api/v1/capturas/cap-1/audio', created_at: '2026-11-08T18:00:00Z', by: 'gustavo' },
        ],
      }),
    );
    const user = userEvent.setup();
    const { onCapture } = renderCalendario('/calendario/pieza/p7');
    const comments = await screen.findByRole('region', { name: 'Tus comentarios para el equipo' });
    expect(within(comments).getByText('Usa el ejemplo de la llamada del martes')).toBeInTheDocument();
    expect(within(comments).getByText('hace 2 h')).toBeInTheDocument();
    expect(comments.querySelector('audio')).toHaveAttribute('src', '/api/v1/capturas/cap-1/audio');

    await user.click(within(comments).getByRole('button', { name: 'Comentario para el equipo' }));
    expect(onCapture).toHaveBeenCalledWith({ tipo: 'pieza', id: 'p7', label: 'Pieza del sábado 7 de noviembre' });
  });

  it('folds «Cómo se escribió» and shows the variants as tabs on mobile', async () => {
    server(PUBLISHED);
    const user = userEvent.setup();
    renderCalendario('/calendario/pieza/p7');
    const how = await screen.findByRole('region', { name: 'Cómo se escribió' });
    const folds = how.querySelectorAll('details');
    expect(folds).toHaveLength(6);
    expect([...folds].every((fold) => !fold.open)).toBe(true);
    expect([...folds].map((fold) => fold.querySelector('summary')?.textContent)).toEqual([
      'Brief',
      'Variantes A y B',
      'Panel de lectores',
      'Selección',
      'Verificador',
      'Fuentes y coste',
    ]);

    // Brief
    expect(within(folds[0]!).getByText('Lector comprador')).toBeInTheDocument();
    expect(within(folds[0]!).getByText('LI-05-M001-K02')).toBeInTheDocument();
    expect(within(folds[0]!).getByText('Solo texto')).toBeInTheDocument();

    // Variants: tabs, A chosen
    const tabs = within(folds[1]!).getByRole('tablist', { name: 'Variante' });
    expect(within(tabs).getByRole('tab', { name: 'Variante A · Elegida' })).toHaveAttribute('aria-selected', 'true');
    expect(within(folds[1]!).getByText('Elegida')).toBeInTheDocument();
    await user.click(within(tabs).getByRole('tab', { name: 'Variante B' }));
    expect(within(folds[1]!).getByText('Everyone wants AI everywhere.')).toBeInTheDocument();

    // Readers, selection, verifier, cost
    expect(within(folds[2]!).getByText('Faltan datos')).toBeInTheDocument();
    expect(within(folds[2]!).getByText('Objeción menor')).toBeInTheDocument();
    expect(within(folds[3]!).getByText('Variante A')).toBeInTheDocument();
    expect(within(folds[4]!).getByText('Aprobada')).toBeInTheDocument();
    expect(within(folds[4]!).getByText('Sin correcciones de las guardas')).toBeInTheDocument();
    expect(within(folds[4]!).getByText('2 de 3')).toBeInTheDocument();
    expect(within(folds[5]!).getByText('LI-04-M005-K01 · LI-06-M002-K09')).toBeInTheDocument();
    expect(within(folds[5]!).getByText('0,14 USD')).toBeInTheDocument();
    expect(within(folds[5]!).getByText('0,26 USD')).toBeInTheDocument();
  });

  it('explains a blocked piece', async () => {
    server(piece({ status: 'blocked', state: 'blocked', action: null, verification: { verdict: 'blocked', model_verdict: 'ready_for_execution', blocking_reasons: ['Afirma una experiencia que no está en tu memoria confirmada.'] } }));
    renderCalendario('/calendario/pieza/p7');
    expect(await screen.findByText('El verificador bloqueó la pieza')).toBeInTheDocument();
    expect(screen.getAllByText('Afirma una experiencia que no está en tu memoria confirmada.')[0]).toBeInTheDocument();
    expect(screen.getByText('Iba a salir a las 09:00')).toBeInTheDocument();
    expect(screen.getByText('Las guardas corrigieron al modelo')).toBeInTheDocument();
  });

  it('shows the error with a retry and keeps the way back', async () => {
    server({ status: 404, body: { detail: 'No encontrado.' } });
    renderCalendario('/calendario/pieza/p7');
    expect(await screen.findByText('No se pudo cargar la pieza')).toBeInTheDocument();
    expect(screen.getByText('No encontrado.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Detalle de la pieza', level: 1 })).toBeInTheDocument();
    expect(document.querySelector('.topbar-back')).toHaveAttribute('href', '/calendario');
  });
});

describe('Detalle de una pieza · escritorio', () => {
  beforeEach(() => {
    vi.spyOn(window, 'matchMedia').mockImplementation(
      (query: string) =>
        ({ matches: query.includes('min-width: 900px'), media: query, addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {}, onchange: null, dispatchEvent: () => false }) as unknown as MediaQueryList,
    );
  });

  it('uses a table for the cuts and puts the variants side by side', async () => {
    server(PUBLISHED);
    renderCalendario('/calendario/pieza/p7');
    const table = await screen.findByRole('table', { name: 'Resultado por corte' });
    expect(within(table).getAllByRole('row')).toHaveLength(4);
    expect(within(table).getByRole('rowheader', { name: 'A las 24 h' })).toBeInTheDocument();
    const how = screen.getByRole('region', { name: 'Cómo se escribió' });
    expect(within(how).queryByRole('tablist')).toBeNull();
    expect(within(how).getByText('Variante A · Copywriter A')).toBeInTheDocument();
    expect(within(how).getByText('Variante B · Copywriter B')).toBeInTheDocument();
  });
});
