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
