// Ajustes › Orientación para el equipo (GET/PUT /api/v1/orientacion): how Gustavo steers the team.
import { useId, useState } from 'react';
import { useOrientacion, useSaveOrientacion } from '../../api/hooks';
import { Button, Card, ErrorRetry, Section, Skeleton, useToast } from '../../components/ui';
import { timeAgo } from '../../lib/format';
import { isUnavailable, Unavailable } from './shared';

export const ORIENTATION_MAX = 4000;

export function OrientacionSection() {
  const orientacion = useOrientacion();
  const save = useSaveOrientacion();
  const toast = useToast();
  const fieldId = useId();
  const hintId = useId();
  /** null while the text is the saved one. */
  const [draft, setDraft] = useState<string | null>(null);
  const saved = orientacion.data?.text ?? '';
  const text = draft ?? saved;
  const tooLong = text.length > ORIENTATION_MAX;
  const changed = draft !== null && draft.trim() !== saved.trim();

  const submit = () =>
    save.mutate(text.trim(), {
      onSuccess: () => {
        setDraft(null);
        toast.show('Orientación guardada. El equipo la usa desde su próxima tarea.');
      },
    });

  return (
    <Section
      label="Orientación para el equipo"
      id="orientacion"
      intro="Tu dirección de alto nivel: temas, tono, prioridades o lo que debe evitar. La leen quien redacta los comentarios, el circuito editorial, el clasificador de la red y el agente líder."
    >
      {orientacion.isPending ? <Skeleton variant="card" label="Cargando la orientación…" /> : null}
      {isUnavailable(orientacion.error) ? (
        <Unavailable>El servidor todavía no guarda la orientación.</Unavailable>
      ) : (
        <ErrorRetry error={orientacion.error} onRetry={() => void orientacion.refetch()} />
      )}
      {orientacion.isSuccess ? (
        <Card className="aj-card">
          <form
            className="aj-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (changed && !tooLong) submit();
            }}
          >
            <div className="field">
              <label htmlFor={fieldId}>Qué quieres que el equipo tenga en cuenta ahora</label>
              <textarea
                id={fieldId}
                rows={5}
                value={text}
                aria-describedby={hintId}
                aria-invalid={tooLong || undefined}
                placeholder="Por ejemplo: este mes, más casos de ProjectApp y nada sobre rondas de inversión."
                onChange={(event) => setDraft(event.target.value)}
              />
              <p id={hintId} className={tooLong ? 'field-error' : 'field-hint'}>
                {text.length} de {ORIENTATION_MAX} caracteres. Es privada: orienta las decisiones y nunca aparece en un texto público.
              </p>
            </div>
            <ErrorRetry error={save.error} />
            <div className="aj-actions">
              <Button type="submit" variant="primary" disabled={!changed || tooLong} loading={save.isPending} loadingLabel="Guardando…">
                Guardar orientación
              </Button>
              {changed ? (
                <Button variant="ghost" onClick={() => setDraft(null)} disabled={save.isPending}>
                  Descartar cambios
                </Button>
              ) : null}
            </div>
            <p className="t-detalle text-suave">
              {orientacion.data.updated_at
                ? `Actualizada ${timeAgo(orientacion.data.updated_at)}${orientacion.data.updated_by ? ` por ${orientacion.data.updated_by}` : ''}.`
                : 'Todavía no has escrito ninguna orientación.'}
            </p>
          </form>
        </Card>
      ) : null}
    </Section>
  );
}
