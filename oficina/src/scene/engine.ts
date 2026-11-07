// The office's choreography. Characters move only when the backend records something (an event from
// /api/v1/oficina/eventos) or, for roles really «en espera», to fetch a coffee or chat now and then.
// Nothing is simulated. The engine is plain TypeScript so it can be stepped in tests without a canvas.
//
// Each play is a generator that yields "wait until" conditions; `step(dt)` moves the walkers and resumes
// the plays whose condition holds. While the machine is paused (or the activity is unknown) the clock
// stops and everything freezes; events keep queueing and are summarized afterwards.

import { lookFor, type SceneStatus, type StatusMap } from './activity';
import { EventQueue, actorName, describeEvent, describeSummary, summaryActor, type OfficeEvent, type QueueOptions } from './events';
import { LIBRARY_SPOTS, PLACES, planRoute, visitPlaceFor, type PlaceId } from './plan';
import { CHARACTERS, LIBRARIAN_ID, isCharacterId, isRoleId, type CharacterId, type Direction, type Point, type Role, type TeamId } from './roles';

export type BubbleIcon = 'libro' | 'hoja' | 'cafe' | 'listo' | 'pregunta' | 'busca' | 'charla';

export interface Actor {
  id: CharacterId;
  role: Role;
  index: number;
  x: number;
  y: number;
  dir: Direction;
  /** Points still to walk; null while standing. */
  path: Point[] | null;
  /** `via` of the place where it stands; null at home. */
  at: readonly Point[] | null;
  /** Off its seat (chairs are drawn behind it, the monitor turns off). */
  away: boolean;
  reading: boolean;
  alpha: number;
  /** -1 fading out, 1 fading in (Operación at the door). */
  fade: number;
  bubble: { icon: BubbleIcon; until: number } | null;
  busy: boolean;
  /** What it is doing because of an event («Consultando la biblioteca: “clase 03”»). */
  doing: string | null;
}

/** The «now» line: the last thing narrated. */
export interface NowEntry {
  key: number;
  text: string;
  role: CharacterId | null;
  /** Wall-clock ms when it was narrated. */
  at: number;
}

/** One real event in a role's «Lo último que hizo». */
export interface FeedEntry {
  key: string;
  role: CharacterId;
  text: string;
  /** ms of the event's `ts`. */
  at: number;
}

export interface EngineSnapshot {
  version: number;
  now: NowEntry | null;
  /** Newest first. */
  feed: readonly FeedEntry[];
  doing: Partial<Record<CharacterId, string>>;
  librarianBusy: boolean;
  paused: boolean;
  /** Paused or frozen: the clock does not advance. */
  halted: boolean;
  still: boolean;
}

export interface EngineOptions {
  queue?: Partial<QueueOptions>;
  /** Wall clock for the «now» line; Date.now by default. */
  wallClock?: () => number;
  /** Start still (prefers-reduced-motion). */
  still?: boolean;
  /** Start frozen (activity not loaded yet). */
  frozen?: boolean;
}

/** Logical px per second. */
export const WALK_SPEED = 40;
/** Plays that may run at the same time (with different characters). */
export const MAX_PLAYS = 2;
/** ms between the start of two plays, so each narration can be read. */
export const START_GAP = 1800;
const SUMMARY_HOLD = 2600;
const AMBIENT_FIRST = 9000;
export const AMBIENT_EVERY = 20000;
const FEED_LIMIT = 60;

type Cond = () => boolean;
type Script = Generator<Cond, void, undefined>;

interface Task {
  script: Script;
  cond: Cond | null;
  kind: 'play' | 'ambient' | 'librarian';
  done: boolean;
}

interface LibraryJob {
  visitor: Actor;
  done: boolean;
}

const quoted = (detail: string | null | undefined) => (detail && detail.trim() ? `: “${detail.trim()}”` : '');

export class OfficeEngine {
  readonly actors: Actor[];
  readonly byId: Record<CharacterId, Actor>;
  readonly queue: EventQueue;
  /** Scene clock in ms; stops while halted. */
  clock = 0;
  now: NowEntry | null = null;
  feed: FeedEntry[] = [];

