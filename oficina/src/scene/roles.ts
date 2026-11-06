// Teams, roles and their places in the apartment. Coordinates are in the scene's
// logical pixels (480×330); the canvas draws them at 2× (960×660).

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

export type TeamId =
  | 'estrategia'
  | 'observatorio'
  | 'editorial'
  | 'barrio'
  | 'revision'
  | 'relaciones'
  | 'operacion';

export interface Role {
  id: RoleId;
  name: string;
  purpose: string;
  team: TeamId;
  /** LimeZu character sheet `person<N>` (0–12). The three new roles reuse sheets. */
  sprite: number;
  home: Point;
  facing: Direction;
  /** Chair drawn in front of the seated character, hidden behind it while away. */
  chair: 'north' | 'gold' | null;
  /** Route from the seat to the central corridor (190,186), for ambient walks. */
  exit: readonly Point[] | null;
  /** Desk monitor that lights up only while this role is really working. */
  monitor: { x: number; y: number; w: number; h: number; kind: 0 | 1 | 2 } | null;
  /** True for software services that are not AI agents. */
  service?: boolean;
}

export interface Team {
  id: TeamId;
  name: string;
  icon: string;
  purpose: string;
  place: string;
  label: Point;
  box: readonly [number, number, number, number];
  isNew?: boolean;
}

export const TEAMS: readonly Team[] = [
  {
    id: 'estrategia',
    name: 'Estrategia y perfil',
    icon: '◇',
    purpose: 'Encontrar tu posición y hacer que tu perfil la comunique.',
    place: 'Los escritorios compartidos',
    label: [122, 76],
    box: [52, 87, 128, 68],
  },
  {
    id: 'observatorio',
    name: 'Observatorio',
    icon: '⌕',
    purpose: 'Escuchar al barrio y descubrir referentes, preguntas y oportunidades.',
    place: 'Junto a los ventanales',
    label: [279, 76],
    box: [207, 87, 135, 68],
  },
  {
    id: 'editorial',
    name: 'Mesa editorial',
    icon: '✎',
    purpose: 'Elegir una idea con intención y explorar dos maneras de contarla.',
    place: 'La mesa larga',
    label: [111, 181],
    box: [48, 192, 130, 98],
  },
  {
    id: 'barrio',
    name: 'El barrio',
    icon: '◌',
    purpose: 'Cinco perspectivas lectoras para cuestionar y mejorar las ideas. Son simulaciones, no datos de mercado.',
    place: 'El sofá y la mesa de centro',
    label: [275, 181],
    box: [211, 193, 130, 99],
  },
  {
    id: 'revision',
    name: 'Revisión',
    icon: '✓',
    purpose: 'Comprobar claridad, coherencia y evidencia antes de entregar.',
    place: 'El rincón tranquilo',
    label: [405, 195],
    box: [370, 206, 72, 77],
  },
  {
    id: 'relaciones',
    name: 'Relaciones',
    icon: '❝',
    purpose: 'Cuidar la conversación con la comunidad: comentarios, respuestas y mensajes.',
    place: 'La mesa de la cocina',
    label: [401, 160],
    box: [366, 106, 70, 47],
    isNew: true,
  },
  {
    id: 'operacion',
    name: 'Operación',
    icon: '⚙',
    purpose: 'Llevar a LinkedIn solo lo aprobado, dentro de topes, ventana horaria y pausas.',
    place: 'Junto a la puerta',
    label: [192, 62],
    box: [180, 70, 26, 34],
    isNew: true,
  },
];

const DESK_EXIT_STRATEGY = (x: number): Point[] => [[x, 148], [190, 148], [190, 186]];
const DESK_EXIT_RESEARCH = (x: number): Point[] => [[x, 136], [345, 136], [345, 186], [190, 186]];
const READER_EXIT_SOFA = (x: number): Point[] => [[x, 242], [220, 242], [190, 242], [190, 186]];

