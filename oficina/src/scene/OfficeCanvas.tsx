import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type MouseEvent } from 'react';
import { loadAtlas, type AtlasImage } from './atlas';
import type { OfficeEngine } from './engine';
import { PLAN_HEIGHT, PLAN_WIDTH, zoneAt } from './plan';
import { drawScene, readPalette, type Palette } from './render';
import type { CharacterId, ZoneId } from './roles';
import { useDevicePixels } from './useMediaQuery';

export type ScenePick = { kind: 'role'; id: CharacterId } | { kind: 'zone'; id: ZoneId };

export interface OfficeCanvasProps {
  engine: OfficeEngine;
  /** CSS pixels per logical pixel (integer). */
  scale: number;
  selectedRole: CharacterId | null;
  selectedZone: ZoneId | null;
  /** A tap on a character or a zone. */
  onPick: (pick: ScenePick) => void;
}

/**
 * The office canvas: integer scale, `image-rendering: pixelated`, a backing store in whole device pixels.
 * It steps the engine every animation frame unless the scene is still (reduced motion) or halted
 * (machine paused, activity unknown); then it only repaints when something changes.
 */
export function OfficeCanvas({ engine, scale, selectedRole, selectedZone, onPick }: OfficeCanvasProps) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [atlas, setAtlas] = useState<AtlasImage | null>(null);
  const [failed, setFailed] = useState(false);
  const devicePixels = useDevicePixels();
  const snapshot = useSyncExternalStore(engine.subscribe, engine.getSnapshot, engine.getSnapshot);
  const palette = useRef<Palette | null>(null);
  const view = useRef({ scale, devicePixels, selectedRole, selectedZone, atlas });
  useEffect(() => {
    view.current = { scale, devicePixels, selectedRole, selectedZone, atlas };
  });

  useEffect(() => {
    let alive = true;
    loadAtlas()
      .then((image) => {
        if (alive) setAtlas(image);
      })
      .catch(() => {
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
    };
  }, []);

  const draw = useCallback(() => {
    const context = canvas.current?.getContext('2d');
    if (!context) return;
    const current = view.current;
    palette.current ??= readPalette();
    drawScene(context, current.atlas, engine, {
      scale: current.scale * current.devicePixels,
      selectedRole: current.selectedRole,
      selectedZone: current.selectedZone,
      palette: palette.current,
    });
  }, [engine]);

  const animated = !snapshot.still && !snapshot.halted;

  // Running: step and paint every frame (the clock only advances while the tab is visible).
  useEffect(() => {
    if (!animated || typeof requestAnimationFrame !== 'function') return;
    let frame = 0;
    let last: number | null = null;
    const loop = (time: number) => {
      if (last !== null) engine.step(Math.min(60, Math.max(0, time - last)));
      last = time;
      draw();
      frame = requestAnimationFrame(loop);
    };
    frame = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(frame);
  }, [animated, engine, draw]);

  // Still or halted: repaint when something visible changes.
  useEffect(() => {
    if (!animated) draw();
  }, [animated, draw, snapshot, atlas, scale, devicePixels, selectedRole, selectedZone]);

  const pickAt = (event: MouseEvent<HTMLCanvasElement>): ScenePick | null => {
    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width || !rect.height) return null;
    const x = ((event.clientX - rect.left) / rect.width) * PLAN_WIDTH;
    const y = ((event.clientY - rect.top) / rect.height) * PLAN_HEIGHT;
    const role = engine.hit(x, y);
    if (role) return { kind: 'role', id: role };
    const zone = zoneAt(x, y);
    return zone ? { kind: 'zone', id: zone } : null;
  };

  return (
    <>
      <canvas
        ref={canvas}
        className="of-canvas"
        width={PLAN_WIDTH * scale * devicePixels}
        height={PLAN_HEIGHT * scale * devicePixels}
        style={{ width: PLAN_WIDTH * scale, height: PLAN_HEIGHT * scale }}
        role="img"
        aria-label="La oficina en pixel art. Toca a un personaje para ver su rol o una zona para ver su equipo. Lo mismo está en la tira de equipos, debajo."
        onClick={(event) => {
          const pick = pickAt(event);
          if (pick) onPick(pick);
        }}
        onMouseMove={(event) => {
          event.currentTarget.style.cursor = pickAt(event) ? 'pointer' : 'default';
        }}
      />
      {failed ? (
        <p className="of-canvas-error" role="alert">
          No se pudo cargar el dibujo de la oficina. Recarga la página.
        </p>
      ) : null}
    </>
  );
}
