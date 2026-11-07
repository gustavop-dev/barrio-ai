// The return from the LinkedIn OAuth flow: /ajustes?linkedin=ok or ?linkedin=error&motivo=…
// (linkedin_views.oauth_callback, CONTRATO-API.md «LinkedIn oficial»).
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { LinkedInStatus } from '../../api/types';
import type { Tone } from '../../components/ui';

/** One message per `motivo` of the callback. */
export const LINKEDIN_REASONS: Record<string, string> = {
  sesion:
    'La sesión de la oficina no llegó de vuelta desde LinkedIn o había caducado. Entra de nuevo si hace falta y vuelve a pulsar «Conectar LinkedIn».',
  permiso: 'Tu usuario no tiene el permiso «approve_actions», necesario para conectar la cuenta de LinkedIn.',
  state:
    'La respuesta de LinkedIn no corresponde a esta solicitud: el enlace caduca a los 10 minutos y solo vale una vez. Vuelve a intentarlo desde aquí.',
  denegado: 'Cancelaste o denegaste la autorización en LinkedIn. No se ha conectado nada.',
  code: 'LinkedIn no devolvió un código de autorización válido. Vuelve a intentarlo.',
  scope:
    'LinkedIn no concedió el permiso para publicar (w_member_social). Acepta todos los permisos y comprueba que la app tenga el producto «Share on LinkedIn».',
  canje:
    'No se pudo canjear la autorización con LinkedIn ni leer tu perfil. Vuelve a intentarlo en unos minutos; si se repite, revisa LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET y LINKEDIN_REDIRECT_URI en el servidor.',
};

export interface LinkedInNotice {
  ok: boolean;
  title: string;
  text: string;
}

/** The message for the return from the OAuth flow, or null when the URL carries none. */
export function linkedinReturnMessage(result: string | null, reason: string | null): LinkedInNotice | null {
  if (result === 'ok') {
    return { ok: true, title: 'LinkedIn conectado', text: 'La publicación diaria ya puede usar la API oficial con tu cuenta.' };
  }
  if (result === 'error') {
    const text = (reason && LINKEDIN_REASONS[reason]) || `No se pudo completar la conexión${reason ? ` (motivo: ${reason})` : ''}. Vuelve a intentarlo.`;
    return { ok: false, title: 'No se pudo conectar LinkedIn', text };
  }
  return null;
}

/** Reads `?linkedin=…&motivo=…` once and removes them, so a reload does not repeat the message. */
export function useLinkedInReturn() {
  const [params, setParams] = useSearchParams();
  const [notice, setNotice] = useState(() => linkedinReturnMessage(params.get('linkedin'), params.get('motivo')));
  const present = params.has('linkedin') || params.has('motivo');
  useEffect(() => {
    if (!present) return;
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.delete('linkedin');
        next.delete('motivo');
        return next;
      },
      { replace: true },
    );
  }, [present, setParams]);
  return [notice, () => setNotice(null)] as const;
}

/** Conectado, Caduca pronto, Caducado o Sin conectar. */
export function linkedinBadge(status: LinkedInStatus): { label: string; tone: Tone } {
  if (status.expired) return { label: 'Caducado', tone: 'bad' };
  if (status.connected && status.expiring_soon) return { label: 'Caduca pronto', tone: 'warn' };
  if (status.connected) return { label: 'Conectado', tone: 'ok' };
  return { label: 'Sin conectar', tone: 'muted' };
}

export const days = (n: number) => `${n} ${n === 1 ? 'día' : 'días'}`;
