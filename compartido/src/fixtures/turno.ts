// Bandeja de entrada, «Lo que el equipo sabe de ti» and Notificaciones sample data, shaped like the backend
// of CONTRATO-API «Rediseño» plus the rev 18 fields (priority, state, items, vistos, notificaciones).
import type { NotificationItem, Notificaciones } from '../api/notificaciones';
import type { MemoryFact, Question, TuTurno, TurnoCard } from '../api/types';

const HOUR = 3_600_000;

/** An ISO instant `hours` from now (negative: in the past). */
export function hoursFromNow(hours: number, now: number = Date.now()): string {
  return new Date(now + hours * HOUR).toISOString();
}

/** Local time `days` from today at hh:mm, as ISO. */
export function dayAt(days: number, hour: number, minute = 0, now: number = Date.now()): string {
  const date = new Date(now);
  date.setDate(date.getDate() + days);
  date.setHours(hour, minute, 0, 0);
  return date.toISOString();
}

/**
 * An empty GET /tu-turno, like `tuTurnoFixture` of test/app.tsx but without importing the whole app,
 * so these screens' tests do not depend on the other views compiling.
 */
export function turnoFixture(overrides: Partial<TuTurno> = {}): TuTurno {
  return {
    count: 0,
    critical: false,
    counts: { avisos: 0, preguntas: 0, tareas: 0 },
    top: null,
    alerts: [],
    questions: [],
    later: [],
    tasks: { perfil: [], conversaciones: [] },
    recent: [],
    summary: { done_today: { posts: 0, comments: 0, reactions: 0, follows: 0, invites: 0, accepts: 0 }, next_piece: null },
    ...overrides,
  };
}

export function questionFixture(overrides: Partial<Question> = {}): Question {
  return {
    id: 'q1',
    kind: 'ask',
    agent: 'director_editorial',
    agent_label: 'Director editorial',
    question: '¿Has liderado la migración de un monolito a microservicios en una startup?',
    purpose: 'Para el post del jueves sobre arquitectura. Sin un caso real, el post se queda en opinión.',
    answer_type: 'yes_no',
    options: [],
    memory_key: 'experiencia.migracion',
    proposed_value: null,
    suggested_public: true,
    deadline: null,
    postponed_until: null,
    pending: true,
    expired: false,
    origin: 'piece:p1',
    state: 'open',
    answer: '',
    public_use: null,
    answered_at: null,
    created_at: hoursFromNow(-3),
    ...overrides,
  };
}

export function cardFixture(overrides: Partial<TurnoCard> = {}): TurnoCard {
  return {
    id: 'linkedin_expiring',
    type: 'aviso',
    critical: false,
    tone: 'warn',
    agent: 'operador_cuenta',
    agent_label: 'Operador de cuenta',
    title: 'Reconecta LinkedIn',
    body: 'El permiso para publicar caduca pronto.',
    deadline: null,
    created_at: hoursFromNow(-48),
    actions: [],
    ...overrides,
  };
}

export function questionCard(question: Partial<Question> = {}, overrides: Partial<TurnoCard> = {}): TurnoCard {
  const q = questionFixture(question);
  return cardFixture({
    id: `question:${q.id}`,
    type: 'pregunta',
    tone: 'info',
    agent: q.agent,
    agent_label: q.agent_label,
    title: q.question,
    body: q.purpose,
    deadline: q.deadline,
    created_at: q.created_at,
    priority: 'cuando_puedas',
    state: 'vista',
    actions: [
      { label: 'Responder', endpoint: `/api/v1/preguntas/${q.id}/responder`, primary: true },
      { label: 'Más tarde', endpoint: `/api/v1/preguntas/${q.id}/mas-tarde` },
      { label: 'No quiero compartir esto', endpoint: `/api/v1/preguntas/${q.id}/no-compartir` },
    ],
    question: q,
    ...overrides,
  });
}

export const UNCERTAIN_CARD: TurnoCard = cardFixture({
  id: 'uncertain:a1',
  critical: true,
  tone: 'bad',
  title: '¿Salió o no?',
  body: 'El proveedor no confirmó si se aplicó. Comprueba en LinkedIn.',
  created_at: hoursFromNow(-14),
  priority: 'urgente',
  state: 'nueva',
  actions: [
    { label: 'Sí, se aplicó', endpoint: '/api/v1/operador/actions/a1/resolve', body: { outcome: 'confirmed' }, note_required: true, primary: true },
    { label: 'No se aplicó', endpoint: '/api/v1/operador/actions/a1/resolve', body: { outcome: 'failed' }, note_required: true },
  ],
  attempt: {
    capability: 'INT-03',
    label: 'Comentario',
    text: 'Scoping from the decision a feature supports is what keeps the first version small.',
    reaction: null,
    target: { kind: 'post', name: 'Pablo Ficticio', url: 'https://www.linkedin.com/feed/update/urn:li:activity:1' },
    at: hoursFromNow(-14),
    url: 'https://www.linkedin.com/feed/update/urn:li:activity:1',
  },
});

