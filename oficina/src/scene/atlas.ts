import { ATLAS_URL } from '../components/ui/atlas';
export * from '../../../compartido/src/scene/atlas';

export type AtlasImage = CanvasImageSource & { width: number; height: number };

let loading: Promise<AtlasImage> | null = null;

/** Loads the atlas once per page. A failure can be retried. */
export function loadAtlas(): Promise<AtlasImage> {
  if (!loading) {
    loading = new Promise<AtlasImage>((resolve, reject) => {
      const image = new Image();
      image.decoding = 'async';
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error('No se pudo cargar el dibujo de la oficina'));
      image.src = ATLAS_URL;
    }).catch((error: unknown) => {
      loading = null;
      throw error;
    });
  }
  return loading;
}
