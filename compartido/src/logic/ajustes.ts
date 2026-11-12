// Ajustes (Ajustes.dc.html, DISENO-VISTAS «6. Ajustes», rev 18): the sections and their anchors, the
// names and tones of the machine, autonomy and caps, the spend lines and the per-type push switches.
// Pure: shared by the PWA and the native app, each draws it with its own components.
import type { AjustesConPush, PushType } from '../api/capturas';
import { ApiError } from '../api/client';
import type { Account, Ajustes, AjustesSpend, CapacityInfo, Control, NetworkRead, Orientation, Overview, RedSummary } from '../api/types';
import { formatUsd, timeAgo } from './format';
import type { Tone } from './tone';

/** The sections in order; the ids are the anchors (`/ajustes#maquina`, the pause banner links there). */
export const AJUSTES_SECTIONS = [
  { id: 'maquina', label: 'Máquina' },
  { id: 'orientacion', label: 'Orientación para el equipo' },
  { id: 'autonomia', label: 'Autonomía y límites' },
  { id: 'gasto', label: 'Gasto de IA' },
  { id: 'linkedin', label: 'LinkedIn oficial' },
  { id: 'captura', label: 'Captura y galería' },
  { id: 'notificaciones', label: 'Notificaciones' },
  { id: 'sabe', label: 'Lo que el equipo sabe de ti' },
  { id: 'sesion', label: 'Sesión y Acerca de' },
] as const;

export type AjustesSection = (typeof AJUSTES_SECTIONS)[number]['id'];

export function isAjustesSection(value: unknown): value is AjustesSection {
  return AJUSTES_SECTIONS.some((section) => section.id === value);
}

/** The backend does not have this endpoint yet (404/501): DISENO-VISTAS «Aún no disponible», never an error. */
export function isUnavailable(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 404 || error.status === 501);
}

// ---------------------------------------------------------------- Máquina

export const ACCOUNT_STATUS: Record<string, { label: string; tone: Tone }> = {
  running: { label: 'Conectada', tone: 'ok' },
  unknown: { label: 'Sin comprobar', tone: 'muted' },
  token_expired: { label: 'Token caducado', tone: 'bad' },
};

export const PROVIDER_LABEL: Record<string, string> = { unipile: 'Unipile', fake: 'simulada' };

export function accountStatus(account: Pick<Account, 'status'>): { label: string; tone: Tone } {
  return ACCOUNT_STATUS[account.status] ?? { label: account.status, tone: 'warn' };
}

export function providerLabel(account: Pick<Account, 'provider'>): string {
  return PROVIDER_LABEL[account.provider] ?? account.provider;
}

/** The accounts the machine acts with through Unipile; the official LinkedIn one lives in its own section. */
export function unipileAccounts(accounts: Account[] | undefined): Account[] {
  return (accounts ?? []).filter((account) => !account.provider.startsWith('linkedin'));
}

/** «Motivo: revisando los topes de la semana.» */
export function controlReason(control: Pick<Control, 'reason'>): string {
  return `Motivo: ${control.reason ? control.reason.replace(/\.$/, '') : 'sin motivo indicado'}.`;
}

/** A stop that comes from the environment (OPERATOR_PAUSED=true) cannot be lifted from the apps. */
export function stoppedFromServer(control: Pick<Control, 'paused' | 'source'>): boolean {
  return control.paused && control.source === 'env';
}

// ---------------------------------------------------------------- Orientación

export const ORIENTATION_MAX = 4000;

export function orientationCounter(length: number): string {
  return `${length} de ${ORIENTATION_MAX} caracteres. Es privada: orienta las decisiones y nunca aparece en un texto público.`;
}

/** «Actualizada hace 2 h por gustavo.» or that there is none yet. */
export function orientationUpdated(orientation: Pick<Orientation, 'updated_at' | 'updated_by'>, now: number = Date.now()): string {
  if (!orientation.updated_at) return 'Todavía no has escrito ninguna orientación.';
  return `Actualizada ${timeAgo(orientation.updated_at, now)}${orientation.updated_by ? ` por ${orientation.updated_by}` : ''}.`;
}

// ---------------------------------------------------------------- Autonomía y límites

export const CAPABILITY_ORDER = ['INT-03', 'INT-02', 'CONT-09', 'RED-01', 'RED-02', 'RED-04'] as const;

