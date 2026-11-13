// What each calendar event and each activity item says, per DISENO-VISTAS «Elementos de la línea de tiempo».
import type { ActividadTipo, ActivityItem, CalendarEvent, CalendarLayer, CalendarioDay } from '../api/types';
import { CALENDAR_LAYERS } from '../api/types';
import { dayOf, daysBetween, relativeDayInSentence } from './dates';
import { CONTACT_ROLE_LABEL, excerpt, formatNumber, formatTime } from './format';
import type { Tone } from './tone';
import { turnoAnchor } from './turno';

export const LAYER_LABEL: Record<CalendarLayer, string> = {
  tuyo: 'Tuyo',
  publicaciones: 'Publicaciones',
  red: 'Red',
  conversaciones: 'Conversaciones',
  sistema: 'Sistema',
};

/** When they do not all fit: Tuyo > Sistema > Publicaciones > Conversaciones > Red. */
export const LAYER_PRIORITY: readonly CalendarLayer[] = ['tuyo', 'sistema', 'publicaciones', 'conversaciones', 'red'];

export function isLayer(value: string): value is CalendarLayer {
  return (CALENDAR_LAYERS as readonly string[]).includes(value);
}

const priority = (layer: CalendarLayer) => LAYER_PRIORITY.indexOf(layer);

/** Important events of the visible layers, by layer priority and then time (as the API sends them). */
export function importantEvents(day: CalendarioDay | undefined, visible: ReadonlySet<CalendarLayer>): CalendarEvent[] {
  if (!day) return [];
  return day.events
    .filter((event) => event.important && visible.has(event.layer))
    .sort((a, b) => priority(a.layer) - priority(b.layer) || String(a.at ?? '').localeCompare(String(b.at ?? '')));
}

/** The same events in time order: all-day ones first, then by hour. */
export function chronological(events: CalendarEvent[]): CalendarEvent[] {
  return [...events].sort((a, b) => {
    if (!a.at && !b.at) return 0;
    if (!a.at) return -1;
    if (!b.at) return 1;
    return a.at.localeCompare(b.at);
  });
}

/** One dot per visible layer with important events, in priority order. */
export function dayDots(day: CalendarioDay | undefined, visible: ReadonlySet<CalendarLayer>): CalendarLayer[] {
  const layers = new Set(importantEvents(day, visible).map((event) => event.layer));
  return LAYER_PRIORITY.filter((layer) => layers.has(layer));
}

export function isPieceEvent(event: CalendarEvent): boolean {
  return event.kind.startsWith('piece_');
}

