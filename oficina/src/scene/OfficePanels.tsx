// The team and role panels of the Oficina (DISENO-VISTAS «1. Oficina», F and G), shown in the bottom
// sheet on the phone and in the 340 px side panel on desktop.

import { Link } from 'react-router-dom';
import type { Activity } from '../api/types';
import { AgentPortrait, Badge, Button, Note } from '../components/ui';
import { timeAgo } from '../lib/format';
import { STATUS_LABEL, STATUS_TONE, roleActivity, summarize, summaryText, type SceneStatus } from './activity';
import type { EngineSnapshot } from './engine';
import { CHARACTER_BY_ID, LIBRARIAN_ID, rolesOfTeam, teamById, zoneName, type CharacterId, type TeamId } from './roles';

export interface PanelData {
  statusOf: (id: CharacterId) => SceneStatus;
  activity: Activity | undefined;
  snapshot: EngineSnapshot;
  /** Wall clock, for «hace X». */
  now: number;
}

export function StatusBadge({ status }: { status: SceneStatus }) {
  return <Badge tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Badge>;
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

const SERVICE_NOTE: Partial<Record<CharacterId, string>> = {
  operador_cuenta: 'Es un servicio de software, no un agente de IA. Solo ejecuta lo que el equipo ya decidió.',
  [LIBRARIAN_ID]: 'Es un servicio de software, no un agente de IA: la búsqueda en la base de conocimiento. Cada visita a la biblioteca es una consulta real de un agente.',
};

export function TeamPanel({ team: teamId, data, onRole, headingId }: { team: TeamId; data: PanelData; onRole: (id: CharacterId) => void; headingId: string }) {
  const team = teamById(teamId);
  const members = rolesOfTeam(teamId);
  const counts = summarize(
    members.map((m) => m.id),
    Object.fromEntries(members.map((m) => [m.id, data.statusOf(m.id)])),
  );
  return (
    <div className="of-panel">
      <div className="of-panel-top t-etiqueta text-suave">
        <span>ESPACIO DEL EQUIPO</span>
        <span className="of-panel-number">{team.number}</span>
        {team.isNew ? <Badge tone="warn">Nuevo</Badge> : null}
      </div>
      <h2 id={headingId} className="t-subtitulo">
        {team.name}
      </h2>
      <p className="t-cuerpo text-suave">{team.purpose}</p>
      <p className="t-etiqueta text-suave">
        {members.length} {members.length === 1 ? 'INTEGRANTE' : 'INTEGRANTES'} · {team.place.toUpperCase()}
      </p>
      <p className="t-detalle">{summaryText(counts)}</p>
      <ul className="of-members">
        {members.map((member) => (
          <li key={member.id}>
            <button type="button" className="of-member" onClick={() => onRole(member.id)}>
              <AgentPortrait role={member.id} size="md" />
              <span className="of-member-text">
                <span className="of-member-name">{member.name}</span>
                <span className="of-member-detail">{detailOf(member.id, data)}</span>
              </span>
              <StatusBadge status={data.statusOf(member.id)} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function RolePanel({ id, data, onTeam, headingId }: { id: CharacterId; data: PanelData; onTeam: (team: TeamId) => void; headingId: string }) {
  const role = CHARACTER_BY_ID[id];
  const librarian = id === LIBRARIAN_ID;
  const status = data.statusOf(id);
  const info = roleActivity(data.activity, id);
  const recent = data.snapshot.feed.filter((entry) => entry.role === id).slice(0, 3);
  const zone = zoneName(role.team);
  const since = status !== 'desconocido' && !data.snapshot.doing[id] && info?.since ? `En este estado desde ${timeAgo(info.since, data.now)}` : '';
  const team: TeamId = librarian ? 'observatorio' : (role.team as TeamId);
  return (
    <div className="of-panel">
      <div className="of-role-head">
        <AgentPortrait role={id} size="lg" />
        <div className="of-role-title">
          <p className="t-etiqueta text-suave">
            {role.service ? 'SERVICIO' : 'AGENTE'} · {zone.toUpperCase()}
          </p>
          <h2 id={headingId} className="t-subtitulo">
            {role.name}
          </h2>
          <StatusBadge status={status} />
        </div>
      </div>
      {SERVICE_NOTE[id] ? (
        <Note tone="info" role={null}>
          {SERVICE_NOTE[id]}
        </Note>
      ) : null}
      <section className="of-panel-block" aria-labelledby={`${headingId}-mision`}>
        <h3 id={`${headingId}-mision`} className="t-etiqueta text-suave">
          MISIÓN
        </h3>
        <p className="t-cuerpo">{role.purpose}</p>
      </section>
      <section className="of-panel-block" aria-labelledby={`${headingId}-estado`}>
        <h3 id={`${headingId}-estado`} className="t-etiqueta text-suave">
          ESTADO REAL
        </h3>
        <p className="t-cuerpo">{status === 'desconocido' ? 'Sin datos de actividad.' : `${STATUS_LABEL[status]} · ${detailOf(id, data)}`}</p>
        {since ? <p className="t-detalle text-suave">{since}</p> : null}
      </section>
      {status === 'diseno' ? <p className="of-design-note">Este rol está en diseño. Aparece en la oficina, pero todavía no trabaja.</p> : null}
      <section className="of-panel-block" aria-labelledby={`${headingId}-ultimo`}>
        <h3 id={`${headingId}-ultimo`} className="t-etiqueta text-suave">
          LO ÚLTIMO QUE HIZO
        </h3>
        {recent.length ? (
          <ul className="of-recent">
            {recent.map((entry) => (
              <li key={entry.key}>
                <span className="of-recent-text">{entry.text}</span>
                <span className="t-detalle text-suave">{timeAgo(new Date(entry.at).toISOString(), data.now)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="t-detalle text-suave">Nada todavía en esta sesión.</p>
        )}
        {librarian ? null : (
          <Link to="/calendario" className="of-panel-link">
            Ver en el Calendario
          </Link>
        )}
      </section>
      <Button variant="secondary" block onClick={() => onTeam(team)}>
        {librarian ? 'Ver quién la usa · Observatorio' : `Ver su equipo · ${zone}`}
      </Button>
    </div>
  );
}
