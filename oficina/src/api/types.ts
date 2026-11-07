// Shapes from oficina/CONTRATO-API.md. Fields the contract does not fix are optional.

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface User {
  username: string;
  is_superuser: boolean;
  permissions: string[];
}

export interface Session {
  authenticated: boolean;
  user: User | null;
}

// ---------------------------------------------------------------- machine

export type ControlSource = 'db' | 'env' | 'none';

export interface Control {
  paused: boolean;
  reason: string;
  source: ControlSource;
  updated_at: string | null;
  updated_by: string | null;
}

export interface WindowInfo {
  start: string;
  end: string;
  timezone: string;
  open_now: boolean;
  min_spacing_seconds: number;
}

export interface CapacityInfo {
  daily: number;
  weekly: number;
  daily_used: number;
  weekly_used: number;
  left: number;
}

export interface Account {
  id: string;
  label: string;
  provider: string;
  status: string;
  is_locked: boolean;
  paused: boolean;
  paused_reason: string;
  last_checked_at: string | null;
  capacity?: Record<string, CapacityInfo>;
}

export interface Overview {
  autopilot: { enabled: boolean; policy_version: string };
  control: Control;
  window: WindowInfo;
  accounts: Account[];
  today: {
    proposals: Record<string, number>;
    llm_spent_usd: string;
    llm_daily_cap_usd: string;
    drafts: number;
    drafts_daily_cap: number;
    // Daily own publication: separate editorial budget (absent on older backends).
    editorial_llm_spent_usd?: string;
    editorial_llm_daily_cap_usd?: string;
  };
  counts: { referents: number; posts: number; uncertain: number };
}

export interface FeedEvent {
  id: string | number;
  action: string;
  target: string;
  created_at: string;
  actor: string | null;
  metadata: Record<string, unknown>;
}

// ---------------------------------------------------------------- actions

export const ACTION_STATES = [
  'proposed',
  'approved',
  'rejected',
  'superseded',
  'discarded',
  'executing',
  'sent',
  'confirmed',
  'uncertain',
  'failed',
  'expired',
] as const;

export type ActionState = (typeof ACTION_STATES)[number];

export interface ObservedPost {
  id: string;
  author_name: string;
  text: string;
  share_url: string;
  posted_at: string | null;
}

export interface Execution {
  id?: string;
  state: string;
  provider?: string;
  external_id: string | null;
  external_url: string | null;
  error_kind?: string;
  note: string;
  http_status: number | null;
  started_at: string | null;
  finished_at: string | null;
  reconciled_at?: string | null;
}

/**
 * INT-03 comment and INT-02 reaction on someone else's post; CONT-09 own publication; RED-01 follow,
 * RED-02 connection invitation without a note and RED-04 accepting a received invitation (network block).
 */
export const CAPABILITIES = ['INT-03', 'INT-02', 'CONT-09', 'RED-01', 'RED-02', 'RED-04'] as const;
export type Capability = (typeof CAPABILITIES)[number];

export const NETWORK_CAPABILITIES = ['RED-01', 'RED-02', 'RED-04'] as const;
export type NetworkCapability = (typeof NETWORK_CAPABILITIES)[number];

export interface Action {
  id: string;
  account_id?: string;
  capability: Capability;
  /** `text` (INT-03, CONT-09), `reaction` (INT-02), `user_id` and, for RED-04, `request_id` (network). */
  payload: { text?: string; reaction?: string; user_id?: string; request_id?: string };
  payload_hash: string;
  version: number;
  previous_id?: string | null;
  state: ActionState;
  source: 'agent' | 'human';
  rationale: string;
  citations: string[];
  risks: string[];
  model?: string;
  approved_hash?: string;
  decision_note: string;
  decided_at: string | null;
  created_at: string;
  /** Someone else's post for INT-03/INT-02; always null for an own publication (CONT-09). */
  post: ObservedPost | null;
  /** CONT-09 only: the editorial piece and its scheduled hour; null otherwise. */
  piece_id: string | null;
  scheduled_for: string | null;
  execution: Execution | null;
  /** RED-* only: the person the action targets; null on INT-* and CONT-09 (absent on backends without the network block). */
  contact?: ContactBrief | null;
}