export const EXPIRING_CARD: TurnoCard = cardFixture({
  id: 'linkedin_expiring',
  deadline: hoursFromNow(72),
  priority: 'importante',
  state: 'vista',
  actions: [{ label: 'Reconectar LinkedIn', href: '/api/v1/linkedin/oauth/start', primary: true }],
});

/** A follow (RED-01) in `approval` mode, waiting for Gustavo: Aprobar sends the exact version, Vetar discards the person. */
export const APPROVAL_CARD: TurnoCard = cardFixture({
  id: 'approval:a-1',
  type: 'aprobacion',
  tone: 'warn',
  priority: 'importante',
  state: 'nueva',
  agent: 'relaciones_comunidad',
  agent_label: 'Relaciones con la comunidad',
  title: '¿Apruebas seguir a Laura Prueba?',
  body: 'Lidera producto en un marketplace B2B.',
  deadline: hoursFromNow(40),
  created_at: hoursFromNow(-5),
  actions: [
    { label: 'Aprobar', endpoint: '/api/v1/operador/actions/a-1/approve', body: { expected_hash: 'a'.repeat(64) }, primary: true },
    { label: 'Vetar', endpoint: '/api/v1/operador/actions/a-1/reject', note_required: true },
    { label: 'Ver ficha', href: '/personas/c-9' },
  ],
  approval: {
    proposal_id: 'a-1',
    capability: 'RED-01',
    label: 'Seguimiento',
    text: null,
    reaction: null,
    target: { kind: 'person', name: 'Laura Prueba', headline: 'Head of Product en un marketplace B2B', url: null, contact_id: 'c-9', role: 'comprador' },
    piece_id: null,
    network: true,
    expires_at: hoursFromNow(40),
  },
});

export function factFixture(overrides: Partial<MemoryFact> = {}): MemoryFact {
  return {
    key: 'idioma.textos',
    topic: 'Idioma de los textos públicos',
    text: 'Inglés. Con personas hispanohablantes, las conversaciones pueden ir en español.',
    public_use: true,
    version: 1,
    edits: 1,
    origin: { kind: 'question', agent: 'perfil', agent_label: 'Perfil', question: '¿En qué idioma van tus textos públicos?' },
    updated_at: hoursFromNow(-48),
    ...overrides,
  };
}

export function notificationFixture(overrides: Partial<NotificationItem> = {}): NotificationItem {
  return {
    id: 'n1',
    kind: 'piece_published',
    layer: 'publicaciones',
    title: 'Publicaste «Scope features from the decision they support.»',
    detail: 'Las impresiones a las 24 h llegan mañana.',
    link: '/calendario/pieza/p1',
    at: hoursFromNow(-1),
    read: false,
    ...overrides,
  };
}

export function notificacionesFixture(overrides: Partial<Notificaciones> = {}): Notificaciones {
  return {
    upcoming: [
      notificationFixture({
        id: 'piece_scheduled:p2',
        kind: 'piece_scheduled',
        title: 'Sale la pieza «Turning a sales call into a product spec.»',
        detail: 'Puedes vetarla en el detalle hasta esa hora.',
        link: '/calendario/pieza/p2',
        at: dayAt(1, 9),
        read: undefined,
      }),
    ],
    items: [
      notificationFixture({ id: 'n-hoy', at: dayAt(0, 0, 30) }),
      notificationFixture({
        id: 'n-ayer',
        kind: 'piece_blocked',
        layer: 'sistema',
        title: 'El verificador bloqueó la pieza del viernes',
        detail: 'Afirmaba una experiencia que no está en tu memoria.',
        link: '/calendario/pieza/p3',
        at: dayAt(-1, 7, 40),
        read: true,
      }),
      notificationFixture({
        id: 'n-antes',
        kind: 'connection_fit',
        layer: 'red',
        title: 'Diego Supuesto aceptó tu invitación',
        detail: 'Founder @ Rumbo Pagos (seed) · Comprador',
        link: '/personas/c1',
        at: dayAt(-3, 11, 20),
        read: true,
      }),
    ],
    unread: 1,
    ...overrides,
  };
}

