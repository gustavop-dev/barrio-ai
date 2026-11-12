// Teams, roles and their places in the office. Coordinates are logical pixels of the vertical
// plan (192×452 with the game room, see plan.ts); the canvas draws them at an integer scale (2× = 384×904).
// The 17 role ids are the backend's (`/api/v1/oficina/actividad`); the librarian is an 18th
// character, a service with no activity row of its own.

export type Point = readonly [number, number];
/** Sprite sheet direction: 0 right, 1 up (back to the viewer), 2 left, 3 down. */
export type Direction = 0 | 1 | 2 | 3;

export const ROLE_IDS = [
  'posicionamiento',
  'perfil',
  'investigador_referentes',
  'analista_barrio_resultados',
  'director_editorial',
  'copywriter_a',
  'copywriter_b',
  'editor_visual',
  'lector_comprador',
  'lector_recomendador',
  'lector_divulgador',
  'lector_lider',
  'lector_par',
  'editor_verificador',
  'relaciones_comunidad',
  'conversaciones_inbox',
  'operador_cuenta',
] as const;

export type RoleId = (typeof ROLE_IDS)[number];
export const LIBRARIAN_ID = 'bibliotecario';
/** Every character in the scene: the 17 roles plus the librarian. */
export type CharacterId = RoleId | typeof LIBRARIAN_ID;

export type TeamId = 'estrategia' | 'observatorio' | 'editorial' | 'barrio' | 'revision' | 'relaciones' | 'operacion';
/** A zone of the plan: a team's space or the library. */
export type ZoneId = TeamId | 'biblioteca';

/** Logical box [x, y, w, h]. */
export type Box = readonly [number, number, number, number];

export interface Role {
  id: CharacterId;
  name: string;
  /** Short name for the «now» line («Operación», «Copywriter A»). */
  short: string;
  purpose: string;
  /** Team, or the library for the librarian. */
  team: ZoneId;
  /** Character sheet in the atlas (`p<N>`): 0–12 are LimeZu people, 13 is the librarian. */
  sprite: number;
  home: Point;
  facing: Direction;
  /** Chair drawn in front of the seated character (north, gold) or part of the furniture behind it (back, pouf). */
  chair: 'north' | 'gold' | 'back' | 'pouf' | null;
  /**
   * Route from the central corridor (x = 96) to the seat. The first point is on the corridor and the last
   * one is `home`, so the planner can join any two places through the corridor.
   */
  via: readonly Point[];
  /** Top-left of the desk monitor that lights up only while this role is really working. */
  monitor: Point | null;
  /** Software services that are not AI agents (Operación, the librarian). */
  service?: boolean;
}

export type AgentRole = Role & { id: RoleId; team: TeamId };

export interface Team {
  id: TeamId;
  /** 01–07, as in the team panel. */
  number: string;
  name: string;
  purpose: string;
  place: string;
  /** Tappable zone of the plan. */
  box: Box;
  isNew?: boolean;
}

export const TEAMS: readonly Team[] = [
  { id: 'estrategia', number: '01', name: 'Estrategia y perfil', purpose: 'Encontrar tu posición y hacer que tu perfil la comunique.', place: 'Los escritorios compartidos', box: [112, 112, 76, 68] },
  { id: 'observatorio', number: '02', name: 'Observatorio', purpose: 'Escuchar al barrio y descubrir referentes, preguntas y oportunidades.', place: 'Junto a la biblioteca', box: [4, 112, 76, 68] },
  { id: 'editorial', number: '03', name: 'Mesa editorial', purpose: 'Elegir una idea con intención y explorar dos maneras de contarla.', place: 'La mesa larga', box: [4, 182, 76, 72] },
  { id: 'barrio', number: '04', name: 'El barrio', purpose: 'Cinco perspectivas lectoras para cuestionar y mejorar las ideas. Son simulaciones, no datos de mercado.', place: 'El sofá y la mesa de centro', box: [28, 258, 136, 76] },
  { id: 'revision', number: '05', name: 'Revisión', purpose: 'Comprobar claridad, coherencia y evidencia antes de entregar.', place: 'El rincón tranquilo', box: [112, 182, 76, 72] },
  { id: 'relaciones', number: '06', name: 'Relaciones', purpose: 'Cuidar la conversación con la comunidad: comentarios, respuestas y mensajes.', place: 'La mesa de la cocina', box: [112, 30, 76, 80], isNew: true },
  { id: 'operacion', number: '07', name: 'Operación', purpose: 'Llevar a LinkedIn solo lo aprobado, dentro de topes, ventana horaria y pausas.', place: 'Junto a la puerta', box: [80, 30, 32, 52], isNew: true },
];

