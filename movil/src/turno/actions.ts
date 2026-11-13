// Rules of the Tu turno card actions (the PWA's TurnoCardView), apart from the views so they can be
// tested: which actions ask first, what the toast says, and what a swipe does on each card.
import type { TurnoAction, TurnoCard, TurnoCardType, TurnoPriority } from '@compartido/api/types';
import { APPROVED_MESSAGE, vetoConsequence } from '@compartido/logic/events';
import { messageText } from '@compartido/logic/personas';
import { extras, longDate } from '@compartido/logic/turno';
import type { IconName } from '@/components/icons';

export const TYPE_LABEL: Record<TurnoCardType, string> = {
  referente: 'Referentes del mes',
  experimento: 'Experimento',
  aviso: 'Aviso',
  pregunta: 'Pregunta',
  perfil: 'Perfil',
  conversacion: 'Conversación',
  mensaje: 'Mensaje sugerido',
  fecha: 'Fecha pedida',
  resumen: 'Resumen semanal',
  aprobacion: 'Aprobación',
};

export const TYPE_ICON: Record<TurnoCardType, IconName> = {
  referente: 'personas',
  experimento: 'resultados',
  aviso: 'aviso',
  pregunta: 'pregunta',
  perfil: 'perfil',
  conversacion: 'conversacion',
  mensaje: 'conversacion',
  fecha: 'calendario',
  resumen: 'resultados',
  aprobacion: 'check',
};

/** Colour of the type label: alerta for urgent notices, info for questions and conversations, hondo for profile tasks. */
export function typeTone(card: TurnoCard, priority: TurnoPriority | null): 'suave' | 'alerta' | 'hondo' | 'info' {
  if (!priority) return 'suave';
  if (card.type === 'aviso') return priority === 'urgente' ? 'alerta' : 'suave';
  if (card.type === 'perfil' || card.type === 'aprobacion') return 'hondo';
  return 'info';
}

/** «Comprueba si salió tu comentario» for an uncertain action; the backend's title otherwise. */
const UNCERTAIN_TITLE: Record<string, string> = {
  'INT-03': 'Comprueba si salió tu comentario',
  'INT-04': 'Comprueba si salió tu respuesta',
  'INT-02': 'Comprueba si salió tu reacción',
  'CONT-09': 'Comprueba si salió tu publicación',
  'RED-01': 'Comprueba si se aplicó el seguimiento',
  'RED-02': 'Comprueba si salió tu invitación',
  'RED-04': 'Comprueba si se aceptó la invitación',
};

export function cardTitle(card: TurnoCard): string {
  if (card.question?.question) return card.question.question;
  if (card.attempt && UNCERTAIN_TITLE[card.attempt.capability]) return UNCERTAIN_TITLE[card.attempt.capability]!;
  return card.title;
}

/** A notice's text: the LinkedIn permission that expires says when; any other notice, its body. */
export function noticeText(card: TurnoCard): string {
  const extra = extras(card);
  if (card.id === 'linkedin_expiring' && extra.expires_at && typeof extra.days_left === 'number') {
    const days = extra.days_left;
    return `El permiso para publicar caduca el ${longDate(extra.expires_at)} (${days === 1 ? 'queda 1 día' : `quedan ${days} días`}). LinkedIn no deja renovarlo solo.`;
  }
  return card.body ?? '';
}

/** The last message the other person wrote in a conversation card. */
export function lastInbound(card: TurnoCard) {
  return [...(card.conversation?.messages ?? [])].reverse().find((message) => !message.from_me);
}

/**
 * What a collapsed card says under its title (Gustavo, 11/11/2026: «solo el título con una mini descripción»): the text
 * it is about (the message, the comment to approve or check) or its body. Shown in two lines; the rest is under «Ver más».
 */
