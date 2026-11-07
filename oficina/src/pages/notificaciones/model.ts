// Grouping and time labels of Notificaciones (FUNCIONES-NUEVAS rev 18): PRÓXIMO, HOY, AYER and the
// older days of the week, in the device's time.
import type { NotificationFilter, NotificationItem, Notificaciones } from '../../api/notificaciones';
import { capitalize } from '../../lib/format';
import { clock, dayAndTime, dayOffset, longDate } from '../turno/model';

export interface NotificationGroup {
  key: string;
  /** «Próximo», «Hoy», «Ayer», «Miércoles 4 de noviembre» (UPPERCASE through the label style). */
  title: string;
  /** Upcoming items: computed, never unread, the label says the day. */
  upcoming: boolean;
  items: NotificationItem[];
}

function at(item: NotificationItem): number {
  const value = item.at ? new Date(item.at).getTime() : Number.NaN;
  return Number.isNaN(value) ? 0 : value;
}

export function isUnread(item: NotificationItem): boolean {
  return item.read === false;
}

/** PRÓXIMO first (in the backend's order), then one group per day, newest first. «Sin leer» hides what is read and what is coming. */
export function groupNotifications(data: Notificaciones | undefined, filtro: NotificationFilter, now: number = Date.now()): NotificationGroup[] {
  if (!data) return [];
  const groups: NotificationGroup[] = [];
  const onlyUnread = filtro === 'sin_leer';
  const upcoming = onlyUnread ? [] : (data.upcoming ?? []);
  if (upcoming.length) groups.push({ key: 'proximo', title: 'Próximo', upcoming: true, items: upcoming });

  const items = [...(data.items ?? [])].filter((item) => !onlyUnread || isUnread(item)).sort((a, b) => at(b) - at(a));
  const byDay = new Map<string, NotificationGroup>();
  for (const item of items) {
    const offset = dayOffset(item.at, now);
    const key = offset === null ? 'sin-fecha' : String(offset);
    let group = byDay.get(key);
    if (!group) {
      const title = offset === null ? 'Sin fecha' : offset >= 0 ? 'Hoy' : offset === -1 ? 'Ayer' : capitalize(longDate(item.at));
      group = { key, title, upcoming: false, items: [] };
      byDay.set(key, group);
      groups.push(group);
    }
    group.items.push(item);
  }
  return groups;
}

/** Time of a row: «11:20» for the past (the group says the day); «Mañana 09:00», «Mañana» or «Desde ayer, 18:42» for what is coming. */
export function timeLabel(item: NotificationItem, upcoming: boolean, now: number = Date.now()): string {
  if (!item.at) return '';
  if (!upcoming) return clock(item.at);
  const offset = dayOffset(item.at, now) ?? 0;
  const day = offset <= 0 ? 'Hoy' : offset === 1 ? 'Mañana' : capitalize(longDate(item.at));
  // Expected invitations have a day, not an hour.
  if (item.kind === 'invite_expected') return day;
  // Something already going on (the machine stopped from the server): since when.
  if (at(item) < now) return capitalize(`desde ${dayAndTime(item.at, now)}`);
  return `${day} ${clock(item.at)}`;
}
