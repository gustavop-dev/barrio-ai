import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Animated from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { microLayout, toastDurations } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import { T } from './Text';

export interface ToastOptions {
  /** Shows «Deshacer»; the toast then stays 5 s (the reversible-action window of the spec). */
  undo?: () => unknown;
  /** «Deshacer» by default («Recuperar» for a discarded recording). */
  undoLabel?: string;
  /** Milliseconds; motion.ts toastDurations by default. */
  duration?: number;
  tone?: 'default' | 'error';
  /**
   * Runs once the toast has left the screen without its undo: its time ran out, another toast took its place or it
   * was dismissed. An action that waits for «Deshacer» goes here, so it never goes while «Deshacer» still shows.
   */
  onExpire?: () => void;
}

interface ToastState extends ToastOptions {
  id: number;
  message: string;
}

export interface ToastApi {
  /** One at a time: a new toast replaces the current one. */
  show: (message: string, options?: ToastOptions) => void;
  dismiss: () => void;
}

const NOOP: ToastApi = { show: () => {}, dismiss: () => {} };
const ToastContext = createContext<ToastApi>(NOOP);

export function useToast(): ToastApi {
  return useContext(ToastContext);
}

/**
 * Mount once near the root. It floats above the bottom bar; screen readers announce each toast.
 * MovCaptura: it fades in rising 12 px (fast, EASE_OUT) and fades out sinking back (fast, EASE_IN).
 */
export function ToastProvider({ children, bottomOffset = shell.tabBarHeight }: { children: ReactNode; bottomOffset?: number }) {
  const [toast, setToast] = useState<ToastState | null>(null);
  const nextId = useRef(1);
  const insets = useSafeAreaInsets();
  /** The toast whose «Deshacer» still counts: cleared the moment its time runs out, so a late tap does nothing. */
  const live = useRef<ToastState | null>(null);
  /** Toasts that left without their undo; their onExpire runs once the screen no longer shows them. */
  const expired = useRef<ToastState[]>([]);

  const leave = useCallback(() => {
    const current = live.current;
    live.current = null;
    if (current?.onExpire) expired.current.push(current);
  }, []);
  const dismiss = useCallback(() => {
    leave();
    setToast(null);
  }, [leave]);
  const show = useCallback(
    (message: string, options: ToastOptions = {}) => {
      leave();
      const next = { id: nextId.current++, message, ...options };
      live.current = next;
      setToast(next);
    },
    [leave],
  );

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(
      () => {
        if (live.current?.id !== toast.id) return;
        leave();
        setToast(null);
      },
      toast.duration ?? (toast.undo ? toastDurations.withUndo : toastDurations.plain),
    );
    return () => clearTimeout(timer);
  }, [toast, leave]);

  // After the commit that took a toast off the screen, what waited for it goes (a veto, pendingVeto.ts).
  useEffect(() => {
    for (const gone of expired.current.splice(0)) gone.onExpire?.();
  }, [toast]);

  const api = useMemo(() => ({ show, dismiss }), [show, dismiss]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <View pointerEvents="box-none" style={[styles.region, { bottom: insets.bottom + bottomOffset + space[3] }]}>
        {toast ? (
          <Animated.View
            key={toast.id}
            entering={microLayout.toastIn()}
            exiting={microLayout.toastOut()}
            style={[styles.toast, toast.tone === 'error' ? styles.error : null]}
            accessibilityRole="alert"
            accessibilityLiveRegion="polite"
            testID="toast"
          >
            <T color={colors.paper} style={styles.message}>
              {toast.message}
            </T>
            {toast.undo ? (
              <Pressable
                accessibilityRole="button"
                hitSlop={8}
                onPress={() => {
                  if (live.current?.id !== toast.id) return;
                  live.current = null;
                  setToast(null);
                  toast.undo?.();
                }}
                style={styles.undo}
              >
                <T color={colors.brand}>{toast.undoLabel ?? 'Deshacer'}</T>
              </Pressable>
            ) : null}
          </Animated.View>
        ) : null}
      </View>
    </ToastContext.Provider>
  );
}

const styles = StyleSheet.create({
  region: { position: 'absolute', left: space[4], right: space[4], alignItems: 'center' },
  toast: {
    width: '100%',
    maxWidth: 520,
    minHeight: 48,
    paddingVertical: space[2],
    paddingLeft: space[4],
    paddingRight: space[2],
    borderRadius: radius.md,
    backgroundColor: colors.ink,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space[3],
  },
  error: { backgroundColor: colors.alert },
  message: { flex: 1 },
  undo: { minHeight: shell.touch, paddingHorizontal: space[3], justifyContent: 'center' },
});
