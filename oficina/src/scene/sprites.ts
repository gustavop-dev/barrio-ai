// Loads the LimeZu sprites listed in public/assets/manifest.json, once per page.

export type SpriteImage = CanvasImageSource & { width: number; height: number };
export type SpriteMap = Record<string, SpriteImage>;

const BASE = `${import.meta.env.BASE_URL}assets/`;

let loading: Promise<SpriteMap> | null = null;

function loadImage(name: string): Promise<[string, SpriteImage]> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.decoding = 'async';
    image.onload = () => resolve([name, image]);
    image.onerror = () => reject(new Error(`Recurso no disponible: ${name}`));
    image.src = `${BASE}${name}.png`;
  });
}

export function loadSprites(): Promise<SpriteMap> {
  if (!loading) {
    loading = fetch(`${BASE}manifest.json`, { credentials: 'same-origin' })
      .then((response) => {
        if (!response.ok) throw new Error('No se pudo cargar el catálogo de la oficina');
        return response.json() as Promise<Record<string, unknown>>;
      })
      .then((manifest) => Promise.all(Object.keys(manifest).map(loadImage)))
      .then((entries) => Object.fromEntries(entries))
      .catch((error: unknown) => {
        loading = null;
        throw error;
      });
  }
  return loading;
}

export function portraitUrl(sprite: number): string {
  return `${BASE}portrait${sprite}.png`;
}
