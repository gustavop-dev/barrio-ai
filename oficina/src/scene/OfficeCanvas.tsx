import { useCallback, useEffect, useRef, useState, type MouseEvent } from 'react';
import { drawScene, SCENE_HEIGHT, SCENE_SCALE, SCENE_WIDTH } from './render';
import { TEAMS, type RoleId, type TeamId } from './roles';
import { actorAt, actorsAt, type Actor, type StatusMap } from './simulation';
import { loadSprites, type SpriteMap } from './sprites';

export interface OfficeCanvasProps {
  statuses: StatusMap;
  selectedTeam: TeamId | null;
  selectedRole: RoleId | null;
  moving: boolean;
  evening: boolean;
  onSelectTeam: (team: TeamId) => void;
  onSelectRole: (role: RoleId) => void;
}

function teamAt(x: number, y: number): TeamId | null {
  for (const team of TEAMS) {
    const [bx, by, bw, bh] = team.box;
    if (x >= bx && x <= bx + bw && y >= by && y <= by + bh) return team.id;
  }
  return null;
}

export function OfficeCanvas(props: OfficeCanvasProps) {
  const { moving, selectedTeam, onSelectTeam, onSelectRole } = props;
  const canvas = useRef<HTMLCanvasElement>(null);
  const [sprites, setSprites] = useState<SpriteMap | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const latest = useRef(props);
  const elapsed = useRef(0);
  const lastFrame = useRef<number | null>(null);
  const actors = useRef<Actor[]>([]);

  useEffect(() => {
    latest.current = props;
  });

  useEffect(() => {
    let alive = true;
    loadSprites()
      .then((loaded) => alive && setSprites(loaded))
      .catch((error: unknown) => alive && setFailed(error instanceof Error ? error.message : 'No se pudo cargar la oficina'));
    return () => {
      alive = false;
    };
  }, []);

  const draw = useCallback(() => {
    const context = canvas.current?.getContext('2d');
    if (!context) return;
    const current = latest.current;
    actors.current = actorsAt(elapsed.current, current.statuses);
    drawScene(context, sprites, {
      actors: actors.current,
      statuses: current.statuses,
      selectedTeam: current.selectedTeam,
      selectedRole: current.selectedRole,
      evening: current.evening,
      elapsed: elapsed.current,
      moving: current.moving,
    });
  }, [sprites]);

  // The ambient clock only advances while motion is on; pausing freezes strolls too.
  useEffect(() => {
    if (!moving) {
      lastFrame.current = null;
      return;
    }
    let frame = 0;
    const loop = (time: number) => {
      if (lastFrame.current !== null) elapsed.current += Math.min(100, Math.max(0, time - lastFrame.current));
      lastFrame.current = time;
      draw();
      frame = requestAnimationFrame(loop);
    };
    frame = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(frame);
      lastFrame.current = null;
    };
  }, [moving, draw]);

  // Without motion, repaint whenever something visible changes.
  useEffect(() => {
    if (!moving) draw();
  }, [moving, draw, props.statuses, props.selectedTeam, props.selectedRole, props.evening]);

  const toLogical = (event: MouseEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width || !rect.height) return null;
    return {
      x: ((event.clientX - rect.left) / rect.width) * SCENE_WIDTH,
      y: ((event.clientY - rect.top) / rect.height) * SCENE_HEIGHT,
    };
  };

  const onClick = (event: MouseEvent<HTMLCanvasElement>) => {
    const point = toLogical(event);
    if (!point) return;
    const actor = actorAt(actors.current, point.x, point.y);
    if (actor) return onSelectRole(actor.role);
    const team = teamAt(point.x, point.y);
    if (team) onSelectTeam(team);
  };

  const onMove = (event: MouseEvent<HTMLCanvasElement>) => {
    const point = toLogical(event);
    const hit = point && (actorAt(actors.current, point.x, point.y) || teamAt(point.x, point.y));
    event.currentTarget.style.cursor = hit ? 'pointer' : 'default';
  };

  return (
    <div className="mapwrap">
      {!sprites && !failed ? (
        <div className="maploading" role="status">
          Abriendo el apartamento…
        </div>
      ) : null}
      {failed ? (
        <div className="maploading" role="alert">
          {failed}. Recarga la página.
        </div>
      ) : null}
      <canvas
        ref={canvas}
        width={SCENE_WIDTH * SCENE_SCALE}
        height={SCENE_HEIGHT * SCENE_SCALE}
        role="img"
        aria-label="Apartamento pixel art con los equipos de Barrio AI. Usa los botones de equipo o la lista del panel para ver a cada integrante."
        onClick={onClick}
        onMouseMove={onMove}
      />
      <div className="hotspots">
        {TEAMS.map((team) => (
          <button
            key={team.id}
            type="button"
            className={team.id === selectedTeam ? 'hotspot selected' : 'hotspot'}
            style={{ left: `${(team.label[0] / SCENE_WIDTH) * 100}%`, top: `${(team.label[1] / SCENE_HEIGHT) * 100}%` }}
            onClick={() => onSelectTeam(team.id)}
            aria-pressed={team.id === selectedTeam}
            tabIndex={-1}
          >
            <span aria-hidden="true">{team.icon}</span> {team.name.toUpperCase()}
          </button>
        ))}
      </div>
    </div>
  );
}
