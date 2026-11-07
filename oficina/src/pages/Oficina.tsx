import { useEffect, useMemo, useState } from 'react';
import { useActivity } from '../api/hooks';
import type { Activity } from '../api/types';
import { Badge, ErrorNote, type Tone } from '../components/ui';
import { timeAgo } from '../lib/format';
import { OfficeCanvas } from '../scene/OfficeCanvas';
import { ROLE_BY_ID, TEAMS, rolesOfTeam, teamById, type RoleId, type TeamId } from '../scene/roles';
import { STATUS_LABEL, statusesFrom, summarize, type SceneStatus, type StatusMap } from '../scene/simulation';
import { portraitUrl } from '../scene/sprites';

type Selection = { kind: 'team'; id: TeamId } | { kind: 'role'; id: RoleId };

const STATUS_TONE: Record<SceneStatus, Tone> = {
  trabajando: 'ok',
  en_espera: 'info',
  diseno: 'muted',
  desconocido: 'warn',
};

export function StatusBadge({ status }: { status: SceneStatus }) {
  return (
    <Badge tone={STATUS_TONE[status]}>
      <span className={`statusdot ${status}`} aria-hidden="true" />
      {STATUS_LABEL[status]}
    </Badge>
  );
}

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function isEvening(date = new Date()): boolean {
  const hour = date.getHours();
  return hour >= 18 || hour < 6;
}

function RolePanel({ id, statuses, activity, onTeam }: { id: RoleId; statuses: StatusMap; activity: Activity | undefined; onTeam: (team: TeamId) => void }) {
  const role = ROLE_BY_ID[id];
  const team = teamById(role.team);
  const status = statuses[id] ?? 'desconocido';
  const info = activity?.roles?.[id];
  return (
    <div className="rolepanel">
      <div className="rolehead">
        <img className="portrait big" src={portraitUrl(role.sprite)} alt="" width={40} height={80} />
        <div>
          <p className="eyebrow">{role.service ? 'SERVICIO' : 'AGENTE'} · {team.name.toUpperCase()}</p>
          <h2>{role.name}</h2>
          <StatusBadge status={status} />
        </div>
      </div>
      {role.service ? <p className="note info">Es un servicio de software, no un agente de IA. No redacta ni decide: ejecuta lo aprobado y lo comprueba.</p> : null}
      <h3>Misión</h3>
      <p>{role.purpose}</p>
      <h3>Estado real</h3>
      {status === 'desconocido' ? (
        <p className="muted">Sin datos de actividad para este rol. No se muestra actividad que no esté confirmada.</p>
      ) : (
        <dl className="facts">
          <dt>Estado</dt>
          <dd>{STATUS_LABEL[status]}</dd>
          {info?.detail ? (
            <>
              <dt>Detalle</dt>
              <dd>{info.detail}</dd>
            </>
          ) : null}
          {info?.since ? (
            <>
              <dt>Desde</dt>
              <dd>{timeAgo(info.since)}</dd>
            </>
          ) : null}
        </dl>
      )}
      {status === 'diseno' ? <p className="muted">Tiene contrato, pero aún no está implementado: aparece atenuado en la oficina.</p> : null}
      <button type="button" className="secondary" onClick={() => onTeam(role.team)}>
        Ver su equipo · {team.name}
      </button>
    </div>
  );
}

