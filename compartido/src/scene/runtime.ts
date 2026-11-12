// Serializable scene state + worklet functions. Both renderers run this interpreter. No generators,
// class instances, callbacks or React in the UI runtime. Paths/scripts allocate only at transitions;
// ordinary fixed steps mutate the 17 actors and compact tasks in place.
//
// The agents rest while nothing needs them: a role «en espera» leaves its seat for the game room, the kitchen or the
// library shelves, changes pastime now and then and talks with whoever plays beside it. A role at work, an event that
// involves it (its own delivery, a colleague's, your capture) or a role whose state is unknown keeps it at its seat.
// Each zone's light follows who is in it: the office goes dark while everyone rests.
import type { SceneStatus, StatusMap } from './activity';

import { createQueue, queueIngest, queueShift, actorName, describeEvent, describeSummary, summaryActor, type OfficeEvent, type QueueState } from './events';

import type { Actor, BubbleIcon, EngineOptions, EngineSnapshot, FeedEntry, NowEntry } from './model';

import { SCENE_MOTION, type SceneMotion } from './motion';

import { LIGHT_ZONES, PLACES, REST_IDS, REST_SPOTS, lightZoneAt, planRoute, type LightZone, type Pastime, type PlaceId, type RestId } from './plan';

import { CHARACTERS, LIBRARIAN_ID, isCharacterId, isRoleId, type CharacterId, type Point, type TeamId, type ZoneId } from './roles';

type Command =
  | { op: 'claim'; place: PlaceId | 'library' }
  | { op: 'go' | 'release' | 'home' | 'finish' | 'requestBook' | 'awaitBook' | 'bookDone' }
  | { op: 'sleep'; ms: number }
  | { op: 'capturePickup' | 'captureDone' }
  | { op: 'narrate'; text: string; role: CharacterId }
  | { op: 'doing'; text: string }
  | { op: 'say'; icon: BubbleIcon; ms: number; target?: CharacterId }
  | { op: 'reading'; value: boolean }
  | { op: 'fade'; value: number }
  | { op: 'walk'; route: Point[] }
  | { op: 'face'; dir: Actor['dir']; seated?: boolean }
  | { op: 'rest'; spot: RestId }
  | { op: 'call'; who: CharacterId }
  | { op: 'awaitSeat'; who: CharacterId; ms: number };

interface Task {
  actor: CharacterId;
  kind: 'play' | 'leisure' | 'librarian' | 'capture';
  commands: Command[];
  index: number;
  started: boolean;
  until: number;
  place: PlaceId | null;
  visitor: CharacterId | null;
}

export interface SceneState {
  actors: Actor[];
  queue: QueueState;
  statuses: StatusMap;
  clock: number;
  paused: boolean;
  frozen: boolean;
  still: boolean;
  tasks: Task[];
  occupied: Partial<Record<PlaceId | RestId, CharacterId>>;
  libraryJobs: CharacterId[];
  booksReady: Partial<Record<CharacterId, boolean>>;
  nextStart: number;
  version: number;
  now: NowEntry | null;
  feed: FeedEntry[];
  motion: SceneMotion;
  wallTime: number;
  selectedRole: CharacterId | null;
  selectedZone: ZoneId | null;
  hopAt: number;
  teamAt: number;
  captures: number;
  captureActive: boolean;
  mail: { x: number; y: number; vy: number; nextStep: number; landed: boolean; checkFreeAt: number } | null;
  /** Each zone's light, 0 off to 1 on, and where it is going. */
  light: Record<LightZone, number>;
  lightTarget: Record<LightZone, number>;
  /** The state of the pseudo-random generator of the game room (deterministic: the same scene plays the same). */
  seed: number;
  /** The free agents were placed at rest when the statuses first arrived (the scene opens already in motion). */
  placed: boolean;
  nextLife: number;
  partyUntil: number;
  nextParty: number;
}

// Dependencies precede callers: worklets capture their closures during module initialization.

function allLights(level: number): Record<LightZone, number> {
  'worklet';
  const out = {} as Record<LightZone, number>;
  for (const zone of LIGHT_ZONES) out[zone] = level;
  return out;
}

