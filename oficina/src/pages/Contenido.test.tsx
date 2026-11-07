import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { Action, EditorialCalendar, PieceDetail, PieceSummary } from '../api/types';
import { fakeServer } from '../test/fakeServer';
import { renderAt } from '../test/render';
import { Contenido, EditorialRedirect } from './Contenido';
import { Pieza } from './Pieza';

// Payloads shaped like agentes-linkedin/infra/src/team_backend/editorial_views.py and test_publicacion.py.
const GOOD_POST = `Before writing a line of code for a new feature, ask one question: what decision will this help someone make?

Which decision is your product helping someone make this week?`;
const HASH = 'b'.repeat(64);

function summary(id: string, extra: Partial<PieceSummary> = {}): PieceSummary {
  return {
    id,
    slot_date: '2026-11-07',
    scheduled_for: '2026-11-07T13:30:00Z',
    state: 'ready',
    status: 'scheduled',
    stage: 'verificador',
    note: 'Lista para la política autónoma.',
    modality: 'personal_startups',
    pillar: 'business_to_product',
    primary_reader: 'lector_comprador',
    thesis: 'Scope features from the decision they support.',
    approach: 'LI-05-M001-K02',
    action: { id: `act-${id}`, state: 'approved', payload_hash: HASH },
    external_url: null,
    created_at: '2026-11-06T20:30:00Z',
    ...extra,
  };
}

function calendar(pieces: Record<string, PieceSummary[]>): EditorialCalendar {
  const days = ['2026-11-05', '2026-11-06', '2026-11-07', '2026-11-08'];
  return {
    timezone: 'America/Bogota',
    post_time: '08:30',
    lead_hours: 12,
    config_error: null,
    today: '2026-11-06',
    days: days.map((date) => ({ date, pieces: pieces[date] ?? [] })),
  };
}

const assessment = { strengths: ['Clear question'], objections: [{ text: 'Could use an example', severity: 'preference' as const }] };

function detail(extra: Partial<PieceDetail> = {}): PieceDetail {
  const claims = [{ text: 'A weekly decision rarely needs real-time data.', kind: 'general_knowledge', ref: '' }];
  return {
    ...summary('piece-1'),
    brief: {
      decision: 'write',
      skip_reason: '',
      primary_reader: 'lector_comprador',
      modality: 'personal_startups',
      pillar: 'business_to_product',
      thesis: 'Scope features from the decision they support.',
      approach: 'LI-05-M001-K02',
      format: 'text_only',
      reader_value: 'A scoping question to reuse.',
      evidence: [{ kind: 'general_knowledge', ref: '', note: 'Product scoping practice' }],
      success_criterion: 'Founders reply with their decision.',
      avoid: ['Inventing cases'],
      signals_used: [],
      citations: ['LI-04-M005-K01'],
      rationale: 'Pillar fits; no repetition.',
    },
    variants: {
      variant_a: { angle: 'decision', text: 'Variant A text about decisions.', claims, uncertainties: [] },
      variant_b: { angle: 'objection', text: 'Variant B text about a founder objection.', claims, uncertainties: [] },
      citations: ['LI-06-M002-K09'],
    },
    panel: {
      readers: [
        { reader: 'lector_comprador', variant_a: assessment, variant_b: { strengths: ['Names the founder doubt'], objections: [{ text: 'Hook promises too much', severity: 'material' }] } },
        { reader: 'lector_par', variant_a: assessment, variant_b: assessment },
      ],
      summary: 'A slightly stronger.',
      citations: [],
    },
    selection: {
      decision: 'A',
      final_text: GOOD_POST,
      rationale: 'Clearer hook.',
      claims,
      resolved_objections: [],
      kept_objections: ['Could use an example'],
      citations: ['LI-06-M002-K09'],
    },
    verification: {
      verdict: 'ready_for_execution',
      model_verdict: 'ready_for_execution',
      blocking_reasons: [],
      findings: [{ issue: 'other', severity: 'minor', quote: 'ask one question', detail: 'Slightly generic opening.' }],
      checked_claims: [{ text: 'A weekly decision rarely needs real-time data.', status: 'general_knowledge', ref: '' }],
      summary: 'Checked.',
      citations: ['LI-06-M002-K09'],
      text_sha256: HASH,
    },
    final_text: GOOD_POST,
    citations: ['LI-04-M005-K01', 'LI-06-M002-K09'],
    signals: [],
    usage: [
      { stage: 'director', model: 'claude-opus-5-5', estimated_usd: 0.01, request_id: 'req_editorial-director', units: [], missing_units: [] },
      { stage: 'verificador', model: 'claude-opus-5-5', estimated_usd: 0.02, request_id: 'req_editorial-verificador', units: [], missing_units: [] },
    ],
    action_detail: null as Action | null,
    ...extra,
  };
}

