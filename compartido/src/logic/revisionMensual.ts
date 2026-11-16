// Resultados › «Revisión mensual» (revision_mensual.py): the pure rules and texts the monthly review is drawn with —
// its lists, the partial line, the verdict and state chips, what a decided change says, «Generar ahora» and the texts
// of its Tu turno card. Shared by the native app (movil/src/resultados/RevisionMensual.tsx and movil/src/turno) and by
// the PWA when it shows the review.
import type {
  MonthlyReview,
  MonthlyReviewGenerate,
  MonthlyReviewItem,
  MonthlyReviewState,
  StrategyChange,
  StrategyChangeDecision,
  StrategyChangeState,
  StrategyOutcome,
  StrategyVerdict,
} from '../api/types';
import { dayOf, longDay } from './dates';
import { formatDateTime, formatNumber, formatTime, formatUsd } from './format';
import { OPERATOR_TZ } from './resultados';
import type { Tone } from './tone';

/** The anchor of /resultados#revision-mensual: the monthly_review notification and «Ver la revisión» in Tu turno. */
export const REVISION_ANCHOR = 'revision-mensual';
/** The Resultados tab (`?pestana=`) where the review lives. */
export const REVISION_TAB = 'mensual';
/** Characters an approved change may have (revision_mensual.MAX_PROPOSAL_CHARS). */
export const STRATEGY_CHANGE_MAX = 600;
/** Weeks with measured posts a review needs to compare the month (revision_mensual.FULL_WEEKS). */
export const FULL_WEEKS = 4;

const CHANGE_ENDPOINT = /^\/api\/v1\/resultados\/revision-mensual\/cambios\/[^/]+\/(aprobar|rechazar|revertir)$/;

export type ChangeVerb = 'aprobar' | 'rechazar' | 'revertir';

/** A decision endpoint of a strategy change (…/cambios/<id>/aprobar|rechazar|revertir), optionally of one verb. */
export function isChangeEndpoint(endpoint: string | null | undefined, verb?: ChangeVerb): boolean {
  const match = endpoint ? CHANGE_ENDPOINT.exec(endpoint) : null;
  return Boolean(match && (!verb || match[1] === verb));
}

// ---------------------------------------------------------------- the report

export type ReviewListKey = 'lo_que_paso' | 'lo_que_funciono' | 'lo_que_no';

/** The three lists of the report, with what each says when it is empty. */
export const REVIEW_LISTS: readonly { key: ReviewListKey; title: string; empty: string }[] = [
  { key: 'lo_que_paso', title: 'Lo que pasó', empty: 'Nada que contar con los datos del mes.' },
  { key: 'lo_que_funciono', title: 'Lo que funcionó', empty: 'Nada destacable con los datos del mes.' },
  { key: 'lo_que_no', title: 'Lo que no', empty: 'Nada que señalar con los datos del mes.' },
];

/** A list of the report, without entries that carry no text (a field missing in an older review is an empty list). */
export function reviewItems(review: MonthlyReview, key: ReviewListKey): MonthlyReviewItem[] {
  const items: unknown = review[key];
  return Array.isArray(items) ? items.filter((item): item is MonthlyReviewItem => Boolean(item && typeof item.texto === 'string' && item.texto)) : [];
}

/** A list of sentences of the report (`no_concluyente`, `advertencias`, `avisos`). */
export function reviewLines(lines: unknown): string[] {
  return Array.isArray(lines) ? lines.filter((line): line is string => typeof line === 'string' && line.trim() !== '') : [];
}

export const REVIEW_STATE_BADGE: Record<MonthlyReviewState, { tone: Tone; label: string } | null> = {
  nuevo: { tone: 'ok', label: 'Nueva' },
  visto: null,
};

/** «Parcial: solo 2 de 4 semanas tienen posts medidos y hacen falta 4 para comparar el mes.», or null. */
export function partialSentence(review: Pick<MonthlyReview, 'partial' | 'semanas_con_datos' | 'semanas_del_mes'>): string | null {
  if (!review.partial) return null;
  const withData = review.semanas_con_datos;
  const weeks = review.semanas_del_mes;
  const counted =
    typeof withData === 'number' && typeof weeks === 'number'
      ? `solo ${withData} de ${weeks} ${weeks === 1 ? 'semana tiene' : 'semanas tienen'} posts medidos`
      : 'menos de cuatro semanas tienen posts medidos';
  return `Parcial: ${counted} y hacen falta ${FULL_WEEKS} para comparar el mes. Léela como pistas, no como conclusiones.`;
}