  private statuses: StatusMap = {};
  private paused = false;
  private frozen = false;
  private still = false;
  private tasks: Task[] = [];
  private libraryJobs: LibraryJob[] = [];
  private occupied = new Map<PlaceId, CharacterId>();
  private nextStart = 0;
  private nextAmbient = AMBIENT_FIRST;
  private ambientTurn = 0;
  private nowKey = 0;
  private version = 0;
  private dirty = false;
  private cached: EngineSnapshot | null = null;
  private readonly listeners = new Set<() => void>();
  private readonly wall: () => number;

  constructor(options: EngineOptions = {}) {
    this.queue = new EventQueue(options.queue);
    this.wall = options.wallClock ?? (() => Date.now());
    this.still = options.still ?? false;
    this.frozen = options.frozen ?? false;
    this.actors = CHARACTERS.map((role, index) => ({
      id: role.id,
      role,
      index,
      x: role.home[0],
      y: role.home[1],
      dir: role.facing,
      path: null,
      at: null,
      away: false,
      reading: false,
      alpha: 1,
      fade: 0,
      bubble: null,
      busy: false,
      doing: null,
    }));
    this.byId = Object.fromEntries(this.actors.map((a) => [a.id, a])) as Record<CharacterId, Actor>;
  }

  // ------------------------------------------------------------ inputs

  /** Real statuses from /oficina/actividad. The librarian's comes from its visits. */
  setStatuses(statuses: StatusMap) {
    this.statuses = { ...statuses };
    this.touch();
    this.flush();
  }

  /** Machine paused (overview.control.paused): everything freezes and the scene darkens. */
  setPaused(paused: boolean) {
    if (this.paused === paused) return;
    this.paused = paused;
    this.touch();
    this.flush();
  }

  /** Activity loading or unavailable: the characters stay still, nothing plays. */
  setFrozen(frozen: boolean) {
    if (this.frozen === frozen) return;
    this.frozen = frozen;
    this.touch();
    this.flush();
  }

  /** prefers-reduced-motion: nobody walks; events are only narrated. */
  setStill(still: boolean) {
    if (this.still === still) return;
    this.still = still;
    if (still) this.settle();
    this.pump();
    this.touch();
    this.flush();
  }

  /** A page of /oficina/eventos. */
  ingest(events: readonly unknown[] | null | undefined, serverNow?: string | null): number {
    const added = this.queue.ingest(events, serverNow);
    if (added) this.pump();
    this.flush();
    return added;
  }

  get halted(): boolean {
    return this.paused || this.frozen;
  }

  get isStill(): boolean {
    return this.still;
  }

  get isPaused(): boolean {
    return this.paused;
  }

  // ------------------------------------------------------------ reads

  statusOf(id: CharacterId): SceneStatus {
    if (id === LIBRARIAN_ID) {
      const known = Object.values(this.statuses).some((s) => s && s !== 'desconocido');
      if (!known) return 'desconocido';
      return this.byId[LIBRARIAN_ID].busy ? 'trabajando' : 'en_espera';
    }
    return this.statuses[id] ?? 'desconocido';
  }

  /** The character under a logical point (the front-most one). */
  hit(x: number, y: number): CharacterId | null {
    let best: Actor | null = null;
    for (const a of this.actors) {
      if (a.alpha <= 0.2) continue;
      if (x >= a.x - 8 && x <= a.x + 8 && y >= a.y - 28 && y <= a.y + 2 && (!best || a.y > best.y)) best = a;
    }
    return best?.id ?? null;
  }

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  getSnapshot = (): EngineSnapshot => {
    if (!this.cached || this.cached.version !== this.version) {
      const doing: Partial<Record<CharacterId, string>> = {};
      for (const a of this.actors) if (a.doing) doing[a.id] = a.doing;
      this.cached = {
        version: this.version,
        now: this.now,
        feed: this.feed,
        doing,
        librarianBusy: this.byId[LIBRARIAN_ID].busy,
        paused: this.paused,
        halted: this.halted,
        still: this.still,
      };
    }
    return this.cached;
  };

  /** Plays and idle walks in progress. */
  get activeTasks(): number {
    return this.tasks.length;
  }

  // ------------------------------------------------------------ time

