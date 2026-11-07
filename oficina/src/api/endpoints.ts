import { api, LOGIN_PATH, SESSION_PATH } from './client';
import type {
  Account,
  Action,
  Activity,
  Capability,
  Control,
  EditorialCalendar,
  FeedEvent,
  Job,
  LinkedInStatus,
  MemoryItem,
  Overview,
  Paginated,
  PieceDetail,
  PlanResponse,
  Referent,
  SearchResponse,
  Session,
  Unit,
  User,
} from './types';

const OP = '/api/v1/operador';

/** Lists may be paginated (`{results}`) or plain arrays; accept both. */
export function asList<T>(data: Paginated<T> | T[] | null | undefined): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : (data.results ?? []);
}

const id = (value: string) => encodeURIComponent(value);

// ---------------------------------------------------------------- session
export const getSession = () => api.get<Session>(SESSION_PATH);
export const login = (username: string, password: string) =>
  api.post<{ user: User }>(LOGIN_PATH, { username, password });
export const logout = () => api.post<null>('/api/v1/auth/logout');

// ---------------------------------------------------------------- machine
export const getOverview = () => api.get<Overview>(`${OP}/overview`);
export const setControl = (paused: boolean, reason: string) =>
  api.post<Control>(`${OP}/control`, { paused, reason });
export const getFeed = (limit = 50) => api.get<FeedEvent[]>(`${OP}/feed?limit=${limit}`);
export const getAccounts = () => api.get<Paginated<Account> | Account[]>(`${OP}/accounts`);
export const setAccountPaused = (accountId: string, paused: boolean, reason = '') =>
  api.post<Account>(`${OP}/accounts/${id(accountId)}/pause`, { paused, reason });

// ---------------------------------------------------------------- actions
/**
 * The backend filters by `state` only. `capability` is sent for when it learns to filter too; until
 * then the page filters what it receives, asking for bigger pages so the filter has more to work with.
 */
export function listActions(state: string, page: number, capability: Capability | '' = '') {
  const params = new URLSearchParams();
  if (state) params.set('state', state);
  if (capability) {
    params.set('capability', capability);
    params.set('page_size', '100');
  }
  if (page > 1) params.set('page', String(page));
  const query = params.toString();
  return api.get<Paginated<Action> | Action[]>(`${OP}/actions${query ? `?${query}` : ''}`);
}
export const rejectAction = (actionId: string, note: string) =>
  api.post<Action>(`${OP}/actions/${id(actionId)}/reject`, { note });
export const approveAction = (actionId: string, expectedHash: string, note: string) =>
  api.post<unknown>(`${OP}/actions/${id(actionId)}/approve`, { expected_hash: expectedHash, note });
export const resolveAction = (actionId: string, outcome: 'confirmed' | 'failed', note: string) =>
  api.post<Action>(`${OP}/actions/${id(actionId)}/resolve`, { outcome, note });

// ---------------------------------------------------------------- editorial (daily own publication)
const ED = '/api/v1/editorial';

/** `desde` AAAA-MM-DD (the backend defaults to a week ago) and `dias` 1..60. */
export function getCalendar(desde = '', dias = 15) {
  const params = new URLSearchParams();
  if (desde) params.set('desde', desde);
  params.set('dias', String(dias));
  return api.get<EditorialCalendar>(`${ED}/calendar?${params.toString()}`);
}
export const getPiece = (pieceId: string) => api.get<PieceDetail>(`${ED}/pieces/${id(pieceId)}`);
/** Paid: queues the editorial circuit for the next free slot. The same `request_id` never queues twice. */
export const planPiece = (requestId?: string) => api.post<PlanResponse>(`${ED}/plan`, requestId ? { request_id: requestId } : {});

// ---------------------------------------------------------------- official LinkedIn
export const getLinkedInStatus = () => api.get<LinkedInStatus>('/api/v1/linkedin/status');
/** Opened with a full navigation (never fetch): Django redirects to LinkedIn and back to /ajustes. */
export const LINKEDIN_OAUTH_START = '/api/v1/linkedin/oauth/start';

// ---------------------------------------------------------------- referents
export const listReferents = (account: string) =>
  api.get<Paginated<Referent> | Referent[]>(`${OP}/referents?account=${id(account)}&page_size=100`);
export const addReferent = (account: string, identifier: string, reason: string) =>
  api.post<Referent>(`${OP}/referents`, { account, identifier, reason });
export const observeNow = (account: string) => api.post<Job>(`${OP}/observe`, { account });

// ---------------------------------------------------------------- knowledge
export const searchKnowledge = (query: string, limit = 10) =>
  api.post<SearchResponse>('/api/v1/search', { query, limit, mode: 'lexical' });
export const getUnit = (unitId: string) => api.get<Unit>(`/api/v1/units/${id(unitId)}`);
export const getSource = (key: string) =>
  api.get<unknown>(`/api/v1/sources/${key.split('/').map(encodeURIComponent).join('/')}`);

// ---------------------------------------------------------------- memory
export const listMemory = () => api.get<MemoryItem[] | Paginated<MemoryItem>>('/api/v1/memory');
export const proposeMemory = (key: string, value: string, evidence: string, expectedVersion: number) =>
  api.post<{ id: string; version: number; status: string }>('/api/v1/memory/proposals', {
    namespace: 'user',
    key,
    value,
    evidence,
    expected_version: expectedVersion,
  });
export const confirmMemory = (memoryId: string, expectedVersion: number) =>
  api.post<unknown>(`/api/v1/memory/${id(memoryId)}/confirm`, { expected_version: expectedVersion });

// ---------------------------------------------------------------- office
export const getActivity = () => api.get<Activity>('/api/v1/oficina/actividad');

// ---------------------------------------------------------------- push
export const getPushKey = () => api.get<{ public_key: string }>('/api/v1/push/key');
export const savePushSubscription = (subscription: PushSubscriptionJSON) =>
  api.post<unknown>('/api/v1/push/subscriptions', subscription);
export const deletePushSubscription = (endpoint: string) =>
  api.post<null>('/api/v1/push/unsubscribe', { endpoint });
export const sendTestPush = () => api.post<unknown>('/api/v1/push/test');
