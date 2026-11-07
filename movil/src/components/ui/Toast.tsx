import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Animated from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { layout, toastDurations } from '@/theme/motion';
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

/** Mount once near the root. It floats above the bottom bar; screen readers announce each toast. */
export function ToastProvider({ children, bottomOffset = shell.tabBarHeight }: { children: ReactNode; bottomOffset?: number }) {
  const [toast, setToast] = useState<ToastState | null>(null);
  const nextId = useRef(1);
  const insets = useSafeAreaInsets();

  const dismiss = useCallback(() => setToast(null), []);
  const show = useCallback((message: string, options: ToastOptions = {}) => {
    setToast({ id: nextId.current++, message, ...options });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(
      () => setToast((current) => (current?.id === toast.id ? null : current)),
      toast.duration ?? (toast.undo ? toastDurations.withUndo : toastDurations.plain),
    );
    return () => clearTimeout(timer);
  }, [toast]);

  const api = useMemo(() => ({ show, dismiss }), [show, dismiss]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <View pointerEvents="box-none" style={[styles.region, { bottom: insets.bottom + bottomOffset + space[3] }]}>
        {toast ? (
          <Animated.View
            key={toast.id}
            entering={layout.toastIn()}
            exiting={layout.toastOut()}
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
                  const undo = toast.undo;
                  setToast(null);
                  undo?.();
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
