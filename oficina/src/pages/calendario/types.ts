import type { PieceDetail } from '../../api/types';

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

/** GET /api/v1/editorial/pieces/<id> with the captures' `team_comments`. */
export type PieceDetailFull = PieceDetail & { team_comments?: TeamComment[] };

export type Vista = 'mes' | 'semana' | 'lista';