export function createScene(options: EngineOptions = {}, motion?: SceneMotion): SceneState {
  'worklet';
  const config = motion ?? SCENE_MOTION;
  return {
    actors: CHARACTERS.map((role, index) => ({ id: role.id, role, index, x: role.home[0], y: role.home[1], dir: role.facing,
      path: null, at: null, away: false, reading: false, alpha: 1, fade: 0, bubble: null, busy: false, doing: null,
      spot: null, pastime: null, duty: 0, restAt: -1, emoteAt: 0, reply: null, hurry: false })),
    queue: createQueue(options.queue), statuses: {}, clock: 0, paused: false, frozen: options.frozen ?? false,
    still: options.still ?? false, tasks: [], occupied: {}, libraryJobs: [], booksReady: {}, nextStart: 0,
    version: 0, now: null, feed: [], motion: config, wallTime: 0,
    selectedRole: null, selectedZone: null, hopAt: -config.hopEndMs, teamAt: -config.bracketMs,
    captures: 0, captureActive: false, mail: null,
    light: allLights(1), lightTarget: allLights(1), seed: 0x0ff1ce, placed: false, nextLife: 0,
    partyUntil: 0, nextParty: config.partyFirstMs,
  };
}

export function actorById(s: SceneState, id: CharacterId): Actor {
  'worklet';
  // A linear lookup over 17 actors avoids aliases when SharedValues serialize plain state.
  for (const a of s.actors) if (a.id === id) return a;
  throw new Error(`Personaje desconocido: ${id}`);
}

export function sceneStatus(s: SceneState, id: CharacterId): SceneStatus {
  'worklet';
  if (id !== LIBRARIAN_ID) return s.statuses[id] ?? 'desconocido';
  for (const key in s.statuses) {
    if (s.statuses[key as CharacterId] !== 'desconocido') return actorById(s, id).busy ? 'trabajando' : 'en_espera';
  }
  return 'desconocido';
}

export function hitScene(s: SceneState, x: number, y: number, minWidth = 16, minHeight = 30): CharacterId | null {
  'worklet';
  let best: Actor | null = null;
  for (const a of s.actors) {
    if (a.alpha <= 0.2) continue;
    const half = Math.max(8, minWidth / 2);
    const extra = Math.max(0, (minHeight - 30) / 2);
    if (x >= a.x - half && x <= a.x + half && y >= a.y - 28 - extra && y <= a.y + 2 + extra && (!best || a.y > best.y)) best = a;
  }
  return best?.id ?? null;
}

export function sceneSnapshot(s: SceneState): EngineSnapshot {
  'worklet';
  const doing: EngineSnapshot['doing'] = {};
  for (const a of s.actors) if (a.doing) doing[a.id] = a.doing;
  return { version: s.version, now: s.now, feed: s.feed, doing, librarianBusy: actorById(s, LIBRARIAN_ID).busy,
    paused: s.paused, halted: s.paused || s.frozen, still: s.still };
}

function begin(s: SceneState, a: Actor, doing: string) {
  'worklet';
  a.busy = true; a.doing = doing; s.version++;
}

function finish(s: SceneState, a: Actor) {
  'worklet';
  a.busy = false; a.doing = null; s.version++;
}

function walk(a: Actor, route: Point[]) {
  'worklet';
  while (route.length && route[0]![0] === a.x && route[0]![1] === a.y) route.shift();
  a.path = route.length ? route : null;
  if (a.path) a.away = true;
}

function addTask(s: SceneState, actor: CharacterId, kind: Task['kind'], commands: Command[], visitor: CharacterId | null = null) {
  'worklet';
  const t: Task = { actor, kind, commands, index: 0, started: false, until: 0, place: null, visitor };
  s.tasks.push(t);
  s.version++;
  return t;
}

// ---------------------------------------------------------------- the agents at rest: helpers

/** Next number in [0, 1) of the scene's own generator (mulberry32). */
function rand(s: SceneState): number {
  'worklet';
  s.seed = (s.seed + 0x6d2b79f5) | 0;
  let r = Math.imul(s.seed ^ (s.seed >>> 15), 1 | s.seed);
  r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
  return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
}

function between(s: SceneState, min: number, max: number): number {
  'worklet';
  return min + Math.floor(rand(s) * (max - min));
}

function hasTask(s: SceneState, id: CharacterId): boolean {
  'worklet';
  for (const t of s.tasks) if (t.actor === id && t.index < t.commands.length) return true;
  return false;
}

/** The activity endpoint has answered: until then everyone stays at its seat and every light stays on. */
function statusesKnown(s: SceneState): boolean {
  'worklet';
  for (const key in s.statuses) if (s.statuses[key as CharacterId] !== 'desconocido') return true;
  return false;
}

/** Services stay at their posts; an agent rests only «en espera», free and not called to its seat. */
function wantsSeat(s: SceneState, a: Actor): boolean {
  'worklet';
  if (a.role.service) return true;
  return sceneStatus(s, a.id) !== 'en_espera' || a.busy || a.duty > s.clock;
}

