import type { TurnoCard } from '../api/types';
import type { ExperimentPlan } from '../api/referentes';
export const REFERENTS_SETUP_CARD: TurnoCard = {
  id: 'referents_setup:account-setup', type: 'aviso', priority: 'importante', state: 'nueva', critical: false, tone: 'warn',
  agent: 'investigador_lider', agent_label: 'Investigador líder', title: 'Identificar los cinco referentes main',
  body: 'Identificar los cinco main iniciales.', deadline: null, created_at: null,
  actions: [{ label: 'Gestionar protegidos', href: '/personas?pestana=referentes' }],
};
export const MONTHLY_CARD: TurnoCard = {
  id: 'referent_change:change-1', type: 'referente', priority: 'importante', state: 'nueva', critical: false, tone: 'warn', agent: 'investigador_lider', agent_label: 'Investigador líder',
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
/** An industry referent proposal (invented person and company): explicit decision only, with its criteria. */
export const INDUSTRY_CARD: TurnoCard = {
  ...MONTHLY_CARD, id: 'referent_change:change-2', title: 'Alta de industria: Lia Constructora',
  body: 'Vende MVPs a founders de EE. UU. y conversa con ellos. Requiere decisión explícita; esta versión no se aplicará por silencio.',
  deadline: '2026-11-28T09:00:00-05:00',
  actions: [{ label: 'Aprobar alta', endpoint: '/api/v1/referentes/cambios/change-2/decidir', body: { version: 1, decision: 'approve' }, primary: true }],
  referent_change: { ...MONTHLY_CARD.referent_change!, id: 'change-2', kind: 'industria', version: 1, endpoint: '/api/v1/referentes/cambios/change-2/decidir',
    outgoing: null, occupancy: { before: 6, after: 7, main: 5, variables: 1 },
    sources: [{ id: 'linkedin:lia-constructora-test', url: 'https://www.linkedin.com/in/lia-constructora-test/', title: 'Perfil público en LinkedIn (lectura del equipo)', retrieved_at: '2026-11-14T12:00:00Z' }],
    proposal: { kind: 'add', reason: 'Vende MVPs a founders de EE. UU. y conversa con ellos.', evidence: ['linkedin:lia-constructora-test'], incoming: {
      identifier: 'lia-constructora-test', display_name: 'Lia Constructora', profile_url: 'https://www.linkedin.com/in/lia-constructora-test/',
      niche: 'Estudio de producto', audience: 'Founders de startups en EE. UU.', contribution: 'Criterio de entrega', top_voice: false,
      sources: ['linkedin:lia-constructora-test'],
      industria: { rule: 'industria-v1', passed: true, slug: 'lia-constructora-test', company: 'Estudio Ejemplo', services: ['producto'], reasons: [],
        criteria: [
          { key: 'servicios', label: 'Vende lo mismo que Gustavo', status: 'cumple', status_label: 'Cumple', detail: 'Vende: producto.', required: true },
          { key: 'tamano', label: 'Es grande', status: 'cumple', status_label: 'Cumple', detail: '24.000 seguidores; mediana de 140 interacciones en 12 posts.', required: true },
          { key: 'autoridad', label: 'Autoridad verificable', status: 'cumple', status_label: 'Cumple', detail: '2 de 2 pruebas verificadas (casos, equipo).', required: true },
          { key: 'actividad', label: 'Publica seguido', status: 'cumple', status_label: 'Cumple', detail: '9 posts propios en 30 días; último hace 1 días.', required: true },
          { key: 'mercado_eeuu', label: 'Vende en EE. UU.', status: 'cumple', status_label: 'Cumple', detail: 'Perfil en EE. UU. (Austin, Texas).', required: true },
          { key: 'audiencia', label: 'Su audiencia es el barrio', status: 'sin_medir', status_label: 'Sin medir (no cuenta como cumplido)', detail: 'De 30 comentaristas de su mejor post, 2 ya estaban clasificados (hacen falta 5).', required: false },
        ],
        authority: [{ kind: 'casos', claim: 'Publica casos de MVPs entregados', sources: ['linkedin:lia-constructora-test'], verified: true },
          { kind: 'equipo', claim: 'Equipo de ingenieros propio', sources: ['linkedin:lia-constructora-test'], verified: true }],
        measures: { followers: 24000, median_interactions: 140, sample: 12, posts_30d: 9, days_since_last: 1, location: 'Austin, Texas', region: 'us', found_by: ['producto'] },
        audience: { commenters: 30, classified: 2, fit: 1, us: 1, fit_share: null } } } } },
};
export const EXPERIMENT_PLAN: ExperimentPlan = { base_days: 14, focus_days: 28, followup_days: 7, comments_week: 2,
  min_classified: 10, min_coverage: .7, min_fit_week: 2, min_exposure: 4, control_referent: '', confounders: 'Otras acciones de red',
  hypothesis: 'Atraer personas con encaje', audience: 'Founders', comparison: 'Frente a la base', fit_criterion: 'Necesidad de software',
  positioning_version: 'v1', orientation_version: 'o1', metric: 'Personas únicas con encaje', denominator: 'Personas observadas',
  stop_rule: 'Pausa o cambio material detienen el foco', budget: 'Dentro de BAR-15', limitations: 'Sin causalidad' };
export const EXPERIMENT_CARD: TurnoCard = {
  id: 'referent_experiment:experiment-1', type: 'experimento', priority: 'importante', state: 'nueva', critical: false, tone: 'warn',
  agent: 'investigador_lider', agent_label: 'Investigador líder', title: 'Experimento: Alba Variable', body: EXPERIMENT_PLAN.hypothesis,
  deadline: null, created_at: null,
  actions: [{ label: 'Aprobar experimento', endpoint: '/api/v1/referentes/experimentos/experiment-1/decidir',
    body: { version: 1, decision: 'approve' }, primary: true }],
  referent_experiment: { id: 'experiment-1', version: 1, state: 'proposed', plan: EXPERIMENT_PLAN,
    starts_at: '2026-11-10T09:00:00-05:00', focus_at: '2026-11-24T09:00:00-05:00',
    followup_at: '2026-12-22T09:00:00-05:00', ends_at: '2026-12-29T09:00:00-05:00', can_decide: true,
    endpoint: '/api/v1/referentes/experimentos/experiment-1/decidir', results: {} },
};