/** The library: not a team, but a zone. Tapping it opens the librarian. */
export const LIBRARY = { id: 'biblioteca' as const, name: 'Biblioteca', box: [4, 30, 76, 80] as Box };

const CX = 96;
const A1 = 110;
const A2 = 178;
const A3 = 254;

export const ROLES: readonly AgentRole[] = [
  // Strategy and profile: shared desks, facing their monitors.
  { id: 'posicionamiento', name: 'Posicionamiento', short: 'Posicionamiento', purpose: 'Nicho, comprador y propuesta de valor con evidencia tuya.', team: 'estrategia', sprite: 0, home: [132, 166], facing: 1, chair: 'north', monitor: [117, 116], via: [[CX, A2], [132, A2], [132, 166]] },
  { id: 'perfil', name: 'Perfil', short: 'Perfil', purpose: 'Titular, presentación y claridad del perfil, coherentes con el posicionamiento.', team: 'estrategia', sprite: 1, home: [168, 166], facing: 1, chair: 'north', monitor: [153, 116], via: [[CX, A2], [168, A2], [168, 166]] },
  // Observatory, next to the library.
  { id: 'investigador_referentes', name: 'Investigador de referentes', short: 'Investigador de referentes', purpose: 'Líderes y voces relevantes del barrio.', team: 'observatorio', sprite: 2, home: [24, 166], facing: 1, chair: 'north', monitor: [9, 116], via: [[CX, A2], [24, A2], [24, 166]] },
  { id: 'analista_barrio_resultados', name: 'Analista del barrio y resultados', short: 'Analista del barrio', purpose: 'Conversaciones, señales y resultados reales del barrio.', team: 'observatorio', sprite: 3, home: [60, 166], facing: 1, chair: 'north', monitor: [45, 116], via: [[CX, A2], [60, A2], [60, 166]] },
  // Editorial table.
  { id: 'director_editorial', name: 'Director editorial', short: 'Director editorial', purpose: 'Coordina ideas y selecciona propuestas.', team: 'editorial', sprite: 4, home: [26, 208], facing: 3, chair: 'back', monitor: null, via: [[CX, A2], [26, A2], [26, 208]] },
  { id: 'copywriter_a', name: 'Copywriter A', short: 'Copywriter A', purpose: 'Una primera manera de contar la idea.', team: 'editorial', sprite: 5, home: [58, 208], facing: 3, chair: 'back', monitor: null, via: [[CX, A2], [58, A2], [58, 208]] },
  { id: 'copywriter_b', name: 'Copywriter B', short: 'Copywriter B', purpose: 'Una alternativa independiente.', team: 'editorial', sprite: 6, home: [26, 248], facing: 1, chair: 'north', monitor: null, via: [[CX, A3], [26, A3], [26, 248]] },
  { id: 'editor_visual', name: 'Editor visual', short: 'Editor visual', purpose: 'Propone y prepara la foto, infografía o carrusel de la pieza; el director decide.', team: 'editorial', sprite: 8, home: [58, 248], facing: 1, chair: 'north', monitor: null, via: [[CX, A3], [58, A3], [58, 248]] },
  // The barrio: five simulated readers on the sofa and the poufs.
  { id: 'lector_comprador', name: 'Lector comprador', short: 'Lector comprador', purpose: 'Relevancia del problema y de la ayuda.', team: 'barrio', sprite: 7, home: [80, 286], facing: 3, chair: null, monitor: null, via: [[CX, A3], [124, A3], [124, 294], [80, 294], [80, 286]] },
  { id: 'lector_recomendador', name: 'Lector recomendador', short: 'Lector recomendador', purpose: 'A quién y cuándo recomendarte.', team: 'barrio', sprite: 8, home: [96, 286], facing: 3, chair: null, monitor: null, via: [[CX, A3], [124, A3], [124, 294], [96, 294], [96, 286]] },
  { id: 'lector_divulgador', name: 'Lector divulgador', short: 'Lector divulgador', purpose: 'Valor para compartir con su comunidad.', team: 'barrio', sprite: 9, home: [112, 286], facing: 3, chair: null, monitor: null, via: [[CX, A3], [124, A3], [124, 294], [112, 294], [112, 286]] },
  { id: 'lector_lider', name: 'Lector líder de opinión', short: 'Lector líder', purpose: 'Perspectiva, evidencia y conversación.', team: 'barrio', sprite: 10, home: [52, 322], facing: 0, chair: 'pouf', monitor: null, via: [[CX, A3], [52, A3], [52, 322]] },
  { id: 'lector_par', name: 'Lector par profesional', short: 'Lector par', purpose: 'Criterio y aprendizaje entre colegas.', team: 'barrio', sprite: 11, home: [140, 322], facing: 2, chair: 'pouf', monitor: null, via: [[CX, A3], [140, A3], [140, 322]] },
  // Review corner.
  { id: 'editor_verificador', name: 'Editor verificador', short: 'Editor verificador', purpose: 'Calidad, evidencia y coherencia antes de entregar.', team: 'revision', sprite: 12, home: [156, 240], facing: 1, chair: 'north', monitor: [141, 190], via: [[CX, A3], [156, A3], [156, 240]] },
  // Relations at the two gold chairs of the kitchen table.
  { id: 'relaciones_comunidad', name: 'Relaciones con la comunidad', short: 'Relaciones', purpose: 'Comentarios y respuestas en las conversaciones de los referentes.', team: 'relaciones', sprite: 5, home: [146, 100], facing: 1, chair: 'gold', monitor: null, via: [[CX, A1], [146, A1], [146, 100]] },
  { id: 'conversaciones_inbox', name: 'Conversaciones e inbox', short: 'Conversaciones', purpose: 'Mensajes directos y conversaciones privadas.', team: 'relaciones', sprite: 10, home: [170, 100], facing: 1, chair: 'gold', monitor: null, via: [[CX, A1], [170, A1], [170, 100]] },
  // The account operator stands by the door. It is a service, not an AI agent.
  { id: 'operador_cuenta', name: 'Operador de cuenta', short: 'Operación', purpose: 'Observa a los referentes, ejecuta lo aprobado y concilia el resultado en la cuenta de LinkedIn.', team: 'operacion', sprite: 4, home: [CX, 58], facing: 3, chair: null, monitor: null, via: [[CX, 58]], service: true },
];

