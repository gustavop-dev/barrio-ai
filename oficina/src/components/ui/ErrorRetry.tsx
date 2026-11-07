import { errorMessage, isConflict } from '../../../../compartido/src/api/errors';
import { Button } from './Button';

// Shared with the native app (compartido/src/api/errors.ts).
export { errorMessage, isConflict };

export interface ErrorRetryProps {
  error: unknown;
  onRetry?: () => void;
  /** Overrides «No se pudo completar» / «No se puede ahora». */
  title?: string;
  retryLabel?: string;
  className?: string;
}

/**
 * Error with retry: title, the backend detail and «Reintentar». A 409 shows «No se puede ahora»
 * in the warn tone. Renders nothing without an error, so it can sit in place.
 */
export function ErrorRetry({ error, onRetry, title, retryLabel = 'Reintentar', className }: ErrorRetryProps) {
  if (!error) return null;
  const conflict = isConflict(error);
  return (
    <div className={['note', conflict ? 'warn' : 'error', className].filter(Boolean).join(' ')} role="alert">
      <p className="note-title">{title ?? (conflict ? 'No se puede ahora' : 'No se pudo completar')}</p>
      <p className="note-body">{errorMessage(error)}</p>
      {onRetry ? (
        <div className="note-actions">
          <Button variant="secondary" size="small" onClick={onRetry}>
            {retryLabel}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

/** Name kept for the pages written before the redesign. */
export const ErrorNote = ErrorRetry;
