// Shared wording for a piece: when it goes out, what it achieved and its editorial facts.
import type { PieceDetail, PieceSnapshot } from '../../api/types';
import type { Stage } from '../../components/ui';
import { label, MODALITY_LABEL, PILLAR_LABEL, readerLabel, STAGE_LABEL } from '../../lib/editorial';
import { formatNumber, formatPct, formatTime } from '../../lib/format';
import { dayOf, relativeDay, relativeDayInSentence, timeLeft } from './dates';

/** Director → Redactores → Lectores → Selección → Verificador. */
export const STAGE_ORDER = ['director', 'redactor', 'lectores', 'seleccion', 'verificador'] as const;

const STAGE_SHORT: Record<string, string> = {
  director: 'director',
  redactor: 'redactores',
  lectores: 'panel de lectores',
  seleccion: 'selección del texto final',
  verificador: 'verificador',
};

export function stageShort(stage: string | null | undefined): string {
  return STAGE_SHORT[stage || 'director'] ?? stage ?? '';
}

/** The 5 preparation steps for the numbered StageTrack. */
export function preparationStages(stage: string | null | undefined): Stage[] {
  const current = Math.max(0, STAGE_ORDER.indexOf((stage || 'director') as (typeof STAGE_ORDER)[number]));
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
