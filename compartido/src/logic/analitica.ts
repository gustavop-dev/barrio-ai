// Resultados › Analítica de LinkedIn (GET /api/v1/resultados/analitica): the period kept in the route params
// (?periodo= or ?desde=&hasta=), the custom range checked against the days already imported, and the texts and
// figures the view draws — the period and freshness lines, the coverage notes, the daily chart, the followers, the
// posts with their lifetime figures, LinkedIn's top lists and the demographics. Days are UTC calendar days, as the
// backend stores them. Shared by the native app (movil/src/resultados) and, later, the PWA.
import type { Analitica, AnaliticaData, AnaliticaDay, AnaliticaDemographicGroup, AnaliticaPost, AnaliticaPreset, AnaliticaTopItem, KpiPoint } from '../api/types';
import { daysBetween, isIsoDay } from './dates';
import { formatNumber, formatPct, shiftDay, timeAgo } from './format';
import { shortDate } from './personas';
import { withPeriod } from './resultados';

// ================================================================ the period

export const ANALITICA_PRESETS: readonly { value: AnaliticaPreset; label: string; days: number }[] = [
  { value: '7d', label: '7 días', days: 7 },
  { value: '14d', label: '14 días', days: 14 },
  { value: '28d', label: '28 días', days: 28 },
  { value: '90d', label: '90 días', days: 90 },
  { value: '365d', label: '365 días', days: 365 },
];

/** The backend's default, and no param in the URL. */
export const DEFAULT_PRESET: AnaliticaPreset = '28d';

/** The longest period the backend serves (a leap year). */
export const MAX_DAYS = 366;

export type AnaliticaSelection = { kind: 'preset'; periodo: AnaliticaPreset } | { kind: 'custom'; desde: string; hasta: string };

export function readPreset(value: string | null | undefined): AnaliticaPreset {
  return ANALITICA_PRESETS.find((preset) => preset.value === value)?.value ?? DEFAULT_PRESET;
}

/** The selection of the route params. A custom range that is not two days in order, of at most 366 days, is ignored. */
export function readSelection(params: { periodo?: string; desde?: string; hasta?: string }): AnaliticaSelection {
  const { desde = '', hasta = '' } = params;
  if (isIsoDay(desde) && isIsoDay(hasta) && desde <= hasta && daysBetween(desde, hasta) + 1 <= MAX_DAYS) return { kind: 'custom', desde, hasta };
  return { kind: 'preset', periodo: readPreset(params.periodo) };
}

/** What the request asks for: `periodo`, or `desde` and `hasta` together. */
export function selectionQuery(selection: AnaliticaSelection): { periodo?: AnaliticaPreset; desde?: string; hasta?: string } {
  return selection.kind === 'custom' ? { desde: selection.desde, hasta: selection.hasta } : { periodo: selection.periodo };
}

/** The route params of a selection; an empty value removes the param (the default preset has none). */
export function selectionParams(selection: AnaliticaSelection): { periodo: string; desde: string; hasta: string } {
  if (selection.kind === 'custom') return { periodo: '', desde: selection.desde, hasta: selection.hasta };
  return { periodo: selection.periodo === DEFAULT_PRESET ? '' : selection.periodo, desde: '', hasta: '' };
}

// ================================================================ dates and figures

function year(day: string): string {
  return day.slice(0, 4);
}

function plural(count: number, one: string, many: string): string {
  return `${formatNumber(count)} ${count === 1 ? one : many}`;
}

/** «12 nov de 2026». */
export function dayText(day: string): string {
  return `${shortDate(day)} de ${year(day)}`;
}

/** «del 16 oct al 12 nov de 2026», with each year when they differ; «el 12 nov de 2026» for one day. */
export function rangeText(desde: string, hasta: string): string {
  if (desde === hasta) return `el ${dayText(desde)}`;
  if (year(desde) === year(hasta)) return `del ${shortDate(desde)} al ${shortDate(hasta)} de ${year(hasta)}`;
  return `del ${dayText(desde)} al ${dayText(hasta)}`;
}

