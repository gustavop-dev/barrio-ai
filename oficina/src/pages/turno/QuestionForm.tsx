import { useQueryClient } from '@tanstack/react-query';
import { useId, useState, type FormEvent } from 'react';
import { undoPregunta } from '../../api/endpoints';
import { useAnswerPregunta, useDeclinePregunta, usePostponePregunta } from '../../api/hooks';
import { keys } from '../../api/queryClient';
import type { Question, QuestionAnswer } from '../../api/types';
import { useCapture } from '../../capture/CaptureContext';
import { IconMicrofono } from '../../components/icons';
import { Button, ConfirmModal, ErrorRetry, errorMessage, isConflict, useToast } from '../../components/ui';
import { longDate } from './model';
import { VisibilityField } from './VisibilityField';

const DETAIL_PLACEHOLDER = 'Cuéntalo como se lo contarías a un colega: qué había, qué hiciste y qué salió.';

/** The proposed text of a `kind=confirm` question. */
function proposedText(question: Question): string {
  const value = question.proposed_value as { texto?: unknown } | null;
  return typeof value?.texto === 'string' ? value.texto : '';
}

function initialPublic(question: Question): boolean {
  const value = question.proposed_value as { uso_publico?: unknown } | null;
  if (question.kind === 'confirm' && typeof value?.uso_publico === 'boolean') return value.uso_publico;
  return Boolean(question.suggested_public);
}

/** The body of POST /preguntas/<id>/responder for what was typed, or null while it is not valid yet. */
export function buildAnswer(question: Question, value: string, text: string, publicUse: boolean): QuestionAnswer | null {
  const detail = text.trim();
  if (question.kind === 'confirm') return detail ? { text: detail, public_use: publicUse } : { accept: true, public_use: publicUse };
  switch (question.answer_type) {
    case 'yes_no':
      if (value !== 'si' && value !== 'no') return null;
      return detail ? { value, text: detail, public_use: publicUse } : { value, public_use: publicUse };
    case 'choice':
      return value ? { value, public_use: publicUse } : null;
    case 'number':
      return value.trim() !== '' && Number.isFinite(Number(value)) ? { value: value.trim(), public_use: publicUse } : null;
    case 'date':
      return /^\d{4}-\d{2}-\d{2}$/.test(value) ? { value, public_use: publicUse } : null;
    default:
      return detail ? { text: detail, public_use: publicUse } : null;
  }
}