export function cardSummary(card: TurnoCard): string {
  if (card.conversation) {
    const last = lastInbound(card);
    return last ? `“${messageText(last)}”` : (card.body ?? '');
  }
  if (card.message) return `“${card.message.text}”`;
  if (card.day_request) return card.body ?? '';
  if (card.attempt?.text) return `“${card.attempt.text}”`;
  if (card.approval?.text) return `“${card.approval.text}”`;
  if (card.question) return card.question.purpose || card.body || '';
  return noticeText(card);
}

/** About two lines of body text on a phone: a shorter summary is already the whole text. */
export const SUMMARY_FITS = 90;

/**
 * Whether «Ver más» shows something the collapsed card does not: the details of a referent decision, a check, a
 * conversation or an approval, or a summary too long for two lines. The profile proposal has its own «Abrir».
 */
export function hasDetails(card: TurnoCard): boolean {
  if (card.profile_id) return cardSummary(card).length > SUMMARY_FITS;
  if (card.referent_change || card.referent_experiment || card.attempt || card.conversation || card.message || card.approval || card.day_request) return true;
  return cardSummary(card).length > SUMMARY_FITS;
}

export const isMachineResume = (action: TurnoAction) => action.endpoint === '/api/v1/operador/control' && action.body?.paused === false;
export const isResolve = (action: TurnoAction) => Boolean(action.endpoint?.endsWith('/resolve'));
export const isConversationClose = (action: TurnoAction) => Boolean(action.endpoint?.startsWith('/api/v1/conversaciones/') && action.endpoint.endsWith('/cerrar'));
/** «Hecho, le escribí» / «No escribirle» on a suggested message (INT-04): the team never sends it. */
export const isMessageClose = (action: TurnoAction) => Boolean(action.endpoint?.startsWith('/api/v1/respuestas/') && action.endpoint.endsWith('/mensaje'));
/** «Sí, el viernes 13…» / «Dejarlo el lunes 16» on a day he asked for that already had a post. */
export const isDayDecision = (action: TurnoAction) => Boolean(action.endpoint?.startsWith('/api/v1/capturas/') && action.endpoint.endsWith('/fecha'));
export const isApprove = (action: TurnoAction) => Boolean(action.endpoint?.startsWith('/api/v1/operador/actions/') && action.endpoint.endsWith('/approve'));
export const isReject = (action: TurnoAction) => Boolean(action.endpoint?.startsWith('/api/v1/operador/actions/') && action.endpoint.endsWith('/reject'));

export function successMessage(action: TurnoAction): string {
  if (isResolve(action)) return action.body?.outcome === 'failed' ? 'Anotado: no se aplicó' : 'Anotado: se aplicó';
  if (isConversationClose(action)) return action.body?.how === 'no_responder' ? 'Anotado: no responderás' : 'Anotado: respondiste';
  if (isMessageClose(action)) return action.body?.how === 'no' ? 'Anotado: no le escribirás' : 'Anotado: le escribiste';
  if (isDayDecision(action)) return action.body?.decision === 'mismo_dia' ? 'Listo: sale el día que pediste' : 'Se queda en el siguiente día libre';
  if (isApprove(action)) return APPROVED_MESSAGE;
  if (isReject(action)) return 'Vetada';
  if (isMachineResume(action)) return 'Máquina reanudada';
  if (action.endpoint?.endsWith('/pause') && action.body?.paused === false) return 'Cuenta reanudada';
  if (action.endpoint?.startsWith('/api/v1/resultados/resumen-semanal/') && action.endpoint.endsWith('/descartar')) return 'Resumen descartado';
  return 'Hecho';
}

export interface ModalSpec {
  title: string;
  text: string | null;
  note: 'required' | 'optional';
  noteLabel: string;
  placeholder?: string;
}

/** Which actions ask first: a required note (uncertain actions, «Vetar» and any `note_required`) or the optional reason to resume.
 * `card` gives «Vetar» its consequence (a network action discards the person for good). */
