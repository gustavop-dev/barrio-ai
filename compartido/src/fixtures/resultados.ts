// GET /api/v1/resultados shaped like resultados.py (CONTRATO-API «Resultados»). Invented data only.
import type { Kpi, Resultados } from '../api/types';

export function kpi(value: number | null, extra: Partial<Kpi> = {}): Kpi {
  const previous = extra.previous ?? (value === null ? null : value - 1);
  const comparable = extra.comparable ?? (value !== null && previous !== null);
  return {
    value,
    previous,
    delta: comparable && value !== null && previous !== null ? value - previous : null,
    delta_pct: comparable && value !== null && previous ? Math.round(((value - previous) / previous) * 1000) / 10 : null,
    comparable,
    series: null,
    definition: 'Definición de prueba.',
    formula: null,
    unavailable_reason: value === null ? 'Sin datos en este periodo.' : null,
    ...extra,
  };
}

export function negocioOn(): Resultados['negocio'] {
  return {
    disponible: true,
    motivo: null,
    conversaciones: kpi(null, { unavailable_reason: 'Disponible cuando conectemos el inbox.', definition: 'Conversaciones con personas que encajan abiertas en el periodo.' }),
    abiertas: kpi(2, { definition: 'Oportunidades abiertas al final del periodo (sin acuerdo ni cierre).' }),
    reuniones: kpi(1),
    propuestas: kpi(0, { previous: 0 }),
    acuerdos: kpi(0, { previous: 0 }),
    inbound: kpi(2),
    embudo: {
      steps: [
        { stage: 'conversacion', label: 'Conversación', count: 4, conversion_pct: null },
        { stage: 'necesidad', label: 'Necesidad identificada', count: 3, conversion_pct: 75 },
        { stage: 'cualificada', label: 'Cualificada', count: 2, conversion_pct: 66.67 },
        { stage: 'reunion', label: 'Reunión', count: 1, conversion_pct: 50 },
        { stage: 'propuesta', label: 'Propuesta', count: 0, conversion_pct: 0 },
        { stage: 'acuerdo', label: 'Acuerdo', count: 0, conversion_pct: null },
      ],
      sin_acuerdo: 1,
      definition: 'Oportunidades vivas en el periodo según la etapa más lejana que alcanzaron.',
    },
    modalidades: {
      counts: { personal_startups: 1, projectapp: 1, por_clasificar: 1 },
      pct: { personal_startups: 50, projectapp: 50 },
      objetivo: { personal_startups: 60, projectapp: 40 },
      definition: 'Oportunidades abiertas o ganadas por modalidad frente al objetivo 60/40.',
    },
    activas: [
      {
        id: 'o-1',
        person: 'Lucía Ficticia',
        contact_id: 'c-1',
        company: 'Huerta Labs',
        modality: 'projectapp',
        stage: 'necesidad',
        stage_label: 'Necesidad identificada',
        next_action: 'Enviar la propuesta de piloto',
        next_action_at: '2026-11-12T17:00:00Z',
      },
      {
        id: 'o-2',
        person: 'Mario Externo',
        contact_id: null,
        company: 'Cosecha Data',
        modality: 'personal_startups',
        stage: 'conversacion',
        stage_label: 'Conversación',
        next_action: '',
        next_action_at: null,
      },
    ],
  } as unknown as Resultados['negocio'];
}