/** Librarian: person9 recoloured (grey hair, glasses, aquamarine jacket), behind the library counter. */
export const LIBRARIAN: Role = {
  id: LIBRARIAN_ID,
  name: 'Bibliotecario',
  short: 'Bibliotecario',
  purpose: 'Busca en la biblioteca lo que cada agente necesita: las clases del curso y lo que el equipo sabe de ti.',
  team: 'biblioteca',
  sprite: 13,
  home: [42, 84],
  facing: 3,
  chair: null,
  monitor: null,
  via: [[CX, A1], [42, A1], [42, 84]],
  service: true,
};

/** Every character, the librarian first (as in the design). */
export const CHARACTERS: readonly Role[] = [LIBRARIAN, ...ROLES];

export const ROLE_BY_ID: Readonly<Record<RoleId, AgentRole>> = Object.fromEntries(ROLES.map((r) => [r.id, r])) as Record<RoleId, AgentRole>;

export const CHARACTER_BY_ID: Readonly<Record<CharacterId, Role>> = { ...ROLE_BY_ID, [LIBRARIAN_ID]: LIBRARIAN };

export function isRoleId(value: unknown): value is RoleId {
  'worklet';
  return typeof value === 'string' && (ROLE_IDS as readonly string[]).includes(value);
}

export function isCharacterId(value: unknown): value is CharacterId {
  'worklet';
  return value === LIBRARIAN_ID || isRoleId(value);
}

export function rolesOfTeam(team: TeamId): AgentRole[] {
  'worklet';
  return ROLES.filter((r) => r.team === team);
}

export function teamById(team: TeamId): Team {
  'worklet';
  const found = TEAMS.find((t) => t.id === team);
  if (!found) throw new Error(`Equipo desconocido: ${team}`);
  return found;
}

/** «Mesa editorial», or «Biblioteca» for the library. */
export function zoneName(zone: ZoneId): string {
  'worklet';
  return zone === 'biblioteca' ? LIBRARY.name : teamById(zone).name;
}

/** Sprite sheets in the pack without a `reading` animation. */
export const SPRITES_WITHOUT_READING: ReadonlySet<number> = new Set([11]);