/** Gives up its rest spot (it walks away from where it stands: `at` stays the spot's route). */
function leaveSpot(s: SceneState, a: Actor) {
  'worklet';
  if (a.spot && s.occupied[a.spot] === a.id) delete s.occupied[a.spot];
  a.spot = null; a.pastime = null; a.reading = false; a.reply = null;
}

/** Puts it at a rest spot, or at its seat with `null`, at once (the still scene, the first placement). */
function teleport(s: SceneState, a: Actor, spot: RestId | null) {
  'worklet';
  leaveSpot(s, a);
  a.path = null;
  if (!spot) {
    a.x = a.role.home[0]; a.y = a.role.home[1]; a.dir = a.role.facing; a.at = null; a.away = false;
    return;
  }
  const place = REST_SPOTS[spot];
  const [x, y] = place.via[place.via.length - 1]!;
  s.occupied[spot] = a.id;
  a.spot = spot; a.pastime = place.pastime; a.reading = place.pastime === 'lee';
  a.x = x; a.y = y; a.dir = place.facing; a.at = place.via; a.away = true;
}

/** Each zone is lit while someone is in it; the corridors while any office zone is. Services waiting do not count. */
function lightTargets(s: SceneState) {
  'worklet';
  const target = s.lightTarget;
  const known = statusesKnown(s);
  for (const zone of LIGHT_ZONES) target[zone] = known ? 0 : 1;
  if (!known) return;
  let team = false;
  for (const a of s.actors) {
    if (a.alpha <= 0 || (a.role.service && !a.busy) || (sceneStatus(s, a.id) === 'diseno' && !a.path)) continue;
    const zone = lightZoneAt(a.x, a.y);
    target[zone] = 1;
    if (zone !== 'pasillo' && zone !== 'juegos' && zone !== 'biblioteca' && zone !== 'relaciones') team = true;
  }
  // The corridors: on while someone walks them, half on while a team works, off when only the kitchen or the library is used.
  if (!target.pasillo && team) target.pasillo = 0.6;
}

function updateLights(s: SceneState, dt: number) {
  'worklet';
  const step = dt / s.motion.lightFadeMs;
  for (const zone of LIGHT_ZONES) {
    const from = s.light[zone]; const to = s.lightTarget[zone];
    s.light[zone] = from < to ? Math.min(to, from + step) : Math.max(to, from - step);
  }
}

function serveNext(s: SceneState) {
  'worklet';
  if (!s.libraryJobs.length) return;
  const visitor = actorById(s, s.libraryJobs[0]!);
  const a = actorById(s, LIBRARIAN_ID);
  begin(s, a, `Busca un libro para ${visitor.role.short}`);
  const m = s.motion;
  addTask(s, a.id, 'librarian', [
    { op: 'walk', route: [[42, 66], [visitor.index % 2 ? 20 : 62, 66]] }, { op: 'face', dir: 1 },
    { op: 'say', icon: 'busca', ms: m.searchMs }, { op: 'sleep', ms: m.searchMs },
    { op: 'walk', route: [[42, 66], [42, 84]] }, { op: 'face', dir: 3, seated: true },
    { op: 'say', icon: 'libro', ms: m.librarianBookMs }, { op: 'sleep', ms: m.handBookMs }, { op: 'bookDone' },
  ], visitor.id);
}

function narrate(s: SceneState, text: string, role: string | null) {
  'worklet';
  s.now = { key: (s.now?.key ?? 0) + 1, text, role: isCharacterId(role) ? role : null, at: s.wallTime };
  s.version++;
}

/** MovOficina: selection only changes presentation; it never interrupts an actor's route. */
export function selectScene(s: SceneState, role: CharacterId | null, zone: ZoneId | null) {
  'worklet';
  if (role && role !== s.selectedRole) s.hopAt = s.clock;
  if (zone && zone !== s.selectedZone) s.teamAt = s.clock;
  s.selectedRole = role; s.selectedZone = zone;
}

export function narrateSceneSelection(s: SceneState, id: CharacterId) {
  'worklet';
  const a = actorById(s, id);
  const status = sceneStatus(s, id);
  const activity = s.frozen ? 'Sin datos de actividad' : s.paused ? 'Quieto: la máquina está en pausa'
    : status === 'diseno' ? 'Todavía no trabaja' : a.doing ?? (id === LIBRARIAN_ID ? 'Ordenando la biblioteca'
      : a.spot ? `Descansa · ${REST_SPOTS[a.spot].label}` : a.reading ? 'Leyendo un borrador' : status === 'trabajando' ? 'Trabajando en su puesto'
        : status === 'desconocido' ? 'Sin datos de actividad' : 'En espera, sin encargo');
  narrate(s, `${a.role.name} · ${activity}`, id);
}

