// The upload under way: «Subiendo 10 de 23 fotos…», a bar that moves as each request of up to ten
// photos gets in, and a thumbnail per photo marked as waiting, on its way or uploaded. On a failure,
// «Reintentar» sends only what did not get in.
import { ApiError } from '@compartido/api/client';
import type { PickedPhoto } from '@/capture/types';
import { useEffect } from 'react';
import { ActivityIndicator, Image, ScrollView, StyleSheet, View } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';
import { Icon } from '@/components/icons';
import { Button, Card, ErrorRetry, T } from '@/components/ui';
import { timing } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';
import type { GalleryUpload } from './upload';

/** The capture sheet's explanation of a 413 (capture/sendError.ts), for photos only. */
const TOO_BIG = 'Cada foto puede pesar hasta 10 MB. Descarta las que faltan o elige fotos más livianas.';

type PhotoState = 'esperando' | 'subiendo' | 'subida';

export function photoState(index: number, done: number, sending: number): PhotoState {
  if (index < done) return 'subida';
  if (index < done + sending) return 'subiendo';
  return 'esperando';
}

const STATE_LABEL: Record<PhotoState, string> = { esperando: 'en espera', subiendo: 'subiendo', subida: 'subida' };

function Thumb({ photo, index, state }: { photo: PickedPhoto; index: number; state: PhotoState }) {
  return (
    <View style={styles.thumb} accessible accessibilityLabel={`Foto ${index + 1}, ${STATE_LABEL[state]}`} testID={`upload-${index}-${state}`}>
      <Image source={{ uri: photo.uri }} style={[styles.thumbImage, state === 'esperando' ? styles.waiting : null]} />
      {state === 'subiendo' ? (
        <View style={styles.overlay}>
          <ActivityIndicator size="small" color={colors.paper} />
        </View>
      ) : null}
      {state === 'subida' ? (
        <View style={styles.done}>
          <Icon name="check" size={14} color={colors.onBrand} />
        </View>
      ) : null}
    </View>
  );
}

export function UploadProgressCard({ upload }: { upload: GalleryUpload }) {
  const { photos, progress, pending, error } = upload;
  const total = progress?.total ?? photos.length;
  const done = progress?.done ?? 0;
  const sending = pending ? (progress?.sending ?? 0) : 0;
  const fraction = total > 0 ? done / total : 0;
  const width = useSharedValue(fraction);

  useEffect(() => {
    width.set(withTiming(fraction, timing('progress')));
  }, [fraction, width]);

  const fill = useAnimatedStyle(() => ({ width: `${width.value * 100}%` }));
  const title = pending
    ? `Subiendo ${Math.min(total, done + sending)} de ${total} ${total === 1 ? 'foto' : 'fotos'}…`
    : `${done} de ${total} ${total === 1 ? 'foto subida' : 'fotos subidas'}`;

  return (
    <Card compact>
      <T variant="detalle" accessibilityLiveRegion="polite" testID="upload-title">
        {title}
      </T>
      <View
        style={styles.bar}
        accessible
        accessibilityRole="progressbar"
        accessibilityLabel="Subida de fotos"
        accessibilityValue={{ min: 0, max: total, now: done, text: title }}
      >
        <Animated.View style={[styles.fill, fill]} />
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.thumbs}>
        {photos.map((photo, index) => (
          <Thumb key={photo.id} photo={photo} index={index} state={photoState(index, done, sending)} />
        ))}
      </ScrollView>
      {error && !pending ? (
        <>
          {/* A 413 says why, as the capture sheet does (backlog #27): one from the proxy carries no readable detail. */}
          {error instanceof ApiError && error.status === 413 ? (
            <ErrorRetry error={error} title="Hay fotos demasiado grandes" message={TOO_BIG} onRetry={upload.retry} />
          ) : (
            <ErrorRetry error={error} title="No se pudieron subir todas las fotos" onRetry={upload.retry} />
          )}
          <Button size="small" variant="ghost" quiet onPress={upload.dismiss}>
            Descartar las que faltan
          </Button>
        </>
      ) : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  bar: { height: 8, borderRadius: radius.pill, backgroundColor: colors.line, overflow: 'hidden' },
  fill: { height: 8, backgroundColor: colors.brandDeep },
  thumbs: { gap: space[2] },
  thumb: { width: 48, height: 48, borderRadius: radius.sm, overflow: 'hidden', backgroundColor: colors.line },
  thumbImage: { width: '100%', height: '100%' },
  waiting: { opacity: 0.45 },
  overlay: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, backgroundColor: colors.backdrop, alignItems: 'center', justifyContent: 'center' },
  done: { position: 'absolute', right: 2, bottom: 2, width: 18, height: 18, borderRadius: radius.pill, backgroundColor: colors.brand, alignItems: 'center', justifyContent: 'center' },
});
