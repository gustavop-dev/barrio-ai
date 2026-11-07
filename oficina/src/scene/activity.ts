// From GET /api/v1/oficina/actividad to what each character shows. Nothing is invented: a role the
// endpoint does not describe (or describes with an unknown status) is «sin datos» and stays still.

import type { Tone } from '../components/ui';
import type { Activity, RoleActivity, RoleStatus } from '../api/types';
import { ROLES, type CharacterId, type RoleId } from './roles';

/** `desconocido` when the activity endpoint has not answered for this role. */
export type SceneStatus = RoleStatus | 'desconocido';
export type StatusMap = Partial<Record<CharacterId, SceneStatus>>;

export const STATUS_LABEL: Record<SceneStatus, string> = {
  trabajando: 'Trabajando',
  en_espera: 'En espera',
  diseno: 'En diseño',
  desconocido: 'Sin datos',
};

/** DISENO-VISTAS «Estado de un rol en la escena». */
export const STATUS_TONE: Record<SceneStatus, Tone> = {
  trabajando: 'ok',
  en_espera: 'info',
  diseno: 'muted',
  desconocido: 'warn',
};

const KNOWN: ReadonlySet<string> = new Set<RoleStatus>(['trabajando', 'en_espera', 'diseno']);

/** Status of each of the 16 roles. Loading, errors and unknown values all read «desconocido». */
export function statusesFrom(activity: Activity | null | undefined): Record<RoleId, SceneStatus> {
  const map = {} as Record<RoleId, SceneStatus>;
  for (const role of ROLES) {
    const status = activity?.roles?.[role.id]?.status;
    map[role.id] = typeof status === 'string' && KNOWN.has(status) ? status : 'desconocido';
  }
  return map;
}

export function roleActivity(activity: Activity | null | undefined, id: CharacterId): RoleActivity | null {
  const info = activity?.roles?.[id];
  return info && typeof info === 'object' ? info : null;
}

export interface StatusSummary {
  trabajando: number;
  en_espera: number;
  diseno: number;
  desconocido: number;
}

export function summarize(ids: readonly CharacterId[], statuses: StatusMap): StatusSummary {
  const summary: StatusSummary = { trabajando: 0, en_espera: 0, diseno: 0, desconocido: 0 };
  for (const id of ids) summary[statuses[id] ?? 'desconocido'] += 1;
  return summary;
}

/** «2 trabajando · 1 en espera · 0 en diseño · 1 sin datos»; «sin datos» only when there are any. */
export function summaryText(summary: StatusSummary): string {
  const parts = [`${summary.trabajando} trabajando`, `${summary.en_espera} en espera`, `${summary.diseno} en diseño`];
  if (summary.desconocido) parts.push(`${summary.desconocido} sin datos`);
  return parts.join(' · ');
}

/**
 * What the scene does with a status:
 * - trabajando: at the seat, reading animation, monitor and light in 0ff1ce;
 * - en_espera: idle animation; the only status allowed to go for a coffee or chat;
 * - diseno: faded, still, with «EN DISEÑO»;
 * - desconocido: still, without light.
 */
export interface StatusLook {
  animated: boolean;
  lit: boolean;
  dimmed: boolean;
  idleWalks: boolean;
}

export function lookFor(status: SceneStatus): StatusLook {
  switch (status) {
    case 'trabajando':
      return { animated: true, lit: true, dimmed: false, idleWalks: false };
    case 'en_espera':
      return { animated: true, lit: false, dimmed: false, idleWalks: true };
    case 'diseno':
      return { animated: false, lit: false, dimmed: true, idleWalks: false };
    default:
      return { animated: false, lit: false, dimmed: false, idleWalks: false };
  }
}