/** The answer field for the question's type. */
function AnswerField({
  question,
  value,
  text,
  onValue,
  onText,
}: {
  question: Question;
  value: string;
  text: string;
  onValue: (value: string) => void;
  onText: (text: string) => void;
}) {
  const id = useId();
  if (question.kind === 'confirm') {
    return (
      <>
        <div className="turno-block">
          <p className="turno-label">Lo que el equipo cree</p>
          <p className="turno-proposed">{proposedText(question) || 'Sin texto propuesto.'}</p>
        </div>
        <div className="field">
          <label htmlFor={`${id}-fix`}>
            Corrígelo si no es así<span className="field-flag"> · opcional</span>
          </label>
          <textarea id={`${id}-fix`} rows={3} value={text} onChange={(event) => onText(event.target.value)} />
        </div>
      </>
    );
  }
  switch (question.answer_type) {
    case 'yes_no':
      return (
        <>
          <fieldset className="turno-yesno">
            <legend className="turno-legend">Tu respuesta</legend>
            <div className="turno-yesno-options">
              {(
                [
                  ['si', 'Sí'],
                  ['no', 'No'],
                ] as const
              ).map(([option, label]) => (
                <label key={option} className="turno-pill">
                  <input type="radio" name={`${id}-yn`} value={option} checked={value === option} onChange={() => onValue(option)} />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
          <div className="field">
            <label htmlFor={`${id}-detail`}>Detalle (opcional)</label>
            <textarea id={`${id}-detail`} rows={3} placeholder={DETAIL_PLACEHOLDER} value={text} onChange={(event) => onText(event.target.value)} />
          </div>
        </>
      );
    case 'choice':
      return (
        <div className="field">
          <label htmlFor={`${id}-choice`}>Elige una opción</label>
          <select id={`${id}-choice`} value={value} onChange={(event) => onValue(event.target.value)}>
            <option value="" disabled>
              Elige…
            </option>
            {question.options.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
      );
    case 'number':
      return (
        <div className="field">
          <label htmlFor={`${id}-number`}>Tu respuesta</label>
          <input id={`${id}-number`} type="number" inputMode="decimal" value={value} onChange={(event) => onValue(event.target.value)} />
        </div>
      );
    case 'date':
      return (
        <div className="field">
          <label htmlFor={`${id}-date`}>Tu respuesta</label>
          <input id={`${id}-date`} type="date" value={value} onChange={(event) => onValue(event.target.value)} />
        </div>
      );
    default:
      return (
        <div className="field">
          <label htmlFor={`${id}-text`}>Tu respuesta</label>
          <textarea id={`${id}-text`} rows={3} placeholder={DETAIL_PLACEHOLDER} value={text} onChange={(event) => onText(event.target.value)} />
        </div>
      );
  }
}

/**
 * A team question: the answer field for its type, Público/Privado with the suggestion preselected,
 * Responder, Responder con audio, Más tarde and No quiero compartir esto.
 */
export function QuestionForm({ question }: { question: Question }) {
  const client = useQueryClient();
  const toast = useToast();
  const { openCapture } = useCapture();
  const answer = useAnswerPregunta();
  const postpone = usePostponePregunta();
  const decline = useDeclinePregunta();
  const [value, setValue] = useState('');
  const [text, setText] = useState('');
  const [publicUse, setPublicUse] = useState(() => initialPublic(question));
  const [declining, setDeclining] = useState(false);

  const body = buildAnswer(question, value, text, publicUse);
  const busy = answer.isPending || postpone.isPending || decline.isPending;

  // Toasts and the undo outlive the card (it leaves the list once answered), so they use the client
  // and the toast API directly instead of this component's mutation callbacks.
  const undo = async () => {
    try {
      await undoPregunta(question.id);
      toast.show('Respuesta deshecha. La pregunta vuelve a estar abierta');
    } catch (error) {
      toast.show(isConflict(error) ? 'Ya no se puede deshacer: pasaron más de 15 minutos' : errorMessage(error), { tone: 'error' });
    } finally {
      void Promise.all([keys.tuTurno, keys.preguntasAll, keys.hechos].map((queryKey) => client.invalidateQueries({ queryKey })));
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!body || busy) return;
    try {
      await answer.mutateAsync({ questionId: question.id, answer: body });
      toast.show('Guardado. El equipo ya puede usarlo', { undo: () => void undo() });
    } catch {
      // Shown under the form through answer.error.
    }
  };

  const later = async () => {
    try {
      const result = await postpone.mutateAsync(question.id);
      const back = longDate(result?.postponed_until);
      toast.show(back ? `Pospuesta. Vuelve el ${back}` : 'Pospuesta 3 días');
    } catch {
      // Shown under the form through postpone.error.
    }
  };

  const confirmDecline = async () => {
    try {
      await decline.mutateAsync(question.id);
      setDeclining(false);
      toast.show('Hecho. El equipo no volverá a preguntarlo');
    } catch {
      // Shown inside the modal.
    }
  };

  const submitLabel = question.kind === 'confirm' ? (text.trim() ? 'Guardar corrección' : 'Sí, es correcto') : 'Responder';

  return (
    <>
      <form className="turno-question" onSubmit={submit} noValidate>
        <AnswerField question={question} value={value} text={text} onValue={setValue} onText={setText} />
        <VisibilityField value={publicUse} onChange={setPublicUse} disabled={busy} />
        <ErrorRetry error={answer.error ?? postpone.error} />
        <div className="turno-actions">
          <Button type="submit" variant="primary" block disabled={!body || busy} loading={answer.isPending} loadingLabel="Guardando…">
            {submitLabel}
          </Button>
          <Button
            variant="secondary"
            block
            icon={<IconMicrofono size={20} />}
            onClick={() => openCapture({ tipo: 'pregunta', id: question.id, label: question.question })}
          >
            Responder con audio
          </Button>
          <div className="turno-ghosts">
            <Button variant="ghost" onClick={() => void later()} disabled={busy} loading={postpone.isPending} loadingLabel="Posponiendo…">
              Más tarde
            </Button>
            <Button variant="ghost" quiet onClick={() => setDeclining(true)} disabled={busy}>
              No quiero compartir esto
            </Button>
          </div>
        </div>
      </form>
      {declining ? (
        <ConfirmModal
          title="No compartir esto"
          tone="danger"
          confirmLabel="No quiero compartirlo"
          busy={decline.isPending}
          error={decline.error}
          onConfirm={() => void confirmDecline()}
          onClose={() => {
            decline.reset();
            setDeclining(false);
          }}
        >
          <p>La pregunta se cierra y el equipo no volverá a hacerla. Tampoco podrá contar esto en público.</p>
        </ConfirmModal>
      ) : null}
    </>
  );
}
