// Photos for a capture: the camera or the gallery (expo-image-picker), checked against the contract
// (JPEG, PNG, WebP or HEIC, 10 MB each, 10 per capture).
import { CAPTURE_LIMITS, isAcceptedPhoto } from '@compartido/api/capturas';
import * as ImagePicker from 'expo-image-picker';
import type { PickedPhoto } from './types';

let seq = 0;

/** Type and name of a picked asset; HEIC from some phones comes without a type. */
export function toPickedPhoto(asset: Pick<ImagePicker.ImagePickerAsset, 'uri' | 'fileName' | 'mimeType' | 'fileSize'>): PickedPhoto {
  seq += 1;
  const fromUri = asset.uri.split('/').pop()?.split('?')[0] ?? '';
  const name = asset.fileName || fromUri || `foto-${seq}.jpg`;
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  const guessed = ext === 'png' ? 'image/png' : ext === 'webp' ? 'image/webp' : ext === 'heic' || ext === 'heif' ? 'image/heic' : 'image/jpeg';
  return { id: `f${seq}`, uri: asset.uri, name, type: asset.mimeType || guessed, size: typeof asset.fileSize === 'number' ? asset.fileSize : null };
}

export interface PhotoCheck {
  kept: PickedPhoto[];
  problem: string | null;
}

/** Keeps what fits: accepted types, 10 MB each and the room left of the 10 per capture. */
export function checkPhotos(picked: PickedPhoto[], already: number): PhotoCheck {
  const accepted: PickedPhoto[] = [];
  const rejected: string[] = [];
  for (const photo of picked) {
    if (!isAcceptedPhoto(photo) || (photo.size !== null && photo.size > CAPTURE_LIMITS.photoBytes)) rejected.push(photo.name || 'una foto');
    else accepted.push(photo);
  }
  const room = Math.max(0, CAPTURE_LIMITS.photosPerCapture - already);
  const kept = accepted.slice(0, room);
  const problems: string[] = [];
  if (rejected.length) problems.push(`No se añadió ${rejected.join(', ')}: solo JPEG, PNG, WebP o HEIC de hasta 10 MB.`);
  if (accepted.length > kept.length) problems.push(`Puedes adjuntar hasta ${CAPTURE_LIMITS.photosPerCapture} fotos por envío.`);
  return { kept, problem: problems.length ? problems.join(' ') : null };
}

export type PickOutcome = { photos: PickedPhoto[] } | { denied: 'camera' } | { canceled: true };

export async function takePhoto(): Promise<PickOutcome> {
  const permission = await ImagePicker.requestCameraPermissionsAsync();
  if (!permission.granted) return { denied: 'camera' };
  const result = await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.85 });
  if (result.canceled) return { canceled: true };
  return { photos: result.assets.map(toPickedPhoto) };
}

export async function pickFromGallery(room: number): Promise<PickOutcome> {
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['images'],
    allowsMultipleSelection: true,
    selectionLimit: Math.max(1, room),
    quality: 0.85,
  });
  if (result.canceled) return { canceled: true };
  return { photos: result.assets.map(toPickedPhoto) };
}
