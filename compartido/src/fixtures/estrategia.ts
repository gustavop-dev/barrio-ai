// La semana GASP (GET /api/v1/estrategia/semana): synthetic data, never real content.
import { GASP_LABEL, type GaspType, type PlanDay, type WeekPlan } from '../api/estrategia';

export function planDay(date: string, type: GaspType, overrides: Partial<PlanDay> = {}): PlanDay {
  return {
    date,
    type,
    label: GASP_LABEL[type],
    type_reason: 'Estructura de la semana',
    idea: null,
    reason: null,
    reader_need: null,
    audience_evidence: null,
    evidence_ok: false,
    pillar: null,
    format: null,
    state: 'planned',
    owner_edited: false,
    editable: true,
    piece_id: null,
    ...overrides,
  };
}

/** The week of 9/11/2026, planned: Monday backed by a buyer's question, Thursday without an audience signal. */
export function semanaFixture(overrides: Partial<WeekPlan> = {}): WeekPlan {
  const types: GaspType[] = ['G', 'A', 'G', 'A', 'S', 'P', 'G'];
  const days = types.map((type, index) => planDay(`2026-11-${String(9 + index).padStart(2, '0')}`, type));
  days[0] = {
    ...days[0]!,
    idea: 'What an MVP really needs on day one',
    reader_need: 'Decidir el alcance de su MVP esta semana.',
    audience_evidence: { kind: 'owner_capture', ref: 'cap-9', note: 'Un comprador preguntó si necesita app móvil desde el día uno.' },
    evidence_ok: true,
  };
  days[3] = { ...days[3]!, idea: 'A checklist to scope a pilot', reader_need: 'Saber qué probar primero.', format: 'carrusel' };
  return {
    week_start: '2026-11-09',
    week_end: '2026-11-15',
    state: 'planeada',
    state_label: 'Planeada',
    summary: 'Una semana para founders que dudan del alcance de su MVP.',
    warnings: ['1 día(s) sin señal de la audiencia que respalde la idea: el director la busca ese día.'],
    days,
    kept_ideas: [],
    month_share: {
      G: { posts: 10, pct: 35.7, target_pct: 40 },
      A: { posts: 8, pct: 28.6, target_pct: 30 },
      S: { posts: 6, pct: 21.4, target_pct: 20 },
      P: { posts: 4, pct: 14.3, target_pct: 10 },
    },
    cost_usd: 0.21,
    regenerate: { available: true, pending: false, estimated_usd: 0.2, max_usd: 0.47 },
    enabled: true,
    ...overrides,
  };
}
