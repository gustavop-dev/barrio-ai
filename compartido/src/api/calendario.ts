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

/** EDI-23: what Gustavo can do about a block. Null when the piece is not blocked, or when a budget or cycle stop
 * left it out (the autopilot redoes it). */
export interface PieceRescue {
  /** Who blocked it: the text verifier (or the rules), the image step, or the leader. */
  kind: 'verificador' | 'imagen' | 'lider';
  /** «Desestimar el bloqueo»: it goes out as it is with his approval, without the leader. */
  override: boolean;
  /** «Pedir un cambio»: his comment reworks it. */
  change: boolean;
  /** Why neither applies (its hour passed, the day has another piece); empty when they do. */
  why_not: string;
}

/** His dismissal of a block, kept on the piece's verification and bound to the exact text. */
export interface PieceOverride {
  kind: PieceRescue['kind'];
  at: string;
  reasons: string[];
  note: string;
}

/** GET /api/v1/editorial/pieces/<id> with private media, the captures' `team_comments` and what a block allows. */
export type PieceDetailFull = PieceDetail & PieceMedia & { team_comments?: TeamComment[]; rescue?: PieceRescue | null; override?: PieceOverride | null };
