import { ApiError } from './client';

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
