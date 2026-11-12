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
  'RED-01': 'Seguir',
  'RED-02': 'Invitación sin nota',
  'RED-04': 'Aceptar invitación',
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

/**
 * «08:30», never «8:30»: Hermes (the app's JavaScript engine on Android) ignores `hour: '2-digit'`, so a lone digit
 * before «:mm» gets its zero here (backlog #12). Browsers already pad it; the result is the same everywhere.
 */
export function padHour(text: string): string {
  return text.replace(/(^|[^\d])(\d):(\d{2})/, '$10$2:$3');
}

/** Hour of an instant in the machine's time zone (falls back to the device's). */
export function formatTime(iso: string | null | undefined, timeZone?: string): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  const options: Intl.DateTimeFormatOptions = { hour: '2-digit', minute: '2-digit', hour12: false };
  try {
    return padHour(date.toLocaleTimeString(LOCALE, timeZone ? { ...options, timeZone } : options));
  } catch {
    return padHour(date.toLocaleTimeString(LOCALE, options));
  }
}

/** «1.284», «3,5». At most one decimal unless `digits` says otherwise. */
export function formatNumber(value: number, digits = 1): string {
  return value.toLocaleString(LOCALE, { maximumFractionDigits: digits });
}

/** A value already in percent units (the backend's `engagement_pct`, `delta_pct`): «3,5 %». */
export function formatPct(value: number, digits = 1): string {
  return `${value.toLocaleString(LOCALE, { maximumFractionDigits: digits })} %`;
}

/** «1,20 USD». */
export function formatUsd(value: number): string {
  return `${value.toLocaleString(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD`;
}

export function capabilityLabel(code: string): string {
  return CAPABILITY_LABEL[code] ?? code;
}

export function actionStateLabel(state: string): string {
  return ACTION_STATE_LABEL[state] ?? state;
}

/** A 0..1 fraction as a whole percentage ("80 %", with a non-breaking space). */
export function percent(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  return `${Math.round(Math.min(1, Math.max(0, value)) * 100)}\u00a0%`;
}

/** Shortens a text to `max` characters on a word boundary, with an ellipsis. */
export function excerpt(text: string | null | undefined, max = 160): string {
  const clean = (text ?? '').replace(/\s+/g, ' ').trim();
  if (clean.length <= max) return clean;
  const cut = clean.slice(0, max);
  const space = cut.lastIndexOf(' ');
  return `${(space > max * 0.6 ? cut.slice(0, space) : cut).replace(/[\s.,;:]+$/, '')}…`;
}

// ---------------------------------------------------------------- network (Red)

/** Stage of a contact in the funnel: short label for badges and chips, and what it means. */
export const CONTACT_STAGE: Record<string, { label: string; hint: string }> = {
  candidate: { label: 'Por clasificar', hint: 'Descubierto; pendiente de clasificar.' },
  fit: { label: 'Encaja', hint: 'Encaja; se propondrá seguirlo.' },
  discarded: { label: 'Descartado', hint: 'No encaja o lo descartaste; no se vuelve a proponer.' },
  followed: { label: 'Seguido', hint: 'Seguido; se espera al menos 48 h antes de invitar.' },
  invited: { label: 'Invitado', hint: 'Invitación sin nota enviada.' },
  connected: { label: 'Conectado', hint: 'Conexión de primer grado.' },
  closed: { label: 'Cerrado', hint: 'Invitación ignorada o retirada; no se reinvita sin ti.' },
  incoming: { label: 'Te invitó', hint: 'Te invitó; se aceptará si encaja.' },
};

export function contactStageLabel(stage: string): string {
  return CONTACT_STAGE[stage]?.label ?? stage;
}

export const CONTACT_ROLE_LABEL: Record<string, string> = {
  par: 'Par',
  recomendador: 'Recomendador',
  lider: 'Líder',
  comprador: 'Comprador',
  divulgador: 'Divulgador',
  aliado: 'Aliado',
};

/** Network classification; the editorial calendar has its own modality labels (lib/editorial.ts). */
export const CONTACT_MODALITY_LABEL: Record<string, string> = {
  personal_startups: 'Startups (personal)',
  projectapp: 'ProjectApp',
  alianzas: 'Alianzas',
  comunidad_autoridad: 'Comunidad',
};

export const CONTACT_AFFINITY_LABEL: Record<string, string> = {
  hispanohablante_declarada: 'Hispanohablante (declarado)',
  otra: 'Otra',
  desconocida: 'Sin dato',
};

/** Missing values read as "—"; unknown codes are shown as they arrive. */
export function labelOf(table: Record<string, string>, value: string | null | undefined): string {
  if (!value) return '—';
  return table[value] ?? value;
}

/** How the contact was found: «Comentó en un post de <referent>», «Búsqueda: <query>»… */
export function contactSourceLabel(source: string, evidence: { referent?: string | null; query?: string | null } | null | undefined): string {
  switch (source) {
    case 'commenter':
      return evidence?.referent ? `Comentó en un post de ${evidence.referent}` : 'Comentó en un post de un referente';
    case 'search':
      return evidence?.query ? `Búsqueda: ${evidence.query}` : 'Búsqueda';
    case 'incoming':
      return 'Te invitó';
    case 'manual':
      return 'Añadido a mano';
    default:
      return source || 'Origen desconocido';
  }
}

export const NETWORK_DISTANCE_LABEL: Record<string, string> = {
  FIRST_DEGREE: '1.er grado',
  SECOND_DEGREE: '2.º grado',
  THIRD_DEGREE: '3.er grado',
  OUT_OF_NETWORK: 'Fuera de tu red',
};

/** Empty when LinkedIn did not report the distance. */
export function networkDistanceLabel(distance: string | null | undefined): string {
  if (!distance) return '';
  return NETWORK_DISTANCE_LABEL[distance] ?? distance;
}

export const CONTACT_EVENT_LABEL: Record<string, string> = {
  discovered: 'Descubierto',
  classified: 'Clasificado',
  followed: 'Seguido',
  invited: 'Invitado',
  connected: 'Conectado',
  closed: 'Cerrado',
  discarded: 'Descartado',
  rejected: 'Acción vetada',
  incoming: 'Te invitó',
  note: 'Nota',
};

/** Autonomy mode of a capability, read as «Modo auto», «Modo aprobación», «Modo apagado». */
export const AUTONOMY_MODE_LABEL: Record<string, string> = {
  auto: 'auto',
  approval: 'aprobación',
  off: 'apagado',
};

/** Daily LinkedIn reads of the network block, each with its own cap. */
export const NETWORK_READ_LABEL: Record<string, string> = {
  comments: 'Lecturas de comentarios',
  search: 'Búsquedas',
  profile: 'Perfiles consultados',
  sync: 'Sincronizaciones',
};
