// Pure rules of Tu turno (FUNCIONES-NUEVAS rev 18 «Tu turno: prioridades y estados»), kept apart so
// they can be tested without rendering. The backend sends `priority`, `state` and `items`; until it
// does, the same rules are derived here from `critical`, `tone`, `deadline` and the question flags.
import type { DoneToday, MemoryFact, TuTurno, TurnoCard, TurnoPriority, TurnoState } from '../api/types';

const LOCALE = 'es-CO';
const HOUR = 3_600_000;
const DAY = 24 * HOUR;

/** Anchor id of a Tu turno card, so other views can link to it: `/tu-turno#${turnoAnchor(card.id)}`. */
export function turnoAnchor(cardId: string): string {
  return `turno-${cardId.replace(/[^A-Za-z0-9_-]/g, '-')}`;
}

export const PRIORITIES: readonly TurnoPriority[] = ['urgente', 'importante', 'cuando_puedas'];

export const PRIORITY_LABEL: Record<TurnoPriority, string> = {
  urgente: 'Urgente',
  importante: 'Importante',
  cuando_puedas: 'Cuando puedas',
};

/** Extra fields some notices carry (linkedin_expiring, machine_paused). */
export interface CardExtras {
  expires_at?: string | null;
  days_left?: number | null;
  stopped_by?: string | null;
}

export function extras(card: TurnoCard): CardExtras {
  return card as TurnoCard & CardExtras;
}

function time(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const value = new Date(iso).getTime();
  return Number.isNaN(value) ? null : value;
}

/** The card's priority; derived when the backend does not send it yet (escalates under 48 h). */
export function priorityOf(card: TurnoCard, now: number = Date.now()): TurnoPriority {
  if (card.priority) return card.priority;
  if (card.critical) return 'urgente';
  const deadline = time(card.deadline);
  if (deadline !== null && deadline > now && deadline - now < 48 * HOUR) return 'importante';
  if (card.tone === 'warn' || card.tone === 'bad') return 'importante';
  return 'cuando_puedas';
}

/** The card's state; for `later` cards without one, an expired question is caducada and the rest pospuesta. */
export function stateOf(card: TurnoCard, inLater = false): TurnoState {
  if (card.state) return card.state;
  if (!inLater) return 'vista';
  return card.question?.expired ? 'caducada' : 'pospuesta';
}

const RANK: Record<TurnoPriority, number> = { urgente: 0, importante: 1, cuando_puedas: 2 };

/** Priority, then nearest deadline (cards with one first), then most recent. */
export function compareCards(a: TurnoCard, b: TurnoCard, now: number = Date.now()): number {
  const rank = RANK[priorityOf(a, now)] - RANK[priorityOf(b, now)];
  if (rank) return rank;
  const da = time(a.deadline);
  const db = time(b.deadline);
  if (da !== null && db !== null && da !== db) return da - db;
  if (da !== null && db === null) return -1;
  if (da === null && db !== null) return 1;
  return (time(b.created_at) ?? 0) - (time(a.created_at) ?? 0);
}

/** Active cards: `items` when the backend sends it (already ordered); otherwise every section, ordered here. */
export function activeCards(data: TuTurno, now: number = Date.now()): TurnoCard[] {
  if (Array.isArray(data.items)) return data.items;
  const all = [
    ...(data.alerts ?? []),
    ...(data.questions ?? []),
    ...(data.tasks?.perfil ?? []),
    ...(data.tasks?.conversaciones ?? []),
    ...(data.tasks?.resumen ?? []),
  ];
  return all.sort((a, b) => compareCards(a, b, now));
}

export interface PriorityGroup {
  priority: TurnoPriority;
  cards: TurnoCard[];
}

/** Urgente → Importante → Cuando puedas, keeping the order inside each group. Empty groups are left out. */
export function groupByPriority(cards: readonly TurnoCard[], now: number = Date.now()): PriorityGroup[] {
  return PRIORITIES.map((priority) => ({ priority, cards: cards.filter((card) => priorityOf(card, now) === priority) })).filter(
    (group) => group.cards.length > 0,
  );
}

