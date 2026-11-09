import type { TurnoCard } from '../api/types';
import type { ExperimentPlan } from '../api/referentes';
export const MONTHLY_CARD: TurnoCard = {
  id: 'referent_change:change-1', type: 'referente', critical: false, tone: 'info', agent: 'investigador_lider', agent_label: 'Investigador líder',
  title: 'sale Alba Variable · entra Nora Investigación', body: 'Si no respondes, se aplicará al terminar el día 5 (America/Bogota).',
  deadline: '2026-11-06T00:00:00-05:00', created_at: '2026-11-01T09:00:00-05:00',
  actions: [{ label: 'Aprobar sustitución', endpoint: '/api/v1/referentes/cambios/change-1/decidir', body: { version: 3, decision: 'approve' }, primary: true }],
  referent_change: { id: 'change-1', account: 'account-1', version: 3, state: 'pending', can_decide: true, conflict: '', endpoint: '/api/v1/referentes/cambios/change-1/decidir',
    proposal: { kind: 'swap', outgoing: 'variable-1', reason: 'Mejor encaje observado', evidence: ['source-1'], incoming: {
      identifier: 'nora-test', display_name: 'Nora Investigación', profile_url: 'https://www.linkedin.com/in/nora-test/',
      niche: 'Producto', audience: 'Founders', contribution: 'Entrega de software', top_voice: false, sources: ['source-1'] } },
    outgoing: { id: 'variable-1', display_name: 'Alba Variable', profile_url: 'https://www.linkedin.com/in/alba-test/' },
    sources: [{ id: 'source-1', url: 'https://example.org/evidence', title: 'Fuente pública', retrieved_at: '2026-10-31T12:00:00Z' }],
    evidence: { coverage: { observed: 12, classified: 8, fit: 5, fit_pct: 62.5 } }, limitations: ['Muestra parcial; sin causalidad.'],
    occupancy: { before: 15, after: 15, main: 5, variables: 10 } },
};
export const EXPERIMENT_PLAN: ExperimentPlan = { base_days: 14, focus_days: 28, followup_days: 7, comments_week: 2,
  min_classified: 10, min_coverage: .7, min_fit_week: 2, min_exposure: 4, control_referent: '', confounders: 'Otras acciones de red',
  hypothesis: 'Atraer personas con encaje', audience: 'Founders', comparison: 'Frente a la base', fit_criterion: 'Necesidad de software',
  positioning_version: 'v1', orientation_version: 'o1', metric: 'Personas únicas con encaje', denominator: 'Personas observadas',
  stop_rule: 'Pausa o cambio material detienen el foco', budget: 'Dentro de BAR-15', limitations: 'Sin causalidad' };
