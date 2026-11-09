import type { PieceImage } from '../api/imagenes';

export function pieceImage(overrides: Partial<PieceImage> = {}): PieceImage {
  return {
    id: 'img-1', kind: 'foto', position: 1, url: '/api/v1/editorial/pieces/p8/images/img-1',
    alt: 'People sharing a product demonstration.', width: 1080, height: 1080, mime: 'image/png', sha256: 'sha-1',
    source_photos: [{ id: 'f1', url: '/api/v1/galeria/f1/imagen' }], edited: false, ai_edit: 'no',
    reason: 'Instrucción de Gustavo: úsala tal cual', template: null, review: {}, ...overrides,
  };
}

export const CAROUSEL_IMAGES: PieceImage[] = (['portada', 'pasos', 'cierre'] as const).map((template, index) => pieceImage({
  id: `slide-${index + 1}`, kind: 'carrusel', position: index + 1, template,
  url: `/api/v1/editorial/pieces/p8/images/slide-${index + 1}`, sha256: `slide-sha-${index + 1}`,
  alt: ['Cover: compare the options.', 'Name the decision and record the reason.', 'Which decision needs a reason?'][index]!,
  source_photos: [], height: 1350, ai_edit: 'auto', reason: '',
  review: { ok: true, checks: [{ point: 1, ok: true, reason: 'Texto legible' }] },
}));
