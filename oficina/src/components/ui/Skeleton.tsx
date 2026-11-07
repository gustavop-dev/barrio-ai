export interface SkeletonProps {
  /** card (Tu turno), row (list of people or events), kpi (Resultados tile), line (text). */
  variant?: 'card' | 'row' | 'kpi' | 'line';
  count?: number;
  /** Announced once to screen readers. */
  label?: string;
}

/** Loading placeholders. The shimmer stops with reduced motion. */
export function Skeleton({ variant = 'card', count = 1, label = 'Cargando…' }: SkeletonProps) {
  return (
    <div className={`skeleton-group ${variant}`} role="status" aria-live="polite">
      <span className="vh">{label}</span>
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className={`skeleton ${variant}`} aria-hidden="true">
          {variant === 'card' ? (
            <>
              <span className="sk sk-label" />
              <span className="sk sk-title" />
              <span className="sk sk-text" />
              <span className="sk sk-text short" />
              <span className="sk sk-button" />
            </>
          ) : null}
          {variant === 'row' ? (
            <>
              <span className="sk sk-avatar" />
              <span className="sk-lines">
                <span className="sk sk-text" />
                <span className="sk sk-text short" />
              </span>
            </>
          ) : null}
          {variant === 'kpi' ? (
            <>
              <span className="sk sk-text short" />
              <span className="sk sk-value" />
              <span className="sk sk-text short" />
            </>
          ) : null}
          {variant === 'line' ? <span className="sk sk-text" /> : null}
        </div>
      ))}
    </div>
  );
}
