// Pure rules of the Personas screens (the PWA's Barrio, the person card, Oportunidades and Referentes), kept apart
// from the markup so the PWA (oficina/src/pages/personas) and the native app (movil/src/personas) say the same. The
// app's Conexiones tab has its own rules in conexiones.ts.
import type {
  Contact,
  ContactHistoryEntry,
  ContactNote,
  ContactStage,
  ConversationAssessment,
  Opportunity,
  OpportunityAttribution,
  OpportunityChannel,
  OpportunityInput,
  OpportunityModality,
  OpportunityStage,
  RedSummary,
  Referent,
} from '../api/types';
import { actionStateLabel, capabilityLabel, CONTACT_EVENT_LABEL, excerpt, networkDistanceLabel, timeAgo } from './format';
import { agree, isFeminineName } from './genero';
import {
  ATTRIBUTION_LABEL,
  BOARD_STAGES,
  CHANNEL_LABEL,
  daysInStage,
  fromDateInput,
  labelFrom,
  longDate,
  MODALITY_SHORT,
  OPPORTUNITY_MODALITY_LABEL,
  OPPORTUNITY_STAGE_LABEL,
  relativeDay,
  shortDate,
  type PersonStage,
} from './personas';
import type { Tone } from './tone';

// ================================================================ Barrio

const CONTACT_STAGE_KEYS: readonly ContactStage[] = ['candidate', 'fit', 'followed', 'invited', 'connected', 'incoming', 'closed', 'discarded'];

/** Count of a funnel chip from red/summary; null for «En conversación» until the inbox arrives. */
export function stageCount(summary: RedSummary | undefined, stage: PersonStage): number | null | undefined {
  if (!summary) return undefined;
  if (stage === 'conversation') return summary.stages.conversation ?? null;
  if (stage === 'opportunity') return summary.stages.opportunity ?? 0;
  return summary.stages[stage] ?? 0;
}

/** «Todas · 51»: every contact stage (opportunity and conversation overlap them). */
export function totalCount(summary: RedSummary | undefined): number | undefined {
  if (!summary) return undefined;
  return CONTACT_STAGE_KEYS.reduce((sum, stage) => sum + (summary.stages[stage] ?? 0), 0);
}

/** «Seguido hace 2 días» («Seguida» for a woman), from the last event (or the last update). */
export function lastActivity(contact: Contact): string {
  const event = contact.last_event ?? contact.history?.[contact.history.length - 1] ?? null;
  if (event) return `${agree(CONTACT_EVENT_LABEL[event.event] ?? event.event, isFeminineName(contact.display_name))} ${timeAgo(event.at)}`;
  return `Actualizado ${timeAgo(contact.updated_at)}`;
}

export function displayName(contact: Pick<Contact, 'display_name' | 'public_identifier'>): string {
  return contact.display_name || contact.public_identifier || 'Sin nombre';
}

// ================================================================ person card

/** «Medellín, Colombia · 1.er grado · Lo sigues». */
export function personMeta(contact: Contact): string {
  const followers = contact.signals?.followers;
  return [
    contact.location,
    networkDistanceLabel(contact.network_distance),
    contact.is_following ? 'Lo sigues' : '',
    typeof followers === 'number' ? `${followers.toLocaleString('es-CO')} ${followers === 1 ? 'seguidor' : 'seguidores'}` : '',
  ]
    .filter(Boolean)
    .join(' · ');
}

/** BAR-17: why the lead stopped a person the classifier said fits, and until when it rests; null without a doubt. */
export function leadDoubtText(contact: Contact): string | null {
  const doubt = contact.lead_doubt;
  if (!doubt) return null;
  const why = doubt.reasons.length ? ` (${doubt.reasons.join('; ')})` : '';
  const action = DOUBTED_ACTION[doubt.capability] ?? capabilityLabel(doubt.capability);
  return `El clasificador dice que encaja, pero el líder frenó ${action}${why}. Descansa hasta el ${shortDate(doubt.until)} salvo que confirmes que encaja.`;
}

const DOUBTED_ACTION: Record<string, string> = { 'RED-01': 'el follow', 'RED-02': 'la invitación', 'RED-04': 'la aceptación de su invitación' };

/** The modality the team read in their conversation when it looks like business; otherwise their classification's. */
export function suggestedModality(contact: Contact): string | null | undefined {
  const read = contact.conversation?.assessment;
  return read?.opportunity && read.modality && read.modality !== 'por_clasificar' ? read.modality : contact.classification?.modality;
}

export interface NextStepView {
  /** Gustavo's move: warn tone and «Ir a la Bandeja». */
  mine: boolean;
  /** «Siguiente paso · Te toca». */
  label: string;
  text: string;
  /** «Para el 12 nov» or «A partir del 7 nov». */
  at: string | null;
  /** «Invitación sin nota · Aprobada», when an action is open. */
  action: string | null;
}

