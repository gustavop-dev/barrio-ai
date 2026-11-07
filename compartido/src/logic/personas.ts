// Vocabularies of Personas (DISENO-VISTAS «Etapa de una persona», «Etapa de una oportunidad») and the
// short dates the design screens use («12 nov», «21 de octubre», «hoy»).
import type { ContactStage, ConversationMessage, DisplayStage, OpportunityAttribution, OpportunityChannel, OpportunityModality, OpportunityStage } from '../api/types';
import { formatTime } from './format';
import type { Tone } from './tone';

/** Personas shows the contact stages plus «En conversación» (with the inbox) and «Oportunidad». */
export type PersonStage = DisplayStage | 'conversation';

export const PERSON_STAGE: Record<PersonStage, { label: string; tone: Tone | 'ink' }> = {
  candidate: { label: 'Por clasificar', tone: 'muted' },
  fit: { label: 'Encaja', tone: 'info' },
  followed: { label: 'Seguido', tone: 'info' },
  invited: { label: 'Invitado', tone: 'warn' },
  connected: { label: 'Conectado', tone: 'ok' },
  conversation: { label: 'En conversación', tone: 'ok' },
  opportunity: { label: 'Oportunidad', tone: 'ink' },
  incoming: { label: 'Te invitó', tone: 'info' },
  closed: { label: 'Cerrado', tone: 'muted' },
  discarded: { label: 'Descartado', tone: 'muted' },
};

export function personStage(stage: string | null | undefined): { label: string; tone: Tone | 'ink' } {
  return PERSON_STAGE[(stage ?? '') as PersonStage] ?? { label: stage || 'Sin etapa', tone: 'muted' };
}

/** The funnel chips, in order; the aside ones go after a gap. */
export const FUNNEL_MAIN: readonly PersonStage[] = ['candidate', 'fit', 'followed', 'invited', 'connected', 'conversation', 'opportunity'];
export const FUNNEL_ASIDE: readonly PersonStage[] = ['incoming', 'closed', 'discarded'];

/** The contract only accepts a discard in these stages (409 otherwise). */
export const DISCARDABLE: readonly ContactStage[] = ['candidate', 'fit', 'followed', 'incoming'];

/** Short modality names for chips (the network modalities; the full names live in lib/format). */
export const MODALITY_SHORT: Record<string, string> = {
  personal_startups: 'Startups',
  projectapp: 'ProjectApp',
  alianzas: 'Alianzas',
  comunidad_autoridad: 'Comunidad',
  por_clasificar: 'Por clasificar',
};

export const SOURCE_FILTER: Record<string, string> = {
  commenter: 'Comentó en un post',
  search: 'Búsqueda',
  incoming: 'Te invitó',
  manual: 'Añadido a mano',
};

// ---------------------------------------------------------------- opportunities

export const OPPORTUNITY_STAGE_LABEL: Record<OpportunityStage, string> = {
  conversacion: 'Conversación',
  necesidad: 'Necesidad identificada',
  cualificada: 'Cualificada',
  reunion: 'Reunión',
  propuesta: 'Propuesta',
  acuerdo: 'Acuerdo',
  sin_acuerdo: 'Cerrada sin acuerdo',
};

/** The board columns; «Cerrada sin acuerdo» goes folded under them. */
export const BOARD_STAGES: readonly OpportunityStage[] = ['conversacion', 'necesidad', 'cualificada', 'reunion', 'propuesta', 'acuerdo'];

export function opportunityStageLabel(stage: string | null | undefined): string {
  return OPPORTUNITY_STAGE_LABEL[(stage ?? '') as OpportunityStage] ?? stage ?? '—';
}

export const OPPORTUNITY_MODALITY_LABEL: Record<OpportunityModality, string> = {
  personal_startups: 'Startups (personal)',
  projectapp: 'ProjectApp',
  por_clasificar: 'Por clasificar',
};

export const CHANNEL_LABEL: Record<OpportunityChannel, string> = {
  linkedin: 'LinkedIn',
  email: 'Email',
  llamada: 'Llamada',
  evento: 'Evento',
  otro: 'Otro',
};

export const ATTRIBUTION_LABEL: Record<OpportunityAttribution, string> = {
  cito_contenido: 'Citó un post o el perfil',
  lo_dijo: 'Lo dijo la persona',
  inferido: 'Se infiere',
  desconocido: 'Se desconoce',
};

export function labelFrom<T extends string>(table: Record<T, string>, value: string | null | undefined): string {
  if (!value) return '—';
  return table[value as T] ?? value;
}

// ---------------------------------------------------------------- dates

const MONTHS_SHORT = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sept', 'oct', 'nov', 'dic'];
const MONTHS_LONG = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

/** An ISO instant, or an AAAA-MM-DD day read as such (never shifted by the time zone). */
function parts(value: string | null | undefined): { y: number; m: number; d: number } | null {
  if (!value) return null;
  const day = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (day) return { y: Number(day[1]), m: Number(day[2]) - 1, d: Number(day[3]) };
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return { y: date.getFullYear(), m: date.getMonth(), d: date.getDate() };
}

/** «12 nov». */
export function shortDate(value: string | null | undefined): string {
  const p = parts(value);
  return p ? `${p.d} ${MONTHS_SHORT[p.m]}` : '';
}

/** «21 de octubre». */
export function longDate(value: string | null | undefined): string {
  const p = parts(value);
  return p ? `${p.d} de ${MONTHS_LONG[p.m]}` : '';
}

/** «hoy», «mañana», «ayer» or «12 nov». */
export function relativeDay(value: string | null | undefined, now: Date = new Date()): string {
  const p = parts(value);
  if (!p) return '';
  const target = Date.UTC(p.y, p.m, p.d);
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  const diff = Math.round((target - today) / 86_400_000);
  if (diff === 0) return 'hoy';
  if (diff === 1) return 'mañana';
  if (diff === -1) return 'ayer';
  return shortDate(value);
}

/** A local AAAA-MM-DD (for <input type="date">) from an ISO instant. */
export function toDateInput(value: string | null | undefined): string {
  const p = parts(value);
  if (!p) return '';
  return `${p.y}-${String(p.m + 1).padStart(2, '0')}-${String(p.d).padStart(2, '0')}`;
}

/** The ISO instant at local noon of an AAAA-MM-DD (the API wants a datetime). */
export function fromDateInput(value: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

/** «1 día en esta etapa». */
export function daysInStage(days: number | null | undefined): string {
  if (typeof days !== 'number' || days < 0) return '';
  if (days === 0) return 'Desde hoy en esta etapa';
  return `${days} ${days === 1 ? 'día' : 'días'} en esta etapa`;
}

/** «hoy 10:12», «ayer 18:03» or «6 nov». */
export function messageWhen(iso: string | null | undefined): string {
  if (!iso) return '';
  const day = relativeDay(iso);
  return day === 'hoy' || day === 'ayer' ? `${day} ${formatTime(iso)}` : day;
}

/** The message text, or what it carried when it has none. */
export function messageText(message: ConversationMessage): string {
  if (message.text) return message.text;
  return message.attachments ? 'Envió un adjunto.' : 'Mensaje sin texto.';
}
