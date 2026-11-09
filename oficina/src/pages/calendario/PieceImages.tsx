import { useRef, useState } from 'react';
import type { PieceImage, PieceMedia } from '../../../../compartido/src/api/imagenes';
import { imageAspect, IMAGE_KIND_LABEL, orderedImages, reviewLines, TEMPLATE_LABEL } from '../../../../compartido/src/logic/imagenes';
import { sameOrigin } from '../../api/capturas';
import { Badge, Button, Card, Note, Section } from '../../components/ui';
import '../../components/ui/imagenes.css';

function ImageFrame({ path, alt, ratio, active }: { path: string | undefined; alt: string; ratio: number; active: boolean }) {
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const src = sameOrigin(path);
  if (failed || !src) return <Note tone="error" title="No se pudo cargar la imagen" actions={
    <Button size="small" disabled={!active} onClick={() => { setFailed(false); setAttempt((value) => value + 1); }}>Reintentar</Button>
  } />;
  return <img key={attempt} src={src} alt={alt} style={{ aspectRatio: ratio }} onError={() => setFailed(true)} />;
}

function Gallery({ images, media }: { images: PieceImage[]; media: PieceMedia }) {
  const pager = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);
  const [original, setOriginal] = useState(false);
  const current = images[index]!;
  const compare = current.edited && Boolean(sameOrigin(current.source_photos[0]?.url));
  const go = (next: number) => {
    setOriginal(false);
    setIndex(next);
    if (pager.current) pager.current.scrollLeft = next * pager.current.clientWidth;
  };
  return <div className="piece-images" data-testid="piece-images">
    <div className="piece-image-labels">
      <Badge tone="info">{IMAGE_KIND_LABEL[media.image_kind ?? current.kind]}</Badge>
      {current.edited ? <Badge tone="info">Editada con IA</Badge> : current.kind === 'foto' ? <span>Se publica tal cual</span> : null}
    </div>
    <div ref={pager} className="piece-image-pager" role="region" aria-label="Imágenes de la pieza" tabIndex={0}
      onScroll={(event) => {
        const node = event.currentTarget;
        if (!node.clientWidth) return;
        const next = Math.max(0, Math.min(images.length - 1, Math.round(node.scrollLeft / node.clientWidth)));
        if (next !== index) { setIndex(next); setOriginal(false); }
      }}>
      {images.map((image, page) => {
        const hasOriginal = image.edited && Boolean(sameOrigin(image.source_photos[0]?.url));
        return <div key={image.id} className={`piece-image-page${hasOriginal ? ' has-original' : ''}${original && page === index ? ' show-original' : ''}`} aria-hidden={page !== index}>
          <figure className="piece-image-final">
            <ImageFrame path={image.url} alt={image.alt} ratio={imageAspect(image)} active={page === index} />
            {hasOriginal ? <figcaption>Editada con IA</figcaption> : null}
          </figure>
          {hasOriginal ? <figure className="piece-image-original">
            <ImageFrame path={image.source_photos[0]?.url} alt={`Original de la foto. ${image.alt}`} ratio={imageAspect(image)} active={page === index} />
            <figcaption>Original</figcaption>
          </figure> : null}
        </div>;
      })}
    </div>
    {images.length > 1 ? <div className="piece-image-controls">
      <Button size="small" disabled={index === 0} onClick={() => go(index - 1)}>Anterior</Button>
      <span aria-live="polite" data-testid="piece-image-count">{index + 1}/{images.length}</span>
      <Button size="small" disabled={index === images.length - 1} onClick={() => go(index + 1)}>Siguiente</Button>
    </div> : null}
    {compare ? <Button className="piece-image-toggle" size="small" onClick={() => setOriginal((value) => !value)}>{original ? 'Ver editada' : 'Ver original'}</Button> : null}
    {current.template ? <p className="t-detalle text-suave">Plantilla: {TEMPLATE_LABEL[current.template]}</p> : null}
    {current.reason || media.image_reason ? <p>{current.reason || media.image_reason}</p> : null}
    <p className="t-detalle text-suave">Texto alternativo: {current.alt}</p>
    {reviewLines(current.review).map((line, i) => <p key={i} className="t-detalle text-suave">{line}</p>)}
    {reviewLines(media.image_review).length ? <div>
      <p className="t-detalle">Revisión de la pieza</p>
      {reviewLines(media.image_review).map((line, i) => <p key={i} className="t-detalle text-suave">{line}</p>)}
    </div> : null}
  </div>;
}

export function PieceImages({ piece }: { piece: PieceMedia & { status: string } }) {
  const images = orderedImages(piece.images);
  if (!images.length) return piece.status === 'preparing'
    ? <Section label="Imagen"><p className="text-suave">La imagen aparece cuando el equipo la prepare</p></Section> : null;
  return <Section label="Imagen"><Card><Gallery key={images.map((image) => `${image.id}:${image.sha256}`).join(',')} images={images} media={piece} /></Card></Section>;
}
