// Resultados (GET /api/v1/resultados and the weekly summary): the shape of section 1 and the pure rules both
// apps draw with — the period and modality controls, the KPI «sin dato» and variation rules, funnels, the
// 60/40 split, the impressions chart with its median line, the posts sorting, the team line and the summary
// texts. Shared by the PWA (oficina/src/pages/resultados) and the native app (movil/src/resultados).
import type {
  Kpi,
  KpiPoint,
  OpportunityModality,
  OpportunityStage,
  Resultados,
  ResultadosDias,
  ResultadosModalidad,
  ResultadosPost,
  WeeklySummary,
  WeeklySummaryAnalysis,
  WeeklySummaryGenerate,
  WeeklySummaryState,
} from '../api/types';
import { CONTACT_ROLE_LABEL, contactStageLabel, formatDateTime, formatNumber, formatPct, formatTime, formatUsd } from './format';
import { relativeDay, shortDate } from './personas';
import type { Tone } from './tone';

// ================================================================ section 1 (resultados.py, negocio())

export interface NegocioStep {
  stage: OpportunityStage;
  label: string;
  count: number;
  conversion_pct: number | null;
}

export interface NegocioActiva {
  id: string;
  person: string;
  contact_id: string | null;
  company: string;
  modality: OpportunityModality;
  stage: OpportunityStage;
  stage_label: string;
  next_action: string;
  next_action_at: string | null;
}

export type BusinessModality = 'personal_startups' | 'projectapp';

export interface NegocioOn {
  disponible: true;
  motivo?: string | null;
  conversaciones: Kpi;
  abiertas: Kpi;
  reuniones: Kpi;
  propuestas: Kpi;
  acuerdos: Kpi;
  inbound: Kpi;
  embudo: { steps: NegocioStep[]; sin_acuerdo: number; definition: string };
  modalidades: {
    counts: Partial<Record<OpportunityModality, number>>;
    pct: Partial<Record<BusinessModality, number | null>>;
    objetivo: Partial<Record<BusinessModality, number>>;
    definition: string;
  };
  activas: NegocioActiva[];
}

export interface NegocioOff {
  disponible: false;
  motivo: string | null;
  inbound: Kpi;
}

export type Negocio = NegocioOn | NegocioOff;

export function readNegocio(data: Resultados['negocio']): Negocio {
  return data as unknown as Negocio;
}

// ================================================================ controls

export const RESULTADOS_PERIODS: readonly { value: ResultadosDias; label: string }[] = [
  { value: 7, label: '7 días' },
  { value: 28, label: '28 días' },
  { value: 90, label: '90 días' },
];

export const RESULTADOS_MODALITIES: readonly { value: ResultadosModalidad; label: string }[] = [
  { value: 'todo', label: 'Todo' },
  { value: 'personal_startups', label: 'Startups' },
  { value: 'projectapp', label: 'ProjectApp' },
];

/** The four sections, in the order business → audience → content → team, with their jump chip. */
export const RESULTADOS_SECTIONS = [
  { id: 'res-negocio', chip: '1 · Negocio', label: '1 · ¿Genera negocio?' },
  { id: 'res-gente', chip: '2 · Gente', label: '2 · ¿Llegamos a la gente correcta?' },
  { id: 'res-contenido', chip: '3 · Contenido', label: '3 · ¿El contenido aporta?' },
  { id: 'res-equipo', chip: '4 · Equipo', label: '4 · ¿El equipo trabaja bien?' },
] as const;

export type ResultadosSectionId = (typeof RESULTADOS_SECTIONS)[number]['id'];

/** Content and team are not split by modality. */
export const NOT_SPLIT_BY_MODALITY = 'No se separa por modalidad: muestra toda la cuenta.';

export function readDias(value: string | null | undefined): ResultadosDias {
  return value === '7' ? 7 : value === '90' ? 90 : 28;
}

export function readModalidad(value: string | null | undefined): ResultadosModalidad {
  return value === 'personal_startups' || value === 'projectapp' ? value : 'todo';
}