/** Names of DISENO-VISTAS 6.2 (mode table). */
export const MODE_NAME: Record<string, string> = {
  'INT-03': 'Comentarios',
  'INT-02': 'Reacciones',
  'CONT-09': 'Publicación diaria',
  'RED-01': 'Seguir',
  'RED-02': 'Invitar sin nota',
  'RED-04': 'Aceptar invitaciones',
};

/** Names of the cap meters. */
export const CAP_NAME: Record<string, string> = {
  'INT-03': 'Comentarios',
  'INT-02': 'Reacciones',
  'CONT-09': 'Publicaciones',
  'RED-01': 'Seguir',
  'RED-02': 'Invitaciones',
  'RED-04': 'Aceptar invitaciones',
};

export const MODE: Record<string, { label: string; tone: Tone }> = {
  auto: { label: 'Auto', tone: 'ok' },
  approval: { label: 'Aprobación', tone: 'info' },
  off: { label: 'Apagado', tone: 'muted' },
};

export function modeOf(mode: string): { label: string; tone: Tone } {
  return MODE[mode] ?? { label: mode, tone: 'muted' };
}

export const READS: { key: NetworkRead; label: string }[] = [
  { key: 'comments', label: 'Comentarios leídos' },
  { key: 'search', label: 'Búsquedas' },
  { key: 'profile', label: 'Perfiles' },
  { key: 'sync', label: 'Sincronizaciones' },
];

/** «20 min entre acciones». */
export function spacingLabel(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return 'Sin espaciado mínimo';
  if (seconds < 60) return `${Math.round(seconds)} s entre acciones`;
  return `${Math.round(seconds / 60)} min entre acciones`;
}

/** Usage of a capability: the overview accounts (INT-*, CONT-09) or the network summary (RED-*). */
export function capacityOf(code: string, overview: Overview | undefined, red: RedSummary | undefined): CapacityInfo | null {
  const network = red?.capacity?.[code as keyof RedSummary['capacity']];
  if (network) return network;
  for (const account of overview?.accounts ?? []) {
    const capacity = account.capacity?.[code];
    if (capacity) return capacity;
  }
  return null;
}

/** A line of the caps or reads: a meter with its usage, or only the cap («sin dato de uso», never 0). */
export type LimitLine = { key: string; label: string; used: number; max: number } | { key: string; label: string; text: string };

export function isMeterLine(line: LimitLine): line is Extract<LimitLine, { used: number }> {
  return 'used' in line;
}

/** The meters of «Topes de hoy» or «Topes de la semana», in the order of the mode table. */
export function capLines(ajustes: Ajustes | undefined, overview: Overview | undefined, red: RedSummary | undefined, period: 'daily' | 'weekly'): LimitLine[] {
  const lines: LimitLine[] = [];
  for (const code of CAPABILITY_ORDER) {
    const label = CAP_NAME[code]!;
    const capacity = capacityOf(code, overview, red);
    if (capacity) {
      const max = period === 'daily' ? capacity.daily : capacity.weekly;
      const used = period === 'daily' ? capacity.daily_used : capacity.weekly_used;
      if (typeof max === 'number' && max >= 0 && typeof used === 'number') {
        lines.push({ key: code, label, used, max });
        continue;
      }
    }
    const limit = ajustes?.limits?.[code];
    const cap = limit ? (period === 'daily' ? limit.daily : limit.weekly) : null;
    if (typeof cap === 'number' && cap >= 0) lines.push({ key: code, label, text: `Tope ${cap} · sin dato de uso` });
  }
  return lines;
}

export const EXECUTION_CHECKS_LABEL = 'Comprobaciones antes y después de escribir';

/** «Lecturas de la red»: each read against its cap; profile checks share the profile-read cap. */
export function readLines(red: RedSummary): { lines: LimitLine[]; execution: string | null } {
  const lines: LimitLine[] = [];
  for (const { key, label } of READS) {
    const max = red.read_caps?.[key];
    if (typeof max !== 'number' || max <= 0) continue;
    const used = red.reads_today?.[key];
    lines.push(typeof used === 'number' ? { key, label, used, max } : { key, label, text: `Tope ${max} · sin dato de uso` });
  }
  const execution = red.reads_today?.execution;
  return { lines, execution: typeof execution === 'number' ? `${execution} hoy · cuentan en el tope compartido de perfiles` : null };
}

// ---------------------------------------------------------------- Gasto de IA

export const knownAmount = (value: number | null | undefined): value is number => typeof value === 'number' && Number.isFinite(value);

