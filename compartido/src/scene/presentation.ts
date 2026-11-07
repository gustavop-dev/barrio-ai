import type { Activity } from '../api/types';
import { roleActivity, type SceneStatus } from './activity';
import type { NowEntry } from './model';
import { LIBRARIAN_ID, ROLES, type CharacterId, type RoleId } from './roles';
const NOW_FRESH_MS = 3 * 60_000;
export interface NowLine {
  text: string;
  role: CharacterId;
}

/**
 * The floating line on top of the scene: the last real event while it is fresh; otherwise who is working
 * right now, from the activity. Hidden while the activity is unavailable.
 */
export function nowLine(input: {
  loading: boolean;
  unavailable: boolean;
  paused: boolean;
  entry: NowEntry | null;
  statuses: Record<RoleId, SceneStatus>;
  activity: Activity | undefined;
  now: number;
}): NowLine | null {
  if (input.unavailable) return null;
  if (input.loading) return { text: 'Abriendo la oficina…', role: LIBRARIAN_ID };
  if (input.paused) return { text: 'La máquina está en pausa. Nadie toca tu LinkedIn.', role: 'operador_cuenta' };
  const entry = input.entry;
  if (entry && input.now - entry.at < NOW_FRESH_MS) return { text: entry.text, role: entry.role ?? LIBRARIAN_ID };
  const working = ROLES.filter((r) => input.statuses[r.id] === 'trabajando')
    .map((r) => ({ role: r, info: roleActivity(input.activity, r.id) }))
    .sort((a, b) => (Date.parse(b.info?.since ?? '') || 0) - (Date.parse(a.info?.since ?? '') || 0));
  const first = working[0];
  if (first) {
    const detail = first.info?.detail?.trim();
    return { text: detail ? `${first.role.short}: ${detail}` : `${first.role.short} trabaja en su puesto`, role: first.role.id };
  }
  return { text: 'Nadie camina: el equipo está en espera.', role: LIBRARIAN_ID };
}

