// Calendar dates. Days are AAAA-MM-DD strings computed in the editorial calendar's time zone
// (America/Bogota), never in the device's (DISENO-VISTAS «3. Calendario · Zona horaria»).
import { shiftDay } from './format';

export const CALENDAR_TZ = 'America/Bogota';

const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
const DIAS_CORTOS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];
/** Monday-first initials of the design (X is miércoles). */
const INICIALES = ['D', 'L', 'M', 'X', 'J', 'V', 'S'];
const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
const MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

export const WEEKDAY_INITIALS = ['L', 'M', 'X', 'J', 'V', 'S', 'D'] as const;

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

function utc(day: string): Date {
  return new Date(`${day}T00:00:00Z`);
}

export function isIsoDay(value: string | null | undefined): value is string {
  return Boolean(value && ISO_DAY.test(value) && !Number.isNaN(utc(value).getTime()) && utc(value).toISOString().startsWith(value));
}

export const addDays = shiftDay;

/** Calendar parts of an instant in `timeZone`. */
function zonedParts(at: Date, timeZone: string) {
  const values: Record<string, string> = {};
  for (const part of new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(at)) {
    values[part.type] = part.value;
  }
  return {
    day: `${values.year}-${values.month}-${values.day}`,
    hour: Number(values.hour) % 24,
    minute: Number(values.minute),
    second: Number(values.second),
  };
}

/** The local day (AAAA-MM-DD) of an instant in the calendar's zone. */
export function dayOf(iso: string | Date | null | undefined, timeZone = CALENDAR_TZ): string | null {
  if (!iso) return null;
  const at = iso instanceof Date ? iso : new Date(iso);
  if (Number.isNaN(at.getTime())) return null;
  try {
    return zonedParts(at, timeZone).day;
  } catch {
    return zonedParts(at, CALENDAR_TZ).day;
  }
}

export function todayIn(timeZone = CALENDAR_TZ, now: number = Date.now()): string {
  return dayOf(new Date(now), timeZone) ?? new Date(now).toISOString().slice(0, 10);
}

/** Minutes since local midnight of an instant in the calendar's zone. */
export function minutesOfDay(iso: string, timeZone = CALENDAR_TZ): number | null {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return null;
  try {
    const parts = zonedParts(at, timeZone);
    return parts.hour * 60 + parts.minute;
  } catch {
    return null;
  }
}

/** Offset of `timeZone` from UTC, in minutes (Bogotá: -300). */
export function zoneOffsetMinutes(timeZone: string, at: Date = new Date()): number {
  try {
    const parts = zonedParts(at, timeZone);
    const [y, m, d] = parts.day.split('-').map(Number) as [number, number, number];
    const asUtc = Date.UTC(y, m - 1, d, parts.hour, parts.minute, parts.second);
    return Math.round((asUtc - Math.floor(at.getTime() / 1000) * 1000) / 60_000);
  } catch {
    return -at.getTimezoneOffset();
  }
}

/** True when the device shows other hours than the calendar's zone: the header then says «Horas de Bogotá». */
export function deviceDiffers(timeZone = CALENDAR_TZ, at: Date = new Date()): boolean {
  return -at.getTimezoneOffset() !== zoneOffsetMinutes(timeZone, at);
}

/** 0 = Monday … 6 = Sunday. */
export function weekdayIndex(day: string): number {
  return (utc(day).getUTCDay() + 6) % 7;
}

export function startOfWeek(day: string): string {
  return addDays(day, -weekdayIndex(day));
}

export function weekDays(day: string): string[] {
  const monday = startOfWeek(day);
  return Array.from({ length: 7 }, (_, index) => addDays(monday, index));
}

export function monthOf(day: string): string {
  return day.slice(0, 7);
}

export function firstOfMonth(day: string): string {
  return `${monthOf(day)}-01`;
}

function lastOfMonth(day: string): string {
  const date = utc(firstOfMonth(day));
  date.setUTCMonth(date.getUTCMonth() + 1);
  date.setUTCDate(0);
  return date.toISOString().slice(0, 10);
}

