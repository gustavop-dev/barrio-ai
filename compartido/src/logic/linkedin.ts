// Ajustes › LinkedIn oficial: the status badge, the dates and the return from the OAuth flow
// (/ajustes?linkedin=ok or ?linkedin=error&motivo=…, linkedin_views.oauth_callback, CONTRATO-API.md
// «LinkedIn oficial»). Shared by the PWA and the native app.
import type { LinkedInStatus, User } from '../api/types';
import { shortDay } from './capturas';
import type { Tone } from './tone';

const LOCALE = 'es-CO';

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
export function linkedinReturnMessage(result: string | null | undefined, reason: string | null | undefined): LinkedInNotice | null {
  if (result === 'ok') {
    return { ok: true, title: 'LinkedIn conectado', text: 'La publicación diaria ya puede usar la API oficial con tu cuenta.' };
  }
  if (result === 'error') {
    const text = (reason && LINKEDIN_REASONS[reason]) || `No se pudo completar la conexión${reason ? ` (motivo: ${reason})` : ''}. Vuelve a intentarlo.`;
    return { ok: false, title: 'No se pudo conectar LinkedIn', text };
  }
  return null;
}

/** Conectado, Caduca pronto, Caducado o Sin conectar. */
export function linkedinBadge(status: LinkedInStatus): { label: string; tone: Tone } {
  if (status.expired) return { label: 'Caducado', tone: 'bad' };
  if (status.connected && status.expiring_soon) return { label: 'Caduca pronto', tone: 'warn' };
  if (status.connected) return { label: 'Conectado', tone: 'ok' };
  return { label: 'Sin conectar', tone: 'muted' };
}

export const days = (n: number) => `${n} ${n === 1 ? 'día' : 'días'}`;

/** Superusers and whoever has `approve_actions` can start the OAuth flow. */
export function canConnectLinkedIn(user: User | null | undefined): boolean {
  return Boolean(user && (user.is_superuser || user.permissions.includes('approve_actions')));
}

/** «martes, 10 de noviembre» for the expiry warning. */
export function linkedinLongDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(LOCALE, { weekday: 'long', day: 'numeric', month: 'long' });
}

/** «10 nov 2026» for the Caduca row. */
export function linkedinShortDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : shortDay(date, true);
}

/** The scopes the OAuth asks for, as the hint under the button says them. */
export function linkedinScopesText(status: Pick<LinkedInStatus, 'scopes_required'>): string {
  return (status.scopes_required.length ? status.scopes_required : ['w_member_social']).join(', ');
}

/** A new credential arrived (a first connection or a reconnection): `connected_at` or `expires_at` moved. */
export function linkedinReconnected(before: LinkedInStatus | undefined, after: LinkedInStatus | undefined): boolean {
  if (!before || !after || !after.connected) return false;
  return (after.connected_at ?? null) !== (before.connected_at ?? null) || after.expires_at !== before.expires_at || !before.connected;
}
