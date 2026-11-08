// The sheet of one photo (Galeria.dc.html): the big image (tap it for the full-screen viewer), its
// state, where it was used, the note, «El equipo puede editarla con IA», Guardar (only what changed
// is PATCHed) and «Quitar de la galería» behind a confirmation.
import { useDeleteFoto, useUpdateFoto, type PhotoOutput } from '@compartido/api/capturas';
import { inUseWarning, photoName, photoPatch, photoTone } from '@compartido/logic/galeria';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Icon } from '@/components/icons';
import { ApiImage, Badge, Button, ConfirmSheet, ErrorRetry, Field, Sheet, SwitchRow, T, useToast } from '@/components/ui';
import { haptic } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';

export function PhotoSheet({
  photo,
  onClose,
  onOpenViewer,
  onDirtyChange,
  covered,
}: {
  photo: PhotoOutput;
  onClose: () => void;
  /** Tapping the image opens the full-screen viewer on this photo. */
  onOpenViewer: () => void;
  /** Unsaved changes: the viewer then keeps this photo when it closes. */
  onDirtyChange?: (dirty: boolean) => void;
  /** The viewer is on top: the sheet ignores the back button meanwhile. */
  covered?: boolean;
}) {
  const toast = useToast();
  const update = useUpdateFoto();
  const remove = useDeleteFoto();
  const [note, setNote] = useState(photo.note ?? '');
  const [allowAi, setAllowAi] = useState(photo.allow_ai_edit);
  const [confirming, setConfirming] = useState(false);
  const patch = photoPatch(photo, note, allowAi);
  const dirty = Object.keys(patch).length > 0;
  const warning = inUseWarning(photo);

  const changeNote = (text: string) => {
    setNote(text);
    onDirtyChange?.(Object.keys(photoPatch(photo, text, allowAi)).length > 0);
  };
  const changeAi = (next: boolean) => {
    setAllowAi(next);
    onDirtyChange?.(Object.keys(photoPatch(photo, note, next)).length > 0);
  };

  const save = () => {
    if (!dirty || update.isPending) return;
    update.mutate(
      { photoId: photo.id, patch },
      {
        onSuccess: () => {
          haptic('actionSuccess');
          toast.show('Foto guardada.');
          onClose();
        },
        onError: () => haptic('actionError'),
      },
    );
  };

  const confirmRemove = () =>
    remove.mutate(photo.id, {
      onSuccess: () => {
        setConfirming(false);
        haptic('actionSuccess');
        toast.show('Foto quitada de la galería.');
        onClose();
      },
      onError: () => haptic('actionError'),
    });

  return (
    <>
      <Sheet
        label="Foto"
        onClose={onClose}
        suspended={confirming || update.isPending || covered}
        testID="photo-sheet"
        header={
          <View style={styles.head}>
            <T variant="etiqueta" soft accessibilityRole="header">
              Foto
            </T>
            <Pressable accessibilityRole="button" accessibilityLabel="Cerrar" onPress={onClose} style={styles.close} testID="photo-sheet-close">
              <Icon name="cerrar" size={22} color={colors.inkSoft} />
            </Pressable>
          </View>
        }
      >
        <Pressable
          accessibilityRole="imagebutton"
          accessibilityLabel={photo.note ? `Foto: ${photo.note}` : 'Foto de la galería'}
          accessibilityHint="Abre la foto a pantalla completa: pellizca para acercarla y desliza para ver las demás."
          onPress={onOpenViewer}
          style={styles.big}
          testID="photo-sheet-image"
        >
          <ApiImage path={photo.url} style={StyleSheet.absoluteFill} recyclingKey={photo.id} />
        </Pressable>
        <View style={styles.state}>
          <Badge tone={photoTone(photo.tone)}>{photo.label}</Badge>
          <T variant="detalle" soft style={styles.used}>
            {photo.used_in?.text || 'Todavía sin usar'}
          </T>
        </View>
        <Field
          label="Nota para el equipo (opcional)"
          value={note}
          onChangeText={changeNote}
          multiline
          placeholder="Por ejemplo: recórtala para que no se lean nombres de clientes."
          editable={!update.isPending}
          testID="photo-note"
        />
        <SwitchRow label="El equipo puede editarla con IA" value={allowAi} onChange={changeAi} disabled={update.isPending} testID="photo-ai" />
        <ErrorRetry error={update.error} />
        <Button variant="primary" block disabled={!dirty} loading={update.isPending} loadingLabel="Guardando…" onPress={save} testID="photo-save">
          Guardar
        </Button>
        <Button
          variant="ghost"
          block
          onPress={() => {
            remove.reset();
            setConfirming(true);
          }}
          accessibilityLabel={`Quitar de la galería: ${photoName(photo)}`}
        >
          <T color={colors.alert} center>
            Quitar de la galería
          </T>
        </Button>
      </Sheet>
      {confirming ? (
        <ConfirmSheet
          title="¿Quitar esta foto de la galería?"
          tone="danger"
          confirmLabel="Quitar la foto"
          busy={remove.isPending}
          error={remove.error}
          onConfirm={confirmRemove}
          onClose={() => setConfirming(false)}
        >
          <View style={styles.paragraphs}>
            <T soft>Se borran la foto y su archivo; el equipo ya no podrá usarla.</T>
            {warning ? <T soft>{warning}</T> : null}
          </View>
        </ConfirmSheet>
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  close: { width: shell.touch + 4, height: shell.touch + 4, marginRight: -space[2], alignItems: 'center', justifyContent: 'center' },
  big: { height: 220, borderRadius: radius.md, overflow: 'hidden', backgroundColor: colors.line },
  state: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: space[2] },
  used: { flexShrink: 1 },
  paragraphs: { gap: space[2] },
});
