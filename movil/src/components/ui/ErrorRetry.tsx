import { errorMessage, isConflict } from '@compartido/api/errors';
import { Button } from './Button';
import { Note } from './Note';

export { errorMessage, isConflict };

/**
 * Error with retry: title, the backend detail and «Reintentar». A 409 shows «No se puede ahora» in the
 * warn tone. Renders nothing without an error, so it can sit in place.
 */
export function ErrorRetry({ error, onRetry, title, retryLabel = 'Reintentar' }: { error: unknown; onRetry?: () => void; title?: string; retryLabel?: string }) {
  if (!error) return null;
  const conflict = isConflict(error);
  return (
    <Note
      tone={conflict ? 'warn' : 'error'}
      title={title ?? (conflict ? 'No se puede ahora' : 'No se pudo completar')}
      actions={
        onRetry ? (
          <Button variant="secondary" size="small" onPress={onRetry}>
            {retryLabel}
          </Button>
        ) : undefined
      }
    >
      {errorMessage(error)}
    </Note>
  );
}