export function sceneHop(s: SceneState, id: CharacterId): number {
  'worklet';
  if (s.still || s.paused || s.frozen || id !== s.selectedRole) return 0;
  const elapsed = s.clock - s.hopAt;
  return elapsed < s.motion.hopStepMs ? s.motion.hopPx : elapsed < s.motion.hopEndMs ? s.motion.hopSettlePx : 0;
}

export function sceneBracketLength(s: SceneState): number {
  'worklet';
  if (s.still || s.paused || s.frozen) return s.motion.bracketPx;
  return Math.max(1, Math.round(s.motion.bracketPx * Math.min(1, (s.clock - s.teamAt) / s.motion.bracketMs)));
}

/** A confirmed local send, separate from the backend event feed and its real-work history. */
export function receiveSceneCapture(s: SceneState) {
  'worklet';
  narrate(s, 'Llegó tu captura a la oficina.', 'operador_cuenta');
  if (s.still) return;
  s.captures++;
  if (!s.captureActive) {
    const m = s.motion;
    s.captureActive = true;
    // The board performs the first fall step synchronously on receipt.
    s.mail = { x: m.mailX, y: m.mailStartY + m.mailAcceleration, vy: m.mailAcceleration,
      nextStep: s.clock + m.mailStepMs, landed: false, checkFreeAt: 0 };
  }
}

function runTask(s: SceneState, t: Task) {
  'worklet';
  const a = actorById(s, t.actor);
  for (let guard = 0; guard < 64 && t.index < t.commands.length; guard++) {
    const c = t.commands[t.index]!;
    switch (c.op) {
      case 'claim': {
        const place = c.place === 'library' ? (!s.occupied.biblioteca1 ? 'biblioteca1' : 'biblioteca2') : c.place;
        if (s.occupied[place]) return;
        s.occupied[place] = a.id; t.place = place; break;
      }
      case 'go':
      case 'home': {
        const place = c.op === 'go' && t.place ? PLACES[t.place] : null;
        if (!t.started) {
          a.pastime = null;
          if (place) walk(a, planRoute(a.at ?? a.role.via, place.via));
          else if (a.at) walk(a, planRoute(a.at, a.role.via));
          t.started = true;
        }
        if (a.path) return;
        a.at = place?.via ?? null; a.away = Boolean(place); a.dir = place?.facing ?? a.role.facing;
        if (!place) a.reading = false;
        break;
      }
      case 'walk':
        if (!t.started) { walk(a, c.route.slice()); t.started = true; }
        if (a.path) return;
        break;
      case 'rest': {
        const spot = REST_SPOTS[c.spot];
        if (!t.started) { a.pastime = null; walk(a, planRoute(a.at ?? a.role.via, spot.via)); t.started = true; }
        if (a.path) return;
        a.at = spot.via; a.away = true; a.dir = spot.facing; a.pastime = spot.pastime; a.reading = spot.pastime === 'lee';
        break;
      }
      case 'call': {
        const who = actorById(s, c.who);
        who.duty = Math.max(who.duty, s.clock + s.motion.callMs);
        break;
      }
      case 'awaitSeat': {
        if (!t.started) { t.until = s.clock + c.ms; t.started = true; }
        const who = actorById(s, c.who);
        if ((who.at || who.path || who.spot) && s.clock < t.until) return;
        break;
      }
      case 'release':
        if (t.place && s.occupied[t.place] === a.id) delete s.occupied[t.place];
        break;
      case 'sleep':
        if (!t.started) { t.until = s.clock + c.ms; t.started = true; }
        if (s.clock < t.until) return;
        break;
      case 'say': {
        const target = c.target ? actorById(s, c.target) : a;
        target.bubble = { icon: c.icon, until: s.clock + c.ms }; break;
      }
      case 'reading': a.reading = c.value; break;
      case 'fade': a.fade = c.value; break;
      case 'face': a.dir = c.dir; if (c.seated) a.away = false; break;
      case 'finish': finish(s, a); a.duty = Math.max(a.duty, s.clock + s.motion.dutyMs); break;
      case 'doing': a.doing = c.text; s.version++; break;
      case 'narrate': narrate(s, c.text, c.role); break;
      case 'capturePickup': s.mail = null; break;
      case 'captureDone': s.captures--; s.captureActive = false; break;
      case 'requestBook':
        s.libraryJobs.push(a.id);
        if (s.libraryJobs.length === 1) serveNext(s);
        break;
      case 'awaitBook':
        if (!s.booksReady[a.id]) return;
        delete s.booksReady[a.id]; break;
      case 'bookDone':
        if (t.visitor) s.booksReady[t.visitor] = true;
        s.libraryJobs.shift();
        if (s.libraryJobs.length) serveNext(s); else finish(s, a);
        break;
    }
    t.index++; t.started = false;
  }
}