export function modalFor(action: TurnoAction, card?: TurnoCard): ModalSpec | null {
  if (isReject(action)) {
    const approval = card?.approval;
    return {
      title: approval?.piece_id ? 'Vetar la pieza' : 'Vetar la acción',
      text: vetoConsequence(approval?.piece_id ? { actionId: approval.proposal_id, kind: 'pieza' } : { actionId: approval?.proposal_id ?? '', kind: 'accion', network: approval?.network, person: approval?.target?.name }),
      note: 'required',
      noteLabel: 'Nota',
      placeholder: 'Por qué no debe salir',
    };
  }
  if (isResolve(action) && action.note_required) {
    const applied = action.body?.outcome !== 'failed';
    return {
      title: applied ? 'Confirmar que se aplicó' : 'Confirmar que no se aplicó',
      text: applied ? 'La acción queda como hecha en LinkedIn.' : 'La acción queda como no aplicada.',
      note: 'required',
      noteLabel: 'Qué comprobaste',
      placeholder: applied ? 'Por ejemplo: el comentario aparece en el post.' : 'Por ejemplo: no aparece en el post ni en mi actividad.',
    };
  }
  if (action.note_required) return { title: action.label, text: null, note: 'required', noteLabel: 'Nota' };
  if (action.note_optional) {
    return {
      title: action.label,
      text: isConversationClose(action)
        ? 'La tarjeta sale de la Bandeja hasta que te vuelva a escribir. Nadie le responde por ti.'
        : isMessageClose(action)
          ? 'La tarjeta sale de la Bandeja. Nadie le escribe por ti.'
          : null,
      note: 'optional',
      noteLabel: 'Motivo',
    };
  }
  if (isMachineResume(action)) {
    return { title: 'Reanudar la máquina', text: 'El equipo vuelve a trabajar dentro de la ventana horaria y los topes.', note: 'optional', noteLabel: 'Motivo' };
  }
  return null;
}

/** The body to POST: the machine takes its optional reason as `reason`, the rest as `note`. */
export function withNote(action: TurnoAction, note: string): { action: TurnoAction; note?: string } {
  if (isMachineResume(action)) return { action: { ...action, body: { ...action.body, ...(note ? { reason: note } : {}) } } };
  return note ? { action, note } : { action };
}

/** The primary action first, then the rest in order: first and second are buttons, the rest ghost links. */
export function orderedActions(actions: readonly TurnoAction[]): TurnoAction[] {
  if (!actions.length) return [];
  const primaryIndex = Math.max(
    0,
    actions.findIndex((action) => action.primary),
  );
  return [actions[primaryIndex]!, ...actions.filter((_, index) => index !== primaryIndex)];
}

// ---------------------------------------------------------------- swipe

/** What a committed swipe does. `run` POSTs the action (or opens its modal first); `postpone` is «Más tarde». */
export type SwipeIntent = { kind: 'run'; action: TurnoAction; label: string } | { kind: 'postpone'; questionId: string; label: string };

export interface SwipeIntents {
  /** Swipe right: the card's primary action («done»). */
  right: SwipeIntent | null;
  /** Swipe left: «Más tarde» (questions; the other cards have no postpone in the API). */
  left: SwipeIntent | null;
}

/**
 * Right runs the card's first request action, the primary one when it is a request (links and the
 * opportunity form are left to their buttons): «Hecho, respondí» on a conversation, «Sí, se aplicó»
 * (with its note) on an uncertain action. Left postpones a question 3 days. Expired cards and
 * questions have no «done» swipe: a question needs its answer typed.
 */
export function swipeIntents(card: TurnoCard, expired = false): SwipeIntents {
  if (expired) return { right: null, left: null };
  if (card.question) {
    return { right: null, left: card.question.state === 'open' || !card.question.state ? { kind: 'postpone', questionId: card.question.id, label: 'Más tarde' } : null };
  }
  // A second post that day is a decision he takes with a tap on its button, never with a swipe.
  if (card.day_request) return { right: null, left: null };
  const runnable = orderedActions(card.actions ?? []).find((action) => action.endpoint && !action.href && !action.opportunity) ?? null;
  return { right: runnable ? { kind: 'run', action: runnable, label: runnable.label } : null, left: null };
}