// ---------------------------------------------------------------- network (Red)

export type ContactStage = 'candidate' | 'fit' | 'discarded' | 'followed' | 'invited' | 'connected' | 'closed' | 'incoming';

/** Funnel order, used by the filter chips. */
export const CONTACT_STAGES: readonly ContactStage[] = ['candidate', 'fit', 'followed', 'invited', 'connected', 'incoming', 'closed', 'discarded'];

export type ContactSource = 'commenter' | 'search' | 'incoming' | 'manual';

export type NetworkDistance = 'FIRST_DEGREE' | 'SECOND_DEGREE' | 'THIRD_DEGREE' | 'OUT_OF_NETWORK' | '';

/** Why the contact was found; a field that does not apply to its `source` is null. */
export interface ContactEvidence {
  post_id?: string | null;
  post_url?: string | null;
  referent?: string | null;
  comment?: string | null;
  query?: string | null;
  invitation_message?: string | null;
}

/** `{}` until the model has classified the contact, so every field is optional. */
export interface ContactClassification {
  fit?: boolean;
  role?: string;
  modality?: string;
  affinity?: string;
  reason?: string;
  confidence?: number;
  model?: string;
  classified_at?: string;
}

/** The contact as embedded in a RED-* action. */
export interface ContactBrief {
  id: string;
  display_name: string;
  headline: string;
  profile_url: string;
  public_identifier: string;
  network_distance: NetworkDistance;
  stage: ContactStage;
  source: ContactSource;
  evidence: ContactEvidence;
  classification: ContactClassification;
}

export type ContactEvent =
  | 'discovered'
  | 'classified'
  | 'followed'
  | 'invited'
  | 'connected'
  | 'closed'
  | 'discarded'
  | 'rejected'
  | 'incoming'
  | 'note';

export interface ContactHistoryEntry {
  at: string;
  event: ContactEvent;
  detail: string;
}

export interface ContactOpenAction {
  id: string;
  capability: Capability;
  state: ActionState;
}

/** `GET /api/v1/red/contacts` and `/api/v1/red/contacts/<id>`. */
export interface Contact extends ContactBrief {
  account_id: string;
  provider_user_id: string;
  location: string;
  is_following: boolean;
  history: ContactHistoryEntry[];
  followed_at: string | null;
  invited_at: string | null;
  connected_at: string | null;
  discovered_at: string;
  updated_at: string;
  open_action: ContactOpenAction | null;
  // Redesign fields (absent on older backends).
  /** Stage as shown in Personas: the contact stage, or `opportunity` while it has an open opportunity. */
  display_stage?: DisplayStage;
  notes?: ContactNote[];
  opportunity?: ContactOpportunity | null;
  next_step?: ContactNextStep | null;
  /** True when the person has an item in Tu turno («Te toca»). */
  your_turn?: boolean;
  last_event?: ContactHistoryEntry | null;
}

/** Contact stage plus `opportunity` (an open opportunity), the stages Personas shows. */
export type DisplayStage = ContactStage | 'opportunity';

export interface ContactNote {
  id: string;
  at: string;
  text: string;
  by: string;
}

export interface ContactOpportunity {
  id: string;
  stage: OpportunityStage;
  stage_label: string;
  modality: string;
  next_action: string;
  next_action_at: string | null;
}

export interface ContactNextStep {
  owner: 'equipo' | 'gustavo' | null;
  text: string;
  at: string | null;
  action?: { id: string; capability: Capability; state: ActionState } | null;
}

export type AutonomyMode = 'auto' | 'approval' | 'off';

export interface NetworkCapacity extends CapacityInfo {
  mode: AutonomyMode;
}

export type NetworkRead = 'comments' | 'search' | 'profile' | 'sync';

