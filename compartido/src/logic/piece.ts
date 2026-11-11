// Shared wording for a piece: when it goes out, what it achieved and its editorial facts.
import type { PieceCommenter, PieceDetail, PieceSnapshot } from '../api/types';
import { dayOf, longDay, relativeDay, relativeDayInSentence, timeLeft } from './dates';
import { label, MODALITY_LABEL, PILLAR_LABEL, readerLabel, STAGE_LABEL, vetoable } from './editorial';
import { CONTACT_ROLE_LABEL, formatNumber, formatPct, formatTime } from './format';

/** IMG-11: the veto covers the whole frozen piece, until its effective publication time. */
export function pieceVetoable(piece: Pick<PieceDetail, 'action' | 'scheduled_for'>, now: number): boolean {
  return vetoable(piece.action) && Date.parse(piece.scheduled_for) > now;
}

/** One step of the numbered preparation track (each app's StageTrack draws it). */
export interface PreparationStage {
  key: string;
  label: string;
  state: 'done' | 'current' | 'pending';
}

/** Director → Redactores → Lectores → Selección → Verificador. */
export const STAGE_ORDER = ['director', 'redactor', 'lectores', 'seleccion', 'verificador'] as const;

const STAGE_SHORT: Record<string, string> = {
  director: 'director',
  redactor: 'redactores',
  lectores: 'panel de lectores',
  seleccion: 'selección del texto final',
  verificador: 'verificador',
  reparacion: 'ronda de reparación',
};

export function stageShort(stage: string | null | undefined): string {
  return STAGE_SHORT[stage || 'director'] ?? stage ?? '';
}

/** The 5 preparation steps for the numbered StageTrack. The repair round belongs to the verification step. */
export function preparationStages(stage: string | null | undefined): PreparationStage[] {
  const step = stage === 'reparacion' ? 'verificador' : stage || 'director';
  const current = Math.max(0, STAGE_ORDER.indexOf(step as (typeof STAGE_ORDER)[number]));
  return STAGE_ORDER.map((key, index) => ({
    key,
    label: STAGE_LABEL[key] ?? key,
    state: index < current ? 'done' : index === current ? 'current' : 'pending',
  }));
}

/** States in which the piece is still on its way to LinkedIn. */
const ON_ITS_WAY = new Set(['preparing', 'scheduled', 'awaiting_approval', 'publishing']);
/** States in which it was going to go out and did not. */
const DID_NOT = new Set(['blocked', 'failed', 'vetoed', 'discarded', 'expired', 'superseded']);

export function isOnItsWay(status: string): boolean {
  return ON_ITS_WAY.has(status);
}

/** When it actually went out (execution end), falling back to its scheduled hour. */
export function publishedAt(piece: Pick<PieceDetail, 'scheduled_for' | 'action_detail'>): string {
  return piece.action_detail?.execution?.finished_at || piece.action_detail?.execution?.started_at || piece.scheduled_for;
}

/**
 * The hour line of a piece card.
 * - published: «Salió a las 09:00»
 * - on its way: «Mañana a las 09:00 · sale en 18 h»
 * - did not go out: «Iba a salir a las 09:00»
 */
export function pieceWhen(
  status: string,
  scheduledFor: string | null | undefined,
  { today, timeZone, now, published }: { today: string; timeZone: string; now: number; published?: string | null },
): string {
  if (status === 'skipped') return 'Día sin pieza';
  if (!scheduledFor) return '';
  const time = formatTime(scheduledFor, timeZone);
  if (status === 'published') return `Salió a las ${formatTime(published || scheduledFor, timeZone)}`;
  if (DID_NOT.has(status) || status === 'uncertain') return `Iba a salir a las ${time}`;
  const day = dayOf(scheduledFor, timeZone) ?? today;
  const left = new Date(scheduledFor).getTime() - now;
  return `${relativeDay(day, today)} a las ${time}${left > 0 ? ` · sale en ${timeLeft(left)}` : ''}`;
}

/** «Sale mañana a las 09:00», for the detail header. */
export function pieceLeaves(scheduledFor: string, { today, timeZone }: { today: string; timeZone: string }): string {
  const day = dayOf(scheduledFor, timeZone) ?? today;
  return `Sale ${relativeDayInSentence(day, today)} a las ${formatTime(scheduledFor, timeZone)}`;
}

/** «Del negocio al producto · Personal · startups · Lector comprador». */
export function pieceMeta(piece: { pillar: string | null; modality: string | null; primary_reader: string | null }): string {
  return [
    piece.pillar ? label(PILLAR_LABEL, piece.pillar) : null,
    piece.modality ? label(MODALITY_LABEL, piece.modality) : null,
    piece.primary_reader ? readerLabel(piece.primary_reader) : null,
  ]
    .filter(Boolean)
    .join(' · ');
}