  /** Advances the scene by `dt` ms. Does nothing while halted. */
  step(dt: number) {
    if (this.halted) return;
    this.clock += dt;
    for (const a of this.actors) {
      if (a.fade) {
        a.alpha = Math.max(0, Math.min(1, a.alpha + (a.fade * dt) / 500));
        if (a.alpha <= 0 || a.alpha >= 1) a.fade = 0;
      }
      if (a.bubble && this.clock > a.bubble.until) a.bubble = null;
      this.move(a, dt);
    }
    this.runTasks();
    this.pump();
    this.ambient();
    this.flush();
  }

  /** Steps in 16 ms frames (tests, catching up). */
  advance(ms: number) {
    for (let left = ms; left > 0; left -= 16) this.step(Math.min(16, left));
  }

  private move(a: Actor, dt: number) {
    if (!a.path) return;
    let left = (WALK_SPEED * dt) / 1000;
    while (left > 0 && a.path.length) {
      const [tx, ty] = a.path[0]!;
      const dx = tx - a.x;
      const dy = ty - a.y;
      const distance = Math.abs(dx) + Math.abs(dy);
      if (Math.abs(dx) > Math.abs(dy)) a.dir = dx > 0 ? 0 : 2;
      else if (distance > 0) a.dir = dy > 0 ? 3 : 1;
      if (distance <= left) {
        a.x = tx;
        a.y = ty;
        a.path.shift();
        left -= distance;
      } else {
        const mx = Math.min(Math.abs(dx), left);
        a.x += Math.sign(dx) * mx;
        left -= mx;
        if (left > 0 && dy) {
          const my = Math.min(Math.abs(dy), left);
          a.y += Math.sign(dy) * my;
          left -= my;
        }
      }
    }
    if (!a.path.length) a.path = null;
  }

  // ------------------------------------------------------------ queue → plays

  private pump() {
    if (this.halted) return;
    for (;;) {
      const item = this.queue.peek();
      if (!item) return;
      if (!this.still && this.clock < this.nextStart) return;
      if (item.kind === 'summary') {
        this.queue.shift();
        for (const event of item.summary.events) this.record(event);
        this.narrate(describeSummary(item.summary), summaryActor(item.summary));
        this.nextStart = this.clock + SUMMARY_HOLD;
        continue;
      }
      const event = item.event;
      const actor = this.actorFor(event);
      const walks = actor !== null && !this.still;
      if (walks && (actor.busy || this.runningPlays() >= MAX_PLAYS)) return;
      this.queue.shift();
      this.record(event);
      this.narrate(describeEvent(event), event.tipo === 'publicacion' ? 'operador_cuenta' : event.rol);
      if (walks) {
        this.start(this.scriptFor(event, actor), 'play');
        this.nextStart = this.clock + START_GAP;
      }
    }
  }

  /** The character an event moves, or null when it only gets narrated. */
  private actorFor(event: OfficeEvent): Actor | null {
    if (event.tipo === 'publicacion') return this.byId.operador_cuenta;
    return isRoleId(event.rol) ? this.byId[event.rol] : null;
  }

  private scriptFor(event: OfficeEvent, actor: Actor): Script {
    if (event.tipo === 'consulta_biblioteca') return this.consult(actor, event);
    if (event.tipo === 'entrega') return this.deliver(actor, event);
    return this.publish(actor);
  }

  private runningPlays(): number {
    return this.tasks.filter((t) => t.kind === 'play' && !t.done).length;
  }

  private start(script: Script, kind: Task['kind']) {
    const task: Task = { script, cond: null, kind, done: false };
    this.advanceTask(task);
    if (!task.done) this.tasks.push(task);
    this.touch();
  }

  private advanceTask(task: Task) {
    for (let guard = 0; guard < 64 && !task.done; guard++) {
      if (task.cond && !task.cond()) return;
      const result = task.script.next();
      if (result.done) task.done = true;
      else task.cond = result.value;
    }
  }

  private runTasks() {
    if (!this.tasks.length) return;
    for (const task of this.tasks) this.advanceTask(task);
    const before = this.tasks.length;
    this.tasks = this.tasks.filter((t) => !t.done);
    if (this.tasks.length !== before) this.touch();
  }