/** The UTC day of an instant the backend sends («2026-11-13T06:10:00Z» → «2026-11-13»). */
function utcDay(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso.slice(0, 10) : date.toISOString().slice(0, 10);
}

/** A figure or «—», never 0 for a missing one. */
export function figure(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : formatNumber(value);
}

// ================================================================ the lines under the controls

export function hasPayload(data: Analitica | undefined): data is AnaliticaData {
  return Boolean(data && 'periodo' in data);
}

export const NOT_AVAILABLE_TITLE = 'Aún no hay analítica de LinkedIn';
export const NOT_AVAILABLE_TEXT =
  'Cuando el equipo la traiga, aquí verás impresiones, interacciones, seguidores y público de 7, 14, 28, 90 o 365 días, o del periodo que elijas.';

/** «Del 16 oct al 12 nov de 2026 · 28 días (UTC). Se compara con los 28 días anteriores.» */
export function periodLine(data: AnaliticaData): string {
  const { desde, hasta, dias } = data.periodo;
  const range = rangeText(desde, hasta);
  const compared = dias === 1 ? 'el día anterior' : `los ${formatNumber(dias)} días anteriores`;
  return `${range.charAt(0).toUpperCase()}${range.slice(1)} · ${plural(dias, 'día', 'días')} (UTC). Se compara con ${compared}.`;
}

/** «Actualizado hace 3 h.», or «Actualizado el …» after a week; null before the first import. */
export function freshnessLine(data: AnaliticaData, now: number = Date.now()): string | null {
  if (!data.actualizado) return null;
  const ago = timeAgo(data.actualizado.at, now);
  return `Actualizado ${ago.startsWith('hace') ? ago : `el ${ago}`}.`;
}

/** The failed import after the last good one: its reason, when it happened and what the figures are. */
export function importErrorNote(data: AnaliticaData, now: number = Date.now()): { title: string; text: string } | null {
  const failed = data.ultimo_error;
  if (!failed) return null;
  const ago = timeAgo(failed.at, now);
  const when = ago.startsWith('hace') ? `Fue ${ago}` : `Fue el ${ago}`;
  const rest = data.actualizado ? `${when}; las cifras son de la última importación que salió bien.` : `${when}.`;
  return { title: 'La última importación de LinkedIn falló', text: `${withPeriod(failed.error)} ${rest}` };
}

/** Days missing in the period (the sums count only the days there are) or in the one before (no comparison). */
export function coverageNote(data: AnaliticaData): string | null {
  const kpi = data.totales.impressions;
  const days = kpi.days ?? data.periodo.dias;
  const seen = kpi.days_with_data ?? days;
  const { primer_dia: first, ultimo_dia: last } = data.limites;
  if (seen === 0) return `Este periodo no tiene días importados de LinkedIn.${first && last ? ` Hay datos ${rangeText(first, last)}.` : ''}`;
  if (seen < days) return `Hay datos de ${formatNumber(seen)} de ${plural(days, 'día', 'días')}: las cifras suman solo esos días y no se comparan con el periodo anterior.`;
  if (kpi.value !== null && !kpi.comparable) {
    const before = data.periodo.anterior;
    return `El periodo anterior (${rangeText(before.desde, before.hasta)}) no tiene todos sus días importados: las cifras no se comparan.`;
  }
  return null;
}

// ================================================================ «Periodo personalizado»

export interface RangeBounds {
  min: string;
  max: string;
}

/** The days a custom range can use: the ones imported, or LinkedIn's first day to yesterday (UTC) before any. */
export function rangeBounds(limites: AnaliticaData['limites'], now: number = Date.now()): RangeBounds {
  const yesterday = shiftDay(new Date(now).toISOString().slice(0, 10), -1);
  return { min: limites.primer_dia ?? limites.linkedin_desde, max: limites.ultimo_dia ?? yesterday };
}

