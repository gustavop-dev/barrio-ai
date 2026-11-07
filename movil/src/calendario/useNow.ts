import { useEffect, useState } from 'react';

/** Countdowns («sale en 5 h») and the cut deadlines move once a minute, as in the PWA. */
export const NOW_REFRESH_MS = 60_000;

/** Date.now(), refreshed every `intervalMs`. */
export function useNow(intervalMs = NOW_REFRESH_MS): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);
  return now;
}