export function nextStepView(contact: Contact): NextStepView | null {
  const step = contact.next_step;
  if (!step) return null;
  const mine = step.owner === 'gustavo' || Boolean(contact.your_turn);
  const owner = mine ? 'Te toca' : step.owner === 'equipo' ? 'Equipo' : null;
  return {
    mine,
    label: `Siguiente paso${owner ? ` · ${owner}` : ''}`,
    text: step.text,
    at: step.at ? (mine ? `Para el ${shortDate(step.at)}` : `A partir del ${shortDate(step.at)}`) : null,
    action: step.action ? `${capabilityLabel(step.action.capability)} · ${actionStateLabel(step.action.state)}` : null,
  };
}

/** The model's confidence as a whole percentage, or null. */
export function confidencePct(confidence: number | undefined): number | null {
  return typeof confidence === 'number' ? Math.round(Math.min(1, Math.max(0, confidence)) * 100) : null;
}

/** The comment or invitation that brought the person, shortened. */
export function originQuote(contact: Contact): string {
  const evidence = contact.evidence ?? {};
  if (contact.source === 'commenter') return excerpt(evidence.comment, 280);
  if (contact.source === 'incoming') return excerpt(evidence.invitation_message, 280);
  return '';
}

/** The fields of the opportunity block: what the brief carries, completed by the full opportunity once it loads. */
export function opportunityFields(brief: NonNullable<Contact['opportunity']>, full: Opportunity | undefined): [string, string][] {
  const nextText = [full?.next_action ?? brief.next_action, relativeDay(full?.next_action_at ?? brief.next_action_at)].filter(Boolean).join(' · ');
  const fields: [string, string][] = [];
  if (full?.need) fields.push(['Necesidad', full.need]);
  if (full) fields.push(['Canal', labelFrom(CHANNEL_LABEL, full.channel)]);
  if (full) fields.push(['Cómo llegó', labelFrom(ATTRIBUTION_LABEL, full.attribution)]);
  if (full?.budget) fields.push(['Presupuesto', full.budget]);
  if (full?.dedication) fields.push(['Dedicación', full.dedication]);
  if (nextText) fields.push(['Siguiente acción', nextText]);
  return fields;
}

/** «Tu nota» or «Nota de ana». */
export function noteAuthor(note: ContactNote, me: string | null | undefined): string {
  return note.by && note.by !== me ? `Nota de ${note.by}` : 'Tu nota';
}

/** Newest first. */
export function sortHistory(entries: readonly ContactHistoryEntry[]): ContactHistoryEntry[] {
  return [...entries].sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0));
}

/** «Seguido», or «Seguida» on a woman's card. */
export function eventLabel(entry: ContactHistoryEntry, feminine = false): string {
  return agree(CONTACT_EVENT_LABEL[entry.event] ?? entry.event, feminine);
}

function asPercent(value: number | undefined): string | null {
  return typeof value === 'number' ? `${Math.round(Math.min(1, Math.max(0, value)) * 100)} %` : null;
}

export interface TeamReadView {
  chips: { text: string; tone: Tone | 'ink'; badge: boolean }[];
  /** «Oportunidad 86 % · Espera respuesta 81 % · Venta o spam 4 %». */
  numbers: string;
}

/** The team's read of the last message, as chips and the probabilities behind them. Null before any read. */
export function teamRead(assessment: ConversationAssessment | null | undefined): TeamReadView | null {
  if (!assessment) return null;
  const answers = assessment.answers ?? {};
  const modality = assessment.modality && assessment.modality !== 'por_clasificar' ? OPPORTUNITY_MODALITY_LABEL[assessment.modality] : null;
  const chips: TeamReadView['chips'] = [];
  if (assessment.opportunity) chips.push({ text: modality ? `Posible oportunidad · ${modality}` : 'Posible oportunidad', tone: 'ok', badge: true });
  if (assessment.awaiting_reply) chips.push({ text: 'Espera tu respuesta', tone: 'warn', badge: true });
  if (assessment.pitch) chips.push({ text: 'Parece venta o spam', tone: 'muted', badge: false });
  if (!assessment.opportunity && !assessment.awaiting_reply && !assessment.pitch) chips.push({ text: 'Sin señales de negocio ni respuesta pendiente', tone: 'muted', badge: false });
  const numbers = [
    ['Oportunidad', asPercent(answers.oportunidad)],
    ['Espera respuesta', asPercent(answers.espera)],
    ['Venta o spam', asPercent(answers.venta)],
  ]
    .filter((pair): pair is [string, string] => Boolean(pair[1]))
    .map(([label, value]) => `${label} ${value}`)
    .join(' · ');
  return { chips, numbers };
}

// ================================================================ Oportunidades

export function opportunityName(opportunity: Pick<Opportunity, 'person' | 'person_name'>): string {
  return opportunity.person || opportunity.person_name || 'Sin nombre';
}

/** «Enviar la propuesta de piloto · 12 nov». */
export function nextActionText(opportunity: Pick<Opportunity, 'next_action' | 'next_action_at'>): string {
  return [opportunity.next_action, relativeDay(opportunity.next_action_at)].filter(Boolean).join(' · ');
}

