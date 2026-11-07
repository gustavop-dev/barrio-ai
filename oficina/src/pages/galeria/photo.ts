import type { GaleriaFiltro, PhotoOutput } from '../../api/capturas';
import { shortDay } from '../../capture/parts';
import type { Tone } from '../../components/ui';

export const FILTERS: readonly { value: GaleriaFiltro; label: string }[] = [
  { value: 'todas', label: 'Todas' },
  { value: 'sin_usar', label: 'Sin usar' },
  { value: 'elegidas', label: 'Elegidas' },
  { value: 'publicadas', label: 'Publicadas' },
];

export function isFiltro(value: string | null): value is GaleriaFiltro {
  return FILTERS.some((filter) => filter.value === value);
}

/** The API sends `tone` (info, muted, ok); anything else reads as muted. */
export function photoTone(tone: string): Tone {
  return tone === 'info' || tone === 'ok' || tone === 'muted' ? tone : 'muted';
}

/** «Foto del 3 nov, elegida · dom 8». */
export function photoName(photo: Pick<PhotoOutput, 'created_at' | 'label'>): string {
  const date = new Date(photo.created_at);
  const day = Number.isNaN(date.getTime()) ? '' : ` del ${shortDay(date)}`;
  return `Foto${day}, ${photo.label.toLowerCase()}`;
}
