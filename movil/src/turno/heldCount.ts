// MovTuTurno: the top bar badge counts down only once the card has left the list (with the group
// counters), not when GET /tu-turno already says it is gone. While Tu turno still shows a card that
// the backend no longer lists, it publishes it here and the badge keeps counting it.
import { useSyncExternalStore } from 'react';

export interface HeldTurno {
  /** Cards still counted on screen that the backend no longer lists. */
  count: number;
  /** How many of them are urgent (they keep the badge in alerta). */
  urgent: number;
}

const NONE: HeldTurno = { count: 0, urgent: 0 };

let held: HeldTurno = NONE;
const listeners = new Set<() => void>();

export function setHeldTurno(next: HeldTurno): void {
  if (next.count === held.count && next.urgent === held.urgent) return;
  held = next.count || next.urgent ? next : NONE;
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

const snapshot = () => held;

export function useHeldTurno(): HeldTurno {
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}
