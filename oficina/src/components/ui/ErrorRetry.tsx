import { ApiError } from '../../api/client';
import { Button } from './Button';

/** The Spanish message to show for any error thrown by the API client or the network. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof TypeError) return 'No hay conexión con el servidor. Comprueba tu red.';
  if (error instanceof Error) return error.message;
  return 'Algo salió mal.';
}

/** 409 is "conflict or safeguard": the action is valid, just not now. */
export function isConflict(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409;
}

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
