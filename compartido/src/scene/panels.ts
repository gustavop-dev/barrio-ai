import type { Activity } from '../api/types';
import type { SceneStatus } from './activity';
import { roleActivity } from './activity';
import type { EngineSnapshot } from './model';
import { CHARACTER_BY_ID, LIBRARIAN_ID, type CharacterId } from './roles';
export interface PanelData {
  statusOf: (id: CharacterId) => SceneStatus;
  activity: Activity | undefined;
  snapshot: EngineSnapshot;
  /** Wall clock, for «hace X». */
  now: number;
}

/** What a character is doing: the event it is playing, else the backend's detail, else its mission. */
export function detailOf(id: CharacterId, data: PanelData): string {
  const doing = data.snapshot.doing[id];
  if (doing) return doing;
  const status = data.statusOf(id);
  if (status === 'desconocido') return 'Sin datos de actividad';
  const detail = roleActivity(data.activity, id)?.detail?.trim();
  if (detail) return detail;
  if (id === LIBRARIAN_ID) return status === 'trabajando' ? 'Busca un libro' : 'Esperando la próxima consulta';
  return CHARACTER_BY_ID[id].purpose;
}

export const SERVICE_NOTE: Partial<Record<CharacterId, string>> = {
  operador_cuenta: 'Es un servicio de software, no un agente de IA. Solo ejecuta lo que el equipo ya decidió.',
  [LIBRARIAN_ID]: 'Es un servicio de software, no un agente de IA: la búsqueda en la base de conocimiento. Cada visita a la biblioteca es una consulta real de un agente.',
};

