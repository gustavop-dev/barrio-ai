// The full-screen loading spinner used while the session opens. Views use Skeleton instead.
export function Loading({ label = 'Cargando…', full = false }: { label?: string; full?: boolean }) {
  return (
    <div className={full ? 'loading full' : 'loading'} role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  );
}