/** `GET /api/v1/red/summary`. */
export interface RedSummary {
  /** False when the block is off (`NETWORK_ENABLED=false`). */
  enabled: boolean;
  /** `opportunity` counts open opportunities; `conversation` is null until the inbox arrives. */
  stages: Partial<Record<ContactStage, number>> & { opportunity?: number; conversation?: number | null };
  capacity: Partial<Record<NetworkCapability, NetworkCapacity>>;
  reads_today: Partial<Record<NetworkRead, number>>;
  read_caps: Partial<Record<NetworkRead, number>>;
  /** USD as JSON numbers (the overview sends its budget as decimal strings). */
  llm: { spent_today: number; daily: number; model: string };
  /** LinkedIn rejected invitations for hitting its limit in the last 7 days: invitations are paused. */
  invites_blocked: { blocked: boolean; reason: string };
  last_discovery_at: string | null;
  last_sync_at: string | null;
}

// ---------------------------------------------------------------- editorial (daily own publication)

/** Circuit state of a piece; once its CONT-09 action exists, `status` follows the action. */
export type PieceState = 'preparing' | 'skipped' | 'blocked' | 'failed' | 'ready';

export type PieceStatus =
  | 'preparing'
  | 'skipped'
  | 'blocked'
  | 'failed'
  | 'awaiting_approval'
  | 'scheduled'
  | 'publishing'
  | 'published'
  | 'uncertain'
  | 'vetoed'
  | 'discarded'
  | 'expired'
  | 'superseded';

export type EditorialStage = '' | 'director' | 'redactor' | 'lectores' | 'seleccion' | 'verificador';

export interface PieceActionRef {
  id: string;
  state: ActionState;
  payload_hash: string;
}

export interface PieceSummary {
  id: string;
  slot_date: string;
  scheduled_for: string;
  state: PieceState;
  status: PieceStatus;
  stage: EditorialStage;
  note: string;
  modality: string | null;
  pillar: string | null;
  primary_reader: string | null;
  thesis: string | null;
  approach: string | null;
  action: PieceActionRef | null;
  external_url: string | null;
  created_at: string;
}

export interface CalendarDay {
  date: string;
  pieces: PieceSummary[];
}

export interface EditorialCalendar {
  timezone: string;
  post_time: string | null;
  lead_hours: number;
  config_error: string | null;
  today: string;
  days: CalendarDay[];
}

// The JSON blocks below are written by each stage of the circuit (model output with a schema). A
// stage that has not run yet leaves its block empty (`{}`), so every field is optional.

export interface Claim {
  text: string;
  kind?: string;
  status?: string;
  ref?: string;
}

export interface Brief {
  decision?: 'write' | 'skip';
  skip_reason?: string;
  primary_reader?: string;
  modality?: string;
  pillar?: string;
  thesis?: string;
  approach?: string;
  format?: string;
  reader_value?: string;
  evidence?: { kind: string; ref: string; note: string }[];
  success_criterion?: string;
  avoid?: string[];
  signals_used?: string[];
  citations?: string[];
  rationale?: string;
}

export interface Variant {
  angle?: string;
  text?: string;
  claims?: Claim[];
  uncertainties?: string[];
}

export interface Variants {
  variant_a?: Variant;
  variant_b?: Variant;
  citations?: string[];
}

export type ObjectionSeverity = 'material' | 'preference' | 'missing_data';

export interface Assessment {
  strengths?: string[];
  objections?: { text: string; severity: ObjectionSeverity }[];
}

export interface ReaderAssessment {
  reader: string;
  variant_a?: Assessment;
  variant_b?: Assessment;
}

export interface Panel {
  readers?: ReaderAssessment[];
  summary?: string;
  citations?: string[];
}

export interface Selection {
  decision?: 'A' | 'B' | 'merge' | 'discard';
  final_text?: string;
  rationale?: string;
  claims?: Claim[];
  resolved_objections?: string[];
  kept_objections?: string[];
  citations?: string[];
}

export interface Finding {
  issue: string;
  severity: 'material' | 'minor';
  quote?: string;
  detail?: string;
}

export interface Verification {
  /** Final verdict: the model's plus the deterministic guards, computed on `text_sha256`. */
  verdict?: 'ready_for_execution' | 'blocked';
  model_verdict?: 'ready_for_execution' | 'blocked';
  blocking_reasons?: string[];
  findings?: Finding[];
  checked_claims?: Claim[];
  summary?: string;
  citations?: string[];
  text_sha256?: string;
}