/** «1 urgente · 2 importantes · 3 cuando puedas». */
export function prioritySummary(groups: readonly PriorityGroup[]): string {
  return groups
    .map(({ priority, cards }) => {
      const n = cards.length;
      if (priority === 'urgente') return `${n} ${n === 1 ? 'urgente' : 'urgentes'}`;
      if (priority === 'importante') return `${n} ${n === 1 ? 'importante' : 'importantes'}`;
      return `${n} cuando puedas`;
    })
    .join(' · ');
}

/** Postponed and expired cards of `later`. */
export function splitLater(later: readonly TurnoCard[] | undefined): { postponed: TurnoCard[]; expired: TurnoCard[] } {
  const postponed: TurnoCard[] = [];
  const expired: TurnoCard[] = [];
  for (const card of later ?? []) (stateOf(card, true) === 'caducada' ? expired : postponed).push(card);
  return { postponed, expired };
}

// ---------------------------------------------------------------- dates

function startOfDay(value: number): number {
  const date = new Date(value);
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

/** Calendar days from today (device time): 0 today, -1 yesterday, 1 tomorrow. */
export function dayOffset(iso: string | null | undefined, now: number = Date.now()): number | null {
  const value = time(iso);
  if (value === null) return null;
  return Math.round((startOfDay(value) - startOfDay(now)) / DAY);
}

export function clock(iso: string | null | undefined): string {
  const value = time(iso);
  if (value === null) return '';
  return new Date(value).toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', hour12: false });
}

function weekday(value: number): string {
  return new Date(value).toLocaleDateString(LOCALE, { weekday: 'long' });
}

/** «5 nov». */
export function shortDate(iso: string | null | undefined): string {
  const value = time(iso);
  if (value === null) return '';
  return new Date(value).toLocaleDateString(LOCALE, { day: 'numeric', month: 'short' }).replace('.', '');
}

/** «lunes 9 de noviembre». */
export function longDate(iso: string | null | undefined): string {
  const value = time(iso);
  if (value === null) return '';
  const date = new Date(value);
  return `${weekday(value)} ${date.getDate()} de ${date.toLocaleDateString(LOCALE, { month: 'long' })}`;
}

/** «hoy, 10:12», «ayer, 18:42», «mañana, 09:00», «jueves, 09:00» or «5 nov, 18:42». */
export function dayAndTime(iso: string | null | undefined, now: number = Date.now()): string {
  const offset = dayOffset(iso, now);
  if (offset === null) return '';
  const hour = clock(iso);
  if (offset === 0) return `hoy, ${hour}`;
  if (offset === -1) return `ayer, ${hour}`;
  if (offset === 1) return `mañana, ${hour}`;
  if (offset > 1 && offset < 7) return `${weekday(time(iso)!)}, ${hour}`;
  return `${shortDate(iso)}, ${hour}`;
}

/** «antes de las 15:00», «antes de mañana a las 09:00», «antes del jueves 09:00», «antes del 12 nov 09:00». */
export function beforePhrase(iso: string, now: number = Date.now()): string {
  const offset = dayOffset(iso, now) ?? 0;
  const hour = clock(iso);
  if (offset === 0) return `antes de las ${hour}`;
  if (offset === 1) return `antes de mañana a las ${hour}`;
  if (offset > 1 && offset < 7) return `antes del ${weekday(time(iso)!)} ${hour}`;
  return `antes del ${shortDate(iso)} ${hour}`;
}

export interface DeadlineInfo {
  text: string;
  /** Less than 24 h left: shown in alerta. */
  soon: boolean;
}

/** The «Plazo» line of a card, or null when it has none. */
export function deadlineInfo(card: TurnoCard, now: number = Date.now()): DeadlineInfo | null {
  const deadline = time(card.deadline);
  if (deadline === null) return null;
  const left = deadline - now;
  const soon = left > 0 && left < DAY;
  const days = extras(card).days_left;
  if (card.id === 'linkedin_expiring' && typeof days === 'number') {
    return { text: days <= 0 ? 'Plazo: caduca hoy' : `Plazo: caduca en ${days} ${days === 1 ? 'día' : 'días'}`, soon };
  }
  if (left <= 0) return { text: `El plazo era ${dayAndTime(card.deadline, now)}`, soon: false };
  if (card.type === 'pregunta') return { text: `Útil ${beforePhrase(card.deadline!, now)}`, soon };
  return { text: `Plazo: ${beforePhrase(card.deadline!, now)}`, soon };
}

/** «Creada hace 14 h», «Creada ayer», «Creada el 5 nov». */
export function createdText(iso: string | null | undefined, now: number = Date.now()): string | null {
  const value = time(iso);
  if (value === null) return null;
  const seconds = Math.max(0, Math.round((now - value) / 1000));
  if (seconds < 60) return 'Creada hace un momento';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `Creada hace ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `Creada hace ${hours} h`;
  const days = dayOffset(iso, now) ?? 0;
  if (days === -1) return 'Creada ayer';
  if (days > -7) return `Creada hace ${-days} días`;
  return `Creada el ${shortDate(iso)}`;
}

/** «hace 2 días» for the folded lists. */
export function agoText(iso: string | null | undefined, now: number = Date.now()): string {
  const created = createdText(iso, now);
  if (!created) return '';
  return created.replace(/^Creada /, '').replace(/^el /, '');
}

// ---------------------------------------------------------------- copy

const PERSON_ROLES = /^(director|analista|copywriter|editor|lector|investigador|operador|estratega)\b/i;

/** «al Director editorial», «a Perfil», «a Relaciones con la comunidad». */
export function toAgent(label: string | null | undefined): string {
  const name = (label ?? '').trim();
  if (!name) return 'al equipo';
  return PERSON_ROLES.test(name) ? `al ${name}` : `a ${name}`;
}

/** «Hoy el equipo publicó 1 post, comentó en 6 y siguió a 4 personas.» The backend leaves zeros out. */
export function doneTodaySentence(done: Partial<DoneToday> | null | undefined): string | null {
  if (!done) return null;
  const parts: string[] = [];
  const n = (key: keyof DoneToday) => (typeof done[key] === 'number' ? done[key]! : 0);
  if (n('posts')) parts.push(`publicó ${n('posts')} ${n('posts') === 1 ? 'post' : 'posts'}`);
  if (n('comments')) parts.push(`comentó en ${n('comments')}`);
  if (n('reactions')) parts.push(`reaccionó a ${n('reactions')}`);
  if (n('follows')) parts.push(`siguió a ${n('follows')} ${n('follows') === 1 ? 'persona' : 'personas'}`);
  if (n('invites')) parts.push(`invitó a ${n('invites')} ${n('invites') === 1 ? 'persona' : 'personas'}`);
  if (n('accepts')) parts.push(`aceptó ${n('accepts')} ${n('accepts') === 1 ? 'invitación' : 'invitaciones'}`);
  if (!parts.length) return 'Hoy el equipo aún no ha publicado ni interactuado.';
  const last = parts.pop()!;
  return `Hoy el equipo ${parts.length ? `${parts.join(', ')} y ${last}` : last}.`;
}

/** Where a fact came from: «Respondiste al Director editorial» or «Lo añadiste tú». */
export function factOrigin(fact: MemoryFact): string {
  if (fact.origin?.kind === 'manual') return 'Lo añadiste tú';
  if (fact.origin?.kind === 'question') return fact.origin.agent_label ? `Respondiste ${toAgent(fact.origin.agent_label)}` : 'Respondiste a una pregunta del equipo';
  return 'Lo confirmaste en la memoria';
}

/** Accent- and case-insensitive text for the facts search. */
export function normalize(text: string | null | undefined): string {
  return (text ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLocaleLowerCase(LOCALE);
}
