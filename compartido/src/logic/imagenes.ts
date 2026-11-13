import type { AIEdit, ImageKind, ImageReview, PieceImage } from '../api/imagenes';

export const AI_EDIT_OPTIONS: readonly { value: AIEdit; label: string }[] = [
  { value: 'no', label: 'No editar' },
  { value: 'auto', label: 'Que decida el equipo' },
  { value: 'si', label: 'Editar' },
];

export const IMAGE_KIND_LABEL: Record<ImageKind, string> = {
  foto: 'Foto', infografia: 'Infografía', carrusel: 'Carrusel', tarjeta: 'Tarjeta de marca',
};
export const TEMPLATE_LABEL: Record<NonNullable<PieceImage['template']>, string> = {
  portada: 'Portada', pasos: 'Pasos', barras: 'Barras', numero: 'Número', cierre: 'Cierre', preguntas: 'Preguntas',
};

export function orderedImages(images: readonly PieceImage[] = []): PieceImage[] {
  return [...images].sort((a, b) => a.position - b.position);
}

export function imageAspect(image: Pick<PieceImage, 'width' | 'height'>): number {
  return image.width > 0 && image.height > 0 ? image.width / image.height : 1;
}

/** Describe only the verdict actually received; a fixed card is not a model's visual check. */
export function reviewLines(review: ImageReview = {}): string[] {
  const title = review.mode === 'fixed_brand_card' ? 'Plantilla fija de marca; sin revisión visual dinámica.'
    : review.ok === true ? 'Comprobación aprobada' : review.ok === false ? 'Comprobación no aprobada'
      : review.started ? 'Comprobación en curso' : '';
  return [
    ...(title ? [title] : []),
    ...(review.failures ?? []), ...(review.reasons ?? []),
    ...(review.checks ?? []).map((check) => `${check.point}. ${check.ok ? 'Correcto' : 'Revisar'}: ${check.reason}`),
  ];
}
