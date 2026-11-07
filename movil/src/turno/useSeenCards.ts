// Nueva → Vista: cards that show on screen are reported in one batched POST /tu-turno/vistos per
// burst. Each id is sent once per visit; a failed batch is retried the next time it shows.
import { markTurnoSeen } from '@compartido/api/tuTurno';
import { useCallback, useEffect, useRef } from 'react';

/** How long to gather cards before one POST /tu-turno/vistos. */
export const SEEN_BATCH_MS = 1200;

/** FlatList viewability: fully visible, or covering a fifth of the screen (very tall question cards). */
export const SEEN_VIEWABILITY = { viewAreaCoveragePercentThreshold: 20, minimumViewTime: 250 } as const;

export function useSeenCards(): (ids: readonly string[]) => void {
  const sent = useRef(new Set<string>());
  const queue = useRef(new Set<string>());
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flush = useCallback(() => {
    timer.current = null;
    const ids = [...queue.current];
    queue.current.clear();
    if (!ids.length) return;
    markTurnoSeen(ids).catch(() => {
      for (const id of ids) sent.current.delete(id);
    });
  }, []);

  useEffect(
    () => () => {
      if (timer.current !== null) {
        clearTimeout(timer.current);
        flush();
      }
    },
    [flush],
  );

  return useCallback(
    (ids: readonly string[]) => {
      for (const id of ids) {
        if (sent.current.has(id)) continue;
        sent.current.add(id);
        queue.current.add(id);
      }
      if (queue.current.size && timer.current === null) timer.current = setTimeout(flush, SEEN_BATCH_MS);
    },
    [flush],
  );
}