export interface Signal {
  id: string;
  author?: string;
  why_followed?: string;
  posted_at?: string | null;
  reactions?: number | null;
  comments?: number | null;
  text?: string;
}

export interface StageUsage {
  stage: string;
  model?: string | null;
  estimated_usd?: number | string | null;
  request_id?: string | null;
  units?: string[];
  missing_units?: string[];
}

/** APRE-01: impressions read through Unipile when the publication is reconciled. Missing is not zero. */
export interface PieceMetrics {
  impressions?: number | null;
  reactions?: number | null;
  comments?: number | null;
  reposts?: number | null;
  observed_at?: string | null;
  source?: string;
  unipile_post_id?: string | null;
  share_url?: string | null;
}

/** Cut of a published piece at the same age as the others (24 h, 72 h, 7 days). Missing is not zero. */
export interface PieceSnapshot {
  kind: '24h' | '72h' | '7d';
  impressions: number | null;
  reactions: number | null;
  comments: number | null;
  reposts: number | null;
  engagement_pct: number | null;
  captured_at: string;
  age_hours: number;
}

export interface PieceCommenter {
  provider_user_id: string;
  name: string;
  substantive: boolean;
  role: string | null;
  fit: boolean | null;
}

export interface PieceDetail extends PieceSummary {
  brief: Brief;
  variants: Variants;
  panel: Panel;
  selection: Selection;
  verification: Verification;
  final_text: string;
  citations: string[];
  signals: Signal[];
  usage: StageUsage[];
  action_detail: Action | null;
  /** Last values read from the post. */
  metrics?: PieceMetrics | null;
  /** Cuts at 24 h, 72 h and 7 days. */
  snapshots?: PieceSnapshot[];
  /** Who commented; null when the comments were never read. */
  commenters?: PieceCommenter[] | null;
}

export interface PlanResponse {
  slot_date: string;
  job: Job;
}

// ---------------------------------------------------------------- official LinkedIn

export interface LinkedInStatus {
  configured: boolean;
  live: boolean;
  api_version: string | null;
  scopes_required: string[];
  connected: boolean;
  member_urn: string | null;
  member_name: string | null;
  scopes: string[];
  expires_at: string | null;
  days_left: number | null;
  expired: boolean;
  expiring_soon: boolean;
  account: { id: string; paused: boolean; paused_reason: string } | null;
  connected_at?: string;
}

// ---------------------------------------------------------------- referents

export interface Referent {
  id: string;
  account_id?: string;
  public_identifier?: string;
  display_name?: string;
  profile_url?: string;
  reason: string;
  active?: boolean;
  created_at?: string;
  last_observed_at?: string | null;
  /** People of the barrio discovered in this referent's posts. */
  contacts_count?: number;
}

export interface Job {
  id: string;
  status?: string;
}

// ---------------------------------------------------------------- knowledge

export interface SearchResult {
  id: string;
  title: string;
  session: number;
  score: number;
  channels: string[];
}

export interface SearchResponse {
  results: SearchResult[];
  relations?: unknown[];
  warnings?: string[];
}

export interface UnitSource {
  key: string;
  original?: unknown;
}

export interface Unit {
  id: string;
  title: string;
  session: number;
  original?: unknown;
  sources: UnitSource[];
}

export interface MemoryItem {
  id: string;
  namespace: string;
  key: string;
  version: number;
  value: unknown;
  status: 'confirmed' | 'proposed' | string;
  author: string;
  evidence: string;
  created_at: string;
}

// ---------------------------------------------------------------- office

export type RoleStatus = 'trabajando' | 'en_espera' | 'diseno';

export interface RoleActivity {
  status: RoleStatus;
  detail: string;
  since: string | null;
}

export interface Activity {
  updated_at: string;
  roles: Record<string, RoleActivity>;
}

// ================================================================ redesign (CONTRATO-API «Rediseño»)

// ---------------------------------------------------------------- Tu turno

export type TurnoCardType = 'aviso' | 'pregunta' | 'perfil' | 'conversacion';
export type TurnoTone = 'bad' | 'warn' | 'info' | 'ok' | 'muted';

