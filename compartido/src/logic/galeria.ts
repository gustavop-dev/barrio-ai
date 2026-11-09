// Galería (FUNCIONES-NUEVAS rev 18 «Galería»): the filters, the tone of each photo's state, its
// accessible name and what the photo sheet PATCHes. Shared by the PWA and the native app.
import type { GaleriaFiltro, PhotoOutput, PhotoPatch } from '../api/capturas';
import type { AIEdit } from '../api/imagenes';
import { shortDay } from './capturas';
import type { Tone } from './tone';

export const FILTERS: readonly { value: GaleriaFiltro; label: string }[] = [
  { value: 'todas', label: 'Todas' },
  { value: 'sin_usar', label: 'Sin usar' },
  { value: 'elegidas', label: 'Elegidas' },
  { value: 'publicadas', label: 'Publicadas' },
];

export function isFiltro(value: string | null | undefined): value is GaleriaFiltro {
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

/** Only what changed in the photo sheet: the trimmed note and the AI-edit choice. Empty when nothing did. */
export function photoPatch(photo: Pick<PhotoOutput, 'note' | 'ai_edit'>, note: string, aiEdit: AIEdit): PhotoPatch {
  const patch: PhotoPatch = {};
  if (note.trim() !== (photo.note ?? '').trim()) patch.note = note.trim();
  if (aiEdit !== photo.ai_edit) patch.ai_edit = aiEdit;
  return patch;
}

/** «Ojo: elegida para el post del jueves 12.» when a photo chosen or edited for a piece is removed. */
export function inUseWarning(photo: Pick<PhotoOutput, 'display_state' | 'used_in'>): string | null {
  const inUse = photo.display_state === 'elegida' || photo.display_state === 'editada';
  const text = photo.used_in?.text;
  if (!inUse || !text) return null;
  return `Ojo: ${text.charAt(0).toLowerCase() + text.slice(1)}.`;
}

/** The toast after an upload. */
export function uploadedMessage(count: number): string {
  return count === 1 ? 'Foto subida. El equipo la verá en su próxima ronda.' : `${count} fotos subidas. El equipo las verá en su próxima ronda.`;
}

/** The line under «Subir fotos» when some files were refused (null when none was). */
export function rejectedMessage(names: readonly string[]): string | null {
  return names.length ? `No se subió ${names.join(', ')}: solo JPEG, PNG, WebP o HEIC de hasta 10 MB.` : null;
}
