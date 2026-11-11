import type { PieceMedia, PieceImage, RejectedEdit } from '@compartido/api/imagenes';
import { sameOrigin } from '@compartido/api/capturas';
import { imageAspect, IMAGE_KIND_LABEL, orderedImages, reviewLines, TEMPLATE_LABEL } from '@compartido/logic/imagenes';
import { useEffect, useRef, useState } from 'react';
import { ScrollView, StyleSheet, View, type ScrollViewInstance } from 'react-native';
import { ApiImage, Badge, Button, Card, Note, Section, T } from '@/components/ui';
import { useMotion } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';

function ImageFrame({ image, original }: { image: PieceImage; original: boolean }) {
  const path = original ? image.source_photos[0]?.url : image.url;
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  if (failed || !sameOrigin(path)) {
    return <Note tone="error" title="No se pudo cargar la imagen" actions={
      <Button size="small" onPress={() => { setFailed(false); setAttempt((value) => value + 1); }}>Reintentar</Button>
    } />;
  }
  return <ApiImage key={attempt} path={path} contentFit="contain" style={[styles.image, { aspectRatio: imageAspect(image) }]}
    accessibilityLabel={original ? `Original de la foto. ${image.alt}` : image.alt}
    testID={original ? 'piece-image-original' : `piece-image-${image.position}`} onError={() => setFailed(true)} />;
}

/** IMG-11 criterion 3: the AI edit the visual check rejected stays visible, with why, so Gustavo judges it himself. */
function Rejected({ edit, alt }: { edit: RejectedEdit; alt: string }) {
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const ratio = edit.width && edit.height ? edit.width / edit.height : 4 / 5;
  return (
    <View testID="piece-image-rejected" collapsable={false} style={styles.rejected}>
      <View style={styles.labels}>
        <Badge tone="warn">Edición con IA descartada</Badge>
        <T variant="detalle" soft>No se publica</T>
      </View>
      {failed ? (
        <Note tone="error" title="No se pudo cargar la imagen" actions={
          <Button size="small" onPress={() => { setFailed(false); setAttempt((value) => value + 1); }}>Reintentar</Button>
        } />
      ) : (
        <View style={styles.frame}>
          <ApiImage key={attempt} path={edit.url} contentFit="contain" style={[styles.image, { aspectRatio: ratio }]}
            accessibilityLabel={`Edición con IA descartada. ${alt}`} onError={() => setFailed(true)} />
        </View>
      )}
      {edit.reasons.length ? <T variant="detalle">Por qué la descartó el verificador:</T> : null}
      {edit.reasons.map((reason, i) => <T key={i} variant="detalle" soft>{`• ${reason}`}</T>)}
    </View>
  );
}

function Gallery({ images, media }: { images: PieceImage[]; media: PieceMedia }) {
  const pager = useRef<ScrollViewInstance>(null);
  const [width, setWidth] = useState(0);
  const [index, setIndex] = useState(0);
  const [original, setOriginal] = useState(false);
  const { reduced } = useMotion();
  const current = images[index]!;
  const compare = current.edited && Boolean(sameOrigin(current.source_photos[0]?.url));
  const go = (next: number) => { setOriginal(false); setIndex(next); };
  useEffect(() => { pager.current?.scrollTo({ x: index * width, animated: !reduced }); }, [index, width, reduced]);

  return (
    <View testID="piece-images" collapsable={false} style={styles.content}>
      <View style={styles.labels}>
        <Badge tone="info">{IMAGE_KIND_LABEL[media.image_kind ?? current.kind]}</Badge>
        {current.edited ? <Badge tone="info">Editada con IA</Badge> : current.kind === 'foto' ? <T variant="detalle">Se publica tal cual</T> : null}
      </View>
      <View onLayout={(event) => setWidth(event.nativeEvent.layout.width)} style={styles.frame}>
        <ScrollView ref={pager} testID="piece-images-pager" horizontal pagingEnabled showsHorizontalScrollIndicator={false}
          onMomentumScrollEnd={(event) => {
            if (width) go(Math.max(0, Math.min(images.length - 1, Math.round(event.nativeEvent.contentOffset.x / width))));
          }}>
          {images.map((image, page) => (
            <View key={image.id} style={{ width: width || undefined }} collapsable={false}
              accessibilityElementsHidden={page !== index} importantForAccessibility={page === index ? 'auto' : 'no-hide-descendants'}>
              {width ? <ImageFrame key={`${image.sha256}:${original && page === index}`} image={image} original={original && page === index} /> : null}
            </View>
          ))}
        </ScrollView>
      </View>
      {images.length > 1 ? <View style={styles.controls} collapsable={false}>
        <Button size="small" disabled={index === 0} onPress={() => go(index - 1)} testID="piece-image-prev">Anterior</Button>
        <T testID="piece-image-count" accessibilityLiveRegion="polite">{`${index + 1}/${images.length}`}</T>
        <Button size="small" disabled={index === images.length - 1} onPress={() => go(index + 1)} testID="piece-image-next">Siguiente</Button>
      </View> : null}
      {compare ? <Button size="small" onPress={() => setOriginal((value) => !value)} testID="piece-image-compare">
        {original ? 'Ver editada' : 'Ver original'}
      </Button> : null}
      {current.rejected_edit && sameOrigin(current.rejected_edit.url) ? <Rejected key={current.rejected_edit.url} edit={current.rejected_edit} alt={current.alt} /> : null}
      {current.template ? <T variant="detalle" soft>{`Plantilla: ${TEMPLATE_LABEL[current.template]}`}</T> : null}
      {current.reason || media.image_reason ? <T variant="detalle">{current.reason || media.image_reason}</T> : null}
      <T variant="detalle" soft>{`Texto alternativo: ${current.alt}`}</T>
      {reviewLines(current.review).map((line, i) => <T key={i} variant="detalle" soft>{line}</T>)}
      {reviewLines(media.image_review).length ? <View style={styles.content}>
        <T variant="detalle">Revisión de la pieza</T>
        {reviewLines(media.image_review).map((line, i) => <T key={i} variant="detalle" soft>{line}</T>)}
      </View> : null}
    </View>
  );
}

export function PieceImages({ piece }: { piece: PieceMedia & { status: string } }) {
  const images = orderedImages(piece.images);
  if (!images.length) return piece.status === 'preparing'
    ? <Section label="Imagen"><T soft>La imagen aparece cuando el equipo la prepare</T></Section> : null;
  return <Section label="Imagen"><Card><Gallery key={images.map((image) => `${image.id}:${image.sha256}`).join(',')} images={images} media={piece} /></Card></Section>;
}

const styles = StyleSheet.create({
  content: { gap: space[3] },
  labels: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: space[2] },
  frame: { overflow: 'hidden', borderRadius: radius.md, backgroundColor: colors.line },
  rejected: { gap: space[2], paddingTop: space[3], borderTopWidth: 1, borderTopColor: colors.line },
  image: { width: '100%', aspectRatio: 4 / 5 },
  controls: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: space[2] },
});