/** A card action: either a POST (`endpoint` + `body`, plus `note` when `note_required`) or a full navigation (`href`). */
export interface TurnoAction {
  label: string;
  endpoint?: string;
  body?: Record<string, unknown>;
  note_required?: boolean;
  href?: string;
  primary?: boolean;
}

/** What an `uncertain` action tried to do. */
export interface TurnoAttempt {
  capability: Capability | string;
  label: string;
  text: string | null;
  reaction: string | null;
  target: { kind: 'post' | 'person' | 'own'; name: string; url: string | null } | null;
  at: string | null;
  url: string | null;
}

export interface TurnoCard {
  /** `linkedin_expired`, `linkedin_expiring`, `uncertain:<id>`, `machine_paused`, `machine_paused_env`, `account_paused:<id>`, `question:<id>`. */
  id: string;
  type: TurnoCardType;
  critical: boolean;
  tone: TurnoTone;
  /** Role id of the agent asking (scene/roles.ts); system notices use `operador_cuenta`. */
  agent: string;
  agent_label: string;
  title: string;
  body: string;
  deadline: string | null;
  created_at: string | null;
  actions: TurnoAction[];
  /** Only on `uncertain` notices. */
  attempt?: TurnoAttempt | null;
  /** Only on questions. */
  question?: Question | null;
  /** rev 18 priority group (being added to the backend). */
  priority?: TurnoPriority;
  /** rev 18 state: nueva and vista count, pospuesta and caducada go in `later` (being added to the backend). */
  state?: TurnoState;
}

export type TurnoPriority = 'urgente' | 'importante' | 'cuando_puedas';
export type TurnoState = 'nueva' | 'vista' | 'pospuesta' | 'caducada';

export interface TurnoRecent {
  kind: 'question' | 'alert' | string;
  id: string;
  title: string;
  at: string;
  /** «Respondida», «No quisiste compartirla», «Confirmaste que se aplicó», «Reconectado», «Reanudada». */
  how: string;
}

export interface DoneToday {
  posts: number;
  comments: number;
  reactions: number;
  follows: number;
  invites: number;
  accepts: number;
}

/** GET /api/v1/tu-turno. */
export interface TuTurno {
  /** Notices + open questions + tasks (not postponed or expired questions). */
  count: number;
  /** Any critical notice: the counter turns alerta. */
  critical: boolean;
  counts: { avisos: number; preguntas: number; tareas: number };
  /** The most urgent item, for the Oficina card. */
  top: TurnoCard | null;
  alerts: TurnoCard[];
  questions: TurnoCard[];
  /** Postponed or expired questions (muted tone). */
  later: TurnoCard[];
  tasks: { perfil: TurnoCard[]; conversaciones: TurnoCard[] };
  recent: TurnoRecent[];
  summary: { done_today: DoneToday; next_piece: { id: string; scheduled_for: string } | null };
  /** Unread items in Notificaciones, for the bell dot (being added to the backend). */
  notifications_unread?: number;
  /** Every active card, ordered by priority, nearest deadline, most recent (being added to the backend). */
  items?: TurnoCard[];
  /** Cards with priority urgente (being added to the backend). */
  urgent_count?: number;
}

// ---------------------------------------------------------------- team questions

export type QuestionAnswerType = 'text' | 'yes_no' | 'choice' | 'number' | 'date';
export type QuestionState = 'open' | 'answered' | 'declined';

export interface Question {
  id: string;
  /** ask: open question; confirm: confirm or correct a proposed value. */
  kind: 'ask' | 'confirm';
  agent: string;
  agent_label: string;
  question: string;
  purpose: string;
  answer_type: QuestionAnswerType;
  options: string[];
  memory_key: string;
  proposed_value: { texto?: string; uso_publico?: boolean } | Record<string, unknown> | null;
  suggested_public: boolean;
  deadline: string | null;
  postponed_until: string | null;
  pending: boolean;
  expired: boolean;
  /** `piece:<id>` or `memoria`. */
  origin: string;
  state: QuestionState;
  answer: string;
  public_use: boolean | null;
  answered_at: string | null;
  created_at: string;
}

