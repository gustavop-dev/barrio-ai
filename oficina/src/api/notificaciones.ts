// Notificaciones (rev 18): what is coming or happened and asks nothing of Gustavo, kept 7 days.
// GET /api/v1/notificaciones?filtro=todas|sin_leer and POST /api/v1/notificaciones/leer.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { REFRESH } from './hooks';
import { keys } from './queryClient';
import type { CalendarLayer, TuTurno } from './types';

export type NotificationKind =
  | 'piece_scheduled'
  | 'piece_published'
  | 'piece_blocked'
  | 'piece_discarded'
  | 'connection_fit'
  | 'opportunity'
  | 'observatory'
  | 'capture_processed'
  | 'invite_expected'
  | 'machine_paused_env'
  | (string & {});

export interface NotificationItem {
  /** uuid, or `<kind>:<id>` for the computed upcoming ones. */
  id: string;
  kind: NotificationKind;
  /** Calendar layer: colours the dot. */
  layer: CalendarLayer;
  title: string;
  detail: string;
  /** In-app destination («/calendario/pieza/<id>», «/personas/<id>», «/?enviado=1»). */
  link: string | null;
  at: string | null;
  /** Upcoming items are computed and never unread: they carry no `read`. */
  read?: boolean;
}

export interface Notificaciones {
  /** Next piece within 48 h, the invitations expected and, while active, the machine stopped from the server. */
  upcoming: NotificationItem[];
  /** The last 7 days, newest first. */
  items: NotificationItem[];
  unread: number;
}

export type NotificationFilter = 'todas' | 'sin_leer';

export const notificacionesKeys = {
  all: ['notificaciones'] as const,
  list: (filtro: NotificationFilter) => ['notificaciones', filtro] as const,
};

export const getNotificaciones = (filtro: NotificationFilter = 'todas') =>
  api.get<Notificaciones>(`/api/v1/notificaciones?filtro=${filtro}`);

export type MarkReadInput = { ids: string[] } | { todas: true };

/** Marks some notifications (or all of them) as read; returns the unread count left. */
export const markNotificacionesRead = (input: MarkReadInput) => api.post<{ unread: number }>('/api/v1/notificaciones/leer', input);

export function useNotificaciones(filtro: NotificationFilter = 'todas') {
  return useQuery({ queryKey: notificacionesKeys.list(filtro), queryFn: () => getNotificaciones(filtro), refetchInterval: REFRESH.tuTurno });
}

type Snapshot = [readonly unknown[], Notificaciones | undefined][];

function markLocally(data: Notificaciones | undefined, input: MarkReadInput): Notificaciones | undefined {
  if (!data) return data;
  const all = 'todas' in input;
  const ids = new Set('ids' in input ? input.ids : []);
  let cleared = 0;
  const items = data.items.map((item) => {
    if (item.read === false && (all || ids.has(item.id))) {
      cleared += 1;
      return { ...item, read: true };
    }
    return item;
  });
  return { ...data, items, unread: all ? 0 : Math.max(0, data.unread - cleared) };
}

/**
 * Marks as read, at once on screen (optimistic), then refreshes Notificaciones and Tu turno so the bell
 * dot (`notifications_unread`) follows. On error the lists go back to what they were.
 */
export function useMarkNotificacionesRead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: markNotificacionesRead,
    onMutate: async (input: MarkReadInput) => {
      await client.cancelQueries({ queryKey: notificacionesKeys.all });
      const snapshot: Snapshot = client.getQueriesData<Notificaciones>({ queryKey: notificacionesKeys.all });
      client.setQueriesData<Notificaciones>({ queryKey: notificacionesKeys.all }, (data) => markLocally(data, input));
      return { snapshot };
    },
    onError: (_error, _input, context) => {
      for (const [queryKey, data] of context?.snapshot ?? []) client.setQueryData(queryKey, data);
    },
    onSuccess: (result) => {
      if (typeof result?.unread !== 'number') return;
      client.setQueryData<TuTurno>(keys.tuTurno, (turno) => (turno ? { ...turno, notifications_unread: result.unread } : turno));
    },
    onSettled: () =>
      Promise.all([client.invalidateQueries({ queryKey: notificacionesKeys.all }), client.invalidateQueries({ queryKey: keys.tuTurno })]),
  });
}
