// Labels of the capture history («Lo que enviaste»), shared by the PWA and the native app.
import { isProcessing, type CaptureOutput } from '../api/capturas';
import { mmss } from './audio';
import { padHour } from './format';
import { CALENDAR_TZ } from './dates';
import type { Tone } from './tone';

const LOCALE = 'es-CO';

function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/** «3 nov», «10 nov 2026»: the short day of the designs (es-CO writes «3 de nov.»). */
export function shortDay(date: Date, withYear = false): string {
  const options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' };
  if (withYear) options.year = 'numeric';
  return date.toLocaleDateString(LOCALE, options).replace(/\./g, '').replace(/ de /g, ' ');
}

/** «Hoy, 10:40», «Ayer, 19:05», «3 nov» (and the year when it is not this one). */
export function whenLabel(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  const time = padHour(date.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', hour12: false }));
  if (sameDay(date, now)) return `Hoy, ${time}`;
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameDay(date, yesterday)) return `Ayer, ${time}`;
  return shortDay(date, date.getFullYear() !== now.getFullYear());
}

/** «1 foto», «3 fotos». */
export function fotosLabel(count: number): string {
  return `${count} ${count === 1 ? 'foto' : 'fotos'}`;
}

export const STATE_TONE: Record<string, Tone> = {
  recibida: 'info',
  transcribiendo: 'info',
  procesando: 'info',
  dato_guardado: 'ok',
  anotado: 'ok',
  idea: 'ok',
  usado: 'ok',
  sin_usar: 'muted',
  error: 'bad',
  deshecha: 'muted',
};

export const CONTEXT_PREFIX: Record<string, string> = {
  pregunta: 'Responde a',
  persona: 'Sobre',
  pieza: 'Sobre la pieza',
};

/** «AUDIO 0:42», «2 FOTOS», «NOTA». */
export function contentsOf(capture: Pick<CaptureOutput, 'has_audio' | 'audio_duration_s' | 'photos' | 'note'>): string[] {
  const parts: string[] = [];
  if (capture.has_audio) parts.push(capture.audio_duration_s ? `Audio ${mmss(capture.audio_duration_s)}` : 'Audio');
  if (capture.photos?.length) parts.push(fotosLabel(capture.photos.length));
  if (capture.note?.trim()) parts.push('Nota');
  return parts;
}

/** «Idea para un post», «Dato sobre mí · lo decidió el equipo», «El equipo decide». */
export function purposeOf(capture: Pick<CaptureOutput, 'purpose_label' | 'team_decided' | 'state'>): string {
  if (capture.purpose_label) return capture.purpose_label;
  if (capture.team_decided?.label) return `${capture.team_decided.label} · lo decidió el equipo`;
  return isProcessing(capture.state) ? 'El equipo lo transcribe y decide' : 'Sin elegir';
}

export function canUndo(capture: CaptureOutput, now: number): boolean {
  if (!capture.can_undo || !capture.undo_until) return false;
  const until = Date.parse(capture.undo_until);
  return Number.isFinite(until) && until > now;
}

/** This is the team's interpretation and a forecast, never a new urgency input. */
export function publishAsapLines(capture: Pick<CaptureOutput, 'publish_asap' | 'publish_asap_evidence' | 'publish_asap_expected_slot' | 'publish_asap_reason'>): string[] {
  if (!capture.publish_asap) return [];
  const slot = capture.publish_asap_expected_slot ? new Date(capture.publish_asap_expected_slot) : null;
  const when = slot && Number.isFinite(slot.getTime()) ? padHour(new Intl.DateTimeFormat('es-CO', {
    timeZone: CALENDAR_TZ, weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(slot)) : null;
  return [
    `Saldrá lo antes posible · ${when ? `fecha prevista: ${when}` : 'fecha por confirmar'}`,
    ...(capture.publish_asap_reason?.trim() ? [capture.publish_asap_reason] : []),
    ...(capture.publish_asap_evidence?.trim() ? [`«${capture.publish_asap_evidence}»`] : []),
  ];
}
