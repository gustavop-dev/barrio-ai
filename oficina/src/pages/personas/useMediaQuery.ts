import { useCallback, useSyncExternalStore } from 'react';

/** Desktop board and list-detail breakpoint (the `.split` grids switch at the same width). */
export const WIDE = '(min-width: 1100px)';
/** Desktop shell (sidebar) breakpoint. */
export const DESKTOP = '(min-width: 900px)';

/** window.matchMedia(query).matches, kept up to date. False where matchMedia is missing (tests). */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (callback: () => void) => {
      const list = typeof window.matchMedia === 'function' ? window.matchMedia(query) : null;
      list?.addEventListener?.('change', callback);
      return () => list?.removeEventListener?.('change', callback);
    },
    [query],
  );
  return useSyncExternalStore(
    subscribe,
    () => (typeof window.matchMedia === 'function' ? window.matchMedia(query).matches : false),
    () => false,
  );
}
