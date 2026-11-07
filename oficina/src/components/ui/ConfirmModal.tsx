import { useId, useState, type FormEvent, type ReactNode } from 'react';
import { Button, type ButtonVariant } from './Button';
import { ErrorRetry } from './ErrorRetry';
import { Modal } from './Modal';

export interface ConfirmModalProps {
  title: string;
  /** The consequence, in plain words («La pieza no saldrá y ese día quedará sin publicación»). */
  children?: ReactNode;
  confirmLabel: string;
  /** Label while `busy` (defaults to «Enviando…»). */
  busyLabel?: string;
  cancelLabel?: string;
  /** primary (0ff1ce), danger (alerta outline) or stop (alerta fill). */
  tone?: Extract<ButtonVariant, 'primary' | 'danger' | 'stop'>;
  /** required: Confirm stays disabled until there is text. optional: may be empty. none: no field. */
  note?: 'required' | 'optional' | 'none';
  noteLabel?: string;
  notePlaceholder?: string;
  initialNote?: string;
  busy?: boolean;
  /** Error of the last attempt (shown inside the modal, which stays open). */
  error?: unknown;
  /** Receives the trimmed note ('' with note="none"). */
  onConfirm: (note: string) => void;
  onClose: () => void;
}

/** Confirmation: title, consequence, an optional or required note, and Cancelar / Confirmar. */
export function ConfirmModal({
  title,
  children,
  confirmLabel,
  busyLabel = 'Enviando…',
  cancelLabel = 'Cancelar',
  tone = 'primary',
  note = 'none',
  noteLabel = 'Nota',
  notePlaceholder,
  initialNote = '',
  busy = false,
  error,
  onConfirm,
  onClose,
}: ConfirmModalProps) {
  const [text, setText] = useState(initialNote);
  const fieldId = useId();
  const descriptionId = useId();
  const missing = note === 'required' && !text.trim();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (missing || busy) return;
    onConfirm(note === 'none' ? '' : text.trim());
  };

  return (
    <Modal title={title} onClose={onClose} busy={busy} describedBy={children ? descriptionId : undefined}>
      <form className="confirm" onSubmit={submit} noValidate>
        {children ? (
          <div id={descriptionId} className="confirm-text">
            {children}
          </div>
        ) : null}
        {note !== 'none' ? (
          <div className="field">
            <label htmlFor={fieldId}>
              {noteLabel}
              <span className="field-flag">{note === 'required' ? ' · obligatoria' : ' · opcional'}</span>
            </label>
            <textarea
              id={fieldId}
              rows={3}
              value={text}
              placeholder={notePlaceholder}
              required={note === 'required'}
              aria-required={note === 'required' || undefined}
              onChange={(event) => setText(event.target.value)}
            />
          </div>
        ) : null}
        <ErrorRetry error={error} />
        <div className="confirm-actions">
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            {cancelLabel}
          </Button>
          <Button type="submit" variant={tone} disabled={missing} loading={busy} loadingLabel={busyLabel}>
            {confirmLabel}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
