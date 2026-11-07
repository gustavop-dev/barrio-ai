const LOCALE = 'es-CO';

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(LOCALE, { dateStyle: 'medium', timeStyle: 'short' });
}

export function timeAgo(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '—';
  const seconds = Math.round((now - then) / 1000);
  if (seconds < 0) return formatDateTime(iso);
  if (seconds < 45) return 'hace un momento';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  const days = Math.round(hours / 24);
  if (days < 7) return `hace ${days} ${days === 1 ? 'día' : 'días'}`;
  return formatDateTime(iso);
}

export function money(value: string | number | null | undefined): string {
  const number = Number(value ?? 0);
  return `USD ${(Number.isFinite(number) ? number : 0).toLocaleString(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function ratio(used: number, cap: number): number {
  if (!Number.isFinite(used) || !Number.isFinite(cap) || cap <= 0) return 0;
  return Math.min(1, Math.max(0, used / cap));
}

export function prettyValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return '';
  return JSON.stringify(value, null, 2);
}

export const CAPABILITY_LABEL: Record<string, string> = {
  'INT-03': 'Comentario',
  'INT-02': 'Reacción',
  'CONT-09': 'Publicación propia',
};

export const ACTION_STATE_LABEL: Record<string, string> = {
  proposed: 'Propuesta',
  approved: 'Aprobada',
  rejected: 'Vetada',
  superseded: 'Sustituida',
  discarded: 'Descartada',
  executing: 'Ejecutándose',
  sent: 'Enviada',
  confirmed: 'Confirmada',
  uncertain: 'Incierta',
  failed: 'Fallida',
  expired: 'Caducada',
};

/** A calendar date (AAAA-MM-DD) read as such, never shifted by the device's time zone. */
export function formatDay(date: string | null | undefined, style: 'long' | 'short' = 'long'): string {
  if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) return date || '—';
  const value = new Date(`${date}T00:00:00Z`);
  if (Number.isNaN(value.getTime())) return date;
  return value.toLocaleDateString(LOCALE, {
    timeZone: 'UTC',
    weekday: style === 'long' ? 'long' : 'short',
    day: 'numeric',
    month: style === 'long' ? 'long' : 'short',
  });
}

export function capitalize(text: string): string {
  return text.charAt(0).toLocaleUpperCase(LOCALE) + text.slice(1);
}

/** Adds whole days to an AAAA-MM-DD date. */
export function shiftDay(date: string, days: number): string {
  const value = new Date(`${date}T00:00:00Z`);
  if (Number.isNaN(value.getTime())) return date;
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}

/** Hour of an instant in the machine's time zone (falls back to the device's). */
export function formatTime(iso: string | null | undefined, timeZone?: string): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  const options: Intl.DateTimeFormatOptions = { hour: '2-digit', minute: '2-digit', hour12: false };
  try {
    return date.toLocaleTimeString(LOCALE, timeZone ? { ...options, timeZone } : options);
  } catch {
    return date.toLocaleTimeString(LOCALE, options);
  }
}

export function formatNumber(value: number): string {
  return value.toLocaleString(LOCALE);
}

export function capabilityLabel(code: string): string {
  return CAPABILITY_LABEL[code] ?? code;
}

export function actionStateLabel(state: string): string {
  return ACTION_STATE_LABEL[state] ?? state;
}
