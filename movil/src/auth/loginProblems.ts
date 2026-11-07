// What went wrong with a login attempt, in the PWA's words.
import { ApiError } from '@compartido/api/client';

/** After a 429 the button stays locked this long; the server keeps its own limit anyway. */
export const LOCK_MS = 60_000;

export type LoginProblem = 'credentials' | 'offline' | 'too-many' | 'other';

export function problemOf(error: unknown): LoginProblem | null {
  if (!error) return null;
  if (error instanceof ApiError) {
    if (error.status === 429) return 'too-many';
    if (error.status === 400 || error.status === 401) return 'credentials';
    return 'other';
  }
  if (error instanceof TypeError) return 'offline';
  return 'other';
}

export const PROBLEM_TEXT: Record<Exclude<LoginProblem, 'other'>, string> = {
  credentials: 'Usuario o contraseña incorrectos.',
  'too-many': 'Demasiados intentos. Espera unos minutos.',
  offline: 'No pudimos conectar con la oficina. Revisa tu conexión e intenta de nuevo.',
};