/** «Hay datos del 10 oct de 2025 al 12 nov de 2026 (UTC). Como mucho 366 días.» */
export function boundsLine(bounds: RangeBounds): string {
  return `Hay datos ${rangeText(bounds.min, bounds.max)} (UTC). Como mucho ${MAX_DAYS} días.`;
}

export interface RangeCheck {
  desde: string | null;
  hasta: string | null;
  /** About the pair: order and length. */
  rango: string | null;
  ok: boolean;
}

/** Each day written as AAAA-MM-DD and inside the imported days; «desde» not after «hasta»; at most 366 days. */
export function checkCustomRange(desde: string, hasta: string, bounds: RangeBounds): RangeCheck {
  const from = desde.trim();
  const to = hasta.trim();
  const outside = `Elige un día entre el ${dayText(bounds.min)} y el ${dayText(bounds.max)}.`;
  const field = (day: string) => (!isIsoDay(day) ? 'Escribe la fecha como AAAA-MM-DD.' : day < bounds.min || day > bounds.max ? outside : null);
  const errors = { desde: field(from), hasta: field(to) };
  let rango: string | null = null;
  if (!errors.desde && !errors.hasta) {
    if (from > to) rango = '«Desde» no puede ser posterior a «Hasta».';
    else if (daysBetween(from, to) + 1 > MAX_DAYS) rango = `El periodo tiene como mucho ${MAX_DAYS} días.`;
  }
  return { ...errors, rango, ok: !errors.desde && !errors.hasta && !rango };
}

// ================================================================ the daily chart

export type SerieMetric = 'impressions' | 'engagements' | 'new_followers';

export const SERIE_METRICS: readonly { value: SerieMetric; label: string; one: string; many: string }[] = [
  { value: 'impressions', label: 'Impresiones', one: 'impresión', many: 'impresiones' },
  { value: 'engagements', label: 'Interacciones', one: 'interacción', many: 'interacciones' },
  { value: 'new_followers', label: 'Seguidores', one: 'seguidor nuevo', many: 'seguidores nuevos' },
];

export function readMetric(value: string | null | undefined): SerieMetric {
  return SERIE_METRICS.find((metric) => metric.value === value)?.value ?? 'impressions';
}

export interface SeriePoint {
  date: string;
  value: number | null;
  /** 0–100, left to right. */
  x: number;
  /** 0–100 from the top; null without data. */
  y: number | null;
}

export interface SerieChart {
  points: SeriePoint[];
  /** Runs of consecutive days with data: a missing day breaks the line, it is never drawn as 0. */
  segments: SeriePoint[][];
  /** The top of the scale, a round number over the largest day. */
  top: number;
  topText: string;
  first: string | null;
  last: string | null;
  empty: boolean;
  /** What a screen reader says for the whole chart. */
  summary: string;
}

/** 1, 2, 2.5 or 5 times a power of ten, at or over `value`. */
export function niceTop(value: number): number {
  if (!(value > 0)) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  return ([1, 2, 2.5, 5, 10].find((step) => step * power >= value) ?? 10) * power;
}

