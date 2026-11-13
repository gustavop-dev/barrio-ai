// Personas › Conexiones (Gustavo, 12/11/2026): his people database is only the people who accepted (stage connected),
// labelled by their barrio role, the most recent connection first and grouped by when they accepted. The agents'
// queue (candidate … discarded) is never listed. Pure rules, apart from the markup (movil/src/personas/Conexiones.tsx).
import type { Contact, RedSummary } from '../api/types';
import { dayOf, monthOf, startOfWeek } from './dates';
import { CONTACT_ROLE_LABEL } from './format';

/** The filter value and count key of a connection without a barrio role (the backend's `red.NO_ROLE`). */
export const NO_ROLE = 'sin_etiqueta';
export const NO_ROLE_LABEL = 'Sin etiqueta';

/** The order of the role chips; a role this table does not know goes after them, and «Sin etiqueta» last. */
const ROLE_ORDER = ['comprador', 'par', 'recomendador', 'divulgador', 'lider', 'aliado'];

const ROLE_PLURAL: Record<string, string> = {
  comprador: 'Compradores',
  par: 'Pares',
  recomendador: 'Recomendadores',
  divulgador: 'Divulgadores',
  lider: 'Líderes',
  aliado: 'Aliados',
};

/** «Compradores», «Sin etiqueta»; an unknown role keeps its own name. */
export function rolePlural(role: string): string {
  if (role === NO_ROLE) return NO_ROLE_LABEL;
  return ROLE_PLURAL[role] ?? CONTACT_ROLE_LABEL[role] ?? role;
}

/** The role of a row: «Comprador», or «Sin etiqueta» when the person has none. */
export function roleLabel(contact: Pick<Contact, 'classification'>): string {
  const role = contact.classification?.role;
  return role ? (CONTACT_ROLE_LABEL[role] ?? role) : NO_ROLE_LABEL;
}

export interface RoleChip {
  /** The `role` filter: a barrio role or NO_ROLE. */
  value: string;
  /** «Compradores · 2». */
  label: string;
}

function rank(role: string): number {
  if (role === NO_ROLE) return ROLE_ORDER.length + 1;
  const index = ROLE_ORDER.indexOf(role);
  return index >= 0 ? index : ROLE_ORDER.length;
}

/** «Todas · N» (without a number until red/summary answers), then one chip per role present among the connections. */
export function roleChips(summary: RedSummary | undefined): { all: string; chips: RoleChip[] } {
  const counts = summary?.connections;
  if (!counts) return { all: 'Todas', chips: [] };
  const chips = Object.entries(counts.roles)
    .filter(([, count]) => count > 0)
    .sort(([a], [b]) => rank(a) - rank(b) || a.localeCompare(b, 'es'))
    .map(([value, count]) => ({ value, label: `${rolePlural(value)} · ${count}` }));
  return { all: `Todas · ${counts.total}`, chips };
}

/** When the person accepted: `connected_at`, or their last update for a connection recorded before that field. */
export function connectedOn(contact: Pick<Contact, 'connected_at' | 'updated_at'>): string {
  return contact.connected_at || contact.updated_at;
}

/** «Aceptó el 12/11» (the Bogotá day), with the year when it is not this one; '' without `connected_at`. */
export function acceptedLabel(contact: Pick<Contact, 'connected_at'>, now: Date = new Date()): string {
  const day = dayOf(contact.connected_at);
  if (!day) return '';
  const [year, month, date] = day.split('-');
  return `Aceptó el ${date}/${month}${year !== dayOf(now)?.slice(0, 4) ? `/${year}` : ''}`;
}

export type ConnectionPeriod = 'semana' | 'mes' | 'antes';

export const CONNECTION_PERIOD_TITLE: Record<ConnectionPeriod, string> = {
  semana: 'Esta semana',
  mes: 'Este mes',
  antes: 'Antes',
};

/** «Esta semana» from Monday (Bogotá days), «Este mes» for the rest of the month, «Antes» otherwise. */
export function connectionPeriod(contact: Pick<Contact, 'connected_at' | 'updated_at'>, now: Date = new Date()): ConnectionPeriod {
  const day = dayOf(connectedOn(contact));
  const today = dayOf(now);
  if (!day || !today) return 'antes';
  if (day >= startOfWeek(today)) return 'semana';
  return monthOf(day) === monthOf(today) ? 'mes' : 'antes';
}

export interface ConnectionSection {
  key: ConnectionPeriod;
  title: string;
  data: Contact[];
}

/** The list's sections in order, without the empty ones; each keeps the order the API gave (most recent first). */
export function connectionSections(contacts: readonly Contact[], now: Date = new Date()): ConnectionSection[] {
  const periods: ConnectionPeriod[] = ['semana', 'mes', 'antes'];
  const buckets: Record<ConnectionPeriod, Contact[]> = { semana: [], mes: [], antes: [] };
  for (const contact of contacts) buckets[connectionPeriod(contact, now)].push(contact);
  return periods.filter((key) => buckets[key].length > 0).map((key) => ({ key, title: CONNECTION_PERIOD_TITLE[key], data: buckets[key] }));
}
