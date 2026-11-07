import { useTuTurno } from '@compartido/api/hooks';

export interface TurnCount {
  count: number;
  critical: boolean;
  /** Urgent items, for the accessible label. */
  urgent: number;
  /** Unread notifications: only drives the bell dot, never a number. */
  unread: number;
}

/** Badges from GET /api/v1/tu-turno: the Tu turno counter and `notifications_unread` for the bell dot. */
export function useTurnCount(): TurnCount {
  const { data } = useTuTurno();
  const cards = data ? [...(data.alerts ?? []), ...(data.questions ?? []), ...(data.tasks?.perfil ?? []), ...(data.tasks?.conversaciones ?? [])] : [];
  return {
    count: data?.count ?? 0,
    critical: Boolean(data?.critical),
    urgent: data?.urgent_count ?? cards.filter((card) => card.critical).length,
    unread: data?.notifications_unread ?? 0,
  };
}

/** «Tu turno, 6 pendientes, 1 urgente». */
export function turnLabel({ count, critical, urgent }: Pick<TurnCount, 'count' | 'critical' | 'urgent'>): string {
  if (count <= 0) return 'Tu turno';
  const pending = `${count} ${count === 1 ? 'pendiente' : 'pendientes'}`;
  const urgentText = critical ? (urgent > 0 ? `, ${urgent} ${urgent === 1 ? 'urgente' : 'urgentes'}` : ', con algo urgente') : '';
  return `Tu turno, ${pending}${urgentText}`;
}

export function notificationsLabel(unread: number): string {
  return unread > 0 ? 'Notificaciones, hay novedades' : 'Notificaciones';
}