export function resultadosFixture(overrides: Partial<Resultados> = {}): Resultados {
  return {
    periodo: { desde: '2026-10-11', hasta: '2026-11-07', dias: 28, datos_hasta: '2026-11-07T19:20:00Z', anterior: { desde: '2026-09-13', hasta: '2026-10-10' } },
    modalidad: 'todo',
    zona_horaria: 'America/Bogota',
    negocio: {
      disponible: false,
      motivo: 'Mediremos oportunidades cuando registres la primera o conectemos el inbox',
      inbound: kpi(2, { definition: 'Personas que encajan y te invitaron sin que las buscáramos.' }),
    },
    audiencia: {
      followers: kpi(null, { unavailable_reason: 'Sin captura de audiencia en este periodo.' }),
      connections: kpi(812, { previous: 793 }),
      profile_views: kpi(null, { unavailable_reason: 'LinkedIn no entregó visitas al perfil en este periodo.' }),
      new_fit_connections: kpi(7, { previous: 4 }),
      roles: {
        items: [
          { role: 'par', value: 2 },
          { role: 'comprador', value: 3 },
          { role: 'aliado', value: 0 },
        ],
        definition: 'Rol del barrio de las conexiones nuevas que encajan.',
        unavailable_reason: null,
      },
      acceptance_rate: kpi(41, { previous: 45, formula: 'conectados / (conectados + cerrados) × 100' }),
      funnel: {
        stages: { candidate: 38, fit: 21, followed: 15, invited: 9, connected: 7, discarded: 6, closed: 2, incoming: 1 },
        order: ['candidate', 'fit', 'followed', 'invited', 'connected'],
        aside: ['discarded', 'closed', 'incoming'],
        definition: 'Personas del barrio por etapa hoy.',
      },
      recurrent_people: kpi(null, { unavailable_reason: 'Aún no medimos las interacciones repetidas por persona.', top: null }),
    },
    contenido: {
      kpis: {
        median_impressions: kpi(1520, { previous: 1357, cut: '7d' }),
        engagement_pct: kpi(3.2, { previous: 2.8, formula: '(reacciones + comentarios + republicaciones) / impresiones × 100' }),
        substantive_comments: kpi(null, { unavailable_reason: 'Aún no se leyeron los comentarios de los posts del periodo.' }),
        consistency: kpi(85.71, { previous: 89.29, numerator: 24, denominator: 28 }),
      },
      chart: {
        bars: [
          { piece_id: 'p-1', date: '2026-11-02', impressions: 1840, cut: '7d', fallback: false },
          { piece_id: 'p-2', date: '2026-11-05', impressions: 960, cut: '24h', fallback: true },
          { piece_id: 'p-3', date: '2026-11-07', impressions: null, cut: null, fallback: false },
        ],
        median_previous_4_weeks: { '7d': 1250, '24h': 800 },
        definition: 'Impresiones de cada post a los 7 días.',
      },
      best_post: { piece_id: 'p-1', first_line: 'AI features should start from a workflow, not a model.', date: '2026-11-02', pillar: 'applied_ai', impressions: 1840, engagement_pct: 3.1, cut: '7d' },
      by_pillar: {
        cut: '7d',
        formula: '(reacciones + comentarios + republicaciones) / impresiones × 100',
        items: [
          { pillar: 'business_to_product', value: 2.9, posts: 2 },
          { pillar: 'applied_ai', value: 3.4, posts: 1 },
          { pillar: 'architecture_delivery', value: null, posts: 0 },
        ],
      },
      posts: [
        {
          piece_id: 'p-1',
          date: '2026-11-02',
          published_at: '2026-11-02T13:00:00Z',
          first_line: 'AI features should start from a workflow, not a model.',
          pillar: 'applied_ai',
          url: 'https://www.linkedin.com/feed/update/urn:li:activity:1',
          impressions_24h: 1210,
          impressions_7d: 1840,
          reactions: 38,
          comments: 12,
          reposts: 3,
          engagement_pct: 2.9,
          cut: '7d',
          commenters_by_role: { comprador: 3, par: 4 },
        },
        {
          piece_id: 'p-2',
          date: '2026-11-05',
          published_at: '2026-11-05T13:00:00Z',
          first_line: 'A monolith is fine until your team says otherwise.',
          pillar: 'architecture_delivery',
          url: null,
          impressions_24h: 960,
          impressions_7d: null,
          reactions: 24,
          comments: 7,
          reposts: 1,
          engagement_pct: 3.3,
          cut: '24h',
          commenters_by_role: { par: 2, lider: 1 },
        },
        {
          piece_id: 'p-3',
          date: '2026-11-07',
          published_at: '2026-11-07T13:00:00Z',
          first_line: 'Scope features from the decision they support.',
          pillar: 'business_to_product',
          url: null,
          impressions_24h: null,
          impressions_7d: null,
          reactions: null,
          comments: null,
          reposts: null,
          engagement_pct: null,
          cut: null,
          commenters_by_role: null,
        },
      ],
    },
    equipo: {
      comments_published: kpi(24),
      comments_replied: kpi(null, { unavailable_reason: 'Aún no leemos las respuestas a tus comentarios.' }),
      follows: kpi(31),
      invites: kpi(12),
      accepts: kpi(5),
      pieces_published: kpi(24),
      pieces_blocked: kpi(1),
      pieces_vetoed: kpi(0),
      spend: {
        today: { general: { spent: 1.2, budget: 1 }, editorial: { spent: 1.5, budget: 3 }, network: { spent: 0.4, budget: 1 }, other: { spent: 0, budget: null } },
        month: { general: { spent: 20, budget: null }, total: { spent: 61.2, budget: 120 } },
        accumulated: { spent: 61.2, budget: 120 },
        other_providers: {},
        month_start: '2026-11-01',
        definition: 'Gasto de Anthropic por presupuesto diario.',
      },
    },
    ...overrides,
  };
}
