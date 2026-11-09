// Galería (Galeria.dc.html, FUNCIONES-NUEVAS «Galería», rev 18: photos only). The photos Gustavo
// uploads for his posts; the team decides when to use them and whether to edit them with AI.
// A virtualized 3-column grid, the filter in the route (`/galeria?filtro=sin_usar`), pull to refresh,
// the upload with its progress, and the photo sheet with the full-screen viewer.
import { useGaleria, type PhotoCategory, type GaleriaFiltro, type PhotoOutput } from '@compartido/api/capturas';
import { PROFILE_CONSENT, FILTERS, isFiltro, photoName, photoTone } from '@compartido/logic/galeria';
import { router, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { FlatList, Pressable, RefreshControl, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { Icon } from '@/components/icons';
import { ApiImage, Button, EmptyState, EmptyText, ErrorRetry, FilterChip, Note, PageHeader, Skeleton, T, pageContent } from '@/components/ui';
import { timing, useMotion } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import { PhotoSheet } from './PhotoSheet';
import { PhotoViewer } from './PhotoViewer';
import { UploadProgressCard } from './UploadProgressCard';
import { useGalleryUpload } from './upload';

const COLUMNS = 3;
const GAP = 6;

function PhotoTile({ photo, size, onOpen }: { photo: PhotoOutput; size: number; onOpen: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={photoName(photo)}
      onPress={onOpen}
      style={({ pressed }) => [styles.tile, { width: size, height: size }, pressed ? styles.tilePressed : null]}
      testID={`photo-${photo.id}`}
    >
      <ApiImage path={photo.url} style={StyleSheet.absoluteFill} recyclingKey={photo.id} />
      <View style={[styles.tileLabel, TILE_TONE[photoTone(photo.tone)]]}>
        <T variant="etiqueta" numberOfLines={1} center style={styles.tileText} color={TILE_TEXT[photoTone(photo.tone)]}>
          {photo.label}
        </T>
      </View>
    </Pressable>
  );
}

/**
 * A tile fading in as it joins the grid (`timings.listEnter`). A shared value, not Reanimated `entering`: in the QA, the
 * grid that reloaded right after the capture sheet's Modal closed stayed blank, every tile stuck at opacity 0 (run
 * 42481844121, 05-captura-envios). With reduced motion it is visible at once.
 */
function TileIn({ children }: { children: ReactNode }) {
  const { reduced } = useMotion();
  const shown = useSharedValue(reduced ? 1 : 0);
  useEffect(() => {
    shown.set(withTiming(1, timing('listEnter')));
  }, [shown]);
  const style = useAnimatedStyle(() => ({ opacity: shown.value }));
  return <Animated.View style={style}>{children}</Animated.View>;
}

/** The state label over a tile: the Badge colours (info, muted, ok), solid so it reads over the photo. */
const TILE_TONE = {
  info: { backgroundColor: colors.infoLight },
  ok: { backgroundColor: colors.brandLight },
  muted: { backgroundColor: colors.surface },
  warn: { backgroundColor: colors.postIt },
  bad: { backgroundColor: colors.surface },
} as const;
const TILE_TEXT = { info: colors.info, ok: colors.brandDeep, muted: colors.inkSoft, warn: colors.ink, bad: colors.alert } as const;

export function GaleriaScreen() {
  const params = useLocalSearchParams<{ filtro?: string }>();
  // The filter of the link, until Gustavo picks another one (a new link resets it).
  const linked: GaleriaFiltro = isFiltro(params.filtro) ? params.filtro : 'todas';
  const [choice, setChoice] = useState<{ link: GaleriaFiltro; value: GaleriaFiltro } | null>(null);
  const filtro = choice && choice.link === linked ? choice.value : linked;
  const galeria = useGaleria(filtro);
  const [category, setCategory] = useState<PhotoCategory>('posts');
  const upload = useGalleryUpload(category);
  const { width } = useWindowDimensions();
  const { bottom } = useContentInsets();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedSnapshot, setSelectedSnapshot] = useState<PhotoOutput | null>(null);
  const [viewerAt, setViewerAt] = useState<number | null>(null);
  const [viewed, setViewed] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const size = Math.floor((width - shell.gutter * 2 - GAP * (COLUMNS - 1)) / COLUMNS);
  const items = galeria.items;
  const current = selectedId ? (items.find((photo) => photo.id === selectedId) ?? selectedSnapshot) : null;
  const emptyGallery = galeria.isSuccess && items.length === 0 && filtro === 'todas';
  const emptyFilter = galeria.isSuccess && items.length === 0 && filtro !== 'todas';

  const setFiltro = (next: GaleriaFiltro) => {
    setChoice({ link: linked, value: next });
    router.setParams({ filtro: next === 'todas' ? undefined : next });
  };

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

  const openViewer = () => {
    const index = current ? items.findIndex((photo) => photo.id === current.id) : -1;
    setViewed(null);
    setViewerAt(index >= 0 ? index : 0);
  };

  /** Back from the viewer: the sheet follows the photo on screen, unless the open one has unsaved changes. */
  const closeViewer = () => {
    const landed = viewed !== null ? items[viewed] : undefined;
    if (landed && !dirty && landed.id !== selectedId) open(landed);
    setViewerAt(null);
  };

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await galeria.refetch();
    } finally {
      setRefreshing(false);
    }
  }, [galeria]);

  const header = (
    <View style={styles.header}>
      <PageHeader title="Galería" subtitle="Fotos para tus posts y tu perfil." />
      <T variant="detalle">Categoría al subir</T>
      <View style={styles.chips}>
        <FilterChip pressed={category === 'posts'} onPress={() => { if (!upload.pending) setCategory('posts'); }}>Posts</FilterChip>
        <FilterChip pressed={category === 'perfil'} onPress={() => { if (!upload.pending) setCategory('perfil'); }} testID="upload-category-perfil">Perfil</FilterChip>
      </View>
      {category === 'perfil' ? <Note tone="info">{PROFILE_CONSENT}</Note> : null}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={upload.pending ? 'Subiendo…' : 'Subir fotos'}
        accessibilityState={{ busy: upload.pending, disabled: upload.pending }}
        disabled={upload.pending}
        onPress={() => void upload.pick()}
        style={({ pressed }) => [styles.upload, pressed ? styles.uploadPressed : null]}
        testID="gallery-upload"
      >
        <Icon name="galeria" size={22} color={upload.pending ? colors.inkSoft : colors.ink} />
        <T color={upload.pending ? colors.inkSoft : colors.ink}>{upload.pending ? 'Subiendo…' : 'Subir fotos'}</T>
      </Pressable>
      <T variant="detalle" soft>
        Para usar la cámara, toca el botón aguamarina y elige «Foto para la galería».
      </T>
      {upload.rejected ? (
        <T variant="detalle" color={colors.alert}>
          {upload.rejected}
        </T>
      ) : null}
      {upload.photos.length ? <UploadProgressCard upload={upload} /> : null}
      <Note tone="info">El equipo decide cuándo usarlas y si las edita con IA. Tú puedes dejar una nota o prohibir la edición en cada foto.</Note>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chips}
        style={styles.chipStrip}
        accessibilityRole="toolbar"
        accessibilityLabel="Filtrar fotos"
        testID="gallery-filters"
      >
        {FILTERS.map((option) => (
          <FilterChip key={option.value} pressed={filtro === option.value} onPress={() => setFiltro(option.value)} testID={`filtro-${option.value}`}>
            {option.label}
          </FilterChip>
        ))}
      </ScrollView>
      {galeria.isPending ? <Skeleton variant="row" count={3} label="Cargando la galería…" /> : null}
      <ErrorRetry error={galeria.error} onRetry={() => void galeria.refetch()} />
    </View>
  );

  const footer = (
    <View style={styles.footer}>
      {galeria.hasNextPage ? (
        <Button block loading={galeria.isFetchingNextPage} loadingLabel="Cargando…" onPress={() => void galeria.fetchNextPage()}>
          Ver más fotos
        </Button>
      ) : null}
      {emptyGallery ? (
        <EmptyState title="Todavía no hay fotos">
          <EmptyText>Sube fotos tuyas, de eventos o de tu trabajo. El equipo las usará en tus posts cuando encajen.</EmptyText>
        </EmptyState>
      ) : null}
      {emptyFilter ? (
        <T variant="detalle" soft center style={styles.noMatch}>
          {filtro === 'perfil' ? 'Añade fotos a Perfil' : 'No hay fotos con este filtro.'}
        </T>
      ) : null}
    </View>
  );

  return (
    <>
      <FlatList
        testID="screen-galeria"
        style={styles.screen}
        contentContainerStyle={[pageContent, styles.content, { paddingBottom: bottom }]}
        data={items}
        keyExtractor={(photo) => photo.id}
        numColumns={COLUMNS}
        columnWrapperStyle={styles.row}
        ListHeaderComponent={header}
        ListFooterComponent={footer}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} colors={[colors.brandDeep]} tintColor={colors.brandDeep} />}
        accessibilityLabel="Fotos"
        initialNumToRender={18}
        windowSize={7}
        renderItem={({ item }) => (
          <TileIn>
            <PhotoTile photo={item} size={size} onOpen={() => open(item)} />
          </TileIn>
        )}
      />
      {current ? (
        <PhotoSheet
          key={current.id}
          photo={current}
          onClose={close}
          onOpenViewer={openViewer}
          onDirtyChange={setDirty}
          covered={viewerAt !== null}
        />
      ) : null}
      {viewerAt !== null && items.length ? <PhotoViewer photos={items} index={viewerAt} onIndex={setViewed} onClose={closeViewer} /> : null}
    </>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  content: { gap: GAP },
  header: { gap: 14, marginBottom: space[2] },
  upload: {
    minHeight: 64,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: colors.inkSoft,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
  },
  uploadPressed: { backgroundColor: colors.paper },
  chipStrip: { marginHorizontal: -shell.gutter },
  chips: { gap: space[2], paddingHorizontal: shell.gutter },
  row: { gap: GAP },
  tile: { borderRadius: radius.sm, overflow: 'hidden', backgroundColor: colors.line },
  tilePressed: { opacity: 0.85 },
  tileLabel: { position: 'absolute', left: 4, right: 4, bottom: 4, borderRadius: radius.pill, paddingHorizontal: 6, paddingVertical: 2 },
  tileText: { fontSize: 11, letterSpacing: 0.66 },
  footer: { gap: space[3], marginTop: space[3] },
  noMatch: { paddingVertical: space[4] },
});