/** C2 «Conversación que te toca», as rediseno_views builds it. */
export const CONVERSATION_CARD: TurnoCard = cardFixture({
  id: 'conversation:conv-1:3f2a9c1b7e',
  type: 'conversacion',
  tone: 'warn',
  priority: 'importante',
  state: 'nueva',
  agent: 'conversaciones_inbox',
  agent_label: 'Conversaciones e inbox',
  title: 'Lucía Ficticia te escribió',
  body: 'Posible oportunidad: ProjectApp (86 %) · Espera tu respuesta (81 %)',
  created_at: hoursFromNow(-2),
  actions: [
    { label: 'Abrir en LinkedIn', href: 'https://www.linkedin.com/messaging/thread/2-SHVlcnRhTGFicw==/', primary: true },
    { label: 'Hecho, respondí', endpoint: '/api/v1/conversaciones/conv-1/cerrar', body: { how: 'respondi' } },
    {
      label: 'Marcar como oportunidad',
      opportunity: {
        contact: 'c-1',
        display_name: 'Lucía Ficticia',
        headline: 'Cofundadora @ Huerta Labs (pre-seed)',
        modality: 'projectapp',
        channel: 'linkedin',
        notes: 'Detectada por el equipo en una conversación de LinkedIn.',
      },
    },
    { label: 'No responder', endpoint: '/api/v1/conversaciones/conv-1/cerrar', body: { how: 'no_responder' }, note_optional: true },
  ],
  conversation: {
    id: 'conv-1',
    chat_url: 'https://www.linkedin.com/messaging/thread/2-SHVlcnRhTGFicw==/',
    attendee_name: 'Lucía Ficticia',
    contact_id: 'c-1',
    last_message_at: hoursFromNow(-2),
    last_from_me: false,
    last_message_preview: 'Hola Gustavo, ¿tienes disponibilidad para un proyecto corto de IA en enero?',
    messages: [
      { id: 'm-1', at: hoursFromNow(-50), from_me: true, text: 'Thanks Lucía! Happy to share how we scoped it if useful.' },
      { id: 'm-2', at: hoursFromNow(-2), from_me: false, text: 'Hola Gustavo, ¿tienes disponibilidad para un proyecto corto de IA en enero?' },
    ],
    assessment: {
      message_id: 'm-2',
      opportunity: true,
      awaiting_reply: true,
      pitch: false,
      modality: 'projectapp',
      answers: { oportunidad: 0.86, espera: 0.81, venta: 0.04 },
      model: 'jev-1.14.0',
      at: hoursFromNow(-1),
    },
    why: 'Posible oportunidad: ProjectApp (86 %) · Espera tu respuesta (81 %)',
    needs_you: true,
    person: {
      id: 'c-1',
      display_name: 'Lucía Ficticia',
      headline: 'Cofundadora @ Huerta Labs (pre-seed)',
      profile_url: 'https://www.linkedin.com/in/lucia-ficticia',
      role: 'comprador',
      modality: 'projectapp',
    },
  },
});

/** INT-04: someone who conversed with the team on his post is now a connection; the team drafted a first message. */
export const MESSAGE_CARD: TurnoCard = cardFixture({
  id: 'dm:pc-1',
  type: 'mensaje',
  tone: 'info',
  priority: 'importante',
  state: 'nueva',
  agent: 'relaciones_comunidad',
  agent_label: 'Relaciones y comunidad',
  title: 'Marta Ejemplo aceptó tu invitación',
  body: 'Venían hablando de «Most feature requests arrive as a solution» en tu post. El equipo te dejó un primer mensaje; lo envías tú desde LinkedIn.',
  created_at: hoursFromNow(-1),
  actions: [
    { label: 'Abrir su perfil', href: 'https://www.linkedin.com/in/marta-ejemplo', primary: true },
    { label: 'Hecho, le escribí', endpoint: '/api/v1/respuestas/pc-1/mensaje', body: { how: 'enviado' } },
    { label: 'No escribirle', endpoint: '/api/v1/respuestas/pc-1/mensaje', body: { how: 'no' }, note_optional: true },
  ],
  message: {
    text: 'Marta, gracias por seguir la conversación del post. ¿Cómo lo están resolviendo en tu equipo hoy?',
    comment: 'We ask customers for the problem first, but they still bring a feature list.',
    reply: 'That list is still useful: we read it as symptoms and ask what broke the week before.',
    piece_id: 'p7',
    topic: 'Most feature requests arrive as a solution',
    person: {
      id: 'c-9',
      display_name: 'Marta Ejemplo',
      headline: 'Head of Product @ Ejemplo SaaS',
      profile_url: 'https://www.linkedin.com/in/marta-ejemplo',
      role: 'par',
    },
  },
});

/**
 * A date he asked for that cannot be kept (14/11/2026): that day already has the daily post and another one he asked
 * for. A date that can be kept never asks: it goes out as an extra post that day.
 */
export const DAY_REQUEST_CARD: TurnoCard = cardFixture({
  id: 'day_request:cap-1',
  type: 'fecha',
  tone: 'info',
  priority: 'importante',
  state: 'nueva',
  agent: 'director_editorial',
  agent_label: 'Director editorial',
  title: 'No puedo publicarlo cuando pediste',
  body: 'Ese día ya tiene dos posts: el diario y otro que pediste. Pediste «lo publiques mañana a las 12 del día, del mediodía». Mientras decides, la idea espera.',
  deadline: null,
  created_at: hoursFromNow(-1),
  actions: [
    { label: 'Al primer día libre', endpoint: '/api/v1/capturas/cap-1/fecha', body: { decision: 'siguiente' }, primary: true },
    { label: 'Descartarla', endpoint: '/api/v1/capturas/cap-1/fecha', body: { decision: 'descartar' } },
  ],
  day_request: {
    capture_id: 'cap-1',
    asked_at: hoursFromNow(21),
    evidence: 'lo publiques mañana a las 12 del día, del mediodía',
    problem: 'llena',
    problem_label: 'Ese día ya tiene dos posts: el diario y otro que pediste.',
    idea: 'How do founders decide how long to fund a business that loses money?',
    piece: null,
    others: [],
  },
});
