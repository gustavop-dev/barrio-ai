import { createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { durations, microMotion, timingWith, toastDurations, useMotion } from '@/theme/motion';
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

/** What a toast outlet needs from the provider: the current toast, and which outlet draws it. */
interface ToastHost {
  toast: ToastState | null;
  close: () => void;
  /** «Deshacer» on toast `id`: true while it still counts (its time has not run out). */
  take: (id: number) => boolean;
  register: (id: string) => () => void;
  /** The outlet that draws the toast: the last one mounted, or none (the provider draws it in the app's window). */
  top: string | null;
}

const ToastHostContext = createContext<ToastHost | null>(null);

/**
 * One toast. MovCaptura: it fades in rising 12 px (fast, EASE_OUT) and, `leaving`, fades out sinking back (fast, EASE_IN).
 * Driven by a shared value, not by Reanimated `entering`/`exiting`: in the QA, toasts shown in the frame a sheet's Modal
 * closed («Enviado al equipo.», «Foto quitada de la galería.») sometimes never became visible, with or without the
 * outlet, and an entering animation that never starts leaves the toast at opacity 0. With reduced motion it starts
 * fully visible.
 */
function ToastCard({ toast, leaving, take, onGone }: { toast: ToastState; leaving: boolean; take: (id: number) => boolean; onGone: () => void }) {
  const { reduced } = useMotion();
  const shown = useSharedValue(reduced ? 1 : 0);
  useEffect(() => {
    shown.set(withTiming(leaving ? 0 : 1, timingWith(durations.fast, leaving ? 'exit' : 'enter')));
    if (!leaving) return;
    // A JS timer, not the animation's callback: the toast goes even if the animation never reports back.
    const timer = setTimeout(onGone, durations.fast);
    return () => clearTimeout(timer);
  }, [leaving, shown, onGone]);
  const motion = useAnimatedStyle(() => ({ opacity: shown.value, transform: [{ translateY: (1 - shown.value) * microMotion.toastRise }] }));
  return (
    <Animated.View
      style={[styles.toast, toast.tone === 'error' ? styles.error : null, motion]}
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
            // A tap after its time ran out (the toast fading out) no longer undoes: the action may have gone.
            if (!take(toast.id)) return;
            toast.undo?.();
          }}
          style={styles.undo}
        >
          <T color={colors.brand}>{toast.undoLabel ?? 'Deshacer'}</T>
        </Pressable>
      ) : null}
    </Animated.View>
  );
}

/** The toast region, at `bottom` px from the bottom of its window: the current toast, or the last one fading out. */
function ToastRegion({ toast, take, bottom }: { toast: ToastState | null; take: (id: number) => boolean; bottom: number }) {
  const [drawn, setDrawn] = useState<ToastState | null>(toast);
  // A new toast replaces the one on screen at once.
  if (toast && toast !== drawn) setDrawn(toast);
  const gone = useCallback(() => setDrawn(null), []);
  return (
    <View pointerEvents="box-none" style={[styles.region, { bottom }]}>
      {drawn ? <ToastCard key={drawn.id} toast={drawn} leaving={!toast} take={take} onGone={gone} /> : null}
    </View>
  );
}

/**
 * Mount once near the root. It floats above the bottom bar; screen readers announce each toast.
 *
 * A Modal (a sheet) is a window of its own, drawn over the app's: a toast drawn in the app's window would sit under
 * it, where Gustavo cannot see it. So each sheet mounts a ToastOutlet, and while one is mounted the newest draws the
 * toast, above that sheet.
 */
export function ToastProvider({ children, bottomOffset = shell.tabBarHeight }: { children: ReactNode; bottomOffset?: number }) {
  const [toast, setToast] = useState<ToastState | null>(null);
  const [outlets, setOutlets] = useState<string[]>([]);
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
  const take = useCallback((id: number) => {
    if (live.current?.id !== id) return false;
    live.current = null;
    setToast(null);
    return true;
  }, []);
  const register = useCallback((id: string) => {
    setOutlets((current) => [...current, id]);
    return () => setOutlets((current) => current.filter((outlet) => outlet !== id));
  }, []);

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

  // Once a toast that left without its undo has faded out (ToastCard keeps it `durations.fast`), what waited for it
  // goes (a veto, calendario/pendingVeto.ts): «Deshacer» is never on screen when the action is sent.
  useEffect(() => {
    const due = expired.current.splice(0);
    if (!due.length) return;
    setTimeout(() => due.forEach((gone) => gone.onExpire?.()), durations.fast + 20);
  }, [toast]);

  const api = useMemo(() => ({ show, dismiss }), [show, dismiss]);
  const top = outlets[outlets.length - 1] ?? null;
  const host = useMemo(() => ({ toast, close: dismiss, take, register, top }), [toast, dismiss, take, register, top]);

  return (
    <ToastContext.Provider value={api}>
      <ToastHostContext.Provider value={host}>
        {children}
        {top === null ? <ToastRegion toast={toast} take={take} bottom={insets.bottom + bottomOffset + space[3]} /> : null}
      </ToastHostContext.Provider>
    </ToastContext.Provider>
  );
}

/**
 * Where the toast is drawn while this outlet is the newest one mounted: inside a Modal's window (Sheet mounts one),
 * so a toast shown while a sheet is open («Envío deshecho.» in «Lo que enviaste», or the one that comes with a sheet
 * opening again) shows above the sheet. There is no bottom bar in a modal: it sits `bottomOffset` px above the safe area.
 */
export function ToastOutlet({ bottomOffset = 0 }: { bottomOffset?: number }) {
  const host = useContext(ToastHostContext);
  const insets = useSafeAreaInsets();
  const id = useId();
  const register = host?.register;
  useEffect(() => register?.(id), [register, id]);
  if (!host || host.top !== id) return null;
  return <ToastRegion toast={host.toast} take={host.take} bottom={insets.bottom + bottomOffset + space[3]} />;
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
