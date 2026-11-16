// Monthly review sample data (revision_mensual.py `overview`, `payload`, `change_payload` and `cards`), with invented
// figures and texts. Used by the app's Resultados and Tu turno tests.
import type { MonthlyReview, MonthlyReviewGenerate, MonthlyReviews, StrategyChange, TurnoCard } from '../api/types';
import { cardFixture, hoursFromNow } from './turno';

const REVISION = '/api/v1/resultados/revision-mensual';

export function strategyChangeFixture(overrides: Partial<StrategyChange> = {}): StrategyChange {
  const id = overrides.id ?? 'ch-1';
  const base = `${REVISION}/cambios/${id}`;
  return {
    id,
    review_id: 'rv-10',
    position: 0,
    title: 'Más posts de caso práctico',
    proposal: 'Publica al menos un caso práctico por semana, con el problema del cliente en la primera línea.',
    reason: 'Los dos casos prácticos del mes tuvieron el doble de impresiones a las 72 h que el resto.',
    evidence: [
      {
        cifra: 'por_tipo.caso.mediana_impresiones_72h: 1180',
        comparado_con: 'metricas.mediana_impresiones_72h.mes: 590',
        refs: ['pz-21'],
      },
    ],
    expected: 'Que la mediana de impresiones a las 72 h suba el mes que viene.',
    metric: 'mediana_impresiones_72h',
    metric_label: 'Mediana de impresiones de los posts a las 72 h',
    baseline: { metrica: 'mediana_impresiones_72h', etiqueta: 'Mediana de impresiones de los posts a las 72 h', valor: 590, mes: '2026-10-01', desde: '2026-10-01', hasta: '2026-10-31' },
    state: 'propuesto',
    state_label: 'Propuesto',
    final_text: null,
    decided_by: null,
    decided_at: null,
    decision_note: '',
    reverted_at: null,
    outcome: null,
    can_decide: true,
    can_revert: false,
    endpoints: { approve: `${base}/aprobar`, edit: `${base}/editar`, reject: `${base}/rechazar`, revert: `${base}/revertir` },
    ...overrides,
  };
}

export function monthlyReviewFixture(overrides: Partial<MonthlyReview> = {}): MonthlyReview {
  const changes = overrides.changes ?? [strategyChangeFixture()];
  return {
    id: 'rv-10',
    month_start: '2026-10-01',
    month_end: '2026-10-31',
    label: 'Revisión de octubre de 2026',
    state: 'visto',
    state_label: 'Vista',
    partial: false,
    titular: 'Octubre: 9 posts y 590 impresiones de mediana a las 72 h, con los casos prácticos por delante',
    metodo: 'Comparación del mes con el anterior con pocos datos: señala pistas, no es una prueba estadística.',
    lo_que_paso: [{ texto: 'Se publicaron 9 posts, 2 más que en septiembre.', cifra: 'metricas.publicaciones.mes: 9', course_citations: [] }],
    lo_que_funciono: [{ texto: 'Los casos prácticos llegaron a 1.180 impresiones de mediana.', cifra: 'por_tipo.caso.mediana_impresiones_72h: 1180', course_citations: [] }],
    lo_que_no: [{ texto: 'Solo 3 de 12 invitaciones resueltas acabaron en conexión.', cifra: 'red.aceptacion.conectadas: 3', course_citations: [] }],
    no_concluyente: ['Con 2 posts de opinión no se puede decir si funcionan peor.'],
    cambios_previos: [
      { id: 'ch-0', titulo: 'Responder antes a los comentarios', veredicto: 'se_conserva', texto: 'La tasa de respuesta pasó de 20 a 31.', cifra: 'metricas.tasa_respuesta_comentarios.mes: 31' },
      { id: 'ch-00', titulo: 'Menos posts de opinión', veredicto: 'empeoro', texto: 'La interacción bajó de 2,4 a 1,9.', cifra: 'metricas.mediana_interaccion_pct_72h.mes: 1.9' },
      { id: 'ch-000', titulo: 'Invitar después de comentar', veredicto: 'sin_dato', texto: 'El analista no lo valoró con cifras de los datos del mes.', cifra: '' },
    ],
    advertencias: ['Se quitaron 2 frases con cifras que no están en los datos del mes.'],
    avisos: ['La semana del 2026-10-26 no tiene posts medidos a las 72 h.'],
    semanas_con_datos: 4,
    semanas_del_mes: 4,
    validacion: { ok: false, descartado: [] },
    model: 'claude-opus-5-5',
    cost_usd: 0.19,
    created_at: '2026-11-02T13:31:00Z',
    pending: changes.filter((change) => change.can_decide).length,
    ...overrides,
    changes,
  };
}

export function monthlyGenerateFixture(overrides: Partial<MonthlyReviewGenerate> = {}): MonthlyReviewGenerate {
  return {
    month_start: '2026-10-01',
    month_end: '2026-10-31',
    label: 'Revisión de octubre de 2026',
    available: false,
    reason: 'El mes pasado ya tiene su revisión.',
    pending: false,
    last_error: null,
    automatic: true,
    automatic_at: '2026-11-02T13:30:00Z',
    estimated_usd: 0.19,
    max_usd: 0.47,
    ...overrides,
  };
}

export function monthlyReviewsFixture(overrides: Partial<MonthlyReviews> = {}): MonthlyReviews {
  const latest = overrides.latest === undefined ? monthlyReviewFixture() : overrides.latest;
  return { latest, pending: latest?.pending ?? 0, previous: [], generate: monthlyGenerateFixture(), ...overrides };
}

/** The Tu turno card of a proposed change (revision_mensual.cards): its four actions, the change and its review. */
export function strategyCardFixture(change: StrategyChange = strategyChangeFixture(), overrides: Partial<TurnoCard> = {}): TurnoCard {
  return cardFixture({
    id: `strategy_change:${change.id}`,
    type: 'cambio_estrategia',
    tone: 'info',
    priority: 'cuando_puedas',
    state: 'nueva',
    agent: 'analista_barrio_resultados',
    agent_label: 'Analista del barrio',
    title: `Cambio de estrategia: ${change.title}`,
    body: change.proposal,
    deadline: null,
    created_at: hoursFromNow(-30),
    actions: [
      { label: 'Aprobar', endpoint: change.endpoints.approve, primary: true },
      { label: 'Editar y aprobar', endpoint: change.endpoints.edit ?? change.endpoints.approve, editable: { field: 'text', value: change.proposal } },
      { label: 'Rechazar', endpoint: change.endpoints.reject, note_optional: true },
      { label: 'Ver la revisión', href: '/resultados#revision-mensual' },
    ],
    strategy_change: change,
    review: { id: 'rv-10', month_start: '2026-10-01', label: 'Revisión de octubre de 2026', partial: true, titular: 'Octubre con los casos prácticos por delante' },
    ...overrides,
  });
}