  /** Cancels every play and puts everyone back at their seat (reduced motion turned on). */
  private settle() {
    for (const task of this.tasks) task.script.return(undefined);
    this.tasks = [];
    this.libraryJobs = [];
    this.occupied.clear();
    for (const a of this.actors) {
      Object.assign(a, { x: a.role.home[0], y: a.role.home[1], dir: a.role.facing, path: null, at: null, away: false, reading: false, alpha: 1, fade: 0, bubble: null, busy: false, doing: null });
    }
    this.nextStart = this.clock;
  }

  // ------------------------------------------------------------ building blocks

  private *sleep(ms: number): Script {
    const end = this.clock + ms;
    yield () => this.clock >= end;
  }

  private *walk(a: Actor, route: readonly Point[]): Script {
    const rest = route.map((p) => [p[0], p[1]] as const);
    while (rest.length && rest[0]![0] === a.x && rest[0]![1] === a.y) rest.shift();
    if (!rest.length) return;
    a.path = rest;
    a.away = true;
    yield () => a.path === null;
  }

  private *goTo(a: Actor, place: PlaceId): Script {
    const { via, facing } = PLACES[place];
    yield* this.walk(a, planRoute(a.at ?? a.role.via, via));
    a.at = via;
    a.away = true;
    a.dir = facing;
  }

  private *goHome(a: Actor): Script {
    if (a.at) yield* this.walk(a, planRoute(a.at, a.role.via));
    a.at = null;
    a.away = false;
    a.reading = false;
    a.dir = a.role.facing;
  }

  private *claim(a: Actor, place: PlaceId): Script {
    yield () => !this.occupied.has(place);
    this.occupied.set(place, a.id);
  }

  private *claimLibrarySpot(a: Actor): Generator<Cond, PlaceId, undefined> {
    yield () => LIBRARY_SPOTS.some((spot) => !this.occupied.has(spot));
    const spot = LIBRARY_SPOTS.find((s) => !this.occupied.has(s))!;
    this.occupied.set(spot, a.id);
    return spot;
  }

  private release(a: Actor, place: PlaceId) {
    if (this.occupied.get(place) === a.id) this.occupied.delete(place);
  }

  private say(a: Actor, icon: BubbleIcon, ms: number) {
    a.bubble = { icon, until: this.clock + ms };
  }

  private begin(a: Actor, doing: string) {
    a.busy = true;
    a.doing = doing;
    this.touch();
  }

  private finish(a: Actor) {
    a.busy = false;
    a.doing = null;
    this.touch();
  }

  // ------------------------------------------------------------ plays

  /** Consulta de conocimiento: to the library, asks; the librarian fetches a book; reads it and goes back. */
  private *consult(a: Actor, event: OfficeEvent): Script {
    this.begin(a, `Consultando la biblioteca${quoted(event.detalle)}`);
    const spot = yield* this.claimLibrarySpot(a);
    yield* this.goTo(a, spot);
    this.say(a, 'pregunta', 1800);
    const job: LibraryJob = { visitor: a, done: false };
    this.libraryJobs.push(job);
    if (!this.tasks.some((t) => t.kind === 'librarian' && !t.done)) this.start(this.serveLibrary(), 'librarian');
    yield () => job.done;
    this.say(a, 'libro', 2200);
    a.reading = true;
    yield* this.sleep(1600);
    a.reading = false;
    this.release(a, spot);
    yield* this.goHome(a);
    this.finish(a);
  }

  /** The librarian serves the visitors one by one: shelf, search, back to the counter, hands the book. */
  private *serveLibrary(): Script {
    const librarian = this.byId[LIBRARIAN_ID];
    while (this.libraryJobs.length) {
      const job = this.libraryJobs[0]!;
      this.begin(librarian, `Busca un libro para ${job.visitor.role.short}`);
      const shelf = job.visitor.index % 2 ? 20 : 62;
      yield* this.walk(librarian, [[42, 66], [shelf, 66]]);
      librarian.dir = 1;
      this.say(librarian, 'busca', 1400);
      yield* this.sleep(1400);
      yield* this.walk(librarian, [[42, 66], [42, 84]]);
      librarian.away = false;
      librarian.dir = 3;
      this.say(librarian, 'libro', 1200);
      yield* this.sleep(900);
      job.done = true;
      this.libraryJobs.shift();
    }
    this.finish(librarian);
  }