/** The calendar day of an instant in a time zone, as AAAA-MM-DD. */
function dayIn(date: Date, timeZone: string | undefined): string {
  try {
    const format = new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' });
    if (typeof format.formatToParts === 'function') {
      const parts = Object.fromEntries(format.formatToParts(date).map((part) => [part.type, part.value]));
      if (parts.year && parts.month && parts.day) return `${parts.year}-${parts.month}-${parts.day}`;
    }
    return format.format(date);
  } catch {
    return date.toISOString().slice(0, 10);
  }
}

/** «hoy 14:20», or «6 nov 14:20» when the data stopped on another day. */
export function dataUntil(iso: string, timeZone?: string, now: Date = new Date()): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  const time = formatTime(iso, timeZone);
  const day = dayIn(date, timeZone);
  return day === dayIn(now, timeZone) ? `hoy ${time}` : `${shortDate(day)} ${time}`;
}

/** The line under the controls: «Periodo en curso: datos hasta hoy 14:20. Todo se compara con…». */
export function periodNote(data: Resultados | undefined, pending: boolean, dias: ResultadosDias): string {
  if (data) return `Periodo en curso: datos hasta ${dataUntil(data.periodo.datos_hasta, data.zona_horaria)}. Todo se compara con los ${data.periodo.dias} días anteriores.`;
  if (pending) return 'Cargando el periodo…';
  return `Todo se compara con los ${dias} días anteriores.`;
}

// ================================================================ KPI tiles

export type KpiUnit = 'number' | 'percent' | 'usd';
export type KpiBetter = 'up' | 'down' | 'none';

export function formatKpiValue(value: number, unit: KpiUnit = 'number', format?: (value: number) => string): string {
  if (format) return format(value);
  if (unit === 'percent') return formatPct(value);
  if (unit === 'usd') return formatUsd(value);
  return formatNumber(value);
}

export type KpiDeltaView = { text: string; spoken: string; tone: 'good' | 'bad' | 'flat' };

/** The variation line, per the contract: grey «sin comparación» unless `comparable`. */
export function kpiDelta(kpi: Kpi, unit: KpiUnit = 'number', better: KpiBetter = 'up', asPercent = false): KpiDeltaView {
  if (!kpi.comparable || kpi.delta === null || kpi.delta === undefined) {
    return { text: 'sin comparación', spoken: 'Sin comparación con el periodo anterior', tone: 'flat' };
  }
  const delta = asPercent && kpi.delta_pct !== null && kpi.delta_pct !== undefined ? kpi.delta_pct : kpi.delta;
  if (delta === 0) return { text: '= igual que antes', spoken: 'Igual que en el periodo anterior', tone: 'flat' };
  const up = delta > 0;
  const magnitude = Math.abs(delta);
  let amount: string;
  if (asPercent && kpi.delta_pct !== null && kpi.delta_pct !== undefined) amount = formatPct(magnitude);
  else if (unit === 'percent') amount = `${formatNumber(magnitude)} pts`;
  else if (unit === 'usd') amount = formatUsd(magnitude);
  else amount = formatNumber(magnitude);
  const good = better === 'none' ? null : better === 'up' ? up : !up;
  return {
    text: up ? `▲ ${amount}` : `▼ −${amount}`,
    spoken: `${up ? 'Sube' : 'Baja'} ${amount} frente al periodo anterior`,
    tone: good === null ? 'flat' : good ? 'good' : 'bad',
  };
}

