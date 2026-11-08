// Photos for a capture: the camera or the gallery (expo-image-picker), checked against the contract
// (JPEG, PNG, WebP or HEIC, 10 MB each, 10 per capture).
import { CAPTURE_LIMITS, isAcceptedPhoto, nativeUri, PHOTO_TYPES, typeFromName } from '@compartido/api/capturas';
import * as ImagePicker from 'expo-image-picker';
import type { PickedPhoto } from './types';

let seq = 0;

const EXTENSION: Record<string, string> = { 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'image/heic': 'heic', 'image/heif': 'heif' };

/** The name with the extension of its real type (`IMG_1.heic` re-encoded as JPEG → `IMG_1.jpg`). */
function withExtension(name: string, type: string): string {
  const ext = EXTENSION[type];
  if (!ext || typeFromName(name) === type) return name;
  const base = name.replace(/\.[a-z0-9]+$/i, '') || 'foto';
  return `${base}.${ext}`;
}

/**
 * URI, name and type of a picked asset, as the upload sends them.
 *
 * - The URI always has a scheme (`file://`, or `content://` as given).
 * - The type is the one of the bytes in the file. With `quality` below 1, expo-image-picker on Android
 *   re-encodes the picture into its cache (`…/ImagePicker/<uuid>.jpeg`, `.png` or `.webp`) but keeps the
 *   source's `mimeType` and `fileName`: a HEIC comes back as JPEG bytes labelled `image/heic` and
 *   `IMG_1.heic`. So for an image the extension of the local file wins, then `mimeType`, then the
 *   name's extension (HEIC from some phones comes without a type), then JPEG. Anything that is not an
 *   image keeps its type, so the checks below refuse it.
 */
export function toPickedPhoto(asset: Pick<ImagePicker.ImagePickerAsset, 'uri' | 'fileName' | 'mimeType' | 'fileSize'>): PickedPhoto {
  seq += 1;
  const uri = nativeUri(asset.uri);
  const fromUri = uri.split(/[?#]/)[0]?.split('/').pop() ?? '';
  const size = typeof asset.fileSize === 'number' ? asset.fileSize : null;
  const declared = (asset.mimeType ?? '').trim().toLowerCase();
  if (declared && !declared.startsWith('image/')) {
    return { id: `f${seq}`, uri, name: asset.fileName || fromUri || `archivo-${seq}`, type: declared, size };
  }
  const fromFile = uri.startsWith('file:') ? typeFromName(uri) : null;
  const written = fromFile && PHOTO_TYPES.includes(fromFile) ? fromFile : null;
  const type = written || declared || typeFromName(asset.fileName ?? '') || typeFromName(fromUri) || 'image/jpeg';
  const name = withExtension(asset.fileName || (typeFromName(fromUri) ? fromUri : '') || `foto-${seq}.jpg`, type);
  return { id: `f${seq}`, uri, name, type, size };
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
