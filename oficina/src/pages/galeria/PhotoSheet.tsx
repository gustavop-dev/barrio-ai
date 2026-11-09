// The sheet of one photo (Galeria.dc.html): big image, state, where it was used, the note,
// «Edición con IA», Guardar and «Quitar de la galería» (with confirmation).
import { AIEditControl } from '../../components/ui/AIEditControl';
import { useId, useState } from 'react';
import { sameOrigin, useDeleteFoto, useUpdateFoto, type PhotoOutput, type PhotoPatch } from '../../api/capturas';
import { Sheet } from '../../capture/Sheet';
import { IconCerrar } from '../../components/icons';
import { Badge, Button, ConfirmModal, ErrorRetry, useToast } from '../../components/ui';
import { inUseWarning, photoPatch, photoTone } from './photo';

export function PhotoSheet({ photo, onClose }: { photo: PhotoOutput; onClose: () => void }) {
  const toast = useToast();
  const update = useUpdateFoto();
  const remove = useDeleteFoto();
  const noteId = useId();
  const [note, setNote] = useState(photo.note ?? '');
  const [aiEdit, setAiEdit] = useState(photo.ai_edit);
  const [confirming, setConfirming] = useState(false);
  const src = sameOrigin(photo.url);
  const warning = inUseWarning(photo);
  const patch: PhotoPatch = photoPatch(photo, note, aiEdit);
  const dirty = Object.keys(patch).length > 0;

  const save = () =>
    update.mutate(
      { photoId: photo.id, patch },
      {
        onSuccess: () => {
          toast.show('Foto guardada.');
          onClose();
        },
      },
    );

  const confirmRemove = () =>
    remove.mutate(photo.id, {
      onSuccess: () => {
        setConfirming(false);
        toast.show('Foto quitada de la galería.');
        onClose();
      },
    });

  return (
    <>
      <Sheet label="Foto" onClose={onClose} suspended={confirming || update.isPending} className="gal-sheet">
        <div className="gal-sheet-head">
          <p className="section-label">Foto</p>
          <button type="button" className="gal-close" aria-label="Cerrar" onClick={onClose}>
            <IconCerrar size={22} />
          </button>
        </div>
        <div className="gal-big">{src ? <img src={src} alt={photo.note ? `Foto: ${photo.note}` : 'Foto de la galería'} /> : null}</div>
        <div className="gal-state">
          <Badge tone={photoTone(photo.tone)}>{photo.label}</Badge>
          <span className="t-detalle text-suave">{photo.used_in?.text || 'Todavía sin usar'}</span>
        </div>
        <form
          className="gal-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (dirty) save();
          }}
        >
          <div className="field">
            <label htmlFor={noteId}>Nota para el equipo (opcional)</label>
            <textarea id={noteId} rows={3} value={note} placeholder="Por ejemplo: recórtala para que no se lean nombres de clientes." onChange={(event) => setNote(event.target.value)} />
          </div>
          <AIEditControl value={aiEdit} onChange={setAiEdit} disabled={update.isPending} testID="photo-ai" />
          <ErrorRetry error={update.error} />
          <Button type="submit" variant="primary" block disabled={!dirty} loading={update.isPending} loadingLabel="Guardando…">
            Guardar
          </Button>
          <Button
            variant="ghost"
            block
            className="gal-remove"
            onClick={() => {
              remove.reset();
              setConfirming(true);
            }}
          >
            Quitar de la galería
          </Button>
        </form>
      </Sheet>
      {confirming ? (
        <ConfirmModal
          title="¿Quitar esta foto de la galería?"
          tone="danger"
          confirmLabel="Quitar la foto"
          busyLabel="Quitando…"
          busy={remove.isPending}
          error={remove.error}
          onConfirm={confirmRemove}
          onClose={() => setConfirming(false)}
        >
          <p>Se borran la foto y su archivo; el equipo ya no podrá usarla.</p>
          {warning ? <p>{warning}</p> : null}
        </ConfirmModal>
      ) : null}
    </>
  );
}