  /** Entrega entre equipos: carries a sheet to the receiving team, they talk, and it goes back. */
  private *deliver(a: Actor, event: OfficeEvent): Script {
    const target = isRoleId(event.destino) ? this.byId[event.destino] : null;
    this.begin(a, target ? `Lleva su trabajo a ${target.role.short}` : 'Entrega su trabajo');
    if (target && target !== a) {
      const place = visitPlaceFor(target.role.team as TeamId);
      yield* this.claim(a, place);
      yield* this.goTo(a, place);
      this.say(a, 'hoja', 2200);
      yield* this.sleep(900);
      this.say(target, 'charla', 1800);
      yield* this.sleep(1500);
      this.release(a, place);
      yield* this.goHome(a);
    } else {
      this.say(a, 'hoja', 2200);
      yield* this.sleep(1500);
    }
    this.finish(a);
  }

  /** Publicación ejecutada: Operación walks out of the door and comes back. */
  private *publish(o: Actor): Script {
    this.begin(o, 'Publicando en LinkedIn');
    yield* this.claim(o, 'puerta');
    yield* this.goTo(o, 'puerta');
    o.fade = -1;
    yield* this.sleep(1300);
    this.say(o, 'listo', 2000);
    o.fade = 1;
    yield* this.sleep(800);
    this.release(o, 'puerta');
    yield* this.goHome(o);
    this.finish(o);
  }

  // ------------------------------------------------------------ idle (en espera only)

  /** Now and then a role really «en espera» goes for a coffee or chats with a teammate. Never while events play. */
  private ambient() {
    if (this.still || this.clock < this.nextAmbient) return;
    this.nextAmbient = this.clock + AMBIENT_EVERY;
    if (this.runningPlays() > 0 || this.queue.size > 0) return;
    const free = this.actors.filter((a) => isRoleId(a.id) && !a.role.service && !a.busy && !a.away && lookFor(this.statusOf(a.id)).idleWalks);
    if (!free.length) return;
    const a = free[this.ambientTurn % free.length]!;
    this.ambientTurn += 1;
    const mate = free.find((b) => b !== a && b.role.team === a.role.team);
    const coffee = !this.occupied.has('cafe');
    if (mate && (this.ambientTurn % 2 === 0 || !coffee)) this.start(this.chat(a, mate), 'ambient');
    else if (coffee) this.start(this.coffee(a), 'ambient');
  }

  private *coffee(a: Actor): Script {
    this.begin(a, 'Por un café');
    yield* this.claim(a, 'cafe');
    yield* this.goTo(a, 'cafe');
    this.say(a, 'cafe', 2600);
    yield* this.sleep(2600);
    this.release(a, 'cafe');
    yield* this.goHome(a);
    this.finish(a);
  }

  private *chat(a: Actor, b: Actor): Script {
    this.say(a, 'charla', 2000);
    yield* this.sleep(2200);
    this.say(b, 'charla', 2000);
  }

  // ------------------------------------------------------------ narration

  private narrate(text: string, role: string | null) {
    this.now = { key: ++this.nowKey, text, role: isCharacterId(role) ? role : null, at: this.wall() };
    this.touch();
  }

  private record(event: OfficeEvent) {
    const role = event.tipo === 'publicacion' ? 'operador_cuenta' : event.rol;
    const at = Date.parse(event.ts);
    const entries: FeedEntry[] = [];
    // Every library visit is also the librarian's work.
    if (event.tipo === 'consulta_biblioteca') entries.push({ key: `${event.id}:${LIBRARIAN_ID}`, role: LIBRARIAN_ID, text: `Atiende a ${actorName(event.rol)}${quoted(event.detalle)}`, at });
    if (isCharacterId(role)) entries.push({ key: String(event.id), role, text: describeEvent(event), at });
    if (!entries.length) return;
    this.feed = [...entries, ...this.feed].slice(0, FEED_LIMIT);
    this.touch();
  }

  private touch() {
    this.dirty = true;
  }

  private flush() {
    if (!this.dirty) return;
    this.dirty = false;
    this.version += 1;
    for (const listener of this.listeners) listener();
  }
}