/**
 * POST /api/v1/preguntas/<id>/responder. text: `text`; yes_no: `value` si|no and optional `text`;
 * choice: `value` (one of `options`) and optional `text`; number and date: `value` (AAAA-MM-DD).
 * kind=confirm: `accept: true` confirms the proposed value, `text` corrects it.
 */
export interface QuestionAnswer {
  text?: string;
  value?: string;
  public_use?: boolean | null;
  accept?: boolean;
}

// ---------------------------------------------------------------- what the team knows

export interface MemoryFact {
  key: string;
  topic: string;
  text: string;
  public_use: boolean;
  version: number;
  /** Shown as «v{edits}»: v2 means it was edited once. */
  edits: number;
  origin: { kind: 'question' | 'manual' | 'memoria'; agent?: string | null; agent_label?: string | null; question?: string | null };
  updated_at: string;
}

export interface NewMemoryFact {
  text: string;
  public_use: boolean;
  topic?: string;
}

export interface Orientation {
  text: string;
  updated_at: string | null;
  updated_by: string | null;
}

// ---------------------------------------------------------------- calendar

export type CalendarLayer = 'tuyo' | 'publicaciones' | 'red' | 'conversaciones' | 'sistema';
export const CALENDAR_LAYERS: readonly CalendarLayer[] = ['tuyo', 'publicaciones', 'red', 'conversaciones', 'sistema'];

export type CalendarEventKind =
  | 'piece_published'
  | 'piece_scheduled'
  | 'piece_preparing'
  | 'piece_skipped'
  | 'piece_blocked'
  | 'piece_failed'
  | 'piece_uncertain'
  | 'piece_vetoed'
  | 'piece_discarded'
  | 'piece_publishing'
  | 'connection_fit'
  | 'invitation_received'
  | 'invitation_accepted'
  | 'invite_expected'
  | 'deadline'
  | 'meeting'
  | 'opportunity_next'
  | 'linkedin_expiry'
  | 'resolved'
  | 'opportunity'
  | 'machine_paused'
  | 'machine_resumed'
  | 'account_paused'
  | 'action_uncertain'
  | 'action_failed'
  | 'linkedin_expired';

export interface CalendarPerson {
  id: string;
  name: string;
  role: string | null;
}

export interface CalendarEvent {
  id: string;
  layer: CalendarLayer;
  kind: CalendarEventKind | string;
  at: string | null;
  title: string;
  state: string | null;
  important: boolean;
  /** /calendario/pieza/<id>, /personas/<id>, /tu-turno… */
  link: string | null;
  people?: CalendarPerson[];
  impressions?: number | null;
  skip_reason?: string | null;
  /** invite_expected: an estimate subject to the caps. */
  estimate?: boolean;
}

export interface CalendarDayCounts {
  comments: number;
  reactions: number;
  follows: number;
  invites: number;
  accepts: number;
  connections_fit: number;
}

export interface CalendarioDay {
  date: string;
  counts: CalendarDayCounts;
  /** Ordered by layer priority (Tuyo > Sistema > Publicaciones > Conversaciones > Red), then by time. */
  events: CalendarEvent[];
}

/** GET /api/v1/calendario?desde=&hasta= (93 days at most; days in America/Bogota). */
export interface Calendario {
  timezone: string;
  today: string;
  lead_hours: number;
  /** true, false or 'parcial' (conversaciones until the inbox arrives). */
  layers: Record<CalendarLayer, boolean | 'parcial'>;
  days: CalendarioDay[];
}

// ---------------------------------------------------------------- activity (Lista, Próximo, Ver todo lo del día)

export type ActividadTipo = 'todo' | 'publicaciones' | 'comentarios' | 'reacciones' | 'red';

export interface ActividadFilters {
  tipo?: ActividadTipo;
  desde?: string;
  hasta?: string;
  /** Also what did not go out (vetoed, discarded, expired, superseded). */
  noSalio?: boolean;
  limit?: number;
  offset?: number;
}

export interface ActivityTarget {
  kind: 'post' | 'person' | 'own';
  name: string;
  headline?: string | null;
  url?: string | null;
  post_excerpt?: string | null;
  contact_id?: string | null;
  role?: string | null;
}

