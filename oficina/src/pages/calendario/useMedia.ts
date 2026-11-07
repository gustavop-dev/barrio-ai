import { useEffect, useMemo, useState, useSyncExternalStore } from 'react';

/** Desktop calendar (full grids with chips) from 900px, like the shell's sidebar. */
export const DESKTOP_QUERY = '(min-width: 900px)';

function subscribe(query: string) {
  return (callback: () => void) => {
    if (typeof window.matchMedia !== 'function') return () => {};
    const list = window.matchMedia(query);
    list.addEventListener?.('change', callback);
    return () => list.removeEventListener?.('change', callback);
  };
}

/**
 * Whether a media query matches. The calendar renders either the compact mobile version or the full
 * desktop grid (not both hidden by CSS), so screen readers and tests see one calendar.
 */
export function useMediaQuery(query: string): boolean {
  const onChange = useMemo(() => subscribe(query), [query]);
  return useSyncExternalStore(
    onChange,
    () => typeof window.matchMedia === 'function' && window.matchMedia(query).matches,
    () => false,
  );
}

export function useIsDesktop(): boolean {
  return useMediaQuery(DESKTOP_QUERY);
}

/** Date.now(), refreshed every `intervalMs` (countdowns, the «now» line). */
export function useNow(intervalMs = 60_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs]);
  return now;
}