/** Monday-to-Sunday grid that covers the month: 5 or 6 rows. */
export function monthGrid(day: string): string[] {
  const start = startOfWeek(firstOfMonth(day));
  const end = addDays(startOfWeek(lastOfMonth(day)), 6);
  const days: string[] = [];
  for (let current = start; current <= end; current = addDays(current, 1)) days.push(current);
  return days;
}

/** Same day of the month `n` months later, clamped to the month's length. */
export function addMonths(day: string, n: number): string {
  const [y, m, d] = day.split('-').map(Number) as [number, number, number];
  const target = new Date(Date.UTC(y, m - 1 + n, 1));
  const last = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
  target.setUTCDate(Math.min(d, last));
  return target.toISOString().slice(0, 10);
}

export function daysBetween(from: string, to: string): number {
  return Math.round((utc(to).getTime() - utc(from).getTime()) / 86_400_000);
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** «sábado 7 de noviembre». */
export function longDay(day: string): string {
  const date = utc(day);
  return `${DIAS[date.getUTCDay()]} ${date.getUTCDate()} de ${MESES[date.getUTCMonth()]}`;
}

/** «Sábado 7 de noviembre». */
export function longDayTitle(day: string): string {
  return capitalize(longDay(day));
}

/** «sáb 7». */
export function shortDay(day: string): string {
  const date = utc(day);
  return `${DIAS_CORTOS[date.getUTCDay()]} ${date.getUTCDate()}`;
}

export function dayInitial(day: string): string {
  return INICIALES[utc(day).getUTCDay()]!;
}

export function dayNumber(day: string): number {
  return utc(day).getUTCDate();
}

/** «Noviembre 2026». */
export function monthTitle(day: string): string {
  const date = utc(day);
  return `${capitalize(MESES[date.getUTCMonth()]!)} ${date.getUTCFullYear()}`;
}

/** «2–8 nov 2026», «30 nov – 6 dic 2026», «29 dic 2025 – 4 ene 2026». */
export function weekRangeLabel(day: string): string {
  const start = utc(startOfWeek(day));
  const end = utc(addDays(startOfWeek(day), 6));
  const [sd, sm, sy] = [start.getUTCDate(), start.getUTCMonth(), start.getUTCFullYear()];
  const [ed, em, ey] = [end.getUTCDate(), end.getUTCMonth(), end.getUTCFullYear()];
  if (sy !== ey) return `${sd} ${MESES_CORTOS[sm]} ${sy} – ${ed} ${MESES_CORTOS[em]} ${ey}`;
  if (sm !== em) return `${sd} ${MESES_CORTOS[sm]} – ${ed} ${MESES_CORTOS[em]} ${ey}`;
  return `${sd}–${ed} ${MESES_CORTOS[em]} ${ey}`;
}

/** «Hoy», «Mañana», «Ayer» or «Lunes 9 de noviembre». */
export function relativeDay(day: string, today: string): string {
  const diff = daysBetween(today, day);
  if (diff === 0) return 'Hoy';
  if (diff === 1) return 'Mañana';
  if (diff === -1) return 'Ayer';
  return longDayTitle(day);
}

/** «hoy», «mañana», «ayer» or «el lunes 9 de noviembre», to put inside a sentence. */
export function relativeDayInSentence(day: string, today: string): string {
  const diff = daysBetween(today, day);
  if (diff === 0) return 'hoy';
  if (diff === 1) return 'mañana';
  if (diff === -1) return 'ayer';
  return `el ${longDay(day)}`;
}

/** Time left until an instant: «5 h 20 min», «18 h», «12 min», «2 días». */
export function timeLeft(ms: number): string {
  if (ms < 60_000) return 'menos de 1 min';
  const minutes = Math.floor(ms / 60_000);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    const rest = minutes % 60;
    return hours < 10 && rest ? `${hours} h ${rest} min` : `${hours} h`;
  }
  const days = Math.round(hours / 24);
  return days === 1 ? '1 día' : `${days} días`;
}
