// Spanish labels for the editorial circuit (agentes-linkedin/infra/docs/publicacion-diaria.md).
import type { ActionState, Assessment, PieceStatus, ReaderAssessment, Repair, Selection, StageUsage, Verification } from '../api/types';
import { ROLE_BY_ID, type RoleId } from './roles';
import type { Tone } from './tone';

export const PIECE_STATUS: Record<PieceStatus, { label: string; tone: Tone }> = {
  preparing: { label: 'Preparándose', tone: 'info' },
  skipped: { label: 'Día sin pieza', tone: 'muted' },
  blocked: { label: 'Bloqueada por el verificador', tone: 'bad' },
  failed: { label: 'Fallida', tone: 'bad' },
  awaiting_approval: { label: 'Pendiente de aprobación', tone: 'warn' },
  scheduled: { label: 'Programada', tone: 'info' },
  publishing: { label: 'Publicándose', tone: 'warn' },
  published: { label: 'Publicada', tone: 'ok' },
  uncertain: { label: 'Incierta', tone: 'bad' },
  vetoed: { label: 'Vetada', tone: 'muted' },
  discarded: { label: 'Descartada por la política', tone: 'muted' },
  expired: { label: 'Caducada', tone: 'muted' },
  superseded: { label: 'Sustituida', tone: 'muted' },
};

export function pieceStatus(status: string): { label: string; tone: Tone } {
  return PIECE_STATUS[status as PieceStatus] ?? { label: status, tone: 'muted' };
}

/** A piece can be vetoed while its CONT-09 action has not started executing. */
export function vetoable(action: { state: ActionState } | null | undefined): boolean {
  return action?.state === 'proposed' || action?.state === 'approved';
}

export const STAGE_LABEL: Record<string, string> = {
  director: 'Director: idea y brief',
  redactor: 'Redactores: variantes A y B',
  lectores: 'Panel de lectores',
  seleccion: 'Selección del texto final',
  verificador: 'Verificador',
  reparacion: 'Ronda de reparación',
  visual: 'Editor visual: medios de la pieza',
};

export const MODALITY_LABEL: Record<string, string> = {
  personal_startups: 'Personal · startups',
  projectapp: 'ProjectApp',
  alianzas: 'Alianzas',
  comunidad: 'Comunidad',
};

export const PILLAR_LABEL: Record<string, string> = {
  business_to_product: 'Del negocio al producto',
  applied_ai: 'IA aplicada',
  architecture_delivery: 'Arquitectura y entrega',
};

export const FORMAT_LABEL: Record<string, string> = { text_only: 'Solo texto' };

export const SELECTION_LABEL: Record<string, string> = {
  A: 'Variante A',
  B: 'Variante B',
  merge: 'Fusión de A y B',
  discard: 'Descartada',
};

export const SEVERITY: Record<string, { label: string; tone: Tone }> = {
  material: { label: 'Material', tone: 'bad' },
  preference: { label: 'Preferencia', tone: 'muted' },
  missing_data: { label: 'Faltan datos', tone: 'warn' },
  minor: { label: 'Menor', tone: 'muted' },
};

export const ISSUE_LABEL: Record<string, string> = {
  invented_experience: 'Experiencia inventada',
  unsourced_figure: 'Cifra sin fuente',
  aggressive_pitch: 'Pitch agresivo',
  private_data: 'Datos privados',
  private_guidance_leak: 'Filtración de orientación privada',
  unsupported_claim: 'Afirmación sin respaldo',
  hook_not_delivered: 'Gancho incumplido',
  off_brief: 'Fuera del brief',
  other: 'Otro',
};

export const CLAIM_LABEL: Record<string, string> = {
  public_fact: 'Hecho público',
  observed_source: 'Fuente observada',
  general_knowledge: 'Conocimiento general',
  opinion: 'Opinión',
  supported_public_fact: 'Hecho público',
  supported_source: 'Fuente observada',
  unsupported: 'Sin respaldo',
};

export const VERDICT: Record<string, { label: string; tone: Tone }> = {
  ready_for_execution: { label: 'Lista para publicar', tone: 'ok' },
  blocked: { label: 'Bloqueada', tone: 'bad' },
};

export function readerLabel(reader: string | null | undefined): string {
  if (!reader) return '—';
  return ROLE_BY_ID[reader as RoleId]?.name ?? reader;
}

export function label(table: Record<string, string>, value: string | null | undefined): string {
  if (!value) return '—';
  return table[value] ?? value;
}

// ---------------------------------------------------------------- «Cómo se escribió»

/** A stage's JSON block with something in it (a stage that has not run leaves `{}`). */
export function filled(value: object | null | undefined): boolean {
  return Boolean(value && Object.keys(value).length);
}

export function asArray<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

/** States where the circuit will not run any further stage. */
export const FINISHED_STATUSES: ReadonlySet<string> = new Set(['skipped', 'blocked', 'failed', 'discarded', 'vetoed', 'expired', 'superseded', 'published', 'uncertain']);

/** «Esta etapa no llegó a correr» once the circuit is over; «aún no ha corrido» while it may still run. */
export function notYetText(finished: boolean): string {
  return finished ? 'Esta etapa no llegó a correr.' : 'Esta etapa aún no ha corrido.';
}

