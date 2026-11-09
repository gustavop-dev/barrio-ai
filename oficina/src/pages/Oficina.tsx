// Oficina (home, `/`): the pixel-art office where the 16 agents and the librarian move only when the
// backend records something. Rev 18: nothing above the scene; the scene goes full width under the top
// bar with the zone labels and the floating «now» line; below it the legend and the team strip.
// Tapping a character or a zone opens its panel in a half-height sheet (phone) or the side panel (desktop).

import { nowLine } from '../../../compartido/src/scene/presentation';
import { Link } from 'react-router-dom';
export { nowLine, type NowLine } from '../../../compartido/src/scene/presentation';
import { useCallback, useEffect, useId, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { useOficinaEventos } from '../api/oficina';
import { useActivity, useOverview } from '../api/hooks';
import { AgentPortrait, Button, ChipStrip, FilterChip, Note, Page } from '../components/ui';
import { timeAgo } from '../lib/format';
import { statusesFrom, type SceneStatus } from '../scene/activity';
import { BottomSheet } from '../scene/BottomSheet';
import { OfficeEngine } from '../scene/engine';
import { OfficeCanvas, type ScenePick } from '../scene/OfficeCanvas';
import { RolePanel, TeamPanel, type PanelData } from '../scene/OfficePanels';
import { PLAN_HEIGHT, PLAN_WIDTH, ZONE_LABELS, sceneScale } from '../scene/plan';
import { CHARACTER_BY_ID, LIBRARIAN_ID, ROLES, TEAMS, type CharacterId, type TeamId, type ZoneId } from '../scene/roles';
import { OFICINA_WIDE, REDUCED_MOTION, useMediaQuery, useViewport } from '../scene/useMediaQuery';
import '../scene/oficina.css';

type Selection = { kind: 'team'; id: TeamId } | { kind: 'role'; id: CharacterId };

/** Room above the scene and below it (top bar, bottom bar) when choosing the scale. */
const CHROME_HEIGHT = 120;

function useNow(every: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), every);
    return () => window.clearInterval(id);
  }, [every]);
  return now;
}

/** Width of an element, kept up to date (ResizeObserver; the viewport where it is missing). */
function useWidth(viewportWidth: number) {
  const [width, setWidth] = useState<number | null>(null);
  const observer = useRef<ResizeObserver | null>(null);
  const ref = useCallback((node: HTMLElement | null) => {
    observer.current?.disconnect();
    observer.current = null;
    if (!node || typeof ResizeObserver !== 'function') return;
    observer.current = new ResizeObserver((entries) => setWidth(entries[0]?.contentRect.width ?? null));
    observer.current.observe(node);
  }, []);
  return [ref, width ?? viewportWidth] as const;
}

/** Logical y to keep visible for a selection: the character's body or the zone's middle. */
function revealY(selection: Selection, engine: OfficeEngine): number {
  if (selection.kind === 'role') return engine.byId[selection.id].y - 14;
  const box = TEAMS.find((t) => t.id === selection.id)?.box;
  return box ? box[1] + box[3] / 2 : 0;
}

