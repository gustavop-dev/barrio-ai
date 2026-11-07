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

/** INT-03 comment and INT-02 reaction on someone else's post; CONT-09 own publication. */
export const CAPABILITIES = ['INT-03', 'INT-02', 'CONT-09'] as const;
export type Capability = (typeof CAPABILITIES)[number];

export interface Action {
  id: string;
  account_id?: string;
  capability: Capability;
  payload: { text?: string; reaction?: string };
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
  source?: string;
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
  /** Not serialized by the current backend; shown only if it ever arrives. */
  metrics?: PieceMetrics | null;
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
