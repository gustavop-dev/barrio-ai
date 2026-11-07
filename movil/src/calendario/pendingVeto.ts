// A veto waits the «Deshacer» window (toastDurations.withUndo, 5 s) before it reaches the backend: the
// API cannot take a reject back, so «Deshacer» cancels it before it is sent. The store lives outside
// the views, so leaving the screen does not lose a veto, and the app going to the background sends the
// pending ones at once (a killed app would lose them otherwise).
import { rejectAction } from '@compartido/api/endpoints';
import { keys } from '@compartido/api/queryClient';
import type { QueryClient } from '@tanstack/react-query';
import { useSyncExternalStore } from 'react';
import { AppState, type NativeEventSubscription } from 'react-native';
import { toastDurations } from '@/theme/motion';

interface PendingVeto {
  actionId: string;
  note: string;
  client: QueryClient;
  timer: ReturnType<typeof setTimeout>;
  /** Called once the backend answered: null on success, the error otherwise. */
  onSettled?: (error: unknown) => void;
}

const pending = new Map<string, PendingVeto>();
const listeners = new Set<() => void>();
let appState: NativeEventSubscription | null = null;

function changed() {
  listeners.forEach((listener) => listener());
  if (!pending.size && appState) {
    appState.remove();
    appState = null;
  }
}

/** The same refresh as useVeto (compartido/api/hooks): the piece, the days, the activity, the network and Tu turno. */
function refresh(client: QueryClient) {
  for (const queryKey of [keys.editorialAll, keys.calendarioAll, keys.actividadAll, keys.actionsAll, keys.redAll, keys.tuTurno]) {
    void client.invalidateQueries({ queryKey });
  }
}

async function send(actionId: string): Promise<void> {
  const veto = pending.get(actionId);
  if (!veto) return;
  clearTimeout(veto.timer);
  pending.delete(actionId);
  changed();
  let failure: unknown = null;
  try {
    await rejectAction(veto.actionId, veto.note);
  } catch (error) {
    failure = error;
  }
  refresh(veto.client);
  veto.onSettled?.(failure);
}

export interface ScheduleVeto {
  actionId: string;
  note: string;
  client: QueryClient;
  onSettled?: (error: unknown) => void;
}

/** Schedules the reject; returns «Deshacer» (true when it was still in time). */
export function scheduleVeto({ actionId, note, client, onSettled }: ScheduleVeto): () => boolean {
  const previous = pending.get(actionId);
  if (previous) clearTimeout(previous.timer);
  const timer = setTimeout(() => void send(actionId), toastDurations.withUndo);
  pending.set(actionId, { actionId, note, client, timer, onSettled });
  if (!appState) {
    appState = AppState.addEventListener('change', (state) => {
      if (state !== 'active') void flushVetoes();
    });
  }
  changed();
  return () => cancelVeto(actionId);
}

export function cancelVeto(actionId: string): boolean {
  const veto = pending.get(actionId);
  if (!veto) return false;
  clearTimeout(veto.timer);
  pending.delete(actionId);
  changed();
  return true;
}

/** Sends every pending veto now (the app leaves the foreground). */
export function flushVetoes(): Promise<void> {
  return Promise.all([...pending.keys()].map((actionId) => send(actionId))).then(() => undefined);
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** True while the veto of this action waits its «Deshacer» window. */
export function usePendingVeto(actionId: string | null | undefined): boolean {
  return useSyncExternalStore(
    subscribe,
    () => Boolean(actionId && pending.has(actionId)),
    () => false,
  );
}
