import { useTuTurno } from '@compartido/api/hooks';
import { useHeldTurno } from '@/turno/heldCount';

export interface TurnCount {
  count: number;
  critical: boolean;
  /** Urgent items, for the accessible label. */
  urgent: number;
  /** Unread notifications: only drives the bell dot, never a number. */
  unread: number;
  /** GET /tu-turno has answered at least once (its first answer is not news: nothing sways or pops). */
  loaded: boolean;
}

/**
 * Badges from GET /api/v1/tu-turno: the Tu turno counter and `notifications_unread` for the bell dot.
 * MovTuTurno: a card that Tu turno is still taking off the list keeps counting (`useHeldTurno`), so the
 * badge rolls together with the group counters, once the card has left.
 */
export function useTurnCount(): TurnCount {
  const { data } = useTuTurno();
  const held = useHeldTurno();
  const cards = data ? [...(data.alerts ?? []), ...(data.questions ?? []), ...(data.tasks?.perfil ?? []), ...(data.tasks?.conversaciones ?? [])] : [];
  return {
    count: (data?.count ?? 0) + held.count,
    critical: Boolean(data?.critical) || held.urgent > 0,
    urgent: (data?.urgent_count ?? cards.filter((card) => card.critical).length) + held.urgent,
    unread: data?.notifications_unread ?? 0,
    loaded: data !== undefined,
  };
}

/** «Bandeja de entrada, 6 pendientes, 1 urgente». */
export function turnLabel({ count, critical, urgent }: Pick<TurnCount, 'count' | 'critical' | 'urgent'>): string {
  if (count <= 0) return 'Bandeja de entrada';
  const pending = `${count} ${count === 1 ? 'pendiente' : 'pendientes'}`;
  const urgentText = critical ? (urgent > 0 ? `, ${urgent} ${urgent === 1 ? 'urgente' : 'urgentes'}` : ', con algo urgente') : '';
  return `Bandeja de entrada, ${pending}${urgentText}`;
}

export function notificationsLabel(unread: number): string {
  return unread > 0 ? 'Notificaciones, hay novedades' : 'Notificaciones';
}