const routes = [
  { path: '/contenido', element: <Contenido /> },
  { path: '/contenido/:pieceId', element: <Pieza /> },
  { path: '/editorial/:pieceId', element: <EditorialRedirect /> },
];

describe('Contenido · calendario', () => {
  it('shows each day with the status of its pieces, visible gaps and the autonomous policy', async () => {
    const server = fakeServer({
      'GET /api/v1/editorial/calendar': {
        body: calendar({
          '2026-11-05': [summary('p-pub', { slot_date: '2026-11-05', status: 'published', action: { id: 'act-pub', state: 'confirmed', payload_hash: HASH }, external_url: 'https://www.linkedin.com/feed/update/urn:li:share:1/' })],
          '2026-11-06': [summary('p-skip', { slot_date: '2026-11-06', state: 'skipped', status: 'skipped', thesis: null, pillar: null, modality: null, primary_reader: null, action: null, note: 'No genuine material today.' })],
          '2026-11-07': [summary('p-next')],
        }),
      },
    });
    renderAt('/contenido', routes);

    expect(screen.getByText(/Publicación autónoma: las piezas salen solas/)).toBeInTheDocument();
    expect(await screen.findByText(/se publica sola a las 08:30 \(America\/Bogota\)/)).toBeInTheDocument();
    expect(screen.getByText(/empieza 12 h antes/)).toBeInTheDocument();
    expect(server.requests[0]?.search.get('dias')).toBe('15');

    const items = within(screen.getByRole('list', { name: 'Calendario' })).getAllByRole('listitem');
    expect(items).toHaveLength(4);
    expect(within(items[0]!).getByText('Publicada')).toBeInTheDocument();
    expect(within(items[0]!).getByRole('link', { name: /Ver el post publicado/ })).toHaveAttribute('href', 'https://www.linkedin.com/feed/update/urn:li:share:1/');
    expect(within(items[1]!).getByText('Hoy')).toBeInTheDocument();
    expect(items[1]).toHaveAttribute('aria-current', 'date');
    expect(within(items[1]!).getByText('Día sin pieza')).toBeInTheDocument();
    expect(within(items[1]!).getByText('No genuine material today.')).toBeInTheDocument();
    expect(within(items[2]!).getByText('Programada')).toBeInTheDocument();
    expect(within(items[2]!).getByRole('link', { name: 'Scope features from the decision they support.' })).toHaveAttribute('href', '/contenido/p-next');
    expect(within(items[2]!).getByText(/08:30 · Del negocio al producto · Personal · startups · Lector comprador/)).toBeInTheDocument();
    expect(within(items[2]!).getByRole('button', { name: 'Vetar' })).toBeInTheDocument();
    expect(within(items[0]!).queryByRole('button', { name: 'Vetar' })).not.toBeInTheDocument();
    expect(within(items[3]!).getByText('Hueco libre: aún sin pieza.')).toBeInTheDocument();

    const next = screen.getByRole('region', { name: 'Próxima pieza' });
    expect(within(next).getByRole('link', { name: 'Scope features from the decision they support.' })).toBeInTheDocument();
  });

  it('moves the window through ?desde= and comes back to today', async () => {
    const server = fakeServer({ 'GET /api/v1/editorial/calendar': { body: calendar({}) } });
    const user = userEvent.setup();
    renderAt('/contenido', routes);
    await user.click(await screen.findByRole('button', { name: 'Siguientes →' }));
    expect(screen.getByTestId('location')).toHaveTextContent('/contenido?desde=2026-11-20');
    await waitFor(() => expect(server.requests.at(-1)?.search.get('desde')).toBe('2026-11-20'));
    await user.click(screen.getByRole('button', { name: 'Hoy' }));
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/contenido$/);
  });

  it('prepares the next piece after an explicit confirmation and shows the 409 detail', async () => {
    document.cookie = 'csrftoken=tok';
    let conflict = false;
    const server = fakeServer({
      'GET /api/v1/editorial/calendar': { body: calendar({}) },
      'POST /api/v1/editorial/plan': () =>
        conflict
          ? { status: 409, body: { detail: 'Conecta LinkedIn (API oficial) antes de planificar piezas.' } }
          : { status: 202, body: { slot_date: '2026-11-08', job: { id: 'job-1', status: 'queued' } } },
    });
    const user = userEvent.setup();
    renderAt('/contenido', routes);
    expect(await screen.findByText(/No hay ninguna pieza en preparación ni programada/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Preparar la siguiente pieza' }));
    const dialog = screen.getByRole('dialog', { name: 'Preparar la siguiente pieza' });
    expect(dialog).toHaveTextContent('Tiene coste');
    expect(server.find('POST', '/api/v1/editorial/plan')).toHaveLength(0);
    await user.click(within(dialog).getByRole('button', { name: 'Preparar' }));
    expect(await screen.findByText(/Preparación en cola para el domingo, 8 de noviembre/)).toBeInTheDocument();
    const [plan] = server.find('POST', '/api/v1/editorial/plan');
    expect(plan?.headers['x-csrftoken']).toBe('tok');
    const body = plan?.body as { request_id?: string };
    if (body.request_id !== undefined) expect(body.request_id).toMatch(/^[0-9a-f-]{36}$/);

    conflict = true;
    await user.click(screen.getByRole('button', { name: 'Preparar la siguiente pieza' }));
    const again = screen.getByRole('dialog');
    await user.click(within(again).getByRole('button', { name: 'Preparar' }));
    expect(await within(again).findByRole('alert')).toHaveTextContent('Conecta LinkedIn (API oficial) antes de planificar piezas.');
  });
});

describe('Contenido · detalle de una pieza', () => {
  it('shows brief, variants A and B, the readers panel, the selection, the verifier and the final text', async () => {
    fakeServer({ 'GET /api/v1/editorial/pieces/piece-1': { body: detail() } });
    renderAt('/contenido/piece-1', routes);

    expect(await screen.findByRole('heading', { name: 'Pieza del sábado, 7 de noviembre' })).toBeInTheDocument();
    expect(screen.getByText('Programada')).toBeInTheDocument();
    expect(screen.getByText(/Aprobada por la política autónoma: saldrá sola a esa hora/)).toBeInTheDocument();

    const brief = screen.getByRole('region', { name: 'Brief' });
    for (const text of ['Lector comprador', 'Personal · startups', 'Del negocio al producto', 'Scope features from the decision they support.', 'Solo texto', 'Inventing cases']) {
      expect(within(brief).getByText(text)).toBeInTheDocument();
    }
    expect(within(brief).getByRole('link', { name: 'LI-05-M001-K02' })).toHaveAttribute('href', '/conocimiento?unidad=LI-05-M001-K02');

    const variants = screen.getByRole('region', { name: 'Variantes A y B' });
    expect(within(variants).getByText('Variant A text about decisions.')).toHaveAttribute('lang', 'en');
    expect(within(variants).getByText('Variant B text about a founder objection.')).toBeInTheDocument();
    expect(within(variants).getByText('Elegida').closest('h3')).toHaveTextContent('Variante A');

    const panel = screen.getByRole('region', { name: 'Panel de lectores' });
    expect(within(panel).getByRole('heading', { name: 'Lector comprador' })).toBeInTheDocument();
    expect(within(panel).getByRole('heading', { name: 'Lector par profesional' })).toBeInTheDocument();
    expect(within(panel).getByText('Names the founder doubt')).toBeInTheDocument();
    expect(within(panel).getByText('Hook promises too much').closest('li')).toHaveTextContent('Material');
    expect(within(panel).getAllByText('Could use an example').length).toBeGreaterThan(0);

    const selection = screen.getByRole('region', { name: 'Selección' });
    expect(within(selection).getByText('Variante A')).toBeInTheDocument();
    expect(within(selection).getByText('Clearer hook.')).toBeInTheDocument();
    expect(within(selection).getByText('Could use an example')).toBeInTheDocument();

    const verifier = screen.getByRole('region', { name: 'Veredicto del verificador' });
    expect(within(verifier).getByText('Lista para publicar')).toBeInTheDocument();
    expect(within(verifier).getByText('Slightly generic opening.')).toBeInTheDocument();
    expect(within(verifier).getByText(/bbbbbbbbbbbb…/)).toBeInTheDocument();

    const final = screen.getByRole('region', { name: 'Texto final' });
    expect(within(final).getByText(/Which decision is your product helping/)).toHaveAttribute('lang', 'en');
    expect(screen.queryByText('Impresiones')).not.toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Fuentes y coste' })).toHaveTextContent('USD 0,03');
  });

  it('shows the blocking reasons of a blocked piece and offers no veto', async () => {
    fakeServer({
      'GET /api/v1/editorial/pieces/piece-1': {
        body: detail({
          state: 'blocked',
          status: 'blocked',
          action: null,
          note: 'Hallazgo material (invented_experience): Not in public_facts.',
          selection: {},
          verification: {
            verdict: 'blocked',
            model_verdict: 'ready_for_execution',
            blocking_reasons: ['Experiencia en primera persona sin hechos públicos confirmados'],
            findings: [{ issue: 'invented_experience', severity: 'material', quote: 'Last year I built an AI pipeline', detail: 'Not in public_facts.' }],
            checked_claims: [{ text: 'Cut review costs by 40%', status: 'unsupported', ref: '' }],
            text_sha256: HASH,
          },
        }),
      },
    });
    renderAt('/contenido/piece-1', routes);
    const verifier = await screen.findByRole('region', { name: 'Veredicto del verificador' });
    expect(within(verifier).getByText('Bloqueada')).toBeInTheDocument();
    expect(within(verifier).getByText('MOTIVOS DEL BLOQUEO')).toBeInTheDocument();
    expect(within(verifier).getByText('Experiencia en primera persona sin hechos públicos confirmados')).toBeInTheDocument();
    expect(within(verifier).getByText('Experiencia inventada')).toBeInTheDocument();
    expect(within(verifier).getByText('Last year I built an AI pipeline')).toBeInTheDocument();
    expect(within(verifier).getByText(/las guardas deterministas bloquean la pieza/)).toBeInTheDocument();
    expect(within(verifier).getByText('Sin respaldo')).toBeInTheDocument();
    expect(screen.getByText('Bloqueada por el verificador')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Vetar' })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Selección' })).not.toBeInTheDocument();
  });

  it('shows the published post and its impressions when they exist', async () => {
    fakeServer({
      'GET /api/v1/editorial/pieces/piece-1': {
        body: detail({
          status: 'published',
          action: { id: 'act-piece-1', state: 'confirmed', payload_hash: HASH },
          external_url: 'https://www.linkedin.com/feed/update/urn:li:share:7400000000000000001/',
          metrics: { impressions: 321, source: 'unipile' },
        }),
      },
    });
    renderAt('/contenido/piece-1', routes);
    expect(await screen.findByRole('link', { name: /Ver el post publicado en LinkedIn/ })).toHaveAttribute(
      'href',
      'https://www.linkedin.com/feed/update/urn:li:share:7400000000000000001/',
    );
    expect(screen.getByText('Impresiones').nextElementSibling).toHaveTextContent('321');
    expect(screen.queryByRole('button', { name: 'Vetar' })).not.toBeInTheDocument();
  });

  it('vetoes a piece that has not been published, through its action', async () => {
    document.cookie = 'csrftoken=tok';
    let vetoed = false;
    const server = fakeServer({
      'GET /api/v1/editorial/pieces/piece-1': () => ({
        body: vetoed ? detail({ status: 'vetoed', action: { id: 'act-piece-1', state: 'rejected', payload_hash: HASH } }) : detail(),
      }),
      'POST /api/v1/operador/actions/act-piece-1/reject': () => {
        vetoed = true;
        return { body: { id: 'act-piece-1', state: 'rejected' } };
      },
    });
    const user = userEvent.setup();
    renderAt('/contenido/piece-1', routes);

    await user.click(await screen.findByRole('button', { name: 'Vetar' }));
    const dialog = screen.getByRole('dialog', { name: 'Vetar la pieza' });
    expect(dialog).toHaveTextContent('ese día quedará sin publicación');
    const confirm = within(dialog).getByRole('button', { name: 'Vetar' });
    expect(confirm).toBeDisabled();
    await user.type(within(dialog).getByLabelText('Nota'), 'No me representa');
    await user.click(confirm);

    expect(await screen.findByText('Vetada')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Vetar' })).not.toBeInTheDocument();
    const [reject] = server.find('POST', '/api/v1/operador/actions/act-piece-1/reject');
    expect(reject?.body).toEqual({ note: 'No me representa' });
    expect(reject?.headers['x-csrftoken']).toBe('tok');
  });

  it('explains a piece still waiting for the policy and links to its approval', async () => {
    fakeServer({
      'GET /api/v1/editorial/pieces/piece-1': { body: detail({ status: 'awaiting_approval', action: { id: 'act-piece-1', state: 'proposed', payload_hash: HASH } }) },
    });
    renderAt('/contenido/piece-1', routes);
    expect(await screen.findByText('Pendiente de aprobación')).toBeInTheDocument();
    expect(screen.getByText(/Espera a la política autónoma/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Vetar' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Aprobar desde Acciones' })).toHaveAttribute('href', '/acciones?capacidad=publicaciones&state=proposed');
  });

  it('opens push links to /editorial/<id> on the piece', async () => {
    fakeServer({ 'GET /api/v1/editorial/pieces/piece-1': { body: detail() } });
    renderAt('/editorial/piece-1', routes);
    expect(await screen.findByRole('heading', { name: 'Pieza del sábado, 7 de noviembre' })).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/contenido/piece-1');
  });
});
