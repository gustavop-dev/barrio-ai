import type { PieceDetailFull } from './calendario';
import { api, LOGIN_PATH, SESSION_PATH, TOKEN_PATH } from './client';
import type {
  Account,
  Action,
  Activity,
  Actividad,
  ActividadFilters,
  Ajustes,
  Calendario,
  Capability,
  Contact,
  ContactSearch,
  Control,
  Device,
  EditorialCalendar,
  FeedEvent,
  Job,
  LinkedInStatus,
  MemoryFact,
  MemoryItem,
  NewMemoryFact,
  Opportunity,
  OpportunityFilters,
  OpportunityInput,
  Orientation,
  Overview,
  Paginated,
  PlanResponse,
  Question,
  QuestionAnswer,
  QuestionState,
  RedSummary,
  Referent,
  ReferentPatch,
  Resultados,
  ResultadosDias,
  ResultadosModalidad,
  SearchResponse,
  Session,
  TokenLogin,
  TuTurno,
  TurnoAction,
  Unit,
  User,
  WeeklySummaries,
  WeeklySummaryDecision,
  WeeklySummaryGenerateResponse,
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

// ---------------------------------------------------------------- device token (native app, no cookies or CSRF)
/** 201 with the token (shown once), the user and the device; 400 on wrong credentials, 429 when throttled. */
export const loginWithToken = (username: string, password: string, deviceName: string) =>
  api.post<TokenLogin>(TOKEN_PATH, { username, password, device_name: deviceName });
/** Revokes the token of this request (logout of the native app): 204. */
export const revokeToken = () => api.post<null>(`${TOKEN_PATH}/revocar`);
/** A plain array (older drafts paginated it: read it with asList). */
export const listDevices = () => api.get<Paginated<Device> | Device[]>('/api/v1/auth/dispositivos');
export const revokeDevice = (deviceId: string) => api.delete(`/api/v1/auth/dispositivos/${id(deviceId)}`);

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
export const getPiece = (pieceId: string) => api.get<PieceDetailFull>(`${ED}/pieces/${id(pieceId)}`);
/** Paid: queues the editorial circuit for the next free slot. The same `request_id` never queues twice. */
export const planPiece = (requestId?: string) => api.post<PlanResponse>(`${ED}/plan`, requestId ? { request_id: requestId } : {});
/** EDI-23 «Desestimar el bloqueo»: queues the job that prepares its image if it lacks one and approves it with his
 * decision (paid only then). The same `request_id` never queues twice; 409 when the piece no longer allows it. */
export const overridePiece = (pieceId: string, requestId?: string, note = '') =>
  api.post<{ job: Job }>(`${ED}/pieces/${id(pieceId)}/desestimar`, requestId ? { request_id: requestId, note } : { note });

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
/** Deactivate, reactivate or change the reason of a referent. */
export const updateReferent = (referentId: string, patch: ReferentPatch) => api.patch<Referent>(`${OP}/referents/${id(referentId)}`, patch);
export const deleteReferent = (referentId: string) => api.delete(`${OP}/referents/${id(referentId)}`);

// ---------------------------------------------------------------- network (Red)
const RED = '/api/v1/red';

export type ContactFilters = ContactSearch;

/** URL query from an object, leaving out empty values. */
function queryString(values: Record<string, string | number | boolean | null | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value === undefined || value === null || value === '' || value === false) continue;
    params.set(key, value === true ? '1' : String(value));
  }
  const query = params.toString();
  return query ? `?${query}` : '';
}

/**
 * Paginated, newest `updated_at` first. Empty filters are not sent. `stage=opportunity` lists the people
 * with an open opportunity; `q` searches name and headline. `vista=conexiones` lists only the connected
 * people, the most recent connection first.
 */
export function listContacts({ vista = '', stage = '', source = '', account = '', q = '', role = '', modality = '', page = 1 }: ContactSearch = {}) {
  const query = queryString({ vista, stage, source, account, q: q.trim(), role, modality, page: page > 1 ? page : null });
  return api.get<Paginated<Contact> | Contact[]>(`${RED}/contacts${query}`);
}
/** Adds a free note to the person (201, returns the contact). */
export const addContactNote = (contactId: string, text: string) => api.post<Contact>(`${RED}/contacts/${id(contactId)}/notas`, { text });
export const getContact = (contactId: string) => api.get<Contact>(`${RED}/contacts/${id(contactId)}`);
/** Human session and `approve_actions`; the note is mandatory. Also rejects the contact's open action. 409 once invited or later. */
export const discardContact = (contactId: string, note: string) => api.post<Contact>(`${RED}/contacts/${id(contactId)}/discard`, { note });
/** «Sí, encaja»: Gustavo answers a doubt of the lead about a person the classifier said fits (BAR-17). */
export const confirmContactFit = (contactId: string) => api.post<Contact>(`${RED}/contacts/${id(contactId)}/encaja`, {});
export const getRedSummary = () => api.get<RedSummary>(`${RED}/summary`);

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
/** Native push: registering the same Expo token again updates it (201 `{id}`). */
export const registerExpoPush = (token: string, deviceName: string) =>
  api.post<{ id: string }>('/api/v1/push/expo', { token, device_name: deviceName });
export const unregisterExpoPush = (token: string) => api.delete('/api/v1/push/expo', { token });

// ================================================================ redesign

// ---------------------------------------------------------------- Tu turno
export const getTuTurno = () => api.get<TuTurno>('/api/v1/tu-turno');

/**
 * Runs a card action: POST its `endpoint` with its `body`, plus `note` when `note_required`.
 * Actions with `href` are full navigations (LinkedIn OAuth): render them as links, never call this.
 */
