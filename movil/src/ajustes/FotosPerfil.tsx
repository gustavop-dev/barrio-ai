// Ajustes › Fotos de perfil. Gustavo, 12/11/2026: the Galería left the app («nunca la uso, solo existe ahí para las
// fotos de perfil»); his post photos always arrive with a note through the capture button, and the profile photos
// live here. They are the photos Perfil works from for his portraits and banner (category «perfil», roles 01 Pose y
// sonrisa, 02 Cuerpo del banner, 03 Identidad y gafas) and are never used in posts. Tap one for its sheet (role,
// permission, instructions for Perfil, remove) and the full-screen viewer; «Subir fotos de perfil» adds more.
import { useGaleria, type PhotoOutput } from '@compartido/api/capturas';
import { PROFILE_ROLES, photoName } from '@compartido/logic/galeria';
import { setStatusBarStyle } from 'expo-status-bar';
import { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, View, useWindowDimensions } from 'react-native';
import { Icon } from '@/components/icons';
import { ApiImage, Button, EmptyText, ErrorRetry, Section, Skeleton, T } from '@/components/ui';
import { PhotoSheet } from '@/fotos/PhotoSheet';
import { PhotoViewer } from '@/fotos/PhotoViewer';
import { UploadProgressCard } from '@/fotos/UploadProgressCard';
import { useGalleryUpload } from '@/fotos/upload';
import { colors, radius, shell, space } from '@/theme/tokens';

const COLUMNS = 3;
const GAP = 6;

/** «01 · Pose y sonrisa», or «Sin asignar». */
export function profileRoleLabel(photo: Pick<PhotoOutput, 'profile_role'>): string {
  return PROFILE_ROLES.find((role) => role.value === (photo.profile_role ?? ''))?.label ?? 'Sin asignar';
}

/** The photos in role order (01, 02, 03), the unassigned ones after them, newest first within each. */
export function byRole(photos: readonly PhotoOutput[]): PhotoOutput[] {
  const rank = (photo: PhotoOutput) => (photo.profile_role ? Number(photo.profile_role) : 99);
  return [...photos].sort((a, b) => rank(a) - rank(b));
}

function Tile({ photo, size, onOpen }: { photo: PhotoOutput; size: number; onOpen: () => void }) {
  const role = profileRoleLabel(photo);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${role}. ${photoName(photo)}`}
      onPress={onOpen}
      style={({ pressed }) => [styles.tile, { width: size, height: size }, pressed ? styles.pressed : null]}
      testID={`foto-perfil-${photo.id}`}
    >
      <ApiImage path={photo.url} style={StyleSheet.absoluteFill} recyclingKey={photo.id} />
      <View style={styles.tileLabel}>
        <T variant="etiqueta" numberOfLines={1} center style={styles.tileText}>
          {role}
        </T>
      </View>
    </Pressable>
  );
}

export function FotosPerfilSection() {
  const fotos = useGaleria('perfil');
  const upload = useGalleryUpload('perfil');
  const { width } = useWindowDimensions();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedSnapshot, setSelectedSnapshot] = useState<PhotoOutput | null>(null);
  const [viewerAt, setViewerAt] = useState<number | null>(null);
  const [viewed, setViewed] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);

  const items = byRole(fotos.items);
  const size = Math.floor((width - shell.gutter * 2 - GAP * (COLUMNS - 1)) / COLUMNS);
  const current = selectedId ? (items.find((photo) => photo.id === selectedId) ?? selectedSnapshot) : null;

  const open = useCallback((photo: PhotoOutput) => {
    setSelectedSnapshot(photo);
    setSelectedId(photo.id);
    setDirty(false);
  }, []);

  const close = useCallback(() => {
    setSelectedId(null);
    setSelectedSnapshot(null);
    setDirty(false);
  }, []);

  // Light status bar icons over the viewer's tinta, set before it opens (an Android Modal copies the activity's status
  // bar when it is shown), as the Galería did.
  const openViewer = () => {
    const index = current ? items.findIndex((photo) => photo.id === current.id) : -1;
    setStatusBarStyle('light');
    setViewed(null);
    setViewerAt(index >= 0 ? index : 0);
  };
  const viewerOpen = viewerAt !== null;
  useEffect(() => {
    if (viewerOpen) return () => setStatusBarStyle('dark');
  }, [viewerOpen]);

  /** Back from the viewer: the sheet follows the photo on screen, unless the open one has unsaved changes. */
  const closeViewer = () => {
    const landed = viewed !== null ? items[viewed] : undefined;
    if (landed && !dirty && landed.id !== selectedId) open(landed);
    setViewerAt(null);
  };

  return (
    <Section label="Fotos de perfil" intro="Las fotos con las que Perfil prepara tus retratos y el banner. Nunca se usan en posts.">
      <View style={styles.body} testID="fotos-perfil">
        {fotos.isPending ? <Skeleton variant="row" count={1} label="Cargando las fotos de perfil…" /> : null}
        <ErrorRetry error={fotos.error} onRetry={() => void fotos.refetch()} />
        {fotos.isSuccess && !items.length ? (
          <EmptyText>Todavía no hay fotos de perfil. Sube una pose con sonrisa, una de cuerpo para el banner y una de identidad.</EmptyText>
        ) : null}
        {items.length ? (
          <View style={styles.grid}>
            {items.map((photo) => (
              <Tile key={photo.id} photo={photo} size={size} onOpen={() => open(photo)} />
            ))}
          </View>
        ) : null}
        {fotos.hasNextPage ? (
          <Button block loading={fotos.isFetchingNextPage} loadingLabel="Cargando…" onPress={() => void fotos.fetchNextPage()}>
            Ver más fotos
          </Button>
        ) : null}
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={upload.pending ? 'Subiendo…' : 'Subir fotos de perfil'}
          accessibilityState={{ busy: upload.pending, disabled: upload.pending }}
          disabled={upload.pending}
          onPress={() => void upload.pick()}
          style={({ pressed }) => [styles.upload, pressed ? styles.pressed : null]}
          testID="fotos-perfil-subir"
        >
          <Icon name="galeria" size={22} color={upload.pending ? colors.inkSoft : colors.ink} />
          <T color={upload.pending ? colors.inkSoft : colors.ink}>{upload.pending ? 'Subiendo…' : 'Subir fotos de perfil'}</T>
        </Pressable>
        {upload.rejected ? (
          <T variant="detalle" color={colors.alert}>
            {upload.rejected}
          </T>
        ) : null}
        {upload.photos.length ? <UploadProgressCard upload={upload} /> : null}
      </View>
      {current ? (
        <PhotoSheet key={current.id} photo={current} onClose={close} onOpenViewer={openViewer} onDirtyChange={setDirty} covered={viewerAt !== null} />
      ) : null}
      {viewerAt !== null && items.length ? <PhotoViewer photos={items} index={viewerAt} onIndex={setViewed} onClose={closeViewer} /> : null}
    </Section>
  );
}

const styles = StyleSheet.create({
  body: { gap: space[3] },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: GAP },
  tile: { borderRadius: radius.sm, overflow: 'hidden', backgroundColor: colors.line },
  pressed: { opacity: 0.85 },
  tileLabel: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingVertical: 2, paddingHorizontal: 4, backgroundColor: colors.surface },
  tileText: { letterSpacing: 0, textTransform: 'none' },
  upload: {
    minHeight: 56,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: colors.inkSoft,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: space[2],
  },
});
