// «Subir fotos»: several photos from the phone's library (expo-image-picker), checked against the
// contract (JPEG, PNG, WebP or HEIC of up to 10 MB) and sent ten per request, with the progress of
// each request for the screen.
import { CAPTURE_LIMITS, isAcceptedPhoto, useUploadFotos, type PhotoCategory, type NativeFile, type UploadProgress } from '@compartido/api/capturas';
import { rejectedMessage, uploadedMessage } from '@compartido/logic/galeria';
import * as ImagePicker from 'expo-image-picker';
import { useCallback, useState } from 'react';
import { localPart, reportError } from '@/api/errorReport';
import { toPickedPhoto } from '@/capture/photos';
import type { PickedPhoto } from '@/capture/types';
import { useToast } from '@/components/ui';
import { haptic } from '@/theme/motion';

/** Splits what was picked into what can go up and the names of what cannot. */
export function splitPicked(picked: readonly PickedPhoto[]): { ok: PickedPhoto[]; rejected: string[] } {
  const ok: PickedPhoto[] = [];
  const rejected: string[] = [];
  for (const photo of picked) {
    if (isAcceptedPhoto(photo) && (photo.size === null || photo.size <= CAPTURE_LIMITS.photoBytes)) ok.push(photo);
    else rejected.push(photo.name || 'una foto');
  }
  return { ok, rejected };
}

/** The library, several at once and no limit: the upload sends them ten per request. */
export async function pickPhotos(): Promise<PickedPhoto[] | null> {
  const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsMultipleSelection: true, selectionLimit: 0, quality: 0.85 });
  if (result.canceled || !result.assets?.length) return null;
  return result.assets.map(toPickedPhoto);
}

export interface GalleryUpload {
  /** The photos of the upload under way (or of the last one, until it is dismissed). */
  photos: PickedPhoto[];
  progress: UploadProgress | null;
  pending: boolean;
  error: unknown;
  /** «No se subió …: solo JPEG, PNG, WebP o HEIC de hasta 10 MB.» */
  rejected: string | null;
  pick: () => Promise<void>;
  /** Sends again what did not get in (the requests that already went through are not repeated). */
  retry: () => void;
  dismiss: () => void;
}

export function useGalleryUpload(category: PhotoCategory = 'posts'): GalleryUpload {
  const toast = useToast();
  const [batchCategory, setBatchCategory] = useState<PhotoCategory>(category);
  const [photos, setPhotos] = useState<PickedPhoto[]>([]);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [rejected, setRejected] = useState<string | null>(null);
  const upload = useUploadFotos({ onProgress: setProgress, category });

  const send = useCallback(
    (ok: PickedPhoto[], selectedCategory: PhotoCategory) => {
      setBatchCategory(selectedCategory);
      setPhotos(ok);
      setProgress({ done: 0, sending: 0, total: ok.length });
      const files: NativeFile[] = ok.map(({ uri, name, type }) => ({ uri, name, type }));
      upload.mutate({ files, category: selectedCategory }, {
        onSuccess: (created) => {
          haptic('uploadDone');
          toast.show(selectedCategory === 'perfil' ? 'Fotos subidas a Perfil.' : uploadedMessage(created.length || ok.length));
          setPhotos([]);
          setProgress(null);
        },
        onError: (error) => {
          haptic('actionError');
          reportError('galeria_subida', error, ok.map((photo) => localPart('fotos', photo)));
        },
      });
    },
    [upload, toast],
  );

  const pick = useCallback(async () => {
    if (upload.isPending) return;
    const picked = await pickPhotos();
    if (!picked) return;
    const { ok, rejected: bad } = splitPicked(picked);
    setRejected(rejectedMessage(bad));
    if (ok.length) send(ok, category);
  }, [upload.isPending, send, category]);

  const retry = useCallback(() => {
    const left = photos.slice(progress?.done ?? 0);
    if (left.length) send(left, batchCategory);
  }, [photos, progress, send, batchCategory]);

  const dismiss = useCallback(() => {
    upload.reset();
    setPhotos([]);
    setProgress(null);
  }, [upload]);

  return { photos, progress, pending: upload.isPending, error: upload.error, rejected, pick, retry, dismiss };
}
