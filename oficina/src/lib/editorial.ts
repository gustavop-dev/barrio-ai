// Spanish labels for the editorial circuit (agentes-linkedin/infra/docs/publicacion-diaria.md).
import type { Tone } from '../components/ui';
import type { ActionState, PieceStatus } from '../api/types';
import { ROLE_BY_ID, type RoleId } from '../scene/roles';

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
