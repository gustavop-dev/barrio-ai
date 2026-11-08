// MovNotificaciones: a new notification arriving while the app is open. Two triggers bring it: the
// regular refresh of GET /tu-turno (its `notifications_unread` grows) and a push received in the
// foreground, which refreshes Notificaciones and Tu turno at once. The bell of every top bar sways
// (one top bar per tab stays mounted), but the phone vibrates once per arrival.
import * as Notifications from 'expo-notifications';
import { useQueryClient, type QueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { notificacionesKeys } from '@compartido/api/notificaciones';
import { keys } from '@/api/queryClient';
import { haptic } from '@/theme/motion';

let lastUnread: number | null = null;

/**
 * Every top bar reports the unread count it shows (also the first one it gets). The first report of
 * a higher count than the last one is an arrival: it plays the haptic and returns true.
 */
export function reportUnread(unread: number): boolean {
  const arrived = lastUnread !== null && unread > lastUnread;
  lastUnread = unread;
  if (arrived) haptic('notificationArrive');
  return arrived;
}

let listeners = 0;
let subscription: { remove: () => void } | null = null;

function refresh(client: QueryClient) {
  void client.invalidateQueries({ queryKey: notificacionesKeys.all });
  void client.invalidateQueries({ queryKey: keys.tuTurno });
}

/** A push received with the app open refreshes Notificaciones and the bell, so the arrival shows at once. One listener for all top bars. */
export function useLiveNotifications(): void {
  const client = useQueryClient();
  useEffect(() => {
    listeners += 1;
    if (!subscription) subscription = Notifications.addNotificationReceivedListener(() => refresh(client));
    return () => {
      listeners -= 1;
      if (listeners === 0 && subscription) {
        subscription.remove();
        subscription = null;
      }
    };
  }, [client]);
}
