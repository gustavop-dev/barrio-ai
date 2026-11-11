/** CONTRATO-API.md · Fase 2: imágenes y publicación prioritaria. */
export type AIEdit = 'no' | 'auto' | 'si';
export type ImageKind = 'foto' | 'infografia' | 'carrusel' | 'tarjeta';

export interface ImageReview {
  ok?: boolean;
  started?: boolean;
  stage?: 'datos';
  failures?: string[];
  mode?: 'fixed_brand_card';
  rule_version?: string;
  sha256?: string[];
  reasons?: string[];
  checks?: { point: number; ok: boolean; reason: string }[];
  attempts?: ImageReview[];
  previous?: ImageReview;
}

export interface PieceImage {
  id: string;
  kind: ImageKind;
  position: number;
  url: string;
  alt: string;
  width: number;
  height: number;
  mime: string;
  sha256: string;
  source_photos: { id: string; url: string }[];
  edited: boolean;
  ai_edit: AIEdit;
  reason: string;
  template: 'portada' | 'pasos' | 'barras' | 'numero' | 'cierre' | null;
  review: ImageReview;
  /** IMG-11 criterion 3: the last AI edit the visual check rejected, kept so Gustavo can judge it (never published). */
  rejected_edit?: RejectedEdit | null;
}

export interface RejectedEdit {
  url: string;
  reasons: string[];
  at?: string | null;
  width?: number | null;
  height?: number | null;
}

/** Optional for pieces fetched before phase 1 and for a piece still being prepared. */
export interface PieceMedia {
  image_kind?: ImageKind | null;
  image_reason?: string;
  images?: PieceImage[];
  image_review?: ImageReview;
  image_document_url?: string | null;
}