/** The days of the period as points in a 100 × 100 box, its line segments and a spoken summary. */
export function serieChart(serie: readonly AnaliticaDay[], metric: SerieMetric): SerieChart {
  const meta = SERIE_METRICS.find((item) => item.value === metric)!;
  const values = serie.map((day) => day[metric]);
  const present = values.filter((value): value is number => typeof value === 'number');
  const top = niceTop(Math.max(0, ...present));
  const span = Math.max(1, serie.length - 1);
  const points = serie.map((day, index): SeriePoint => {
    const value = day[metric];
    return { date: day.date, value, x: serie.length === 1 ? 50 : (index / span) * 100, y: value === null ? null : 100 - (value / top) * 100 };
  });
  const segments: SeriePoint[][] = [];
  let run: SeriePoint[] = [];
  for (const point of points) {
    if (point.y === null) {
      if (run.length) segments.push(run);
      run = [];
    } else run.push(point);
  }
  if (run.length) segments.push(run);
  const first = serie[0]?.date ?? null;
  const last = serie.at(-1)?.date ?? null;
  const range = first && last ? ` ${rangeText(first, last)}` : '';
  let summary: string;
  if (!present.length) summary = `${meta.label} por día${range}: sin datos.`;
  else {
    const best = points.reduce((a, b) => ((b.value ?? -1) > (a.value ?? -1) ? b : a));
    const total = present.reduce((sum, value) => sum + value, 0);
    const missing = values.length - present.length;
    summary =
      `${meta.label} por día${range}: ${plural(total, meta.one, meta.many)} en total; el día con más fue el ${dayText(best.date)}, con ${formatNumber(best.value ?? 0)}.` +
      (missing ? ` ${plural(missing, 'día', 'días')} sin dato.` : '');
  }
  return { points, segments, top, topText: formatNumber(top), first, last, empty: !present.length, summary };
}

/** The point under a touch at `fraction` (0–1) of the chart's width. */
export function nearestPoint(chart: SerieChart, fraction: number): SeriePoint | null {
  if (!chart.points.length) return null;
  const index = Math.round(Math.min(1, Math.max(0, fraction)) * (chart.points.length - 1));
  return chart.points[index] ?? null;
}

/** «3 nov de 2026: 120 impresiones», or «…: sin dato». */
export function pointText(point: SeriePoint, metric: SerieMetric): string {
  const meta = SERIE_METRICS.find((item) => item.value === metric)!;
  return `${dayText(point.date)}: ${point.value === null ? 'sin dato' : plural(point.value, meta.one, meta.many)}`;
}

// ================================================================ followers

export interface FollowersView {
  /** «1.480», or null without a capture in the period. */
  total: string | null;
  /** «según LinkedIn el 13 nov de 2026». */
  at: string | null;
  /** «+7 desde el 6 nov», with two captures or more. */
  growth: string | null;
  tone: 'good' | 'bad' | 'flat';
  spoken: string;
  series: KpiPoint[];
}

export function followersView(seguidores: AnaliticaData['seguidores']): FollowersView {
  const known = seguidores.serie.filter((point): point is { date: string; value: number } => typeof point.value === 'number');
  const total = seguidores.total;
  let growth: string | null = null;
  let tone: FollowersView['tone'] = 'flat';
  let spokenGrowth = '';
  if (known.length >= 2) {
    const diff = known.at(-1)!.value - known[0]!.value;
    const since = shortDate(known[0]!.date);
    growth = diff === 0 ? `= igual que el ${since}` : `${diff > 0 ? '+' : '−'}${formatNumber(Math.abs(diff))} desde el ${since}`;
    tone = diff > 0 ? 'good' : diff < 0 ? 'bad' : 'flat';
    spokenGrowth = diff === 0 ? `igual que el ${since}` : `${diff > 0 ? 'suben' : 'bajan'} ${formatNumber(Math.abs(diff))} desde el ${since}`;
  }
  const at = seguidores.at ? `según LinkedIn el ${dayText(seguidores.at)}` : null;
  return {
    total: total === null ? null : formatNumber(total),
    at,
    growth,
    tone,
    spoken:
      total === null
        ? ['Seguidores: sin dato.', seguidores.unavailable_reason].filter(Boolean).join(' ')
        : [plural(total, 'seguidor', 'seguidores'), at, spokenGrowth].filter(Boolean).join(', '),
    series: seguidores.serie,
  };
}

// ================================================================ posts

/** «Publicada el 3 nov de 2026 · Imagen» (the kind as LinkedIn wrote it). */
export function postTitle(post: Pick<AnaliticaPost, 'published' | 'kind'>): string {
  return [post.published ? `Publicada el ${dayText(post.published)}` : 'Sin fecha de publicación', post.kind].filter(Boolean).join(' · ');
}