/** «Faro Salud · ProjectApp · cerrada el 30 de octubre». */
export function closedMeta(opportunity: Opportunity): string {
  return [opportunity.company, MODALITY_SHORT[opportunity.modality], opportunity.closed_at ? `cerrada el ${longDate(opportunity.closed_at)}` : ''].filter(Boolean).join(' · ');
}

/** The stage groups of the mobile list, most advanced first, without the closed ones. */
export function stageGroups(items: readonly Opportunity[], keepEmpty = false): { stage: OpportunityStage; label: string; items: Opportunity[] }[] {
  return [...BOARD_STAGES]
    .reverse()
    .map((stage) => ({ stage, label: OPPORTUNITY_STAGE_LABEL[stage], items: items.filter((item) => item.stage === stage) }))
    .filter((group) => keepEmpty || group.items.length > 0);
}

export function movedToast(stage: OpportunityStage): string {
  return `Movida a «${OPPORTUNITY_STAGE_LABEL[stage]}»`;
}

/** «Deshacer» a move failed: the card stays in the stage it was moved to. */
export function undoFailedToast(stage: OpportunityStage): string {
  return `No se pudo deshacer: sigue en «${OPPORTUNITY_STAGE_LABEL[stage]}»`;
}

export function stageDays(opportunity: Pick<Opportunity, 'days_in_stage'>): string {
  return daysInStage(opportunity.days_in_stage);
}

// ---------------------------------------------------------------- the opportunity form

/** The person the form starts with (Marcar como oportunidad, from the person card). */
export interface OpportunityPerson {
  id: string;
  display_name: string;
  headline?: string;
  /** classification.modality: prefills the modality when it is one of the two business ones. */
  modality?: string | null;
}

export type PersonMode = 'red' | 'fuera';

export function initialModality(opportunity: Opportunity | null | undefined, person: OpportunityPerson | null | undefined): OpportunityModality | '' {
  if (opportunity) return opportunity.modality;
  const modality = person?.modality;
  return modality === 'personal_startups' || modality === 'projectapp' ? modality : '';
}

export interface OpportunityDraft {
  mode: PersonMode;
  picked: OpportunityPerson | null;
  personName: string;
  company: string;
  modality: OpportunityModality | '';
  channel: OpportunityChannel;
  stage: OpportunityStage;
  attribution: OpportunityAttribution | '';
  need: string;
  budget: string;
  dedication: string;
  nextAction: string;
  /** AAAA-MM-DD or ''. */
  nextAt: string;
  notes: string;
}

/** The required fields that are missing (null when fine). */
export function opportunityErrors(draft: OpportunityDraft): { person: string | null; modality: string | null; attribution: string | null } {
  return {
    person: draft.mode === 'red' ? (draft.picked ? null : 'Elige a alguien de Personas.') : draft.personName.trim() ? null : 'Escribe el nombre de la persona.',
    modality: draft.modality ? null : 'Elige la modalidad.',
    attribution: draft.attribution ? null : 'Elige cómo llegó.',
  };
}

/** The body of POST /oportunidades or PATCH /oportunidades/<id>. */
export function opportunityInput(draft: OpportunityDraft): OpportunityInput {
  return {
    contact: draft.mode === 'red' ? (draft.picked?.id ?? null) : null,
    person_name: draft.mode === 'fuera' ? draft.personName.trim() : '',
    company: draft.company.trim(),
    modality: draft.modality as OpportunityModality,
    channel: draft.channel,
    stage: draft.stage,
    attribution: draft.attribution as OpportunityAttribution,
    need: draft.need.trim(),
    budget: draft.budget.trim(),
    dedication: draft.dedication.trim(),
    next_action: draft.nextAction.trim(),
    next_action_at: draft.nextAt ? fromDateInput(draft.nextAt) : null,
    notes: draft.notes.trim(),
  };
}

// ================================================================ Referentes

/** «hace 3 h», «hace 12 días» (timeAgo switches to a full date after a week). */
export function observedAgo(iso: string, now: number = Date.now()): string {
  const days = Math.floor((now - new Date(iso).getTime()) / 86_400_000);
  return days >= 7 ? `hace ${days} días` : timeAgo(iso, now);
}

export function referentName(referent: Referent): string {
  return referent.display_name || referent.public_identifier || referent.profile_url || 'Referente';
}

/** «Observado hace 3 h · 14 personas del barrio salieron de sus posts». */
export function referentMeta(referent: Referent, now: number = Date.now()): string {
  const count = referent.contacts_count;
  const observed = referent.last_observed_at ? `Observado ${observedAgo(referent.last_observed_at, now)}` : 'Aún sin observar';
  const people = typeof count === 'number' ? ` · ${count} ${count === 1 ? 'persona del barrio salió' : 'personas del barrio salieron'} de sus posts` : '';
  return `${observed}${people}`;
}

export const REFERENT_URL_ERROR = 'Pega la URL de un perfil: https://www.linkedin.com/in/…';
export const OBSERVE_QUEUED = 'Observación encolada. Los posts nuevos aparecerán en unos minutos';
