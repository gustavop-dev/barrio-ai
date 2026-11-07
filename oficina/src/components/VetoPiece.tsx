import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { rejectAction } from '../api/endpoints';
import { keys } from '../api/queryClient';
import { formatDay, formatTime } from '../lib/format';
import { ErrorNote, Modal } from './ui';

interface VetoProps {
  /** The piece's CONT-09 action: vetoing is rejecting it before its hour. */
  actionId: string;
  slotDate: string;
  scheduledFor: string;
  timeZone?: string | undefined;
  describedBy?: string;
}

function VetoModal({ actionId, slotDate, scheduledFor, timeZone, onClose }: VetoProps & { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState('');
  const mutation = useMutation({
    mutationFn: () => rejectAction(actionId, note.trim()),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.editorialAll });
      void queryClient.invalidateQueries({ queryKey: keys.actionsAll });
      void queryClient.invalidateQueries({ queryKey: keys.overview });
      void queryClient.invalidateQueries({ queryKey: keys.feed });
      onClose();
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (note.trim() && !mutation.isPending) mutation.mutate();
  };
  return (
    <Modal title="Vetar la pieza" onClose={onClose}>
      <form onSubmit={submit}>
        <p>
          La pieza del {formatDay(slotDate)} no saldrá a las {formatTime(scheduledFor, timeZone)} y ese día quedará sin publicación. Queda
          registrada con tu nota.
        </p>
        <label htmlFor="veto-note">Nota</label>
        <textarea
          id="veto-note"
          value={note}
          maxLength={2000}
          required
          onChange={(event) => setNote(event.target.value)}
          placeholder="Por qué no debe publicarse"
        />
        <ErrorNote error={mutation.error} />
        <div className="buttonrow">
          <button type="button" className="secondary" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="danger" disabled={!note.trim() || mutation.isPending}>
            {mutation.isPending ? 'Enviando…' : 'Vetar'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

/** «Vetar» on a piece that has not been published yet (its action is proposed or approved). */
export function VetoPiece(props: VetoProps) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className="danger" aria-describedby={props.describedBy} onClick={() => setOpen(true)}>
        Vetar
      </button>
      {open ? <VetoModal {...props} onClose={() => setOpen(false)} /> : null}
    </>
  );
}