export function pieceIdFromLink(link: string | null | undefined): string | null {
  const match = /^\/calendario\/pieza\/([^/?#]+)/.exec(link ?? '');
  return match ? decodeURIComponent(match[1]!) : null;
}

/** The day's piece event (one per day: a vetoed piece leaves the day without publication). */
export function pieceOfDay(day: CalendarioDay | undefined): CalendarEvent | null {
  return day?.events.find(isPieceEvent) ?? null;
}

/** Every post of the day, by hour: one, or two when Gustavo authorized a second post on a day he asked for. */
export function piecesOfDay(day: CalendarioDay | undefined): CalendarEvent[] {
  return chronological((day?.events ?? []).filter(isPieceEvent));
}

/** Something of Gustavo's still pending that day (the orange «te toca» dot of a month cell). */
export function hasPendingTuyo(day: CalendarioDay | undefined): boolean {
  return Boolean(day?.events.some((event) => event.layer === 'tuyo' && event.kind !== 'resolved'));
}

/** The proposal behind an event id `action_uncertain:<proposal>:<day>`. */
function eventRef(event: CalendarEvent): string {
  const parts = event.id.split(':');
  return parts.length >= 3 ? parts.slice(1, -1).join(':') : event.id;
}

/** The main sentence of a calendar event. */
export function eventSentence(event: CalendarEvent): string {
  const thesis = event.title;
  switch (event.kind) {
    case 'piece_published':
      return `Publicaste: ${thesis}`;
    case 'piece_scheduled':
      return `Programada: ${thesis}`;
    case 'piece_preparing':
      return thesis && thesis !== 'Publicación del día' ? `Preparándose: ${thesis}` : 'El equipo prepara la pieza del día';
    case 'piece_publishing':
      return `Publicándose: ${thesis}`;
    case 'piece_awaiting_approval':
      return `Pendiente de aprobación: ${thesis}`;
    case 'piece_skipped':
      return 'Ese día no hubo publicación';
    case 'piece_blocked':
      return 'El verificador bloqueó la pieza';
    case 'piece_discarded':
      return 'La política no aprobó la pieza';
    case 'piece_vetoed':
      return 'Vetaste la pieza';
    case 'piece_failed':
      return 'La publicación falló';
    case 'piece_uncertain':
      return 'No se sabe si salió la pieza';
    case 'action_uncertain':
      return `${thesis.replace(/ incierta$/i, '')}: no se sabe si salió`;
    case 'action_failed':
      return `${thesis.replace(/ fallida$/i, '')}: falló`;
    case 'resolved':
      return `Respondiste: ${thesis}`;
    default:
      return thesis;
  }
}

/** Short text for a month or week chip. */
export function eventShort(event: CalendarEvent): string {
  switch (event.kind) {
    case 'piece_published':
      return `Post: ${event.title}`;
    case 'piece_skipped':
      return 'Sin post';
    case 'piece_blocked':
      return 'Post bloqueado';
    case 'piece_vetoed':
      return 'Post vetado';
    case 'piece_failed':
      return 'Post fallido';
    case 'piece_uncertain':
      return 'Post incierto';
    case 'piece_discarded':
      return 'Post descartado';
    case 'piece_preparing':
      return 'Preparándose';
    default:
      return isPieceEvent(event) ? `Post: ${event.title}` : eventSentence(event);
  }
}

function names(people: CalendarEvent['people']): string {
  const list = (people ?? []).map((person) => person.name).filter(Boolean);
  if (list.length <= 1) return list[0] ?? '';
  return `${list.slice(0, -1).join(', ')} y ${list[list.length - 1]}`;
}

function roles(people: CalendarEvent['people']): string {
  const list = (people ?? []).map((person) => (person.role ? (CONTACT_ROLE_LABEL[person.role] ?? person.role) : null)).filter((r): r is string => Boolean(r));
  if (!list.length) return '';
  const lower = list.map((role, index) => (index === 0 ? role : role.toLowerCase()));
  return lower.length === 1 ? lower[0]! : `${lower.slice(0, -1).join(', ')} y ${lower[lower.length - 1]}`;
}

/** The line under the sentence. */
export function eventSub(event: CalendarEvent): string | null {
  switch (event.kind) {
    case 'piece_published':
      return typeof event.impressions === 'number' ? `${formatNumber(event.impressions, 0)} impresiones` : null;
    case 'piece_skipped':
      return event.skip_reason || null;
    case 'piece_blocked':
    case 'piece_discarded':
    case 'piece_vetoed':
    case 'piece_failed':
    case 'piece_uncertain':
      return event.title && event.title !== 'Publicación del día' ? event.title : null;
    case 'connection_fit':
      return roles(event.people) || ((event.people?.length ?? 0) > 1 ? names(event.people) : null);
    case 'invite_expected':
      return [names(event.people), 'Estimación sujeta a los topes'].filter(Boolean).join(' · ');
    case 'linkedin_expiry':
      return 'Reconéctalo antes desde Tu turno';
    default: {
      const detail = (event as CalendarEvent & { detail?: string }).detail;
      return detail || null;
    }
  }
}

const KIND_BADGE: Record<string, { label: string; tone: Tone }> = {
  piece_scheduled: { label: 'Programada', tone: 'info' },
  piece_preparing: { label: 'Preparándose', tone: 'info' },
  piece_publishing: { label: 'Publicándose', tone: 'warn' },
  piece_awaiting_approval: { label: 'Pendiente', tone: 'warn' },
  piece_blocked: { label: 'Bloqueada', tone: 'bad' },
  piece_failed: { label: 'Fallida', tone: 'bad' },
  piece_uncertain: { label: 'Incierta', tone: 'bad' },
  piece_vetoed: { label: 'Vetada', tone: 'muted' },
  piece_discarded: { label: 'Descartada', tone: 'muted' },
  action_uncertain: { label: 'Incierta', tone: 'bad' },
  action_failed: { label: 'Fallida', tone: 'bad' },
  linkedin_expiry: { label: 'Caduca', tone: 'warn' },
  linkedin_expired: { label: 'Caducado', tone: 'bad' },
  invite_expected: { label: 'Estimación', tone: 'muted' },
};

/** Badge only when the state is not a normal success. */
export function eventBadge(event: CalendarEvent): { label: string; tone: Tone } | null {
  return KIND_BADGE[event.kind] ?? null;
}

export function isCritical(event: CalendarEvent): boolean {
  return eventBadge(event)?.tone === 'bad';
}

/** In-app destination; an uncertain action goes straight to its card in Tu turno. */
export function eventLink(event: CalendarEvent): string | null {
  if (event.kind === 'action_uncertain') return `/tu-turno#${turnoAnchor(`uncertain:${eventRef(event)}`)}`;
  return event.link && event.link.startsWith('/') ? event.link : null;
}

export function eventTime(event: CalendarEvent, timeZone: string): string | null {
  return event.at ? formatTime(event.at, timeZone) : null;
}

// ---------------------------------------------------------------- summary of the day

export interface SummaryPart {
  key: string;
  text: string;
  tipo: ActividadTipo;
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** «1 post · 6 comentarios · 3 reacciones · 4 seguidos · 2 invitaciones · 1 conexión nueva que encaja». */
export function summaryParts(day: CalendarioDay | undefined): SummaryPart[] {
  if (!day) return [];
  const posts = day.events.filter((event) => event.kind === 'piece_published').length;
  const c = day.counts;
  const parts: (SummaryPart | null)[] = [
    posts ? { key: 'posts', text: plural(posts, 'post', 'posts'), tipo: 'publicaciones' } : null,
    c.comments ? { key: 'comments', text: plural(c.comments, 'comentario', 'comentarios'), tipo: 'comentarios' } : null,
    c.reactions ? { key: 'reactions', text: plural(c.reactions, 'reacción', 'reacciones'), tipo: 'reacciones' } : null,
    c.follows ? { key: 'follows', text: plural(c.follows, 'seguido', 'seguidos'), tipo: 'red' } : null,
    c.invites ? { key: 'invites', text: plural(c.invites, 'invitación', 'invitaciones'), tipo: 'red' } : null,
    c.accepts ? { key: 'accepts', text: plural(c.accepts, 'invitación aceptada', 'invitaciones aceptadas'), tipo: 'red' } : null,
    c.connections_fit ? { key: 'connections', text: plural(c.connections_fit, 'conexión nueva que encaja', 'conexiones nuevas que encajan'), tipo: 'red' } : null,
  ];
  return parts.filter((part): part is SummaryPart => part !== null);
}

/** Small actions of the day (comments, reactions, follows, invitations, accepts), for the week's all-day strip. */
export function smallActions(day: CalendarioDay | undefined): number {
  if (!day) return 0;
  const c = day.counts;
  return c.comments + c.reactions + c.follows + c.invites + c.accepts;
}

// ---------------------------------------------------------------- activity items (Lista, «Ver todo lo del día»)

export const TIPOS: readonly { value: ActividadTipo; label: string }[] = [
  { value: 'todo', label: 'Todo' },
  { value: 'publicaciones', label: 'Publicaciones' },
  { value: 'comentarios', label: 'Comentarios' },
  { value: 'reacciones', label: 'Reacciones' },
  { value: 'red', label: 'Red' },
];

export function isTipo(value: string | null): value is ActividadTipo {
  return TIPOS.some((tipo) => tipo.value === value);
}

const REACTION_LABEL: Record<string, string> = {
  linkedin_like: 'Recomiendo',
  linkedin_celebrate: 'Celebro',
  linkedin_support: 'Apoyo',
  linkedin_love: 'Me encanta',
  linkedin_insightful: 'Me interesa',
  linkedin_funny: 'Me divierte',
};

export function reactionLabel(reaction: string | null | undefined): string {
  if (!reaction) return '';
  return REACTION_LABEL[reaction] ?? reaction.replace(/^linkedin_/, '');
}

/** «Incierta» and «Fallida» in alerta; what did not go out in gris; «En curso» in info. */
export function stateBadge(item: ActivityItem): { label: string; tone: Tone } | null {
  const label = item.state_label;
  if (!label) return null;
  if (item.state === 'uncertain' || item.state === 'failed') return { label, tone: 'bad' };
  if (item.state === 'executing' || item.state === 'sent') return { label, tone: 'info' };
  return { label, tone: 'muted' };
}

/** Calendar layer of an item: important ones get their layer colour, the small ones stay grey. */
export function itemLayer(item: ActivityItem): CalendarLayer | null {
  if (item.state === 'uncertain' || item.state === 'failed') return 'sistema';
  if (item.capability === 'CONT-09') return 'publicaciones';
  if (item.important && String(item.capability).startsWith('RED-')) return 'red';
  return null;
}

/** The main sentence of an activity item. */
export function itemSentence(item: ActivityItem): string {
  const name = item.target?.name || '';
  switch (item.capability) {
    case 'INT-03':
      return name ? `Comentaste en el post de ${name}` : 'Comentaste en un post';
    case 'INT-04':
      return `Respondiste a ${name || 'un comentario'} en tu post`;
    case 'INT-02': {
      const reaction = reactionLabel(item.reaction);
      if (item.target?.kind === 'comment') return `Reaccionaste${reaction ? ` ${reaction}` : ''} al comentario${name ? ` de ${name}` : ''} en tu post`;
      return `Reaccionaste${reaction ? ` ${reaction}` : ''} al post${name ? ` de ${name}` : ''}`;
    }
    case 'CONT-09': {
      const first = (item.text ?? '').split('\n').find((line) => line.trim());
      return first ? `Publicaste: ${excerpt(first, 120)}` : 'Publicaste la pieza del día';
    }
    case 'RED-01':
      return `Seguiste a ${name || 'una persona'}`;
    case 'RED-02':
      return `Invitaste a ${name || 'una persona'} (sin nota)`;
    case 'RED-04':
      return `Aceptaste la invitación de ${name || 'una persona'}`;
    default:
      return name ? `${item.label}: ${name}` : item.label;
  }
}

/** Headline and role of a person, or the state's explanation. */
export function itemSub(item: ActivityItem): string | null {
  if (item.state === 'failed' && item.execution_note) return item.execution_note;
  if (item.state === 'rejected' && item.decision_note) return `Tu nota: ${item.decision_note}`;
  if (item.state === 'discarded') {
    const reason = item.decision_note || item.review?.reasons?.join(' · ');
    if (reason) return reason;
  }
  const target = item.target;
  if (target?.kind === 'person') {
    const role = target.role ? (CONTACT_ROLE_LABEL[target.role] ?? target.role) : '';
    return [target.headline, role].filter(Boolean).join(' · ') || null;
  }
  return null;
}

/** Where the item leads inside the app. */
export function itemLink(item: ActivityItem): { to: string; label: string } | null {
  if (item.state === 'uncertain') return { to: `/tu-turno#${turnoAnchor(`uncertain:${item.id}`)}`, label: 'Resuélvela en Tu turno' };
  if (item.capability === 'CONT-09' && item.piece_id) return { to: `/calendario/pieza/${encodeURIComponent(item.piece_id)}`, label: 'Ver la pieza' };
  if (item.target?.kind === 'person' && item.target.contact_id) return { to: `/personas/${encodeURIComponent(item.target.contact_id)}`, label: 'Ver ficha' };
  if (item.target?.kind === 'comment' && item.target.piece_id) return { to: `/calendario/pieza/${encodeURIComponent(item.target.piece_id)}`, label: 'Ver el post' };
  return null;
}

// ---------------------------------------------------------------- day panel and queued actions

/** Beyond this, the day panel says «Todavía no hay nada programado tan lejos». */
export const FAR_FUTURE_DAYS = 15;

export type DayKind = 'hoy' | 'pasado' | 'programado';

/** Hoy, Pasado or Programado (the badge of the day panel). */
export function dayKind(date: string, today: string): DayKind {
  const diff = daysBetween(today, date);
  return diff === 0 ? 'hoy' : diff < 0 ? 'pasado' : 'programado';
}

export function formatHours(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toLocaleString('es-CO', { maximumFractionDigits: 1 });
}

/** «6 h» or «unas horas»: how long before its hour the team prepares each piece. */
export function leadText(leadHours: number | null | undefined): string {
  return leadHours ? `${formatHours(leadHours)} h` : 'unas horas';
}

/** «Comentario en el post de Elena Prueba»: an approved action waiting for the window or the spacing. */
export function queuedSentence(item: ActivityItem): string {
  const name = item.target?.name || '';
  switch (item.capability) {
    case 'INT-03':
      return name ? `Comentario en el post de ${name}` : 'Comentario en un post';
    case 'INT-04':
      return `Respuesta a ${name || 'un comentario'} en tu post`;
    case 'INT-02': {
      const reaction = reactionLabel(item.reaction);
      if (item.target?.kind === 'comment') return `Reacción${reaction ? ` ${reaction}` : ''} al comentario${name ? ` de ${name}` : ''} en tu post`;
      return `Reacción${reaction ? ` ${reaction}` : ''} al post${name ? ` de ${name}` : ''}`;
    }
    case 'RED-01':
      return `Seguir a ${name || 'una persona'}`;
    case 'RED-02':
      return `Invitar a ${name || 'una persona'} (sin nota)`;
    case 'RED-04':
      return `Aceptar la invitación de ${name || 'una persona'}`;
    default:
      return name ? `${item.label}: ${name}` : item.label;
  }
}

/** «Saldrá cuando abra la ventana, mañana a las 08:00». */
export function queuedWhen(expectedAt: string | null, { today, timeZone, windowOpen }: { today: string; timeZone: string; windowOpen: boolean | undefined }): string {
  if (!expectedAt) return 'Saldrá en cuanto lo permitan la ventana y el espaciado';
  const day = dayOf(expectedAt, timeZone) ?? today;
  const when = `${relativeDayInSentence(day, today)} a las ${formatTime(expectedAt, timeZone)}`;
  return windowOpen === false ? `Saldrá cuando abra la ventana, ${when}` : `Saldrá ${when}, según el espaciado`;
}

/** The toast after «Aprobar» (Tu turno, «En cola» and the piece). */
export const APPROVED_MESSAGE = 'Aprobada. Sale cuando lo permitan la ventana y los topes.';

/** «Espera tu aprobación · caduca mañana a las 14:05»: a queued row that waits for Gustavo. */
export function awaitingSentence(expiresAt: string | null | undefined, { today, timeZone }: { today: string; timeZone: string }): string {
  if (!expiresAt) return 'Espera tu aprobación';
  const day = dayOf(expiresAt, timeZone) ?? today;
  return `Espera tu aprobación · caduca ${relativeDayInSentence(day, today)} a las ${formatTime(expiresAt, timeZone)}`;
}

export function isNetworkCapability(capability: string | null | undefined): boolean {
  return String(capability).startsWith('RED-');
}

// ---------------------------------------------------------------- veto

export interface VetoTarget {
  /** The action to reject: the piece's CONT-09 or a queued action. */
  actionId: string;
  kind: 'pieza' | 'accion';
  /** «a las 09:00»: when the piece would go out. */
  when?: string;
  /** A network action (RED-*): vetoing it discards the person for good. */
  network?: boolean;
  person?: string | null;
}

/** What the veto dialog says will happen. */
export function vetoConsequence(target: VetoTarget): string {
  if (target.kind === 'pieza') return `La pieza no saldrá${target.when ? ` ${target.when}` : ''} y ese día quedará sin publicación. Queda registrada con tu nota.`;
  if (target.network) return `No saldrá, y vetar una acción de red descarta a ${target.person || 'esa persona'} para siempre: el equipo no la volverá a proponer.`;
  return 'La acción no saldrá. Queda registrada con tu nota.';
}

// ---------------------------------------------------------------- screen state (vista, layers)

export type Vista = 'mes' | 'semana' | 'lista';

export const VISTAS: readonly { value: Vista; label: string }[] = [
  { value: 'mes', label: 'Mes' },
  { value: 'semana', label: 'Semana' },
  { value: 'lista', label: 'Lista' },
];

export const DEFAULT_VISTA: Vista = 'semana';

export function isVista(value: string | null | undefined): value is Vista {
  return VISTAS.some((option) => option.value === value);
}

/** The `capas` param: null when every available layer is on (the default), else the visible ones in order. */
export function toggledLayers(visible: ReadonlySet<CalendarLayer>, available: readonly CalendarLayer[], layer: CalendarLayer): string | null {
  const next = new Set(visible);
  if (next.has(layer)) next.delete(layer);
  else next.add(layer);
  const all = available.every((l) => next.has(l));
  return all ? null : CALENDAR_LAYERS.filter((l) => next.has(l)).join(',');
}

/** Layers the backend offers (not `false`), and those of them the `capas` param leaves on. */
export function visibleLayers(layers: Partial<Record<CalendarLayer, boolean | 'parcial'>> | undefined, capas: ReadonlySet<string> | null): { available: CalendarLayer[]; visible: ReadonlySet<CalendarLayer> } {
  const available = CALENDAR_LAYERS.filter((layer) => layers?.[layer] !== false);
  return { available, visible: new Set(available.filter((layer) => (capas ? capas.has(layer) : true))) };
}

/** A month with no event and no count on any of its own days («No hay nada registrado en este mes»). */
export function monthIsEmpty(days: readonly CalendarioDay[], month: string): boolean {
  return days.filter((day) => day.date.slice(0, 7) === month).every((day) => !day.events.length && !Object.values(day.counts).some(Boolean));
}
