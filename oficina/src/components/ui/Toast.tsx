import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

export interface ToastOptions {
  /** Shows «Deshacer»; the toast then stays 5 s (the reversible-action window of the spec). */
  undo?: () => unknown;
  /** Label of the undo button; «Deshacer» by default («Recuperar» for a discarded recording). */
  undoLabel?: string;
  /** Milliseconds; 5000 with undo, 4000 without. */
  duration?: number;
  tone?: 'default' | 'error';
}

interface ToastState extends ToastOptions {
  id: number;
  message: string;
}

export interface ToastApi {
  /** «Guardado», «Vetada», «Marcada como hecha»… One at a time: a new toast replaces the current one. */
  show: (message: string, options?: ToastOptions) => void;
  dismiss: () => void;
}

const NOOP: ToastApi = { show: () => {}, dismiss: () => {} };
const ToastContext = createContext<ToastApi>(NOOP);

export function useToast(): ToastApi {
  return useContext(ToastContext);
}

/** Mount once near the root. The live region is always present so screen readers announce each toast. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastState | null>(null);
  const nextId = useRef(1);

  const dismiss = useCallback(() => setToast(null), []);
  const show = useCallback((message: string, options: ToastOptions = {}) => {
    setToast({ id: nextId.current++, message, ...options });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast((current) => (current?.id === toast.id ? null : current)), toast.duration ?? (toast.undo ? 5000 : 4000));
    return () => window.clearTimeout(timer);
  }, [toast]);

  const api = useMemo(() => ({ show, dismiss }), [show, dismiss]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-region" role="status" aria-live="polite">
        {toast ? (
          <div key={toast.id} className={toast.tone === 'error' ? 'toast error' : 'toast'}>
            <span className="toast-message">{toast.message}</span>
            {toast.undo ? (
              <button
                type="button"
                className="toast-undo"
                onClick={() => {
                  const undo = toast.undo;
                  setToast(null);
                  undo?.();
                }}
              >
                {toast.undoLabel ?? 'Deshacer'}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </ToastContext.Provider>
  );
}