function runningPlays(s: SceneState): number {
  'worklet';
  let n = 0;
  for (const t of s.tasks) if ((t.kind === 'play' || t.kind === 'capture') && t.index < t.commands.length) n++;
  return n;
}

function quoted(detail: string | null | undefined): string {
  'worklet';
  return detail?.trim() ? `: “${detail.trim()}”` : '';
}

function startPlay(s: SceneState, a: Actor, event: OfficeEvent) {
  'worklet';
  const m = s.motion;
  const commands: Command[] = [];
  // From the game room it walks straight to where the event needs it; a delivery is prepared at its desk first.
  const resting = a.at !== null;
  leaveSpot(s, a);
  a.hurry = resting;
  if (event.tipo === 'consulta_biblioteca') {
    begin(s, a, `Consultando la biblioteca${quoted(event.detalle)}`);
    commands.push({ op: 'claim', place: 'library' }, { op: 'go' }, { op: 'say', icon: 'pregunta', ms: m.questionMs },
      { op: 'requestBook' }, { op: 'awaitBook' }, { op: 'say', icon: 'libro', ms: m.bookMs },
      { op: 'reading', value: true }, { op: 'sleep', ms: m.readMs }, { op: 'reading', value: false }, { op: 'release' }, { op: 'home' });
  } else if (event.tipo === 'entrega') {
    const target = isRoleId(event.destino) ? actorById(s, event.destino) : null;
    begin(s, a, target ? `Lleva su trabajo a ${target.role.short}` : 'Entrega su trabajo');
    if (target && target.id !== a.id) commands.push({ op: 'call', who: target.id });
    if (resting) commands.push({ op: 'home' }, { op: 'sleep', ms: m.workMs });
    if (target && target.id !== a.id) {
      commands.push({ op: 'claim', place: target.role.team as TeamId }, { op: 'go' }, { op: 'awaitSeat', who: target.id, ms: m.awaitSeatMs },
        { op: 'say', icon: 'hoja', ms: m.sheetMs },
        { op: 'sleep', ms: m.handSheetMs }, { op: 'say', target: target.id, icon: 'charla', ms: m.conversationMs },
        { op: 'sleep', ms: m.deliveryMs }, { op: 'release' }, { op: 'home' });
    } else commands.push({ op: 'say', icon: 'hoja', ms: m.sheetMs }, { op: 'sleep', ms: m.deliveryMs });
  } else {
    begin(s, a, 'Publicando en LinkedIn');
    commands.push({ op: 'claim', place: 'puerta' }, { op: 'go' }, { op: 'fade', value: -1 }, { op: 'sleep', ms: m.outsideMs },
      { op: 'say', icon: 'listo', ms: m.doneMs }, { op: 'fade', value: 1 }, { op: 'sleep', ms: m.returnMs }, { op: 'release' }, { op: 'home' });
  }
  commands.push({ op: 'finish' });
  runTask(s, addTask(s, a.id, 'play', commands));
}

function record(s: SceneState, event: OfficeEvent) {
  'worklet';
  const role = event.tipo === 'publicacion' ? 'operador_cuenta' : event.rol;
  const at = Date.parse(event.ts);
  const entries: FeedEntry[] = [];
  if (event.tipo === 'consulta_biblioteca') entries.push({ key: `${event.id}:${LIBRARIAN_ID}`, role: LIBRARIAN_ID, text: `Atiende a ${actorName(event.rol)}${quoted(event.detalle)}`, at });
  if (isCharacterId(role)) entries.push({ key: String(event.id), role, text: describeEvent(event), at });
  if (entries.length) { s.feed = [...entries, ...s.feed].slice(0, 60); s.version++; }
}


