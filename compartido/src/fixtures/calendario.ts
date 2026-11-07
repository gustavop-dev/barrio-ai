// Sample data of the Calendario and piece detail screens (Calendario.dc.html, Pieza.dc.html), shaped as CONTRATO-API.
import type { PieceDetailFull } from '../api/calendario';
import type { Actividad, ActivityItem, Calendario, CalendarEvent, CalendarioDay, Overview, PieceDetail, TuTurno, UpcomingPiece } from '../api/types';

export const TODAY = '2026-11-07';
/** 10:00 in Bogotá on TODAY. */
export const NOW = new Date('2026-11-07T15:00:00Z');
const HASH = 'a'.repeat(64);

/** The shell's own reads (Tu turno counter, pause banner), without importing the whole app (test/app.tsx). */
export function shellTurno(): TuTurno {
  return {
    count: 0,
    critical: false,
    counts: { avisos: 0, preguntas: 0, tareas: 0 },
    top: null,
    alerts: [],
    questions: [],
    later: [],
    tasks: { perfil: [], conversaciones: [] },
    recent: [],
    summary: { done_today: { posts: 0, comments: 0, reactions: 0, follows: 0, invites: 0, accepts: 0 }, next_piece: null },
  };
}

export function shellOverview(openNow = false): Overview {
  return {
    autopilot: { enabled: true, policy_version: 'autonomia-v1' },
    control: { paused: false, reason: '', source: 'none', updated_at: null, updated_by: null },
    window: { start: '07:00', end: '21:00', timezone: 'America/Bogota', open_now: openNow, min_spacing_seconds: 1200 },
    accounts: [],
    today: { proposals: {}, llm_spent_usd: '0.10', llm_daily_cap_usd: '1', drafts: 0, drafts_daily_cap: 6 },
    counts: { referents: 0, posts: 0, uncertain: 0 },
  };
}

const zero = { comments: 0, reactions: 0, follows: 0, invites: 0, accepts: 0, connections_fit: 0 };

export function event(overrides: Partial<CalendarEvent> & Pick<CalendarEvent, 'kind' | 'layer'>): CalendarEvent {
  return {
    id: `${overrides.kind}:x:${Math.random().toString(36).slice(2, 8)}`,
    at: null,
    title: '',
    state: null,
    important: true,
    link: null,
    ...overrides,
  };
}

export function day(date: string, events: CalendarEvent[] = [], counts: Partial<CalendarioDay['counts']> = {}): CalendarioDay {
  return { date, counts: { ...zero, ...counts }, events };
}

/** Every day of [desde, hasta] (the backend always returns the whole range), with the given ones filled in. */
export function calendarioFixture(desde: string, hasta: string, filled: CalendarioDay[] = [], overrides: Partial<Calendario> = {}): Calendario {
  const byDate = new Map(filled.map((d) => [d.date, d]));
  const days: CalendarioDay[] = [];
  for (let current = new Date(`${desde}T00:00:00Z`); current.toISOString().slice(0, 10) <= hasta; current.setUTCDate(current.getUTCDate() + 1)) {
    const date = current.toISOString().slice(0, 10);
    days.push(byDate.get(date) ?? day(date));
  }
  return {
    timezone: 'America/Bogota',
    today: TODAY,
    lead_hours: 6,
    layers: { tuyo: true, publicaciones: true, red: true, conversaciones: 'parcial', sistema: true },
    days,
    ...overrides,
  };
}