export const ROLES: readonly Role[] = [
  // Strategy and profile: desk workers facing their monitors.
  { id: 'posicionamiento', name: 'Posicionamiento', purpose: 'Nicho, comprador y propuesta de valor con evidencia tuya.', team: 'estrategia', sprite: 0, home: [93, 126], facing: 1, chair: 'north', exit: DESK_EXIT_STRATEGY(93), monitor: { x: 79, y: 89, w: 24, h: 20, kind: 0 } },
  { id: 'perfil', name: 'Perfil', purpose: 'Titular, presentación y claridad del perfil, coherentes con el posicionamiento.', team: 'estrategia', sprite: 1, home: [153, 126], facing: 1, chair: 'north', exit: DESK_EXIT_STRATEGY(153), monitor: { x: 139, y: 89, w: 24, h: 20, kind: 0 } },
  // Observatory.
  { id: 'investigador_referentes', name: 'Investigador de referentes', purpose: 'Líderes y voces relevantes del barrio.', team: 'observatorio', sprite: 2, home: [249, 126], facing: 1, chair: 'north', exit: DESK_EXIT_RESEARCH(249), monitor: { x: 234, y: 89, w: 24, h: 20, kind: 1 } },
  { id: 'analista_barrio_resultados', name: 'Analista del barrio y resultados', purpose: 'Conversaciones, señales y resultados reales del barrio.', team: 'observatorio', sprite: 3, home: [309, 126], facing: 1, chair: 'north', exit: DESK_EXIT_RESEARCH(309), monitor: { x: 294, y: 89, w: 24, h: 20, kind: 1 } },
  // Editorial table.
  { id: 'director_editorial', name: 'Director editorial', purpose: 'Coordina ideas y selecciona propuestas.', team: 'editorial', sprite: 4, home: [80, 229], facing: 3, chair: null, exit: [[80, 195], [190, 195], [190, 186]], monitor: null },
  { id: 'copywriter_a', name: 'Copywriter A', purpose: 'Una primera manera de contar la idea.', team: 'editorial', sprite: 5, home: [144, 229], facing: 3, chair: null, exit: [[144, 195], [190, 195], [190, 186]], monitor: null },
  { id: 'copywriter_b', name: 'Copywriter B', purpose: 'Una alternativa independiente.', team: 'editorial', sprite: 6, home: [112, 279], facing: 1, chair: 'north', exit: [[112, 282], [190, 282], [190, 186]], monitor: null },
  // The barrio: five simulated readers on the sofa and easy chairs.
  { id: 'lector_comprador', name: 'Lector comprador', purpose: 'Relevancia del problema y de la ayuda.', team: 'barrio', sprite: 7, home: [243, 226], facing: 3, chair: null, exit: READER_EXIT_SOFA(243), monitor: null },
  { id: 'lector_recomendador', name: 'Lector recomendador', purpose: 'A quién y cuándo recomendarte.', team: 'barrio', sprite: 8, home: [274, 226], facing: 3, chair: null, exit: READER_EXIT_SOFA(274), monitor: null },
  { id: 'lector_divulgador', name: 'Lector divulgador', purpose: 'Valor para compartir con su comunidad.', team: 'barrio', sprite: 9, home: [307, 226], facing: 3, chair: null, exit: READER_EXIT_SOFA(307), monitor: null },
  { id: 'lector_lider', name: 'Lector líder de opinión', purpose: 'Perspectiva, evidencia y conversación.', team: 'barrio', sprite: 10, home: [242, 278], facing: 3, chair: null, exit: [[220, 278], [190, 278], [190, 186]], monitor: null },
  { id: 'lector_par', name: 'Lector par profesional', purpose: 'Criterio y aprendizaje entre colegas.', team: 'barrio', sprite: 11, home: [308, 278], facing: 3, chair: null, exit: [[308, 286], [190, 286], [190, 186]], monitor: null },
  // Review corner.
  { id: 'editor_verificador', name: 'Editor verificador', purpose: 'Calidad, evidencia y coherencia antes de entregar.', team: 'revision', sprite: 12, home: [406, 247], facing: 1, chair: 'north', exit: [[368, 247], [368, 202], [345, 202], [345, 186], [190, 186]], monitor: { x: 391, y: 211, w: 25, h: 21, kind: 2 } },
  // New: Relations at the two gold chairs of the kitchen table.
  { id: 'relaciones_comunidad', name: 'Relaciones con la comunidad', purpose: 'Comentarios y respuestas en las conversaciones de los referentes.', team: 'relaciones', sprite: 5, home: [386, 139], facing: 1, chair: 'gold', exit: null, monitor: null },
  { id: 'conversaciones_inbox', name: 'Conversaciones e inbox', purpose: 'Mensajes directos y conversaciones privadas.', team: 'relaciones', sprite: 10, home: [419, 139], facing: 1, chair: 'gold', exit: null, monitor: null },
  // New: the account operator stands by the door. It is a service, not an AI agent.
  { id: 'operador_cuenta', name: 'Operador de cuenta', purpose: 'Observa a los referentes, ejecuta lo aprobado y concilia el resultado en la cuenta de LinkedIn.', team: 'operacion', sprite: 4, home: [193, 98], facing: 3, chair: null, exit: null, monitor: null, service: true },
];

export const ROLE_BY_ID: Readonly<Record<RoleId, Role>> = Object.fromEntries(ROLES.map((r) => [r.id, r])) as Record<RoleId, Role>;

export function rolesOfTeam(team: TeamId): Role[] {
  return ROLES.filter((r) => r.team === team);
}

export function teamById(team: TeamId): Team {
  const found = TEAMS.find((t) => t.id === team);
  if (!found) throw new Error(`Equipo desconocido: ${team}`);
  return found;
}

/** Sprite sheets in the pack without a `reading` animation. */
export const SPRITES_WITHOUT_READING: ReadonlySet<number> = new Set([11]);

/** The thirteen original characters take turns for ambient walks, as before. */
export const WALKERS: readonly RoleId[] = ROLES.filter((r) => r.exit).map((r) => r.id);