function pumpCapture(s: SceneState) {
  'worklet';
  if (s.still || !s.captures) return;
  const m = s.motion;
  if (!s.captureActive) {
    s.captureActive = true;
    s.mail = { x: m.mailX, y: m.mailStartY + m.mailAcceleration, vy: m.mailAcceleration,
      nextStep: s.clock + m.mailStepMs, landed: false, checkFreeAt: 0 };
    narrate(s, 'Llegó tu captura a la oficina.', 'operador_cuenta');
  }
  const mail = s.mail;
  if (!mail) return;
  while (!mail.landed && s.clock >= mail.nextStep) {
    if (mail.y < m.mailLandingY) {
      mail.vy += m.mailAcceleration;
      mail.y = Math.min(m.mailLandingY, mail.y + mail.vy);
    } else mail.landed = true;
    mail.nextStep += m.mailStepMs;
  }
  if (!mail.landed || s.clock < mail.checkFreeAt) return;
  const o = actorById(s, 'operador_cuenta');
  if (o.busy) { mail.checkFreeAt = s.clock + m.captureFreePollMs; return; }
  begin(s, o, 'Recogiendo tu captura');
  runTask(s, addTask(s, o.id, 'capture', [
    { op: 'call', who: 'director_editorial' },
    { op: 'face', dir: 3 }, { op: 'say', icon: 'pregunta', ms: m.captureQuestionMs },
    { op: 'sleep', ms: m.captureQuestionMs }, { op: 'capturePickup' },
    { op: 'say', icon: 'hoja', ms: m.captureSheetMs }, { op: 'sleep', ms: m.capturePickupMs },
    { op: 'doing', text: 'Llevando tu captura a Mesa editorial' },
    { op: 'narrate', text: 'Operación lleva tu captura a Mesa editorial.', role: o.id },
    { op: 'claim', place: 'editorial' }, { op: 'go' },
    { op: 'awaitSeat', who: 'director_editorial', ms: m.awaitSeatMs },
    { op: 'say', icon: 'hoja', ms: m.captureHandoffMs },
    { op: 'say', target: 'director_editorial', icon: 'charla', ms: m.captureHandoffMs },
    { op: 'narrate', text: 'Director editorial recibe tu captura.', role: 'director_editorial' },
    { op: 'sleep', ms: m.deliveryMs }, { op: 'release' }, { op: 'home' },
    { op: 'finish' }, { op: 'captureDone' },
  ]));
}

// ---------------------------------------------------------------- the agents at rest

const EMOTES: Readonly<Record<Pastime, readonly BubbleIcon[]>> = {
  consola: ['juego', 'exclama', 'risa', 'gota', 'estrella'],
  arcade: ['juego', 'estrella', 'exclama', 'gota'],
  billar: ['estrella', 'exclama', 'risa', 'idea'],
  bateria: ['nota', 'nota', 'estrella'],
  canta: ['nota', 'corazon', 'nota'],
  baila: ['nota', 'corazon', 'estrella'],
  charla: ['charla', 'risa', 'idea', 'pregunta', 'corazon'],
  cafe: ['cafe', 'charla'],
  nevera: ['pizza', 'corazon'],
  lee: ['libro', 'idea'],
};
/** What the partner answers. */
const REPLIES: Partial<Record<BubbleIcon, BubbleIcon>> = {
  juego: 'risa', exclama: 'risa', risa: 'risa', gota: 'risa', estrella: 'corazon', pregunta: 'idea', idea: 'estrella',
  charla: 'charla', corazon: 'corazon', nota: 'nota',
};

/** 22:00–6:00 on the phone's clock: whoever rests dozes off. */
function night(s: SceneState): boolean {
  'worklet';
  if (!s.wallTime) return false;
  const hour = new Date(s.wallTime).getHours();
  return hour >= 22 || hour < 6;
}

/** A free spot, weighted: a partner waiting makes a pair more likely, a party fills the dance floor. */
function pickSpot(s: SceneState, a: Actor): RestId | null {
  'worklet';
  const party = s.partyUntil > s.clock;
  let total = 0;
  const weight = (id: RestId) => {
    'worklet';
    if (s.occupied[id] !== undefined) return 0;
    const spot = REST_SPOTS[id];
    let w = 1;
    if (spot.partner && s.occupied[spot.partner] !== undefined) w *= 3;
    if (party) w *= spot.pastime === 'baila' || spot.pastime === 'charla' || spot.pastime === 'canta' ? 6 : 0.5;
    if (a.pastime === spot.pastime) w *= 0.2;
    return w;
  };
  for (const id of REST_IDS) total += weight(id);
  if (total <= 0) return null;
  let r = rand(s) * total;
  for (const id of REST_IDS) {
    r -= weight(id);
    if (r < 0 && s.occupied[id] === undefined) return id;
  }
  return null;
}

function goRest(s: SceneState, a: Actor, spot: RestId) {
  'worklet';
  const m = s.motion;
  leaveSpot(s, a);
  s.occupied[spot] = a.id; a.spot = spot;
  a.restAt = s.clock + between(s, m.stayMinMs, m.stayMaxMs);
  a.emoteAt = s.clock + between(s, m.emoteGapMinMs, m.emoteGapMaxMs);
  runTask(s, addTask(s, a.id, 'leisure', [{ op: 'rest', spot }]));
}