/** The design's week: published pieces, a skipped day, a blocked piece, today and tomorrow's scheduled piece. */
export const WEEK_DAYS: CalendarioDay[] = [
  day(
    '2026-11-02',
    [
      event({ id: 'piece_published:p2:2026-11-02', layer: 'publicaciones', kind: 'piece_published', at: '2026-11-02T14:00:00Z', title: 'AI features should start from a workflow, not a model.', state: 'published', link: '/calendario/pieza/p2', impressions: 1840 }),
      event({ id: 'connection_fit:connections:2026-11-02', layer: 'red', kind: 'connection_fit', title: '3 conexiones nuevas', link: '/personas?etapa=connected', people: [{ id: 'c1', name: 'Ana', role: 'comprador' }, { id: 'c2', name: 'Bea', role: 'par' }, { id: 'c3', name: 'Ciro', role: 'divulgador' }] }),
    ],
    { comments: 5, reactions: 2, follows: 3, invites: 2, connections_fit: 3 },
  ),
  day(
    '2026-11-04',
    [event({ id: 'piece_skipped:p4:2026-11-04', layer: 'publicaciones', kind: 'piece_skipped', at: '2026-11-04T14:00:00Z', title: 'Publicación del día', state: 'skipped', link: '/calendario/pieza/p4', skip_reason: 'No había material genuino ese día.' })],
    { comments: 5, reactions: 4 },
  ),
  day(
    '2026-11-06',
    [
      event({ id: 'action_uncertain:prop-9:2026-11-06', layer: 'sistema', kind: 'action_uncertain', at: '2026-11-06T23:42:00Z', title: 'Comentario incierta', state: 'uncertain', link: '/tu-turno' }),
      event({ id: 'piece_blocked:p6:2026-11-06', layer: 'publicaciones', kind: 'piece_blocked', at: '2026-11-06T14:00:00Z', title: 'Most startups don’t need microservices.', state: 'blocked', link: '/calendario/pieza/p6' }),
    ],
    { comments: 6, reactions: 5, follows: 4, invites: 2 },
  ),
  day(
    TODAY,
    [
      event({ id: 'deadline:q1:2026-11-07', layer: 'tuyo', kind: 'deadline', at: '2026-11-07T22:00:00Z', title: 'Responde: ¿En qué idioma van tus textos públicos?', link: '/tu-turno', agent: 'director_editorial' } as Partial<CalendarEvent> & Pick<CalendarEvent, 'kind' | 'layer'>),
      event({ id: 'piece_published:p7:2026-11-07', layer: 'publicaciones', kind: 'piece_published', at: '2026-11-07T14:00:00Z', title: 'Scope features from the decision they support.', state: 'published', link: '/calendario/pieza/p7', impressions: null }),
      event({ id: 'opportunity:o1:2026-11-07', layer: 'conversaciones', kind: 'opportunity', at: '2026-11-07T15:12:00Z', title: 'Oportunidad con Lucía Ficticia: Necesidad identificada', link: '/personas/c9' }),
      event({ id: 'invitation_accepted:a1:2026-11-07', layer: 'red', kind: 'invitation_accepted', at: '2026-11-07T16:20:00Z', title: 'Aceptaste la invitación de Diego Supuesto', link: '/personas/c10' }),
      event({ id: 'invite_expected:expected:2026-11-07', layer: 'red', kind: 'invite_expected', title: '2 invitaciones previstas', important: false, estimate: true, people: [{ id: 'c11', name: 'Andrés Ejemplo', role: null }, { id: 'c12', name: 'Sofía Muestra', role: null }] }),
    ],
    { comments: 6, reactions: 3, follows: 4, invites: 2, connections_fit: 1 },
  ),
  day('2026-11-08', [
    event({ id: 'piece_scheduled:p8:2026-11-08', layer: 'publicaciones', kind: 'piece_scheduled', at: '2026-11-08T14:00:00Z', title: 'Turning a sales call into a product spec.', state: 'scheduled', link: '/calendario/pieza/p8' }),
  ]),
];

export function piece(overrides: Partial<PieceDetailFull> = {}): PieceDetailFull {
  const base: PieceDetail = {
    id: 'p7',
    slot_date: TODAY,
    scheduled_for: '2026-11-07T14:00:00Z',
    state: 'ready',
    status: 'published',
    stage: 'verificador',
    note: '',
    modality: 'personal_startups',
    pillar: 'business_to_product',
    primary_reader: 'lector_comprador',
    thesis: 'Scope features from the decision they support.',
    approach: 'LI-05-M001-K02',
    action: { id: 'act-7', state: 'confirmed', payload_hash: HASH },
    external_url: 'https://www.linkedin.com/feed/update/urn:li:share:7/',
    created_at: '2026-11-07T02:00:00Z',
    brief: {
      decision: 'write',
      primary_reader: 'lector_comprador',
      modality: 'personal_startups',
      pillar: 'business_to_product',
      thesis: 'Scope features from the decision they support.',
      approach: 'LI-05-M001-K02',
      format: 'text_only',
      reader_value: 'Una pregunta para acotar funciones.',
      evidence: [{ kind: 'general_knowledge', ref: '', note: 'Práctica de producto' }],
      success_criterion: 'Founders cuentan su decisión.',
      avoid: ['Inventar casos'],
      rationale: 'Encaja con el pilar.',
    },
    variants: {
      variant_a: { angle: 'Un caso concreto, contado como decisión.', text: 'Most feature requests arrive as a solution.\nAsk which decision it changes.', claims: [], uncertainties: [] },
      variant_b: { angle: 'La objeción.', text: 'Everyone wants AI everywhere.', claims: [], uncertainties: [] },
    },
    panel: {
      readers: [
        { reader: 'lector_comprador', variant_a: { strengths: ['Claro y útil'], objections: [] }, variant_b: { strengths: [], objections: [{ text: 'Genérico', severity: 'preference' }] } },
        { reader: 'lector_lider', variant_a: { strengths: [], objections: [{ text: 'Necesita una cifra propia', severity: 'missing_data' }] }, variant_b: {} },
      ],
      summary: 'A es más clara.',
    },
    selection: { decision: 'A', final_text: '', rationale: 'A cuenta un caso concreto.', resolved_objections: ['Se quitó una cifra'], kept_objections: ['Falta una métrica propia'] },
    verification: {
      verdict: 'ready_for_execution',
      model_verdict: 'ready_for_execution',
      blocking_reasons: [],
      findings: [{ issue: 'other', severity: 'minor', quote: 'two weeks', detail: 'Coincide con tu memoria.' }],
      checked_claims: [
        { text: 'a', status: 'supported_public_fact' },
        { text: 'b', status: 'opinion' },
        { text: 'c', status: 'unsupported' },
      ],
      summary: '',
      text_sha256: HASH,
    },
    final_text: 'Most feature requests arrive as a solution.\n\nBefore scoping, I ask which decision the feature should change.\nIf nobody can name it, the feature can wait.\nThat is the whole trick.',
    citations: ['LI-04-M005-K01', 'LI-06-M002-K09'],
    signals: [{ id: 's1', author: 'Elena Prueba', text: 'AI in onboarding works when it removes one step.' }],
    usage: [
      { stage: 'director', model: 'claude', estimated_usd: 0.08 },
      { stage: 'redactor', model: 'claude', estimated_usd: 0.07 },
      { stage: 'redactor', model: 'claude', estimated_usd: 0.07 },
      { stage: 'verificador', model: 'claude', estimated_usd: '0.04' },
    ],
    action_detail: null,
    metrics: { impressions: 1210, reactions: 31, comments: 9, reposts: 2, observed_at: '2026-11-07T14:30:00Z', source: 'unipile', share_url: null },
    snapshots: [],
    commenters: null,
  };
  return { ...base, team_comments: [], ...overrides };
}

