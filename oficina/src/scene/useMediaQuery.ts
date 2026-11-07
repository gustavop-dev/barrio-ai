import { useCallback, useSyncExternalStore } from 'react';

/** Scene plus the 340 px side panel (DISENO-VISTAS «1. Oficina», escritorio). */
export const OFICINA_WIDE = '(min-width: 1100px)';
export const REDUCED_MOTION = '(prefers-reduced-motion: reduce)';

/** window.matchMedia(query).matches, kept up to date. False where matchMedia is missing. */
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

function subscribeResize(callback: () => void) {
  window.addEventListener('resize', callback);
  return () => window.removeEventListener('resize', callback);
}

/** Whole device pixels per CSS pixel, so every logical pixel is an integer block on screen. */
export function useDevicePixels(): number {
  return useSyncExternalStore(
    subscribeResize,
    () => Math.max(1, Math.round(window.devicePixelRatio || 1)),
    () => 1,
  );
}

/** Viewport size, kept up to date. */
export function useViewport(): { width: number; height: number } {
  const width = useSyncExternalStore(
    subscribeResize,
    () => window.innerWidth,
    () => 390,
  );
  const height = useSyncExternalStore(
    subscribeResize,
    () => window.innerHeight,
    () => 844,
  );
  return { width, height };
}