/** Says something about what it does; a partner beside it answers a moment later. */
function emote(s: SceneState, a: Actor) {
  'worklet';
  const m = s.motion;
  const party = s.partyUntil > s.clock;
  const spot = a.spot ? REST_SPOTS[a.spot] : null;
  if (!spot || !a.pastime) return;
  let icon: BubbleIcon;
  if (a.reply) { icon = a.reply; a.reply = null; }
  else if (night(s) && a.pastime !== 'baila' && rand(s) < 0.6) icon = 'zzz';
  else {
    const options = party ? EMOTES.baila : EMOTES[a.pastime];
    icon = options[Math.floor(rand(s) * options.length)]!;
    const partnerId = spot.partner ? s.occupied[spot.partner] : undefined;
    const partner = partnerId ? actorById(s, partnerId) : null;
    if (partner && partner.pastime && !partner.path && !partner.bubble && icon !== 'zzz') {
      partner.reply = REPLIES[icon] ?? icon;
      partner.emoteAt = s.clock + m.replyMs;
    }
  }
  a.bubble = { icon, until: s.clock + m.emoteMs };
  const gap = between(s, m.emoteGapMinMs, m.emoteGapMaxMs);
  a.emoteAt = s.clock + (party ? gap / 2 : gap);
}

/** Now and then a party: the dance floor lights up and a few go dance. */
export function startSceneParty(s: SceneState) {
  'worklet';
  const m = s.motion;
  s.partyUntil = s.clock + m.partyMs;
  s.nextParty = s.clock + m.partyMs + between(s, m.partyGapMinMs, m.partyGapMaxMs);
  let called = 0;
  for (const a of s.actors) {
    if (called >= 4 || !a.pastime || a.pastime === 'baila' || a.path) continue;
    if (rand(s) < 0.6) { a.restAt = s.clock + called * 700; called++; }
  }
  s.version++;
}

function party(s: SceneState) {
  'worklet';
  if (s.partyUntil > s.clock || s.clock < s.nextParty) return;
  let resting = 0;
  for (const a of s.actors) if (a.pastime) resting++;
  if (resting >= 4 && !night(s)) startSceneParty(s);
  else s.nextParty = s.clock + s.motion.partyGapMinMs;
}

/** The first time the statuses arrive, whoever is free is already at a pastime: the scene opens in motion. */
function placeAll(s: SceneState) {
  'worklet';
  const m = s.motion;
  for (const a of s.actors) {
    if (wantsSeat(s, a) || a.busy || hasTask(s, a.id) || a.path) continue;
    const spot = pickSpot(s, a);
    if (!spot) continue;
    teleport(s, a, spot);
    a.restAt = s.clock + between(s, m.restLeaveMinMs, m.stayMaxMs);
    a.emoteAt = s.clock + between(s, 300, m.emoteGapMinMs);
  }
}

/** The still scene (reduced motion): everyone where its state puts it, in a fixed order, and the lights already set. */
function settleStill(s: SceneState) {
  'worklet';
  for (const a of s.actors) {
    if (wantsSeat(s, a)) { if (a.spot || a.at) teleport(s, a, null); continue; }
    if (a.spot) continue;
    for (const id of REST_IDS) if (s.occupied[id] === undefined) { teleport(s, a, id); break; }
  }
  s.placed = statusesKnown(s);
  lightTargets(s);
  for (const zone of LIGHT_ZONES) s.light[zone] = s.lightTarget[zone];
}

/** Four times a second: who goes to its seat, who leaves it to rest, who changes pastime, who says something. */
function life(s: SceneState) {
  'worklet';
  if (s.clock < s.nextLife) return;
  const m = s.motion;
  s.nextLife = s.clock + m.lifeTickMs;
  lightTargets(s);
  if (!statusesKnown(s)) return;
  if (!s.placed) { placeAll(s); s.placed = true; }
  party(s);
  for (const a of s.actors) {
    if (a.role.service || a.busy || a.path || a.fade || hasTask(s, a.id)) continue;
    if (wantsSeat(s, a)) {
      a.restAt = -1;
      if (a.spot || a.at) {
        // Called by a colleague or by its own work it hurries; a role whose state changed walks.
        a.hurry = a.duty > s.clock;
        leaveSpot(s, a); runTask(s, addTask(s, a.id, 'leisure', [{ op: 'home' }]));
      }
      continue;
    }
    if (!a.spot) {
      // Free at its seat: it leaves after a short, different pause for each one.
      if (a.restAt < 0) a.restAt = s.clock + between(s, m.restLeaveMinMs, m.restLeaveMaxMs);
      else if (s.clock >= a.restAt) {
        const spot = pickSpot(s, a);
        if (spot) goRest(s, a, spot); else a.restAt = s.clock + m.restLeaveMaxMs;
      }
      continue;
    }
    if (s.clock >= a.restAt) {
      const spot = pickSpot(s, a);
      if (spot) { goRest(s, a, spot); continue; }
      a.restAt = s.clock + between(s, m.stayMinMs, m.stayMaxMs);
    }
    if (s.clock >= a.emoteAt && !a.bubble) emote(s, a);
  }
}