/** «Desde que se publicó, al 13 nov de 2026»: lifetime figures as LinkedIn gave them that day. */
export function postAsOf(post: Pick<AnaliticaPost, 'as_of'>): string {
  return `Desde que se publicó, al ${dayText(utcDay(post.as_of))}`;
}

const POST_FIGURES: readonly { key: keyof AnaliticaPost; label: string }[] = [
  { key: 'impressions', label: 'Impresiones' },
  { key: 'members_reached', label: 'Alcanzados' },
  { key: 'reactions', label: 'Reacciones' },
  { key: 'comments', label: 'Comentarios' },
  { key: 'shares', label: 'Compartidos' },
  { key: 'saves', label: 'Guardados' },
  { key: 'sends', label: 'Envíos' },
  { key: 'followers_gained', label: 'Seguidores' },
  { key: 'profile_views', label: 'Visitas al perfil' },
];

/** The lifetime figures of a post, «—» for the ones LinkedIn did not give. */
export function postFigures(post: AnaliticaPost): { key: string; label: string; text: string }[] {
  return POST_FIGURES.map(({ key, label }) => ({ key, label, text: figure(post[key] as number | null) }));
}

/** «De tu red 62,5 % · fuera 37,5 %», or null. */
export function postAudienceSplit(post: Pick<AnaliticaPost, 'network_pct' | 'outside_pct'>): string | null {
  if (post.network_pct === null && post.outside_pct === null) return null;
  return [post.network_pct !== null ? `De tu red ${formatPct(post.network_pct)}` : '', post.outside_pct !== null ? `fuera ${formatPct(post.outside_pct)}` : ''].filter(Boolean).join(' · ');
}

/** «3 publicaciones». */
export function publicationsCount(count: number): string {
  return plural(count, 'publicación', 'publicaciones');
}

// ================================================================ LinkedIn's top posts

export const TOP_LIMIT = 5;

/** Bars of one of LinkedIn's top lists: «Post del 3 nov» with its value in the range. */
export function topBars(items: readonly AnaliticaTopItem[], limit = TOP_LIMIT): { key: string; label: string; value: number | null }[] {
  return items.slice(0, limit).map((item, index) => ({
    key: `${item.post_urn || 'post'}-${index}`,
    label: item.published ? `Post del ${shortDate(item.published)}` : 'Post sin fecha',
    value: item.value,
  }));
}

/** «Según LinkedIn, del 6 nov al 12 nov de 2026.» */
export function topLine(top: NonNullable<AnaliticaData['posts']['top_linkedin']>): string {
  return `Según LinkedIn, ${rangeText(top.desde, top.hasta)}.`;
}

// ================================================================ demographics

/** «18,5 %», «< 1 %» when LinkedIn wrote it so, or «—». */
export function demographicPct(row: { pct: number | null; below: boolean }): string {
  if (row.pct === null) return '—';
  return row.below ? `< ${formatPct(row.pct)}` : formatPct(row.pct);
}

/** One group's rows as bars, in LinkedIn's order. */
export function demographicBars(group: AnaliticaDemographicGroup): { key: string; label: string; value: number | null; display: string }[] {
  return group.rows.map((row, index) => ({ key: `${row.label}-${index}`, label: row.label || '—', value: row.pct, display: demographicPct(row) }));
}

/** «Tus seguidores, según LinkedIn el 13 nov de 2026.» */
export function audienceLine(audiencia: NonNullable<AnaliticaData['demografia']['audiencia']>): string {
  return `Tus seguidores, según LinkedIn el ${dayText(audiencia.at)}.`;
}

/** Who saw the posts, with its own range: the period's, or the nearest range imported. */
export function contentLine(contenido: NonNullable<AnaliticaData['demografia']['contenido']>): string {
  const range = rangeText(contenido.desde, contenido.hasta);
  return contenido.exacto ? `Quienes vieron tus publicaciones ${range}.` : `Quienes vieron tus publicaciones ${range}: el rango importado más cercano, no exactamente este periodo.`;
}