export interface ActivityItem {
  id: string;
  capability: Capability | string;
  label: string;
  agent: string | null;
  state: ActionState | string;
  /** null for a normal success; otherwise «En curso», «Incierta», «Fallida», «Vetada por ti»… */
  state_label: string | null;
  important: boolean;
  at: string;
  date: string;
  text: string | null;
  reaction: string | null;
  target: ActivityTarget | null;
  url: string | null;
  rationale: string;
  decided_by: 'gustavo' | 'lider' | 'politica' | null;
  decision_note: string;
  execution_note: string;
  review: { decision: 'approve' | 'discard'; answers: Record<string, number>; reasons: string[]; model: string } | null;
  piece_id: string | null;
}

export interface UpcomingPiece {
  piece_id: string;
  slot_date: string;
  scheduled_for: string;
  status: 'scheduled' | 'preparing' | 'publishing' | 'awaiting_approval' | PieceStatus;
  stage: EditorialStage;
  thesis: string | null;
  excerpt: string | null;
  pillar: string | null;
  modality: string | null;
  primary_reader: string | null;
  action: { id: string; state: ActionState } | null;
  vetoable: boolean;
  impressions: number | null;
  skip_reason: string | null;
  note: string;
}

/** GET /api/v1/actividad. */
export interface Actividad {
  upcoming: { pieces: UpcomingPiece[]; queued: (ActivityItem & { expected_at: string | null })[] };
  items: ActivityItem[];
  next_offset: number | null;
}

// ---------------------------------------------------------------- people: filters and opportunities

export interface ContactSearch {
  stage?: DisplayStage | '';
  source?: string;
  account?: string;
  /** Name or headline. */
  q?: string;
  role?: string;
  modality?: string;
  page?: number;
}

export type OpportunityStage = 'conversacion' | 'necesidad' | 'cualificada' | 'reunion' | 'propuesta' | 'acuerdo' | 'sin_acuerdo';
export const OPPORTUNITY_STAGES: readonly OpportunityStage[] = ['conversacion', 'necesidad', 'cualificada', 'reunion', 'propuesta', 'acuerdo', 'sin_acuerdo'];

export type OpportunityModality = 'personal_startups' | 'projectapp' | 'por_clasificar';
export type OpportunityChannel = 'linkedin' | 'email' | 'llamada' | 'evento' | 'otro';
export type OpportunityAttribution = 'cito_contenido' | 'lo_dijo' | 'inferido' | 'desconocido';

export interface Opportunity {
  id: string;
  person: string;
  contact: { id: string; display_name: string; headline: string; profile_url: string; stage: ContactStage; role: string | null } | null;
  person_name: string;
  company: string;
  modality: OpportunityModality;
  channel: OpportunityChannel;
  stage: OpportunityStage;
  attribution: OpportunityAttribution;
  need: string;
  budget: string;
  dedication: string;
  next_action: string;
  next_action_at: string | null;
  notes: string;
  history: { at: string; event: 'created' | 'stage' | string; detail: string }[];
  days_in_stage: number;
  created_at: string;
  updated_at: string;
  stage_changed_at: string;
  closed_at: string | null;
}

/** POST needs `modality` and `contact` or `person_name`; PATCH accepts any field. */
export interface OpportunityInput {
  contact?: string | null;
  person_name?: string;
  company?: string;
  modality?: OpportunityModality;
  channel?: OpportunityChannel;
  stage?: OpportunityStage;
  attribution?: OpportunityAttribution;
  need?: string;
  budget?: string;
  dedication?: string;
  next_action?: string;
  next_action_at?: string | null;
  notes?: string;
}

export interface OpportunityFilters {
  stage?: OpportunityStage | '';
  modality?: OpportunityModality | '';
  contact?: string;
  page?: number;
}

export interface ReferentPatch {
  active?: boolean;
  reason?: string;
}

// ---------------------------------------------------------------- settings

export interface AjustesSpend {
  budget: 'general' | 'editorial' | 'red' | string;
  label: string;
  spent_usd: number;
  limit_usd: number;
}