/** The badge on a variant: «Elegida», «En la fusión» or none. */
export function variantChosen(decision: Selection['decision'], name: 'A' | 'B'): string | null {
  return decision === name ? 'Elegida' : decision === 'merge' ? 'En la fusión' : null;
}

const SEVERITY_RANK: Record<string, number> = { material: 3, missing_data: 2, preference: 1 };
const SEVERITY_BADGE: Record<string, { label: string; tone: Tone }> = {
  material: { label: 'Objeción material', tone: 'bad' },
  missing_data: { label: 'Faltan datos', tone: 'warn' },
  preference: { label: 'Objeción menor', tone: 'muted' },
};

/** A reader's badge: its worst objection over both variants, or «Sin objeciones». */
export function readerBadge(reader: ReaderAssessment): { label: string; tone: Tone } {
  const worst = [...asArray(reader.variant_a?.objections), ...asArray(reader.variant_b?.objections)].reduce<string | null>(
    (acc, objection) => ((SEVERITY_RANK[objection.severity] ?? 0) > (SEVERITY_RANK[acc ?? ''] ?? 0) ? objection.severity : acc),
    null,
  );
  return (worst ? SEVERITY_BADGE[worst] : undefined) ?? { label: 'Sin objeciones', tone: 'ok' };
}

/** «A: Claro y útil. Objeciones: Genérico». */
export function assessmentLine(name: string, assessment: Assessment | undefined): string | null {
  const strengths = asArray(assessment?.strengths);
  const objections = asArray(assessment?.objections).map((o) => o.text);
  const parts = [strengths.length ? strengths.join('; ') : '', objections.length ? `Objeciones: ${objections.join('; ')}` : ''].filter(Boolean);
  return parts.length ? `${name}: ${parts.join('. ')}` : null;
}

/** The verifier's verdict badge («Aprobada», «Bloqueada») and the line about the guards. */
export function verifierSummary(v: Verification): { verdict: { label: string; tone: Tone } | null; guards: string; supported: number; claims: number } {
  const known = v.verdict ? (VERDICT[v.verdict] ?? { label: v.verdict, tone: 'muted' as Tone }) : null;
  const verdict = known ? { label: v.verdict === 'ready_for_execution' ? 'Aprobada' : known.label, tone: known.tone } : null;
  const corrected = Boolean(v.model_verdict && v.verdict && v.model_verdict !== v.verdict);
  const stoppedByRules = !v.model_verdict && asArray(v.rules).length > 0;
  const claims = asArray(v.checked_claims);
  const supported = claims.filter((claim) => (claim.status ?? claim.kind) !== 'unsupported').length;
  const guards = stoppedByRules
    ? 'El verificador no llegó a leerla: las reglas de publicación la frenaron antes'
    : corrected
      ? 'Las guardas corrigieron al modelo'
      : 'Sin correcciones de las guardas';
  return { verdict, guards, supported, claims: claims.length };
}

export const REPAIR_OUTCOME: Record<string, { label: string; tone: Tone }> = {
  reparada: { label: 'Reparada y verificada', tone: 'ok' },
  bloqueada: { label: 'Siguió bloqueada', tone: 'bad' },
  descartada: { label: 'No se pudo reparar', tone: 'bad' },
  sin_cambios: { label: 'Sin cambios', tone: 'muted' },
  sin_presupuesto: { label: 'Sin presupuesto', tone: 'warn' },
};

export function repairOutcome(repair: Repair): { label: string; tone: Tone } {
  return REPAIR_OUTCOME[repair.outcome] ?? { label: repair.outcome, tone: 'muted' };
}

/** Who asked for the repair round. */
export function repairTrigger(repair: Repair): string {
  return repair.trigger === 'reglas' ? 'La pidieron las reglas de publicación' : 'La pidió el verificador';
}

const COST_STAGES: { key: string; label: string }[] = [
  { key: 'director', label: 'Director' },
  { key: 'redactor', label: 'Redactores' },
  { key: 'lectores', label: 'Lectores' },
  { key: 'seleccion', label: 'Selección' },
  { key: 'verificador', label: 'Verificador' },
  { key: 'reparacion', label: 'Reparación' },
  { key: 'visual', label: 'Editor visual' },
];

/** Cost per stage in circuit order (unknown stages last); rows without an estimate are left out, never 0. */
export function costRows(usage: StageUsage[]): { label: string; usd: number }[] {
  const totals = new Map<string, number>();
  for (const row of usage) {
    const usd = Number(row.estimated_usd);
    if (row.estimated_usd === null || row.estimated_usd === undefined || !Number.isFinite(usd)) continue;
    totals.set(row.stage, (totals.get(row.stage) ?? 0) + usd);
  }
  const known = COST_STAGES.filter((stage) => totals.has(stage.key)).map((stage) => ({ label: stage.label, usd: totals.get(stage.key)! }));
  const other = [...totals.entries()].filter(([stage]) => !COST_STAGES.some((s) => s.key === stage)).map(([stage, usd]) => ({ label: stage, usd }));
  return [...known, ...other];
}