/** What came of a change approved the month before. An unknown verdict reads as «Sin dato». */
export const VERDICT_BADGE: Record<StrategyVerdict, { tone: Tone; label: string }> = {
  se_conserva: { tone: 'ok', label: 'Se conserva' },
  sin_dato: { tone: 'muted', label: 'Sin dato' },
  empeoro: { tone: 'bad', label: 'Empeoró' },
};

export function verdictBadge(verdict: string | null | undefined): { tone: Tone; label: string } {
  return VERDICT_BADGE[verdict as StrategyVerdict] ?? VERDICT_BADGE.sin_dato;
}

/** «Escrita el 2 nov 2026, 8:31 · 0,19 USD». */
export function reviewFooter(review: Pick<MonthlyReview, 'created_at' | 'cost_usd'>): string {
  const cost = typeof review.cost_usd === 'number' ? ` · ${formatUsd(review.cost_usd)}` : '';
  return `Escrita el ${formatDateTime(review.created_at)}${cost}`;
}

/** «2 cambios de estrategia esperan tu decisión.», «Ningún cambio espera tu decisión.» or that it proposes none. */
export function pendingSentence(review: Pick<MonthlyReview, 'pending' | 'changes'>): string {
  const changes = Array.isArray(review.changes) ? review.changes : [];
  if (!changes.length) return 'Este mes no propone cambios de estrategia.';
  const pending = review.pending ?? changes.filter((change) => change.can_decide).length;
  if (pending === 1) return '1 cambio de estrategia espera tu decisión.';
  if (pending > 1) return `${pending} cambios de estrategia esperan tu decisión.`;
  return 'Ningún cambio espera tu decisión.';
}

/** The tab's name, with the changes that wait for him. */
export function revisionTabLabel(pending: number | null | undefined): string {
  return pending && pending > 0 ? `Revisión mensual · ${pending}` : 'Revisión mensual';
}

// ---------------------------------------------------------------- a change

/** The state chip of a change. */
export const CHANGE_STATE_BADGE: Record<StrategyChangeState, { tone: Tone; label: string }> = {
  propuesto: { tone: 'warn', label: 'Por decidir' },
  aprobado: { tone: 'ok', label: 'Aprobado' },
  rechazado: { tone: 'muted', label: 'Rechazado' },
  revertido: { tone: 'muted', label: 'Revertido' },
};

export function changeBadge(change: Pick<StrategyChange, 'state' | 'state_label'>): { tone: Tone; label: string } {
  return CHANGE_STATE_BADGE[change.state] ?? { tone: 'muted', label: change.state_label || String(change.state) };
}

/** The figures behind a change: each with what it is compared with. */
export function evidenceLines(change: Pick<StrategyChange, 'evidence'>): { cifra: string; comparado: string }[] {
  const evidence: unknown = change.evidence;
  if (!Array.isArray(evidence)) return [];
  return evidence
    .filter((item): item is { cifra?: unknown; comparado_con?: unknown } => Boolean(item) && typeof item === 'object')
    .map((item) => ({ cifra: typeof item.cifra === 'string' ? item.cifra : '', comparado: typeof item.comparado_con === 'string' ? item.comparado_con : '' }))
    .filter((line) => line.cifra || line.comparado);
}

/** «Mediana de impresiones de los posts a las 72 h». */
export function metricName(change: Pick<StrategyChange, 'metric' | 'metric_label'>): string {
  return change.metric_label || change.metric;
}

/** «Valor del mes revisado: 840», what the next review compares with; null without a value. */
export function baselineText(change: Pick<StrategyChange, 'baseline'>): string | null {
  const value = change.baseline?.valor;
  return typeof value === 'number' ? `Valor del mes revisado: ${formatNumber(value, 2)}` : null;
}

/** What a decided change says: when he approved, rejected or reverted it. Null while it waits. */
export function decidedSentence(change: Pick<StrategyChange, 'state' | 'decided_at' | 'reverted_at'>): string | null {
  const when = change.decided_at ? ` el ${formatDateTime(change.decided_at)}` : '';
  if (change.state === 'aprobado') return `Lo aprobaste${when}. Entró en la orientación del equipo con este texto:`;
  if (change.state === 'rechazado') return `Lo rechazaste${when}. El analista no lo volverá a proponer igual en los próximos tres meses.`;
  if (change.state === 'revertido') {
    return `Lo aprobaste${when} y lo revertiste${change.reverted_at ? ` el ${formatDateTime(change.reverted_at)}` : ''}: ya no está en la orientación.`;
  }
  return null;
}

