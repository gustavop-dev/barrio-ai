// Backwards-compatible JS facade. Native calls the identical functions with serializable state on UI.
import { EventQueue } from './events';
import type { StatusMap } from './activity';
import type { EngineOptions, EngineSnapshot } from './model';
import { SCENE_MOTION } from './motion';
import { createScene, hitScene, ingestScene, receiveSceneCapture, sceneSnapshot, sceneStatus, setSceneStill, stepScene } from './runtime';
import type { CharacterId } from './roles';
export type * from './model';
export const WALK_SPEED = SCENE_MOTION.walkSpeed;
export const MAX_PLAYS = 2;
export const START_GAP = SCENE_MOTION.startGap;
export const AMBIENT_EVERY = SCENE_MOTION.ambientEvery;

export class OfficeEngine {
  readonly state;
  readonly actors;
  readonly byId;
  readonly queue;
  private readonly wall;
  private readonly listeners = new Set<() => void>();
  private cached: EngineSnapshot | null = null;
  private notified = -1;
  constructor(options: EngineOptions = {}) {
    this.state = createScene(options);
    this.actors = this.state.actors;
    this.byId = Object.fromEntries(this.actors.map((a) => [a.id, a])) as Record<CharacterId, (typeof this.actors)[number]>;
    this.queue = new EventQueue({}, this.state.queue);
    this.wall = options.wallClock ?? Date.now;
  }
  get clock() { return this.state.clock; }
  get now() { return this.state.now; }
  get feed() { return this.state.feed; }
  get halted() { return this.state.paused || this.state.frozen; }
  get isStill() { return this.state.still; }
  get isPaused() { return this.state.paused; }
  get activeTasks() { return this.state.tasks.length; }
  setStatuses(statuses: StatusMap) { this.state.statuses = { ...statuses }; this.state.version++; this.flush(); }
  setPaused(paused: boolean) { if (this.state.paused !== paused) { this.state.paused = paused; this.state.version++; this.flush(); } }
  setFrozen(frozen: boolean) { if (this.state.frozen !== frozen) { this.state.frozen = frozen; this.state.version++; this.flush(); } }
  setStill(still: boolean) { this.state.wallTime = this.wall(); setSceneStill(this.state, still); this.flush(); }
  ingest(events: readonly unknown[] | null | undefined, serverNow?: string | null) {
    this.state.wallTime = this.wall();
    const n = ingestScene(this.state, events, serverNow); this.flush(); return n;
  }
  receiveCapture() { this.state.wallTime = this.wall(); receiveSceneCapture(this.state); this.flush(); }
  statusOf(id: CharacterId) { return sceneStatus(this.state, id); }
  hit(x: number, y: number) { return hitScene(this.state, x, y); }
  step(dt: number) { this.state.wallTime = this.wall(); stepScene(this.state, dt); this.flush(); }
  advance(ms: number) { for (let left = ms; left > 0; left -= 16) this.step(Math.min(16, left)); }
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  getSnapshot = (): EngineSnapshot => {
    if (!this.cached || this.cached.version !== this.state.version) this.cached = sceneSnapshot(this.state);
    return this.cached;
  };
  private flush() {
    if (this.notified === this.state.version) return;
    this.notified = this.state.version;
    for (const listener of this.listeners) listener();
  }
}
