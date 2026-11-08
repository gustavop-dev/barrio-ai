import { api, ApiError } from './client';

/** The Spanish message to show for any error thrown by the API client or the network. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof TypeError) return 'No hay conexión con el servidor. Comprueba tu red.';
  if (error instanceof Error) return error.message;
  return 'Algo salió mal.';
}

/** 409 is "conflict or safeguard": the action is valid, just not now. */
export function isConflict(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409;
}

// ================================================================ client error reports

/**
 * One file part of a failed upload, as reported: its field, type, URI scheme and size. Never its
 * contents, its URI or its name.
 */
export interface ReportedPart {
  field: string;
  type: string;
  scheme: string;
  size: number | null;
}

/**
 * POST /api/v1/app/errores (CONTRATO-API.md «Errores del cliente»): what failed, so the team can
 * diagnose without the phone. Never the audio, the photos, the note text or a token.
 */
export interface ClientErrorReport {
  /** What failed: `captura_envio`, `galeria_subida`… */
  kind: string;
  /** The error class (`UploadNetworkError`, `ApiError`, `TypeError`…). */
  name: string;
  message: string;
  /** HTTP status, or null when no answer came back. */
  status: number | null;
  /** The server's `detail`, if it answered. */
  detail: string;
  parts: ReportedPart[];
  platform: string;
  os_version: string;
  app_version: string;
}

export const reportClientError = (report: ClientErrorReport) => api.post<{ id: string }>('/api/v1/app/errores', report);
