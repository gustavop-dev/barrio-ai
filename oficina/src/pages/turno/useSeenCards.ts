import { useCallback, useEffect, useRef } from 'react';
import { markTurnoSeen } from '../../api/tuTurno';

/** How long to gather cards before one POST /tu-turno/vistos. */
export const SEEN_BATCH_MS = 1200;

/** A card counts as seen with half of it on screen, or 160 px of it for very tall cards. */
function isSeen(entry: IntersectionObserverEntry): boolean {
  return entry.isIntersecting && (entry.intersectionRatio >= 0.5 || entry.intersectionRect.height >= 160);
}

export type ObserveCard = (id: string, element: Element | null) => () => void;

/**
 * Marks Nueva cards as seen once they are on screen, in one batched POST per burst. Each id is sent
 * once per visit; a failed batch is retried the next time its card mounts. Without IntersectionObserver
 * (old browsers, tests) a rendered card counts as seen.
 *
 * Returns a stable `observe(id, element)` that gives back its cleanup, for a card's effect.
 */
export function useSeenCards(): ObserveCard {
  const sent = useRef(new Set<string>());
  const queue = useRef(new Set<string>());
  const timer = useRef<number | null>(null);
  const observer = useRef<IntersectionObserver | null>(null);

  const flush = useCallback(() => {
    timer.current = null;
    const ids = [...queue.current];
    queue.current.clear();
    if (!ids.length) return;
    markTurnoSeen(ids).catch(() => {
      for (const id of ids) sent.current.delete(id);
    });
  }, []);

  const enqueue = useCallback(
    (id: string) => {
      if (sent.current.has(id)) return;
      sent.current.add(id);
      queue.current.add(id);
      if (timer.current === null) timer.current = window.setTimeout(flush, SEEN_BATCH_MS);
    },
    [flush],
  );

  useEffect(() => {
    return () => {
      observer.current?.disconnect();
      observer.current = null;
      if (timer.current !== null) {
        window.clearTimeout(timer.current);
        flush();
      }
    };
  }, [flush]);

  return useCallback<ObserveCard>(
    (id, element) => {
      if (!element || sent.current.has(id)) return () => {};
      if (typeof IntersectionObserver === 'undefined') {
        enqueue(id);
        return () => {};
      }
      if (!observer.current) {
        observer.current = new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              if (!isSeen(entry)) continue;
              const target = entry.target as HTMLElement;
              observer.current?.unobserve(target);
              if (target.dataset.turnoId) enqueue(target.dataset.turnoId);
            }
          },
          { threshold: [0, 0.1, 0.25, 0.5] },
        );
      }
      const io = observer.current;
      (element as HTMLElement).dataset.turnoId = id;
      io.observe(element);
      return () => io.unobserve(element);
    },
    [enqueue],
  );
}