export function Oficina() {
  const activity = useActivity();
  const overview = useOverview();
  const reduced = useMediaQuery(REDUCED_MOTION);
  const wide = useMediaQuery(OFICINA_WIDE);
  const viewport = useViewport();
  const now = useNow(15_000);
  const headingId = useId();

  const [engine] = useState(
    () => new OfficeEngine({ still: typeof window.matchMedia === 'function' && window.matchMedia(REDUCED_MOTION).matches, frozen: true }),
  );
  const snapshot = useSyncExternalStore(engine.subscribe, engine.getSnapshot, engine.getSnapshot);

  const loading = activity.isPending;
  const unavailable = activity.isError;
  const live = Boolean(activity.data) && !unavailable;
  const statuses = useMemo(() => statusesFrom(live ? activity.data : null), [live, activity.data]);
  const paused = Boolean(overview.data?.control?.paused);

  useEffect(() => engine.setStatuses(statuses), [engine, statuses]);
  useEffect(() => engine.setFrozen(!live), [engine, live]);
  useEffect(() => engine.setPaused(paused), [engine, paused]);
  useEffect(() => engine.setStill(reduced), [engine, reduced]);
  useOficinaEventos(useCallback((page) => engine.ingest(page.events, page.now), [engine]));

  const [stageRef, stageWidth] = useWidth(viewport.width);
  const scale = sceneScale(stageWidth, viewport.height - CHROME_HEIGHT);

  // ---------------------------------------------------------------- selection
  const [selection, setSelection] = useState<Selection | null>(null);
  // On desktop the side panel always shows something: Operación by default.
  const shown: Selection | null = selection ?? (wide ? { kind: 'team', id: 'operacion' } : null);
  const selectedRole = shown?.kind === 'role' ? shown.id : null;
  const selectedZone: ZoneId | null = shown ? (shown.kind === 'team' ? shown.id : CHARACTER_BY_ID[shown.id].team) : null;
  const sheetOpen = !wide && selection !== null;

  const sheetRef = useRef<HTMLElement | null>(null);
  const stageEl = useRef<HTMLDivElement | null>(null);
  const reveal = useRef(false);
  const select = useCallback((next: Selection) => {
    reveal.current = true;
    setSelection(next);
  }, []);
  const onPick = useCallback(
    (pick: ScenePick) => {
      if (pick.kind === 'role') select({ kind: 'role', id: pick.id });
      else select(pick.id === 'biblioteca' ? { kind: 'role', id: LIBRARIAN_ID } : { kind: 'team', id: pick.id });
    },
    [select],
  );

  // The sheet never hides what was chosen: if the character or zone ends up under the sheet (or under the
  // top bar), scroll the page so it sits in the visible band above the sheet. The scene itself never moves.
  useEffect(() => {
    if (!reveal.current) return;
    reveal.current = false;
    const sheet = sheetRef.current;
    const stage = stageEl.current;
    if (!selection || !sheet || !stage || typeof window.scrollBy !== 'function') return;
    const y = revealY(selection, engine);
    const point = stage.getBoundingClientRect().top + y * scale;
    const top = document.querySelector('.shell-head')?.getBoundingClientRect().bottom ?? 0;
    const bottom = sheet.getBoundingClientRect().top;
    const margin = 32;
    if (point < top + margin || point > bottom - margin) window.scrollBy({ top: point - (top + bottom) / 2, behavior: reduced ? 'auto' : 'smooth' });
  }, [selection, engine, scale, reduced]);

  const statusOf = useCallback((id: CharacterId): SceneStatus => (id === LIBRARIAN_ID ? engine.statusOf(id) : statuses[id]), [engine, statuses]);
  const panelData: PanelData = { statusOf, activity: live ? activity.data : undefined, snapshot, now };

  const panel = shown ? (
    shown.kind === 'team' ? (
      <TeamPanel team={shown.id} data={panelData} onRole={(id) => select({ kind: 'role', id })} headingId={headingId} />
    ) : (
      <RolePanel id={shown.id} data={panelData} onTeam={(id) => select({ kind: 'team', id })} headingId={headingId} />
    )
  ) : null;

  // ---------------------------------------------------------------- scene geometry
  const line = nowLine({ loading, unavailable, paused, entry: snapshot.now, statuses, activity: activity.data, now });
  const designTags = live ? ROLES.filter((r) => statuses[r.id] === 'diseno') : [];

  const activityLine = activity.data && !unavailable ? `Actividad real · ${timeAgo(activity.data.updated_at, now)}` : loading ? 'Leyendo actividad…' : 'Actividad no disponible';

  return (
    <div className={sheetOpen ? 'of-root has-sheet' : 'of-root'}>
      <Page title="Oficina" hideTitle width="full">
        <div className="of-layout">
          <div className="of-main">
            <div className="of-stage-wrap" ref={stageRef}>
              <div className="of-stage" ref={stageEl} style={{ width: PLAN_WIDTH * scale, height: PLAN_HEIGHT * scale }}>
                <OfficeCanvas engine={engine} scale={scale} selectedRole={selectedRole} selectedZone={selectedZone} onPick={onPick} />
                {ZONE_LABELS.map((label) => (
                  <span key={label.zone} className="of-zone-label" aria-hidden="true" style={{ left: label.at[0] * scale, top: label.at[1] * scale }}>
                    {label.text}
                  </span>
                ))}
                {designTags.map((role) => (
                  <span
                    key={role.id}
                    className="of-design-tag"
                    aria-hidden="true"
                    style={{ left: Math.max(4, Math.min(role.home[0] * scale - 45, PLAN_WIDTH * scale - 98)), top: (role.home[1] - 7) * scale }}
                  >
                    EN DISEÑO
                  </span>
                ))}
                {paused ? <div className="of-paused" data-testid="oficina-pausa" aria-hidden="true" /> : null}
                {line ? (
                  <div className="of-now">
                    <AgentPortrait role={line.role} size="md" />
                    <p aria-live="polite">{line.text}</p>
                  </div>
                ) : null}
              </div>
            </div>

            <div className="of-below">
              <Link to="/equipo">Mapa del equipo</Link>
              <div className="of-legend">
                <span>
                  <i className="of-dot trabajando" aria-hidden="true" />
                  Trabajando
                </span>
                <span>
                  <i className="of-dot en_espera" aria-hidden="true" />
                  En espera
                </span>
                <span>
                  <i className="of-dot diseno" aria-hidden="true" />
                  En diseño
                </span>
                <span className="of-activity">{activityLine}</span>
              </div>

              {unavailable ? (
                <Note
                  tone="error"
                  title="No se pudo leer la actividad."
                  actions={
                    <Button variant="secondary" size="small" onClick={() => void activity.refetch()}>
                      Reintentar
                    </Button>
                  }
                >
                  <p>Mientras tanto los personajes quedan quietos: la oficina no simula trabajo.</p>
                </Note>
              ) : null}

              <ChipStrip label="Equipos" scroll={!wide} className="of-teams">
                {TEAMS.map((team) => (
                  <FilterChip key={team.id} pressed={shown?.kind === 'team' && shown.id === team.id} onClick={() => select({ kind: 'team', id: team.id })}>
                    {team.name}
                  </FilterChip>
                ))}
                <FilterChip pressed={selectedRole === LIBRARIAN_ID} onClick={() => select({ kind: 'role', id: LIBRARIAN_ID })}>
                  Biblioteca
                </FilterChip>
              </ChipStrip>

              <p className="of-credit mobile-only">Arte: LimeZu — Modern Interiors</p>
            </div>
          </div>

          {wide && panel ? (
            <aside className="of-side" aria-labelledby={headingId}>
              {panel}
            </aside>
          ) : null}
        </div>
      </Page>

      {sheetOpen && panel ? (
        <BottomSheet labelledBy={headingId} onClose={() => setSelection(null)} sheetRef={sheetRef}>
          {panel}
        </BottomSheet>
      ) : null}
    </div>
  );
}