export function runTurnoAction(action: TurnoAction, note?: string) {
  if (!action.endpoint) throw new Error('Esta acción es un enlace, no una petición');
  const body: Record<string, unknown> = { ...(action.body ?? {}) };
  if (note !== undefined && note !== '') body.note = note;
  return api.post<unknown>(action.endpoint, body);
}

// ---------------------------------------------------------------- team questions
const PREG = '/api/v1/preguntas';
export const listPreguntas = (state: QuestionState | '' = 'open') =>
  api.get<Paginated<Question> | Question[]>(`${PREG}${queryString({ state })}`);
/** 400 when the value is invalid, 409 when the question is no longer open. */
export const answerPregunta = (questionId: string, answer: QuestionAnswer) => api.post<Question>(`${PREG}/${id(questionId)}/responder`, answer);
/** Within 15 minutes of answering: restores the memory and reopens the question (409 afterwards). */
export const undoPregunta = (questionId: string) => api.post<Question>(`${PREG}/${id(questionId)}/deshacer`);
/** Postpones 3 days and takes it out of the counter. */
export const postponePregunta = (questionId: string) => api.post<Question>(`${PREG}/${id(questionId)}/mas-tarde`);
/** Closes the key for good. */
export const declinePregunta = (questionId: string) => api.post<Question>(`${PREG}/${id(questionId)}/no-compartir`);

// ---------------------------------------------------------------- what the team knows
const HECHOS = '/api/v1/memoria/hechos';
export const listHechos = () => api.get<MemoryFact[]>(HECHOS);
/** «Añadir algo que quieras que sepan»: confirmed directly; 201 with the whole list. */
export const addHecho = (fact: NewMemoryFact) => api.post<MemoryFact[]>(HECHOS, fact);
export const correctHecho = (key: string, text: string, publicUse: boolean) =>
  api.post<MemoryFact>(`${HECHOS}/${id(key)}/corregir`, { text, public_use: publicUse });
export const retireHecho = (key: string, reason: string) => api.post<unknown>(`${HECHOS}/${id(key)}/retirar`, { reason });

export const getOrientacion = () => api.get<Orientation>('/api/v1/orientacion');
/** 4000 characters at most. */
export const saveOrientacion = (text: string) => api.put<Orientation>('/api/v1/orientacion', { text });

// ---------------------------------------------------------------- calendar and activity
/** AAAA-MM-DD; 93 days at most. Without dates the backend returns the current month. */
export const getCalendario = (desde = '', hasta = '') => api.get<Calendario>(`/api/v1/calendario${queryString({ desde, hasta })}`);

export function getActividad({ tipo = 'todo', desde = '', hasta = '', noSalio = false, limit, offset }: ActividadFilters = {}) {
  return api.get<Actividad>(`/api/v1/actividad${queryString({ tipo, desde, hasta, no_salio: noSalio, limit, offset: offset || null })}`);
}

// ---------------------------------------------------------------- results
export const getResultados = (dias: ResultadosDias = 28, modalidad: ResultadosModalidad = 'todo') =>
  api.get<Resultados>(`/api/v1/resultados${queryString({ dias, modalidad })}`);

// ---------------------------------------------------------------- opportunities
const OPP = '/api/v1/oportunidades';
export function listOportunidades({ stage = '', modality = '', contact = '', page = 1 }: OpportunityFilters = {}) {
  return api.get<Paginated<Opportunity> | Opportunity[]>(`${OPP}${queryString({ stage, modality, contact, page: page > 1 ? page : null })}`);
}
/** Needs `modality` and `contact` or `person_name` (400 otherwise). */
export const createOportunidad = (input: OpportunityInput) => api.post<Opportunity>(OPP, input);
export const updateOportunidad = (opportunityId: string, patch: OpportunityInput) => api.patch<Opportunity>(`${OPP}/${id(opportunityId)}`, patch);
export const deleteOportunidad = (opportunityId: string) => api.delete(`${OPP}/${id(opportunityId)}`);

// ---------------------------------------------------------------- settings
export const getAjustes = () => api.get<Ajustes>('/api/v1/ajustes');

// ---------------------------------------------------------------- weekly summary (analista_barrio_resultados)
const RESUMEN = '/api/v1/resultados/resumen-semanal';
export const getResumenSemanal = () => api.get<WeeklySummaries>(RESUMEN);
/** nuevo → visto, once the block is on screen. */
export const markResumenVisto = (summaryId: string) => api.post<WeeklySummaryDecision>(`${RESUMEN}/${id(summaryId)}/visto`, {});
/** «Usar como orientación»: replaces the team orientation and returns the previous text. */
export const aplicarResumen = (summaryId: string) => api.post<WeeklySummaryDecision>(`${RESUMEN}/${id(summaryId)}/aplicar`, {});
export const descartarResumen = (summaryId: string) => api.post<WeeklySummaryDecision>(`${RESUMEN}/${id(summaryId)}/descartar`, {});
/** The 5 s «Deshacer»: restores the previous orientation (409 if it changed since) or reopens a discarded summary. */
export const deshacerResumen = (summaryId: string) => api.post<WeeklySummaryDecision>(`${RESUMEN}/${id(summaryId)}/deshacer`, {});
/** Paid: one Claude call for the last week. `request_id` makes a retry the same job. */
export const generarResumen = (requestId?: string) =>
  api.post<WeeklySummaryGenerateResponse>(`${RESUMEN}/generar`, requestId ? { request_id: requestId } : {});
