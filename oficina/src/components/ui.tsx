import { useEffect, useId, useRef, type ReactNode } from 'react';
import { ApiError } from '../api/client';

export function Loading({ label = 'Cargando…', full = false }: { label?: string; full?: boolean }) {
  return (
    <div className={full ? 'loading full' : 'loading'} role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof TypeError) return 'No hay conexión con el servidor. Comprueba tu red.';
  if (error instanceof Error) return error.message;
  return 'Algo salió mal.';
}

export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (!error) return null;
  const conflict = error instanceof ApiError && error.status === 409;
  return (
    <div className={conflict ? 'note warn' : 'note error'} role="alert">
      <strong>{conflict ? 'No se puede ahora' : 'No se pudo completar'}</strong>
      <p>{errorMessage(error)}</p>
      {onRetry ? (
        <button type="button" className="secondary" onClick={onRetry}>
          Reintentar
        </button>
      ) : null}
    </div>
  );
}

export type Tone = 'ok' | 'warn' | 'bad' | 'muted' | 'info';

export function Badge({ tone = 'muted', children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function Meter({ label, value, max, display }: { label: string; value: number; max: number; display?: string }) {
  const fraction = max > 0 ? Math.min(1, Math.max(0, value / max)) : 0;
  const tone = fraction >= 1 ? 'bad' : fraction >= 0.8 ? 'warn' : 'ok';
  return (
    <div className="meter">
      <div className="meterhead">
        <span>{label}</span>
        <strong>{display ?? `${value} / ${max}`}</strong>
      </div>
      <div
        className={`meterbar ${tone}`}
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        aria-valuetext={display ?? `${value} de ${max}`}
      >
        <span style={{ width: `${fraction * 100}%` }} />
      </div>
    </div>
  );
}

export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <header className="pagehead">
      <p className="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      {children ? <div className="pagelead">{children}</div> : null}
    </header>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}

/** Accessible modal without <dialog>, so it behaves the same in every browser and in tests. */
export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const focusable = panel.current?.querySelector<HTMLElement>('textarea, input, select, button:not(.modalclose)');
    focusable?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      previous?.focus?.();
    };
  }, [onClose]);
  return (
    <div className="backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby={titleId} ref={panel}>
        <button type="button" className="modalclose" aria-label="Cerrar" onClick={onClose}>
          ×
        </button>
        <h2 id={titleId}>{title}</h2>
        {children}
      </div>
    </div>
  );
}

export function ExternalLink({ href, children }: { href: string | null | undefined; children: ReactNode }) {
  if (!href || !/^https:\/\//i.test(href)) return null;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="extlink">
      {children} <span aria-hidden="true">↗</span>
    </a>
  );
}
