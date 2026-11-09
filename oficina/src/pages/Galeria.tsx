// Galería (Galeria.dc.html, FUNCIONES-NUEVAS «Galería», rev 18: photos only). The photos Gustavo
// uploads for his posts; the team decides when to use them and whether to edit them with AI.
import { useState, type ChangeEvent, type DragEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CAPTURE_LIMITS, isAcceptedPhoto, sameOrigin, useGaleria, useUploadFotos, type PhotoCategory, type GaleriaFiltro, type PhotoOutput } from '../api/capturas';
import { IconGaleria } from '../components/icons';
import { Badge, Button, ChipStrip, EmptyState, ErrorRetry, FilterChip, Note, Page, Skeleton, useToast } from '../components/ui';
import { PROFILE_CONSENT } from './galeria/photo';
import { PhotoSheet } from './galeria/PhotoSheet';
import { FILTERS, isFiltro, photoName, photoTone, rejectedMessage, uploadedMessage } from './galeria/photo';
import '../capture/capture.css';
import './galeria/galeria.css';

function PhotoTile({ photo, onOpen }: { photo: PhotoOutput; onOpen: () => void }) {
  const src = sameOrigin(photo.url);
  return (
    <li>
      <button type="button" className="gal-tile" onClick={onOpen} aria-label={photoName(photo)}>
        {src ? <img src={src} alt="" loading="lazy" /> : null}
        <Badge tone={photoTone(photo.tone)} className="gal-tile-label">
          {photo.label}
        </Badge>
      </button>
    </li>
  );
}

export function Galeria() {
  const [params, setParams] = useSearchParams();
  const raw = params.get('filtro');
  const filtro: GaleriaFiltro = isFiltro(raw) ? raw : 'todas';
  const galeria = useGaleria(filtro);
  const [category, setCategory] = useState<PhotoCategory>('posts');
  const upload = useUploadFotos({ category });
  const toast = useToast();
  const [selected, setSelected] = useState<PhotoOutput | null>(null);
  const [rejected, setRejected] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const setFiltro = (next: GaleriaFiltro) => {
    setParams(
      (current) => {
        const updated = new URLSearchParams(current);
        if (next === 'todas') updated.delete('filtro');
        else updated.set('filtro', next);
        return updated;
      },
      { replace: true },
    );
  };

  const send = (files: File[]) => {
    if (!files.length) return;
    const ok = files.filter((file) => isAcceptedPhoto(file) && file.size <= CAPTURE_LIMITS.photoBytes);
    const bad = files.filter((file) => !ok.includes(file)).map((file) => file.name || 'una foto');
    setRejected(rejectedMessage(bad));
    if (!ok.length) return;
    upload.mutate(ok, {
      onSuccess: (created) => {
        toast.show(category === 'perfil' ? 'Fotos subidas a Perfil.' : uploadedMessage(created.length || ok.length));
      },
    });
  };

  const onPick = (event: ChangeEvent<HTMLInputElement>) => {
    send(Array.from(event.target.files ?? []));
    event.target.value = '';
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    send(Array.from(event.dataTransfer?.files ?? []));
  };

  // «Vacía» is the whole gallery empty; a filter without matches says so instead.
  const emptyGallery = galeria.isSuccess && galeria.items.length === 0 && filtro === 'todas';
  const emptyFilter = galeria.isSuccess && galeria.items.length === 0 && filtro !== 'todas';
  const current = selected ? (galeria.items.find((photo) => photo.id === selected.id) ?? selected) : null;

  return (
    <Page title="Galería" subtitle="Fotos para tus posts y tu perfil.">
      <div
        className={dragging ? 'gal-body dragging' : 'gal-body'}
        onDragOver={(event) => {
          if (!Array.from(event.dataTransfer?.types ?? []).includes('Files')) return;
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={(event) => {
          if (event.currentTarget === event.target) setDragging(false);
        }}
        onDrop={onDrop}
      >
        <label>Categoría al subir
          <select aria-label="Categoría al subir" value={category} disabled={upload.isPending} onChange={(e) => setCategory(e.target.value as PhotoCategory)}>
            <option value="posts">Posts</option><option value="perfil">Perfil</option>
          </select>
        </label>
        {category === 'perfil' ? <Note tone="info">{PROFILE_CONSENT}</Note> : null}
        <label className={upload.isPending ? 'gal-upload busy' : 'gal-upload'}>
          <IconGaleria size={22} />
          {upload.isPending ? 'Subiendo…' : 'Subir fotos'}
          <span className="gal-upload-desktop desktop-only"> · o suéltalas aquí</span>
          <input type="file" accept="image/*" multiple onChange={onPick} disabled={upload.isPending} className="cap-file" />
        </label>
        <p className="t-detalle text-suave">Para usar la cámara, toca el botón aguamarina y elige «Foto para la galería».</p>
        {rejected ? <p className="field-error">{rejected}</p> : null}
        <ErrorRetry error={upload.error} />
        <Note tone="info" role={null}>
          El equipo decide cuándo usarlas y si las edita con IA. Tú puedes dejar una nota o prohibir la edición en cada foto.
        </Note>

        <ChipStrip label="Filtrar fotos">
          {FILTERS.map((option) => (
            <FilterChip key={option.value} pressed={filtro === option.value} onClick={() => setFiltro(option.value)}>
              {option.label}
            </FilterChip>
          ))}
        </ChipStrip>

        {galeria.isPending ? <Skeleton variant="line" count={3} label="Cargando la galería…" /> : null}
        <ErrorRetry error={galeria.error} onRetry={() => void galeria.refetch()} />

        {galeria.items.length ? (
          <ul className="gal-grid" aria-label="Fotos">
            {galeria.items.map((photo) => (
              <PhotoTile key={photo.id} photo={photo} onOpen={() => setSelected(photo)} />
            ))}
          </ul>
        ) : null}
        {galeria.hasNextPage ? (
          <Button variant="secondary" block loading={galeria.isFetchingNextPage} loadingLabel="Cargando…" onClick={() => void galeria.fetchNextPage()}>
            Ver más fotos
          </Button>
        ) : null}

        {emptyGallery ? (
          <EmptyState title="Todavía no hay fotos">Sube fotos tuyas, de eventos o de tu trabajo. El equipo las usará en tus posts cuando encajen.</EmptyState>
        ) : null}
        {emptyFilter ? <p className="t-detalle text-suave gal-nomatch">{filtro === 'perfil' ? 'Añade fotos a Perfil' : 'No hay fotos con este filtro.'}</p> : null}
      </div>
      {current ? <PhotoSheet key={current.id} photo={current} onClose={() => setSelected(null)} /> : null}
    </Page>
  );
}