/** A budget of today: a meter when it has a limit, or only what was spent («sin dato», never 0). */
export function spendLine(line: AjustesSpend): { label: string; used: number; max: number; display: string } | { label: string; text: string } {
  if (knownAmount(line.limit_usd) && line.limit_usd > 0) {
    return { label: line.label, used: line.spent_usd, max: line.limit_usd, display: `${formatUsd(line.spent_usd)} de ${formatUsd(line.limit_usd)}` };
  }
  return { label: line.label, text: knownAmount(line.spent_usd) ? formatUsd(line.spent_usd) : 'sin dato' };
}

/** The month against its limit, with the Meter's thresholds: «warn» from 80 %, «bad» at or over it; null below or without a limit. */
export function monthAlert(spend: Ajustes['ai_spend']): { tone: 'warn' | 'bad'; text: string } | null {
  if (!knownAmount(spend.month_usd) || !knownAmount(spend.limit_usd) || spend.limit_usd <= 0) return null;
  const fraction = spend.month_usd / spend.limit_usd;
  if (fraction >= 1) return { tone: 'bad', text: 'Límite del mes alcanzado' };
  if (fraction >= 0.8) return { tone: 'warn', text: 'Cerca del límite del mes' };
  return null;
}

/** The rows under the meters: this month (against its limit), since the start, the lead agent and transcription. */
export function spendRows(spend: Ajustes['ai_spend']): { label: string; text: string }[] {
  const month = knownAmount(spend.month_usd)
    ? knownAmount(spend.limit_usd)
      ? `${formatUsd(spend.month_usd)} de ${formatUsd(spend.limit_usd)}`
      : formatUsd(spend.month_usd)
    : 'sin dato';
  const rows = [
    { label: 'Este mes', text: month },
    { label: 'Desde el inicio', text: knownAmount(spend.total_usd) ? formatUsd(spend.total_usd) : 'sin dato' },
  ];
  if (knownAmount(spend.lead_month_usd)) rows.push({ label: 'Agente líder, este mes', text: formatUsd(spend.lead_month_usd) });
  if (knownAmount(spend.transcription_month_usd)) rows.push({ label: 'Transcripción de audios, este mes', text: formatUsd(spend.transcription_month_usd) });
  return rows;
}

// ---------------------------------------------------------------- Notificaciones (per type)

export function pushTypesOf(ajustes: Ajustes | undefined): PushType[] | undefined {
  return (ajustes as AjustesConPush | undefined)?.push_types;
}

/** «Va a Tu turno» or «Va a Notificaciones». */
export function pushTypeHint(type: Pick<PushType, 'goes_to'>): string | undefined {
  return type.goes_to === 'tu_turno' ? 'Va a Tu turno' : type.goes_to === 'notificaciones' ? 'Va a Notificaciones' : undefined;
}

/** Every kind switched off, for PATCH /ajustes/preferencias `push_disabled`. */
export function disabledKinds(types: readonly PushType[], overrides: Readonly<Record<string, boolean>>): string[] {
  return types.filter((type) => !(overrides[type.kind] ?? type.enabled)).map((type) => type.kind);
}

/** Every kind switched on, for PATCH /ajustes/preferencias `push_enabled` (a kind whose push is off by default can be turned on). */
export function enabledKinds(types: readonly PushType[], overrides: Readonly<Record<string, boolean>>): string[] {
  return types.filter((type) => overrides[type.kind] ?? type.enabled).map((type) => type.kind);
}

/** The body that saves every switch: what is off and what is on, so the server keeps both. */
export function pushPreferencesPatch(types: readonly PushType[], overrides: Readonly<Record<string, boolean>>): { push_disabled: string[]; push_enabled: string[] } {
  return { push_disabled: disabledKinds(types, overrides), push_enabled: enabledKinds(types, overrides) };
}

export function pushToggledMessage(type: Pick<PushType, 'label'>, enabled: boolean): string {
  return enabled ? `Push activada: ${type.label}.` : `Push apagada: ${type.label}.`;
}

// ---------------------------------------------------------------- Lo que el equipo sabe de ti · Acerca de

/** «3 datos confirmados», or what the page holds while the count is unknown. */
export function factsLabel(count: number | null | undefined): string {
  return typeof count === 'number' ? `${count} ${count === 1 ? 'dato confirmado' : 'datos confirmados'}` : 'Los datos que confirmaste y su visibilidad';
}

export const ART_CREDIT = 'Arte: LimeZu — Modern Interiors';
export const ART_CREDIT_URL = 'https://limezu.itch.io/moderninteriors';
