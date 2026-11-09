// Calendario and piece detail types beyond the API's base ones (shared by the PWA and the native app).
import type { PieceMedia } from './imagenes';
import type { PieceDetail } from './types';

/** A capture Gustavo attached to the piece («Comentario para el equipo»), from CONTRATO-API «Cambios en rutas existentes». */
export interface TeamComment {
  id: string;
  text: string;
  note: string;
  transcript: string;
  has_audio: boolean;
  audio_url: string | null;
  created_at: string;
  by: string | null;
}

/** GET /api/v1/editorial/pieces/<id> with private media and the captures' `team_comments`. */
export type PieceDetailFull = PieceDetail & PieceMedia & { team_comments?: TeamComment[] };