/** GET /api/v1/ajustes. */
export interface Ajustes {
  autonomy: Partial<Record<Capability, AutonomyMode>>;
  lead: { enabled: boolean; capabilities: Capability[]; model: string };
  limits: Partial<Record<Capability, { daily: number; weekly: number }>>;
  window: WindowInfo;
  ai_spend: { today: AjustesSpend[]; month_usd: number | null; total_usd: number | null; limit_usd: number | null; lead_month_usd: number | null; transcription_month_usd?: number | null };
  facts_count: number;
  orientation: Orientation | null;
}

// ================================================================ Resultados

export type ResultadosDias = 7 | 28 | 90;
export type ResultadosModalidad = 'todo' | 'personal_startups' | 'projectapp';

export interface KpiPoint {
  date: string;
  value: number | null;
}

/**
 * One indicator. `value: null` is «sin dato» (show a dash and `unavailable_reason`, never 0).
 * `delta`/`delta_pct` only arrive with `comparable: true`; in percent KPIs `delta` is in points.
 */
export interface Kpi {
  value: number | null;
  previous: number | null;
  delta: number | null;
  delta_pct: number | null;
  comparable: boolean;
  series: KpiPoint[] | null;
  definition: string;
  formula: string | null;
  unavailable_reason: string | null;
  numerator?: number | null;
  denominator?: number | null;
  cut?: '7d' | '24h' | null;
  posts_measured?: number | null;
  posts_total?: number | null;
  measured?: { from: string; to: string } | null;
  window_days?: number | null;
  top?: { id?: string; contact_id?: string; name: string; count?: number; interactions?: number }[] | null;
}

export interface ResultadosPost {
  piece_id: string;
  date: string;
  published_at: string | null;
  first_line: string;
  pillar: string | null;
  url: string | null;
  impressions_24h: number | null;
  impressions_7d: number | null;
  reactions: number | null;
  comments: number | null;
  reposts: number | null;
  engagement_pct: number | null;
  cut: '7d' | '24h' | null;
  commenters_by_role: Record<string, number> | null;
}

export interface SpendLine {
  spent: number;
  budget: number | null;
}

/** GET /api/v1/resultados?dias=&modalidad=. */
export interface Resultados {
  periodo: { desde: string; hasta: string; dias: ResultadosDias; datos_hasta: string; anterior: { desde: string; hasta: string } };
  modalidad: ResultadosModalidad;
  zona_horaria: string;
  negocio: { disponible: boolean; motivo: string | null; inbound: Kpi } & Partial<Record<string, unknown>>;
  audiencia: {
    followers: Kpi;
    connections: Kpi;
    profile_views: Kpi;
    new_fit_connections: Kpi;
    roles: { items: { role: string; value: number }[] | null; definition: string; unavailable_reason: string | null };
    acceptance_rate: Kpi;
    funnel: { stages: Record<string, number>; order: string[]; aside: string[]; definition: string };
    recurrent_people: Kpi;
  };
  contenido: {
    kpis: { median_impressions: Kpi; engagement_pct: Kpi; substantive_comments: Kpi; consistency: Kpi };
    chart: {
      bars: { piece_id: string; date: string; impressions: number | null; cut: '7d' | '24h' | null; fallback: boolean }[];
      median_previous_4_weeks: { '7d': number | null; '24h': number | null };
      definition: string;
    };
    best_post: { piece_id: string; first_line: string; date: string; pillar: string | null; impressions: number | null; engagement_pct: number | null; cut: '7d' | '24h' | null } | null;
    by_pillar: { cut: '7d' | '24h' | null; formula: string; items: { pillar: string; value: number | null; posts: number }[] };
    posts: ResultadosPost[];
  };
  equipo: {
    comments_published: Kpi;
    comments_replied: Kpi;
    follows: Kpi;
    invites: Kpi;
    accepts: Kpi;
    pieces_published: Kpi;
    pieces_blocked: Kpi;
    pieces_vetoed: Kpi;
    spend: {
      today: Record<string, SpendLine>;
      month: Record<string, SpendLine>;
      accumulated: SpendLine;
      other_providers: Record<string, { today: number; month: number; accumulated: number; budget: number | null }>;
      month_start: string;
      definition: string;
    };
  };
}