function TeamPanel({ id, statuses, activity, onRole }: { id: TeamId; statuses: StatusMap; activity: Activity | undefined; onRole: (role: RoleId) => void }) {
  const team = teamById(id);
  const roles = rolesOfTeam(id);
  const counts = summarize(roles.map((r) => r.id), statuses);
  const number = String(TEAMS.indexOf(team) + 1).padStart(2, '0');
  return (
    <div className="teampanel">
      <div className="paneltop">
        <span className="teamicon" aria-hidden="true">
          {team.icon}
        </span>
        <span className="eyebrow">ESPACIO DEL EQUIPO</span>
        {team.isNew ? <Badge tone="info">Nuevo</Badge> : null}
        <span className="teamnumber">{number}</span>
      </div>
      <h2>{team.name}</h2>
      <p className="muted">{team.purpose}</p>
      <p className="sectionlabel">
        {roles.length} {roles.length === 1 ? 'INTEGRANTE' : 'INTEGRANTES'} · {team.place.toUpperCase()}
      </p>
      <p className="summary">
        {counts.trabajando} trabajando · {counts.en_espera} en espera · {counts.diseno} en diseño
        {counts.desconocido ? ` · ${counts.desconocido} sin datos` : ''}
      </p>
      <ul className="members">
        {roles.map((role) => {
          const status = statuses[role.id] ?? 'desconocido';
          const detail = activity?.roles?.[role.id]?.detail;
          return (
            <li key={role.id}>
              <button type="button" className="member" onClick={() => onRole(role.id)}>
                <img className="portrait" src={portraitUrl(role.sprite)} alt="" width={30} height={60} />
                <span className="membertext">
                  <strong>{role.name}</strong>
                  <small>{detail || role.purpose}</small>
                </span>
                <StatusBadge status={status} />
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function Oficina() {
  const activity = useActivity();
  const statuses = useMemo(() => statusesFrom(activity.data), [activity.data]);
  const [selection, setSelection] = useState<Selection>({ kind: 'team', id: 'operacion' });
  const [moving, setMoving] = useState(() => !prefersReducedMotion());
  const [evening, setEvening] = useState(() => isEvening());

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const onChange = () => setMoving(!query.matches);
    query.addEventListener?.('change', onChange);
    return () => query.removeEventListener?.('change', onChange);
  }, []);

  const selectedTeam = selection.kind === 'team' ? selection.id : ROLE_BY_ID[selection.id].team;
  const selectTeam = (id: TeamId) => setSelection({ kind: 'team', id });
  const selectRole = (id: RoleId) => setSelection({ kind: 'role', id });

  return (
    <div className="office">
      <section className="world" aria-labelledby="office-title">
        <div className="worldbar">
          <h1 id="office-title">
            <b>PLANTA ABIERTA</b> <span className="muted">/ Barrio AI</span>
          </h1>
          <div className="maptools">
            <button type="button" aria-pressed={evening} onClick={() => setEvening((v) => !v)}>
              {evening ? '☾ Tarde en el estudio' : '☀ Luz de mañana'}
            </button>
            <button type="button" aria-pressed={moving} onClick={() => setMoving((v) => !v)}>
              {moving ? 'Pausar ambiente' : 'Activar ambiente'}
            </button>
          </div>
        </div>
        <OfficeCanvas
          statuses={statuses}
          selectedTeam={selectedTeam}
          selectedRole={selection.kind === 'role' ? selection.id : null}
          moving={moving}
          evening={evening}
          onSelectTeam={selectTeam}
          onSelectRole={selectRole}
        />
        <div className="worldfooter">
          <span className="legend">
            <span><i className="statusdot trabajando" /> Trabajando</span>
            <span><i className="statusdot en_espera" /> En espera</span>
            <span><i className="statusdot diseno" /> En diseño</span>
          </span>
          <span className="muted" aria-live="polite">
            {activity.data ? `Actividad real · ${timeAgo(activity.data.updated_at)}` : activity.isPending ? 'Leyendo actividad…' : 'Actividad no disponible'}
          </span>
        </div>
        {activity.isError ? (
          <div className="activityerror">
            <ErrorNote error={activity.error} onRetry={() => void activity.refetch()} />
            <p className="muted">Mientras tanto los personajes quedan quietos: la oficina no simula trabajo.</p>
          </div>
        ) : null}
        <div className="teamstrip" role="group" aria-label="Equipos">
          {TEAMS.map((team) => (
            <button
              key={team.id}
              type="button"
              className={team.id === selectedTeam ? 'teamchip selected' : 'teamchip'}
              aria-pressed={team.id === selectedTeam}
              onClick={() => selectTeam(team.id)}
            >
              <span aria-hidden="true">{team.icon}</span> {team.name}
            </button>
          ))}
        </div>
      </section>
      <aside className="panel" aria-live="polite">
        {selection.kind === 'role' ? (
          <RolePanel id={selection.id} statuses={statuses} activity={activity.data} onTeam={selectTeam} />
        ) : (
          <TeamPanel id={selection.id} statuses={statuses} activity={activity.data} onRole={selectRole} />
        )}
      </aside>
    </div>
  );
}
