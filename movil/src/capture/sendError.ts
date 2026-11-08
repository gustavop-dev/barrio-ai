// What the capture sheet says when «Guardar y enviar al equipo» fails: the real reason (no network,
// the phone could not read a file, the server's 400 message, 409, 413, a server error), and the
// technical detail in small print so a screenshot is enough to diagnose it.
import { ApiError } from '@compartido/api/client';
import { isFilePartFailure, OFFLINE_REASON, UploadNetworkError } from '@/api/multipart';

export interface SendProblem {
  title: string;
  message: string;
  /** The error as the code saw it («HTTP 400», «UploadNetworkError: …»), or null. */
  technical: string | null;
  tone: 'error' | 'warn';
}

/** Always said under the problem: the draft stays in the sheet. */
export const DRAFT_KEPT = 'Tu audio, tus fotos y tu nota siguen aquí. Puedes reintentar.';

export function describeSendError(error: unknown): SendProblem {
  if (error instanceof ApiError) {
    const technical = `HTTP ${error.status}`;
    if (error.status === 413) {
      return {
        title: 'El envío es demasiado grande',
        message: 'El audio puede pesar hasta 25 MB y cada foto hasta 10 MB. Quita alguna foto o graba un audio más corto.',
        technical,
        tone: 'error',
      };
    }
    if (error.status === 409) {
      return { title: 'No se puede enviar así ahora', message: `${error.detail} Quita el contexto de arriba para enviarlo suelto.`, technical, tone: 'warn' };
    }
    if (error.status === 400) return { title: 'El servidor no aceptó el envío', message: error.detail, technical, tone: 'error' };
    if (error.status === 429) return { title: 'Demasiados envíos seguidos', message: error.detail, technical, tone: 'warn' };
    if (error.status >= 500) return { title: 'El servidor falló al recibirlo', message: error.detail, technical, tone: 'error' };
    return { title: 'No se pudo enviar', message: error.detail, technical, tone: 'error' };
  }
  if (isFilePartFailure(error)) {
    return {
      title: 'El teléfono no pudo leer un archivo',
      message: 'No se pudo abrir el audio o una de las fotos para subirla. Si vuelve a pasar, quita esa foto o graba el audio otra vez.',
      technical: (error as Error).message,
      tone: 'error',
    };
  }
  if (error instanceof TypeError) {
    // The phone knew it had no network: nothing technical to add (and no English, CAP-06).
    const offline = error instanceof UploadNetworkError && error.reason === OFFLINE_REASON;
    return {
      title: 'No hay conexión con el servidor',
      message: 'El envío no salió del teléfono. Comprueba tu red y vuelve a intentarlo.',
      technical: offline ? null : `${error.name}: ${error.message}`,
      tone: 'error',
    };
  }
  if (error instanceof Error) return { title: 'No se pudo enviar', message: error.message, technical: error.name, tone: 'error' };
  return { title: 'No se pudo enviar', message: 'Algo salió mal.', technical: null, tone: 'error' };
}