/** «Antes: 840 · Después: 910» of an outcome, or null when neither figure exists. */
export function outcomeFigures(outcome: Pick<StrategyOutcome, 'antes' | 'despues'>): string | null {
  const before = typeof outcome.antes === 'number' ? formatNumber(outcome.antes, 2) : null;
  const after = typeof outcome.despues === 'number' ? formatNumber(outcome.despues, 2) : null;
  if (before === null && after === null) return null;
  return `Antes: ${before ?? '—'} · Después: ${after ?? '—'}`;
}

export const APPROVE_HINT = 'Si lo apruebas, entra en la orientación que leen todos los agentes. Puedes revertirlo desde Resultados.';
export const EDIT_CHANGE_TEXT = 'Lo que escribas entra tal cual en la orientación del equipo. Podrás revertirlo desde Resultados.';
export const REJECT_CHANGE_TEXT = 'No entra en la orientación. El analista no lo volverá a proponer igual en los próximos tres meses.';
export const REVERT_CHANGE_TEXT = 'Se quita de la orientación del equipo exactamente lo que añadió este cambio; lo demás no se toca.';
export const CHANGE_APPROVED = 'Cambio aprobado. El equipo lo usa desde su próxima tarea.';
export const CHANGE_REJECTED = 'Cambio rechazado';

/** The toast after a decision; a revert that did not find its text says so (the backend's message). */
export function changeToast(decision: ChangeVerb, answer?: Pick<StrategyChangeDecision, 'found' | 'message'> | null): string {
  if (decision === 'aprobar') return CHANGE_APPROVED;
  if (decision === 'rechazar') return CHANGE_REJECTED;
  if (answer?.found === false) return answer.message || 'La orientación ya no contenía este cambio: quedó revertido sin tocarla.';
  return 'Cambio revertido: ya no está en la orientación.';
}

// ---------------------------------------------------------------- «Generar ahora» and the empty state

/** «la revisión de octubre de 2026» from the backend's «Revisión de …». */
export function reviewPhrase(label: string): string {
  return `la ${label.charAt(0).toLowerCase()}${label.slice(1)}`;
}

/**
 * « El analista la escribe el primer lunes de cada mes a las 08:30. La próxima llega el lunes 7 de diciembre.» (with its
 * leading space), or ''. `automatic_at` is the current month's run: once it went by, only the rule is said.
 */
export function automaticSentence(offer: Pick<MonthlyReviewGenerate, 'automatic' | 'automatic_at'>, now: number = Date.now()): string {
  if (!offer.automatic || !offer.automatic_at) return '';
  const at = new Date(offer.automatic_at).getTime();
  if (Number.isNaN(at)) return '';
  const day = at > now ? dayOf(offer.automatic_at, OPERATOR_TZ) : null;
  const next = day ? ` La próxima llega el ${longDay(day)}.` : '';
  return ` El analista la escribe el primer lunes de cada mes a las ${formatTime(offer.automatic_at, OPERATOR_TZ)}.${next}`;
}

export const EMPTY_TITLE = 'Todavía no hay revisiones mensuales';

export function emptyText(offer: Pick<MonthlyReviewGenerate, 'automatic' | 'automatic_at'>, now: number = Date.now()): string {
  return `Una vez al mes el analista compara el mes con el anterior y, si los datos lo respaldan, propone hasta tres cambios de estrategia que decides uno a uno. Necesita alrededor de un mes de datos.${automaticSentence(offer, now)}`;
}

/** The confirmation of «Generar ahora»: what it does and what it costs. */
export function generateText(offer: Pick<MonthlyReviewGenerate, 'label'>): string {
  return `El analista escribe ${reviewPhrase(offer.label)}: compara el mes con el anterior y, si los datos lo respaldan, propone hasta tres cambios de estrategia, con una llamada a Claude.`;
}

export function generateCost(offer: Pick<MonthlyReviewGenerate, 'estimated_usd' | 'max_usd'>): string {
  return `Tiene coste: unos ${formatUsd(offer.estimated_usd)} (como mucho ${formatUsd(offer.max_usd)}), del presupuesto de la revisión mensual.`;
}

export function generatingText(offer: Pick<MonthlyReviewGenerate, 'label'>): string {
  return `El analista está escribiendo ${reviewPhrase(offer.label)}. Tarda unos minutos y aparecerá aquí.`;
}