export function pumpScene(s: SceneState) {
  'worklet';
  if (s.still) settleStill(s);
  if (s.paused || s.frozen) return;
  pumpCapture(s);
  for (;;) {
    if (!s.still && s.clock < s.nextStart) return;
    const summary = s.queue.summary;
    if (summary) {
      queueShift(s.queue);
      for (const e of summary.events) record(s, e);
      narrate(s, describeSummary(summary), summaryActor(summary));
      s.nextStart = s.clock + s.motion.summaryHold;
      continue;
    }
    const event = s.queue.pending[0];
    if (!event) return;
    const actor = event.tipo === 'publicacion' ? actorById(s, 'operador_cuenta') : isRoleId(event.rol) ? actorById(s, event.rol) : null;
    const walks = actor !== null && !s.still;
    // An agent on its way to a pastime or back to its seat arrives first.
    if (walks && (actor.busy || hasTask(s, actor.id) || runningPlays(s) >= 2)) return;
    queueShift(s.queue);
    record(s, event);
    narrate(s, describeEvent(event), event.tipo === 'publicacion' ? 'operador_cuenta' : event.rol);
    if (walks) { startPlay(s, actor, event); s.nextStart = s.clock + s.motion.startGap; }
  }
}

export function ingestScene(s: SceneState, events: readonly unknown[] | null | undefined, serverNow?: string | null): number {
  'worklet';
  const added = queueIngest(s.queue, events, serverNow);
  if (added) pumpScene(s);
  return added;
}

export function setSceneStill(s: SceneState, still: boolean) {
  'worklet';
  if (s.still === still) return;
  s.still = still;
  if (still) {
    s.mail = null; s.captures = 0; s.captureActive = false;
    s.hopAt = s.clock - s.motion.hopEndMs; s.teamAt = s.clock - s.motion.bracketMs;
    s.tasks.length = 0; s.libraryJobs.length = 0; s.occupied = {}; s.booksReady = {};
    for (const a of s.actors) {
      a.x = a.role.home[0]; a.y = a.role.home[1]; a.dir = a.role.facing; a.path = null; a.at = null;
      a.away = false; a.reading = false; a.alpha = 1; a.fade = 0; a.bubble = null; a.busy = false; a.doing = null;
      a.spot = null; a.pastime = null; a.duty = 0; a.restAt = -1; a.emoteAt = 0; a.reply = null; a.hurry = false;
    }
    s.partyUntil = 0;
    s.nextStart = s.clock;
  }
  pumpScene(s); s.version++;
}

export function stepScene(s: SceneState, dt: number) {
  'worklet';
  if (s.paused || s.frozen) return;
  s.clock += dt;
  for (const a of s.actors) {
    if (a.fade) {
      a.alpha = Math.max(0, Math.min(1, a.alpha + a.fade * dt / s.motion.fadeMs));
      if (a.alpha <= 0 || a.alpha >= 1) a.fade = 0;
    }
    if (a.bubble && s.clock > a.bubble.until) a.bubble = null;
    if (!a.path) continue;
    let left = s.motion.walkSpeed * (a.hurry ? s.motion.hurryFactor : 1) * dt / 1000;
    while (left > 0 && a.path.length) {
      const [tx, ty] = a.path[0]!;
      const dx = tx - a.x; const dy = ty - a.y;
      const distance = Math.abs(dx) + Math.abs(dy);
      if (Math.abs(dx) > Math.abs(dy)) a.dir = dx > 0 ? 0 : 2;
      else if (distance > 0) a.dir = dy > 0 ? 3 : 1;
      if (distance <= left) { a.x = tx; a.y = ty; a.path.shift(); left -= distance; }
      else {
        const mx = Math.min(Math.abs(dx), left); a.x += Math.sign(dx) * mx; left -= mx;
        if (left > 0 && dy) { const my = Math.min(Math.abs(dy), left); a.y += Math.sign(dy) * my; left -= my; }
      }
    }
    if (!a.path.length) { a.path = null; a.hurry = false; }
  }
  for (let i = 0; i < s.tasks.length; i++) runTask(s, s.tasks[i]!);
  let keep = 0;
  for (let i = 0; i < s.tasks.length; i++) { const t = s.tasks[i]!; if (t.index < t.commands.length) s.tasks[keep++] = t; }
  if (keep !== s.tasks.length) { s.tasks.length = keep; s.version++; }
  pumpScene(s); life(s); updateLights(s, dt);
}