/** The first three non-empty lines of the final text, joined as one paragraph. */
export function firstLines(text: string | null | undefined, count = 3): string {
  return (text ?? '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, count)
    .join(' ');
}

export const CUT_LABEL: Record<PieceSnapshot['kind'], string> = { '24h': 'las 24 h', '72h': 'las 72 h', '7d': 'los 7 días' };
export const CUT_HOURS: Record<PieceSnapshot['kind'], number> = { '24h': 24, '72h': 72, '7d': 168 };

/** The most recent cut with impressions. */
export function latestSnapshot(snapshots: PieceSnapshot[] | null | undefined): PieceSnapshot | null {
  const list = (snapshots ?? []).filter((snapshot) => typeof snapshot.impressions === 'number');
  return list.length ? list[list.length - 1]! : null;
}

/** One-line result of a card: impressions at the latest cut, the last reading, or when the first cut arrives. */
export function resultLine(piece: PieceDetail, { today, timeZone }: { today: string; timeZone: string }): string | null {
  switch (piece.status) {
    case 'published': {
      const cut = latestSnapshot(piece.snapshots);
      if (cut) {
        const engagement = typeof cut.engagement_pct === 'number' ? ` · interacción ${formatPct(cut.engagement_pct)}` : '';
        return `Impresiones a ${CUT_LABEL[cut.kind]}: ${formatNumber(cut.impressions!, 0)}${engagement}`;
      }
      if (typeof piece.metrics?.impressions === 'number') return `Impresiones: ${formatNumber(piece.metrics.impressions, 0)} (última lectura)`;
      const due = new Date(new Date(publishedAt(piece)).getTime() + 24 * 3_600_000).toISOString();
      return `Impresiones a las 24 h: ${relativeDayInSentence(dayOf(due, timeZone) ?? today, today)} a las ${formatTime(due, timeZone)}`;
    }
    case 'blocked':
      return piece.verification?.blocking_reasons?.[0] || piece.note || null;
    case 'vetoed':
      return piece.action_detail?.decision_note ? `Tu nota: ${piece.action_detail.decision_note}` : null;
    case 'failed':
    case 'uncertain':
      return piece.action_detail?.execution?.note || piece.note || null;
    case 'discarded':
      return piece.action_detail?.decision_note || piece.note || null;
    case 'preparing':
      return `Etapa: ${stageShort(piece.stage)}`;
    default:
      return null;
  }
}

// ---------------------------------------------------------------- «Resultado»: cuts and commenters

export const RESULT_CUTS: readonly PieceSnapshot['kind'][] = ['24h', '72h', '7d'];

export const RESULT_METRICS: readonly { key: 'impressions' | 'reactions' | 'comments' | 'reposts'; label: string }[] = [
  { key: 'impressions', label: 'Impresiones' },
  { key: 'reactions', label: 'Reacciones' },
  { key: 'comments', label: 'Comentarios' },
  { key: 'reposts', label: 'Republicaciones' },
];

/** A metric of a cut: «1.210», or «—» when it is missing (never 0). */
export function metricValue(n: number | null | undefined): string {
  return typeof n === 'number' ? formatNumber(n, 0) : '—';
}

/** «3,5 %», or «—» when it is missing. */
export function engagementValue(n: number | null | undefined): string {
  return typeof n === 'number' ? formatPct(n) : '—';
}

/** A cut not read yet: «Aún no · Llega el lunes 9 de noviembre a las 09:00.», or «Sin dato» once its hour passed. */
export function cutPending(kind: PieceSnapshot['kind'], published: string, timeZone: string, now: number): { badge: string; text: string } {
  const due = new Date(new Date(published).getTime() + CUT_HOURS[kind] * 3_600_000);
  if (due.getTime() <= now) return { badge: 'Sin dato', text: 'El corte no se pudo leer a tiempo.' };
  return { badge: 'Aún no', text: `Llega el ${longDay(dayOf(due, timeZone) ?? '')} a las ${formatTime(due.toISOString(), timeZone)}.` };
}

const ROLE_ORDER = ['comprador', 'par', 'recomendador', 'divulgador', 'lider', 'aliado'];

/** Who commented, counted per role of the barrio in the design's order, and those without a role. */
export function commenterRoles(commenters: readonly PieceCommenter[]): { roles: { role: string; label: string; count: number }[]; unclassified: number } {
  const counts = new Map<string, number>();
  for (const person of commenters) counts.set(person.role ?? '', (counts.get(person.role ?? '') ?? 0) + 1);
  const roles = [...counts.keys()]
    .filter(Boolean)
    .sort((a, b) => {
      const ia = ROLE_ORDER.indexOf(a);
      const ib = ROLE_ORDER.indexOf(b);
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    })
    .map((role) => ({ role, label: CONTACT_ROLE_LABEL[role] ?? role, count: counts.get(role)! }));
  return { roles, unclassified: counts.get('') ?? 0 };
}

/** The post's LinkedIn URL, wherever the backend put it. */
export function pieceUrl(piece: Pick<PieceDetail, 'external_url' | 'metrics' | 'action_detail'>): string | null | undefined {
  return piece.external_url || piece.metrics?.share_url || piece.action_detail?.execution?.external_url;
}

/** Characters as a person counts them (emoji and accents count once): the final text's length. */
export function charCount(text: string | null | undefined): number {
  return [...(text ?? '')].length;
}

/** EDI-23: who blocked the piece, inside a sentence. */
export const RESCUE_WHO: Record<'verificador' | 'imagen' | 'lider', string> = {
  verificador: 'el verificador',
  imagen: 'la revisión de la imagen',
  lider: 'el líder',
};

/** The toast after «Desestimar el bloqueo». */
export const OVERRIDE_DONE = 'Bloqueo desestimado: el equipo la deja lista para salir con tu aprobación.';

/** What «Desestimar el bloqueo» does, for its confirmation. */
export function overrideConsequence(piece: { images?: readonly unknown[] | null }): string {
  const image = piece.images?.length ? '' : ' Antes, el equipo le prepara la imagen (tiene un coste pequeño).';
  return `Sale tal cual en su día y hora, con tu aprobación y sin pasar por el líder.${image} Aún podrás vetarla hasta su hora.`;
}