export function upcomingPiece(overrides: Partial<UpcomingPiece> = {}): UpcomingPiece {
  return {
    piece_id: 'p8',
    slot_date: '2026-11-08',
    scheduled_for: '2026-11-08T14:00:00Z',
    status: 'scheduled',
    stage: 'verificador',
    thesis: 'Turning a sales call into a product spec.',
    excerpt: 'The best spec I wrote last month started as a sales call.\nNot the transcript: the three decisions the buyer kept circling.',
    pillar: 'business_to_product',
    modality: 'projectapp',
    primary_reader: 'lector_comprador',
    action: { id: 'act-8', state: 'approved' },
    vetoable: true,
    impressions: null,
    skip_reason: null,
    note: '',
    ...overrides,
  };
}

export function item(overrides: Partial<ActivityItem> = {}): ActivityItem {
  return {
    id: `i-${Math.random().toString(36).slice(2, 8)}`,
    capability: 'INT-03',
    label: 'Comentario',
    agent: 'relaciones_comunidad',
    state: 'confirmed',
    state_label: null,
    important: false,
    at: '2026-11-07T13:10:00Z',
    date: TODAY,
    text: 'Naming the decision first is underrated.',
    reaction: null,
    target: { kind: 'post', name: 'Elena Prueba', headline: '', url: 'https://www.linkedin.com/feed/update/urn:li:activity:1/', post_excerpt: 'How we scope features at Kanoa.' },
    url: 'https://www.linkedin.com/feed/update/urn:li:activity:1/',
    rationale: 'Aporta una pregunta concreta.',
    decided_by: 'politica',
    decision_note: '',
    execution_note: '',
    review: null,
    piece_id: null,
    ...overrides,
  };
}

export function actividadFixture(overrides: Partial<Actividad> = {}): Actividad {
  return {
    upcoming: {
      pieces: [upcomingPiece()],
      queued: [
        {
          ...item({ id: 'q-1', state: 'approved', target: { kind: 'post', name: 'Elena Prueba', post_excerpt: 'Post' }, at: '2026-11-07T12:00:00Z' }),
          expected_at: '2026-11-07T17:00:00Z',
        },
        {
          ...item({ id: 'q-2', capability: 'RED-02', label: 'Invitación sin nota', state: 'approved', target: { kind: 'person', name: 'Sofía Muestra', contact_id: 'c12' } }),
          expected_at: '2026-11-07T17:20:00Z',
        },
      ],
    },
    items: [
      item({ id: 'i-1' }),
      item({ id: 'i-2', capability: 'INT-02', label: 'Reacción', reaction: 'linkedin_like', text: null, target: { kind: 'post', name: 'Tomás Demo', post_excerpt: 'Shipping small.' }, at: '2026-11-07T13:25:00Z' }),
      item({ id: 'i-3', capability: 'RED-01', label: 'Seguimiento', text: null, target: { kind: 'person', name: 'Andrés Ejemplo', headline: 'Head of Product @ Kanoa', contact_id: 'c11', role: 'par' }, at: '2026-11-07T17:40:00Z' }),
      item({ id: 'i-4', state: 'uncertain', state_label: 'Incierta', important: true, target: { kind: 'post', name: 'Pablo Ficticio' }, at: '2026-11-06T23:42:00Z', date: '2026-11-06' }),
      item({ id: 'i-5', capability: 'CONT-09', label: 'Publicación', text: 'AI features should start from a workflow.\nSecond line.', target: { kind: 'own', name: 'Tu perfil' }, important: true, piece_id: 'p5', at: '2026-11-05T14:00:00Z', date: '2026-11-05' }),
    ],
    next_offset: null,
    ...overrides,
  };
}