/** Points of the minichart in a 100×30 box; null values are skipped. */
export function sparklinePoints(series: KpiPoint[] | null | undefined): string | null {
  const values = (series ?? []).map((p, i) => ({ i, v: p.value })).filter((p): p is { i: number; v: number } => typeof p.v === 'number' && Number.isFinite(p.v));
  if (!series || values.length < 2) return null;
  const min = Math.min(...values.map((p) => p.v));
  const max = Math.max(...values.map((p) => p.v));
  const last = Math.max(1, series.length - 1);
  return values
    .map(({ i, v }) => {
      const x = (i / last) * 100;
      const y = max === min ? 16 : 28 - ((v - min) / (max - min)) * 24;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
}

/** A null value is «sin dato» (a dash and the reason), never 0; a KPI that did not arrive reads «aún no disponible». */
export function kpiState(kpi: Kpi | null | undefined, missingText = 'Aún no disponible'): { available: boolean; reason: string } {
  const available = kpi !== null && kpi !== undefined && kpi.value !== null && kpi.value !== undefined;
  return { available, reason: kpi ? (kpi.unavailable_reason ?? 'Sin dato en este periodo.') : missingText };
}

/** «Constancia» as «24 de 28» when the ratio brings its parts. */
export function consistencyFormat(kpi: Kpi | undefined): ((value: number) => string) | undefined {
  if (kpi && typeof kpi.numerator === 'number' && typeof kpi.denominator === 'number') {
    const { numerator, denominator } = kpi;
    return () => `${formatNumber(numerator)} de ${formatNumber(denominator)}`;
  }
  return undefined;
}

// ================================================================ bars and funnels

export interface FunnelStepInput {
  key?: string;
  label: string;
  /** null is «sin dato» (shown as —), never 0. */
  value: number | null;
}

export interface FunnelRow {
  key: string;
  label: string;
  value: number | null;
  /** «3» or «—». */
  valueText: string;
  /** Percent of the previous step, when shown. */
  conversion: number | null;
  /** Bar width, 0–100, relative to the largest step. */
  width: number;
  /** «Necesidad identificada: 3, 75 % del paso anterior». */
  spoken: string;
}

/** Horizontal bars with their count and the conversion between steps. */
export function funnelRows(steps: readonly FunnelStepInput[], showConversion = true): FunnelRow[] {
  const max = Math.max(0, ...steps.map((s) => s.value ?? 0));
  return steps.map((step, index) => {
    const previous = index > 0 ? steps[index - 1]!.value : null;
    const conversion = showConversion && index > 0 && step.value !== null && previous !== null && previous > 0 ? Math.round((step.value / previous) * 100) : null;
    const width = step.value === null ? 0 : step.value && max > 0 ? Math.max(2, (step.value / max) * 100) : 2;
    const valueText = step.value === null ? '—' : formatNumber(step.value);
    return {
      key: step.key ?? step.label,
      label: step.label,
      value: step.value,
      valueText,
      conversion,
      width,
      spoken: `${step.label}: ${step.value === null ? 'sin dato' : valueText}${conversion !== null ? `, ${conversion} % del paso anterior` : ''}`,
    };
  });
}

export interface BarInput {
  key: string;
  /** null is «sin dato» (a dash), never 0. */
  value: number | null;
  /** Text on the right; defaults to the number. */
  display?: string;
}

/** A bar list relative to the largest value, like the funnel but with any value format. */
export function barRows<T extends BarInput>(items: readonly T[]): (T & { text: string; width: number })[] {
  const max = Math.max(0, ...items.map((item) => item.value ?? 0));
  return items.map((item) => ({
    ...item,
    text: item.value === null ? '—' : (item.display ?? formatNumber(item.value)),
    width: item.value && max > 0 ? Math.max(2, (item.value / max) * 100) : item.value === null ? 0 : 2,
  }));
}

// ================================================================ 1 · negocio

export const NEGOCIO_PENDING_TEXT = 'Mediremos oportunidades cuando registres la primera o conectemos el inbox';

/** Ends a backend sentence with a full stop. */
export function withPeriod(text: string): string {
  const clean = text.trim();
  return /[.!?…]$/.test(clean) ? clean : `${clean}.`;
}

/** «Enviar la propuesta de piloto · 12 nov». */
export function activeNext(item: Pick<NegocioActiva, 'next_action' | 'next_action_at'>): string {
  return [item.next_action, relativeDay(item.next_action_at)].filter(Boolean).join(' · ');
}

/** Where an active opportunity leads: the person card, or the Oportunidades tab without a person. */
export function activeLink(item: Pick<NegocioActiva, 'contact_id'>): string {
  return item.contact_id ? `/personas/${encodeURIComponent(item.contact_id)}` : '/personas?pestana=oportunidades';
}

export interface ModalitySplitView {
  /** Null when there is no opportunity with a business modality yet (sin dato). */
  startups: number | null;
  projectapp: number | null;
  /** Target share of Startups (60). */
  target: number;
  pendingNote: string | null;
  spoken: string;
  legendStartups: string;
  legendProjectapp: string;
  legendTarget: string;
}

/** Stacked Startups / ProjectApp bar against the 60/40 target. */
export function modalitySplit(data: NegocioOn['modalidades']): ModalitySplitView {
  const startups = data.pct.personal_startups ?? null;
  const projectapp = data.pct.projectapp ?? null;
  const target = data.objetivo.personal_startups ?? 60;
  const pending = data.counts.por_clasificar ?? 0;
  const ready = startups !== null && projectapp !== null;
  return {
    startups: ready ? startups : null,
    projectapp: ready ? projectapp : null,
    target,
    pendingNote: pending > 0 ? `${pending} ${pending === 1 ? 'oportunidad por clasificar no cuenta' : 'oportunidades por clasificar no cuentan'} en el reparto.` : null,
    spoken: ready ? `Startups ${formatNumber(startups, 0)} %, ProjectApp ${formatNumber(projectapp, 0)} %, objetivo ${target}/${100 - target}` : '',
    legendStartups: ready ? `Startups ${formatNumber(startups, 0)} % · ${data.counts.personal_startups ?? 0}` : '',
    legendProjectapp: ready ? `ProjectApp ${formatNumber(projectapp, 0)} % · ${data.counts.projectapp ?? 0}` : '',
    legendTarget: `Objetivo ${target}/${100 - target}`,
  };
}

export const MODALITY_SPLIT_MISSING = 'Sin dato: aún no hay oportunidades con modalidad Startups o ProjectApp.';

// ================================================================ 2 · gente

const ROLE_ORDER = ['comprador', 'par', 'recomendador', 'divulgador', 'lider', 'aliado'];
const ASIDE_LABEL: Record<string, string> = { discarded: 'Descartados', closed: 'Cerrados', incoming: 'Te invitaron' };

/** The new fitting connections by role, in the design order (Comprador first), as funnel steps. */
export function roleSteps(items: { role: string; value: number }[] | null | undefined): FunnelStepInput[] | null {
  if (!items) return null;
  return [...items]
    .sort((a, b) => {
      const ia = ROLE_ORDER.indexOf(a.role);
      const ib = ROLE_ORDER.indexOf(b.role);
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    })
    .map((item) => ({ key: item.role, label: CONTACT_ROLE_LABEL[item.role] ?? (item.role === 'sin_rol' ? 'Sin rol' : item.role), value: item.value }));
}

type NetworkFunnel = Resultados['audiencia']['funnel'];

export function networkFunnelSteps(funnel: NetworkFunnel | undefined): FunnelStepInput[] {
  return (funnel?.order ?? []).map((stage) => ({ key: stage, label: contactStageLabel(stage), value: funnel?.stages[stage] ?? 0 }));
}

/** «Descartados: 6 · Cerrados: 2 · Te invitaron: 1». */
export function networkFunnelAside(funnel: NetworkFunnel | undefined): string {
  return (funnel?.aside ?? []).map((stage) => `${ASIDE_LABEL[stage] ?? contactStageLabel(stage)}: ${formatNumber(funnel?.stages[stage] ?? 0)}`).join(' · ');
}

/** The top 5 recurrent people: «Lucía Ficticia · 4 interacciones», linked when they have a contact. */
export function recurrentTop(kpi: Kpi | undefined): { key: string; contactId: string | null; label: string }[] {
  return (kpi?.top ?? []).slice(0, 5).map((person, index) => {
    const count = person.interactions ?? person.count;
    const id = person.contact_id ?? person.id ?? null;
    return { key: id ?? `${person.name}-${index}`, contactId: id, label: `${person.name}${typeof count === 'number' ? ` · ${count} interacciones` : ''}` };
  });
}

// ================================================================ 3 · contenido

type Contenido = Resultados['contenido'];
type Cut = '7d' | '24h' | null;

/** The impressions cut the section compares (7 days unless only 24 h exists). */
export function contenidoCut(data: Contenido): Cut {
  return data.kpis?.median_impressions?.cut ?? data.by_pillar?.cut ?? null;
}

export interface ImpressionBar {
  key: string;
  pieceId: string;
  /** 0–100 of the chart height. */
  height: number;
  /** At or over the median (or no median to compare with). */
  above: boolean;
  /** Measured at 24 h because it has no 7 days yet. */
  fallback: boolean;
  empty: boolean;
  /** «Post 1, 2 nov: 1.840 impresiones». */
  label: string;
}

export interface ImpressionsView {
  title: string;
  /** Median of the 4 previous weeks, or null. */
  reference: number | null;
  /** Height of the median line, 0–100. */
  referenceHeight: number | null;
  bars: ImpressionBar[];
  anyFallback: boolean;
  caption: string;
}

/** Impressions per post over the period with the median of the 4 previous weeks; each bar opens the piece. */
export function impressionsChart(chart: Contenido['chart'], cut: Cut): ImpressionsView {
  const source = chart.bars ?? [];
  const reference = (cut ? chart.median_previous_4_weeks?.[cut] : chart.median_previous_4_weeks?.['7d']) ?? null;
  const max = Math.max(1, reference ?? 0, ...source.map((bar) => bar.impressions ?? 0)) * 1.08;
  const bars = source.map((bar, index) => {
    const value = bar.impressions;
    return {
      key: `${bar.piece_id}-${index}`,
      pieceId: bar.piece_id,
      height: value === null ? 0 : Math.max(2, (value / max) * 100),
      above: reference === null || (value ?? 0) >= reference,
      fallback: Boolean(bar.fallback),
      empty: value === null,
      label: `Post ${index + 1}, ${shortDate(bar.date)}: ${value === null ? 'sin dato' : `${formatNumber(value)} impresiones`}${bar.fallback ? ' a las 24 h' : ''}`,
    };
  });
  return {
    title: cut === '24h' ? 'Impresiones por post a las 24 h' : 'Impresiones por post a los 7 días',
    reference,
    referenceHeight: reference === null ? null : (reference / max) * 100,
    bars,
    anyFallback: bars.some((bar) => bar.fallback),
    caption:
      reference !== null
        ? `La línea es la mediana de las 4 semanas anteriores (${formatNumber(reference)}). Toca una barra para ver la pieza.`
        : 'Aún no hay mediana de las 4 semanas anteriores. Toca una barra para ver la pieza.',
  };
}

// Pillar names of the editorial calendar (the same as oficina/src/lib/editorial.ts PILLAR_LABEL).
const PILLAR_NAMES: Record<string, string> = {
  business_to_product: 'Del negocio al producto',
  applied_ai: 'IA aplicada',
  architecture_delivery: 'Arquitectura y entrega',
};

export function pillarLabel(pillar: string | null | undefined): string {
  if (!pillar || pillar === 'sin_pilar') return 'Sin pilar';
  return PILLAR_NAMES[pillar] ?? pillar;
}

/** «2 nov · IA aplicada · 1.840 impresiones · 3,1 %». */
export function bestPostMeta(best: NonNullable<Contenido['best_post']>): string {
  return [
    shortDate(best.date),
    best.pillar ? pillarLabel(best.pillar) : '',
    best.impressions !== null ? `${formatNumber(best.impressions)} impresiones` : '',
    best.engagement_pct !== null ? formatPct(best.engagement_pct) : '',
  ]
    .filter(Boolean)
    .join(' · ');
}

/** Highest engagement first; pillars without data last. */
export function sortPillars(items: Contenido['by_pillar']['items'] | undefined): Contenido['by_pillar']['items'] {
  return [...(items ?? [])].sort((a, b) => (b.value ?? -1) - (a.value ?? -1));
}

/** «· 2 posts» after a pillar name. */
export function postsCount(posts: number): string {
  return `${posts} ${posts === 1 ? 'post' : 'posts'}`;
}

// ---------------------------------------------------------------- «Posts del periodo»

export type PostSortKey = 'date' | 'first_line' | 'pillar' | 'impressions_24h' | 'impressions_7d' | 'reactions' | 'comments' | 'reposts' | 'engagement_pct' | 'commenters';
export type SortDirection = 'asc' | 'desc';

/** The options of «Ordenar por» on mobile (always descending). */
export const POST_MOBILE_SORTS: readonly { value: PostSortKey; label: string }[] = [
  { value: 'date', label: 'Fecha' },
  { value: 'impressions_7d', label: 'Impresiones a 7 días' },
  { value: 'impressions_24h', label: 'Impresiones a 24 h' },
  { value: 'engagement_pct', label: 'Interacción' },
  { value: 'reactions', label: 'Reacciones' },
  { value: 'comments', label: 'Comentarios' },
  { value: 'commenters', label: 'Quién comentó' },
];

export function commenterRoleLabel(role: string): string {
  if (role === 'sin_clasificar' || role === 'sin_rol') return 'Sin clasificar';
  return CONTACT_ROLE_LABEL[role] ?? role;
}

export function commenterTotal(post: ResultadosPost): number | null {
  if (!post.commenters_by_role) return null;
  return Object.values(post.commenters_by_role).reduce((sum, value) => sum + value, 0);
}

function sortValue(post: ResultadosPost, key: PostSortKey): number | string | null {
  if (key === 'commenters') return commenterTotal(post);
  if (key === 'pillar') return post.pillar ? pillarLabel(post.pillar) : null;
  return post[key];
}

/** Sorted copy; missing values always go last. */
export function sortPosts(posts: ResultadosPost[], key: PostSortKey, direction: SortDirection): ResultadosPost[] {
  const factor = direction === 'asc' ? 1 : -1;
  return [...posts].sort((a, b) => {
    const left = sortValue(a, key);
    const right = sortValue(b, key);
    if (left === null || left === undefined) return right === null || right === undefined ? 0 : 1;
    if (right === null || right === undefined) return -1;
    if (typeof left === 'number' && typeof right === 'number') return (left - right) * factor;
    return String(left).localeCompare(String(right), 'es') * factor;
  });
}

/** «Quién comentó»: not measured yet, not read yet, nobody, or a chip per role («Comprador · 3»). */
export type CommentersView = { kind: 'nocut' } | { kind: 'unread' } | { kind: 'nobody' } | { kind: 'roles'; chips: string[] };

export function commentersView(post: ResultadosPost): CommentersView {
  if (!post.cut) return { kind: 'nocut' };
  if (!post.commenters_by_role) return { kind: 'unread' };
  const entries = Object.entries(post.commenters_by_role).filter(([, count]) => count > 0);
  if (!entries.length) return { kind: 'nobody' };
  return { kind: 'roles', chips: entries.map(([role, count]) => `${commenterRoleLabel(role)} · ${count}`) };
}

// ================================================================ 4 · equipo

/** «24 publicados», or null for «sin dato». */
export function teamCount(kpi: Kpi | undefined, one: string, many: string): string | null {
  const value = kpi?.value;
  if (value === null || value === undefined) return null;
  return `${formatNumber(value)} ${value === 1 ? one : many}`;
}

/** The ⓘ lines of a compact stat: «Seguidos: …», plus the reason when it has no data. */
export function definitionLines(items: [string, Kpi | undefined][]): string[] {
  return items
    .filter(([, kpi]) => kpi?.definition)
    .map(([label, kpi]) => `${label}: ${kpi?.definition}${kpi?.value === null && kpi.unavailable_reason ? ` ${kpi.unavailable_reason}` : ''}`);
}

/** «3,10»: money with two decimals, without the unit. */
export function amount(value: number): string {
  return value.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function sum(values: (number | null | undefined)[]): number {
  return values.reduce<number>((total, value) => total + (typeof value === 'number' ? value : 0), 0);
}

/** «3,10 USD hoy» and «61,20 de 100,00 USD este mes» (the team's single monthly AI budget); null without the spend
 * block. An older backend with per-area daily caps still reads «3,10 de 5,00 USD hoy». */
export function spendSummary(spend: Resultados['equipo']['spend'] | undefined): { today: string; month: string | null } | null {
  if (!spend) return null;
  const today = Object.values(spend.today ?? {});
  const spent = sum(today.map((line) => line.spent));
  const budget = sum(today.map((line) => line.budget));
  const total = (spend.month as Record<string, { spent: number; budget: number | null }> | undefined)?.total;
  const month = total?.spent ?? null;
  const monthly = total?.budget ?? 0;
  return {
    today: budget > 0 ? `${amount(spent)} de ${formatUsd(budget)} hoy` : `${formatUsd(spent)} hoy`,
    month: month === null ? null : monthly > 0 ? `${amount(month)} de ${formatUsd(monthly)} este mes` : `${formatUsd(month)} este mes`,
  };
}

// ================================================================ «Resumen de la semana»

export const RESUMEN_ROLE = 'analista_barrio_resultados';
export const RESUMEN_ROLE_NAME = 'Analista del barrio';
/** Character sheet of the analyst in the scene (scene/roles.ts). */
export const RESUMEN_SPRITE = 3;
export const OPERATOR_TZ = 'America/Bogota';

export const SUMMARY_STATE_BADGE: Record<WeeklySummaryState, { tone: Tone; label: string } | null> = {
  nuevo: { tone: 'ok', label: 'Nuevo' },
  visto: null,
  aplicado: { tone: 'info', label: 'Usado como orientación' },
  descartado: { tone: 'muted', label: 'Descartado' },
};

/** The three lists of the analysis, with what each says when it is empty. */
export const SUMMARY_LISTS: readonly { key: 'lo_que_funciono' | 'lo_que_no' | 'recomendaciones'; title: string; empty: string }[] = [
  { key: 'lo_que_funciono', title: 'Lo que funcionó', empty: 'Nada destacable con los datos de la semana.' },
  { key: 'lo_que_no', title: 'Lo que no', empty: 'Nada que señalar con los datos de la semana.' },
  { key: 'recomendaciones', title: 'Recomendaciones', empty: 'Sin recomendaciones: los datos no dan para tanto.' },
];

export function summaryItems(analysis: WeeklySummaryAnalysis, key: (typeof SUMMARY_LISTS)[number]['key']) {
  return analysis[key] ?? [];
}

/** «la semana del 2 al 8 de noviembre» from the backend's «Semana del …». */
export function weekPhrase(label: string): string {
  return `la ${label.charAt(0).toLowerCase()}${label.slice(1)}`;
}

/** «Escrito el 9 nov 2026, 7:31 · 0,12 USD». */
export function summaryFooter(summary: WeeklySummary): string {
  const cost = summary.cost_usd !== null ? ` · ${formatUsd(summary.cost_usd)}` : '';
  return `Escrito el ${formatDateTime(summary.created_at)}${cost}`;
}

/** Gustavo has not decided on the proposal yet. */
export function summaryPending(summary: WeeklySummary): boolean {
  return summary.state === 'nuevo' || summary.state === 'visto';
}

/** «La usaste como orientación del equipo el …» / «La descartaste el …». */
export function decidedSentence(summary: WeeklySummary): string {
  return `${summary.state === 'aplicado' ? 'La usaste como orientación del equipo' : 'La descartaste'}${summary.decided_at ? ` el ${formatDateTime(summary.decided_at)}` : ''}.`;
}

/** « El analista lo escribe cada lunes a las 07:30.» (with its leading space), or ''. */
export function automaticSentence(offer: WeeklySummaryGenerate): string {
  return offer.automatic && offer.automatic_at ? ` El analista lo escribe cada lunes a las ${formatTime(offer.automatic_at, OPERATOR_TZ)}.` : '';
}

export function decisionToast(decision: 'aplicar' | 'descartar'): string {
  return decision === 'aplicar' ? 'Orientación actualizada. El equipo la usa desde su próxima tarea.' : 'Resumen descartado';
}

/**
 * One id per «Generar ahora» intent: a retry after a network error never queues a second summary.
 * Hermes has no crypto.randomUUID, so the app falls back to a random v4-shaped id (idempotency only).
 */
export function newRequestId(): string {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  } catch {
    // fall through
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
    const random = Math.floor(Math.random() * 16);
    return (char === 'x' ? random : (random % 4) + 8).toString(16);
  });
}
