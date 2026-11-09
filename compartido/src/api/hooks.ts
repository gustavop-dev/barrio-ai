import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient, type QueryClient, type QueryKey } from '@tanstack/react-query';
import {
  addContactNote,
  addHecho,
  answerPregunta,
  aplicarResumen,
  asList,
  correctHecho,
  createOportunidad,
  declinePregunta,
  deleteOportunidad,
  deleteReferent,
  descartarResumen,
  deshacerResumen,
  discardContact,
  generarResumen,
  getAccounts,
  getActividad,
  getActivity,
  getAjustes,
  getCalendar,
  getCalendario,
  getContact,
  getFeed,
  getLinkedInStatus,
  getOrientacion,
  getOverview,
  getPiece,
  getRedSummary,
  getResultados,
  getResumenSemanal,
  getTuTurno,
  listContacts,
  listHechos,
  listOportunidades,
  listPreguntas,
  listReferents,
  markResumenVisto,
  planPiece,
  postponePregunta,
  approveAction,
  rejectAction,
  resolveAction,
  retireHecho,
  runTurnoAction,
  saveOrientacion,
  setAccountPaused,
  setControl,
  undoPregunta,
  updateOportunidad,
  updateReferent,
} from './endpoints';
import { keys } from './queryClient';
import type {
  ActividadFilters,
  ContactSearch,
  ContactStage,
  NewMemoryFact,
  OpportunityFilters,
  OpportunityInput,
  QuestionAnswer,
  QuestionState,
  ReferentPatch,
  ResultadosDias,
  ResultadosModalidad,
  TurnoAction,
} from './types';

/** Refresh intervals of DISENO-VISTAS «Comportamientos globales». */
export const REFRESH = {
  scene: 15_000,
  tuTurno: 30_000,
  calendario: 30_000,
  pieza: 30_000,
  personas: 60_000,
  resultados: 60_000,
  linkedin: 5 * 60_000,
  overview: 30_000,
} as const;

function invalidate(client: QueryClient, ...prefixes: QueryKey[]) {
  return Promise.all(prefixes.map((queryKey) => client.invalidateQueries({ queryKey })));
}

// ================================================================ existing reads

export function useOverview() {
  return useQuery({ queryKey: keys.overview, queryFn: getOverview, refetchInterval: REFRESH.overview });
}

export function useActivity() {
  return useQuery({ queryKey: keys.activity, queryFn: getActivity, refetchInterval: REFRESH.scene });
}

export function useFeed() {
  return useQuery({ queryKey: keys.feed, queryFn: () => getFeed(50), refetchInterval: 30_000 });
}

export function useAccounts() {
  return useQuery({ queryKey: keys.accounts, queryFn: async () => asList(await getAccounts()) });
}

export function useRedSummary() {
  return useQuery({ queryKey: keys.redSummary, queryFn: getRedSummary, refetchInterval: REFRESH.personas });
}

/** Keeps the raw page (`{count,next,previous,results}` or a plain array) so the page can paginate. */
export function useContacts(stage: ContactStage | '', page: number) {
  return useQuery({
    queryKey: keys.contacts(stage, page),
    queryFn: () => listContacts({ stage, page }),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH.personas,
  });
}

export function useContact(contactId: string) {
  return useQuery({ queryKey: keys.contact(contactId), queryFn: () => getContact(contactId), enabled: Boolean(contactId), refetchInterval: REFRESH.personas });
}

export function useLinkedInStatus() {
  return useQuery({ queryKey: keys.linkedin, queryFn: getLinkedInStatus, refetchInterval: REFRESH.linkedin });
}

/** Piece detail with `snapshots` and `commenters`. */
export function usePiece(pieceId: string) {
  return useQuery({ queryKey: keys.piece(pieceId), queryFn: () => getPiece(pieceId), enabled: Boolean(pieceId), refetchInterval: REFRESH.pieza });
}

/** The editorial calendar (pieces per day), for views that need the raw slots. */
export function useEditorialCalendar(desde = '', dias = 15) {
  return useQuery({ queryKey: keys.calendar(`${desde}:${dias}`), queryFn: () => getCalendar(desde, dias), refetchInterval: REFRESH.calendario });
}

export function useReferents(account: string) {
  return useQuery({ queryKey: keys.referents(account), queryFn: async () => asList(await listReferents(account)), enabled: Boolean(account) });
}

// ================================================================ redesign reads

/** GET /api/v1/tu-turno: counter, critical flag and every card. */
export function useTuTurno() {
  return useQuery({ queryKey: keys.tuTurno, queryFn: getTuTurno, refetchInterval: REFRESH.tuTurno });
}

export function usePreguntas(state: QuestionState | '' = 'open') {
  return useQuery({ queryKey: keys.preguntas(state), queryFn: async () => asList(await listPreguntas(state)), refetchInterval: REFRESH.tuTurno });
}

/** «Lo que el equipo sabe de ti». */
export function useHechos() {
  return useQuery({ queryKey: keys.hechos, queryFn: listHechos });
}

export function useOrientacion() {
  return useQuery({ queryKey: keys.orientacion, queryFn: getOrientacion });
}

/** GET /api/v1/calendario for a range (AAAA-MM-DD, 93 days at most). */
export function useCalendario(desde: string, hasta: string) {
  return useQuery({
    queryKey: keys.calendario(desde, hasta),
    queryFn: () => getCalendario(desde, hasta),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH.calendario,
  });
}

/** GET /api/v1/actividad, paginated with «Cargar más» (`fetchNextPage`). `upcoming` comes with the first page. */
export function useActividad({ tipo = 'todo', desde = '', hasta = '', noSalio = false, limit = 50 }: Omit<ActividadFilters, 'offset'> = {}) {
  return useInfiniteQuery({
    queryKey: keys.actividad(tipo, desde, hasta, noSalio),
    queryFn: ({ pageParam }) => getActividad({ tipo, desde, hasta, noSalio, limit, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (last) => last.next_offset ?? undefined,
    refetchInterval: REFRESH.calendario,
  });
}

export function useResultados(dias: ResultadosDias = 28, modalidad: ResultadosModalidad = 'todo') {
  return useQuery({
    queryKey: keys.resultados(dias, modalidad),
    queryFn: () => getResultados(dias, modalidad),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH.resultados,
  });
}

/** Contacts with the redesign filters (display stage incl. `opportunity`, q, role, modality). Raw page kept. */
export function useContactSearch(filters: ContactSearch) {
  const normalized = {
    stage: filters.stage ?? '',
    source: filters.source ?? '',
    account: filters.account ?? '',
    q: (filters.q ?? '').trim(),
    role: filters.role ?? '',
    modality: filters.modality ?? '',
    page: filters.page ?? 1,
  };
  return useQuery({
    queryKey: keys.contactSearch(normalized),
    queryFn: () => listContacts(normalized),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH.personas,
  });
}

export function useOportunidades(filters: OpportunityFilters = {}) {
  const normalized = { stage: filters.stage ?? '', modality: filters.modality ?? '', contact: filters.contact ?? '', page: filters.page ?? 1 };
  return useQuery({
    queryKey: keys.oportunidades(normalized),
    queryFn: () => listOportunidades(normalized),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH.personas,
  });
}

export function useAjustes() {
  return useQuery({ queryKey: keys.ajustes, queryFn: getAjustes });
}

// ================================================================ writes
// Each mutation refreshes what it changes; Tu turno is refreshed whenever its counter can move.

/** Runs a Tu turno card action (`endpoint` + `body` + `note`). */
export function useTurnoAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ action, note }: { action: TurnoAction; note?: string }) => runTurnoAction(action, note),
    // redAll: closing a conversation card changes «Te toca» on the person card.
    onSettled: () => invalidate(client, keys.tuTurno, keys.overview, keys.actionsAll, keys.calendarioAll, keys.actividadAll, keys.linkedin, keys.redAll, ['referents']),
  });
}

export function useAnswerPregunta() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ questionId, answer }: { questionId: string; answer: QuestionAnswer }) => answerPregunta(questionId, answer),
    onSettled: () => invalidate(client, keys.tuTurno, keys.preguntasAll, keys.hechos),
  });
}

export function useUndoPregunta() {
  const client = useQueryClient();
  return useMutation({ mutationFn: undoPregunta, onSettled: () => invalidate(client, keys.tuTurno, keys.preguntasAll, keys.hechos) });
}

export function usePostponePregunta() {
  const client = useQueryClient();
  return useMutation({ mutationFn: postponePregunta, onSettled: () => invalidate(client, keys.tuTurno, keys.preguntasAll) });
}

export function useDeclinePregunta() {
  const client = useQueryClient();
  return useMutation({ mutationFn: declinePregunta, onSettled: () => invalidate(client, keys.tuTurno, keys.preguntasAll) });
}

export function useAddHecho() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (fact: NewMemoryFact) => addHecho(fact), onSettled: () => invalidate(client, keys.hechos, keys.ajustes) });
}

export function useCorrectHecho() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ key, text, publicUse }: { key: string; text: string; publicUse: boolean }) => correctHecho(key, text, publicUse),
    onSettled: () => invalidate(client, keys.hechos),
  });
}

export function useRetireHecho() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ key, reason }: { key: string; reason: string }) => retireHecho(key, reason),
    onSettled: () => invalidate(client, keys.hechos, keys.ajustes),
  });
}

export function useSaveOrientacion() {
  const client = useQueryClient();
  return useMutation({ mutationFn: saveOrientacion, onSettled: () => invalidate(client, keys.orientacion, keys.ajustes) });
}

export function useAddContactNote() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ contactId, text }: { contactId: string; text: string }) => addContactNote(contactId, text),
    onSettled: () => invalidate(client, keys.redAll),
  });
}

export function useDiscardContact() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ contactId, note }: { contactId: string; note: string }) => discardContact(contactId, note),
    onSettled: () => invalidate(client, keys.redAll, keys.actionsAll, keys.calendarioAll),
  });
}

export function useCreateOportunidad() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: OpportunityInput) => createOportunidad(input),
    // tuTurno: a conversation card stops offering «Marcar como oportunidad» once the person has one.
    onSettled: () => invalidate(client, keys.oportunidadesAll, keys.redAll, keys.resultadosAll, keys.calendarioAll, keys.tuTurno),
  });
}

export function useUpdateOportunidad() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ opportunityId, patch }: { opportunityId: string; patch: OpportunityInput }) => updateOportunidad(opportunityId, patch),
    onSettled: () => invalidate(client, keys.oportunidadesAll, keys.redAll, keys.resultadosAll, keys.calendarioAll),
  });
}

export function useDeleteOportunidad() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: deleteOportunidad,
    onSettled: () => invalidate(client, keys.oportunidadesAll, keys.redAll, keys.resultadosAll, keys.calendarioAll),
  });
}

export function useUpdateReferent() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ referentId, patch }: { referentId: string; patch: ReferentPatch }) => updateReferent(referentId, patch),
    onSettled: () => invalidate(client, ['referents']),
  });
}

export function useDeleteReferent() {
  const client = useQueryClient();
  return useMutation({ mutationFn: deleteReferent, onSettled: () => invalidate(client, ['referents']) });
}

/** Veto a piece or a queued action: reject it with a mandatory note (on a network action, discards the person). */
export function useVeto() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ actionId, note }: { actionId: string; note: string }) => rejectAction(actionId, note),
    onSettled: () => invalidate(client, keys.editorialAll, keys.calendarioAll, keys.actividadAll, keys.actionsAll, keys.redAll, keys.tuTurno),
  });
}

/** Approve the exact version (`payload_hash`) of a proposal that waits for Gustavo (a capability in `approval` mode). */
export function useApproveAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ actionId, expectedHash, note = '' }: { actionId: string; expectedHash: string; note?: string }) => approveAction(actionId, expectedHash, note),
    onSettled: () => invalidate(client, keys.editorialAll, keys.calendarioAll, keys.actividadAll, keys.actionsAll, keys.redAll, keys.tuTurno),
  });
}

export function useResolveAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ actionId, outcome, note }: { actionId: string; outcome: 'confirmed' | 'failed'; note: string }) => resolveAction(actionId, outcome, note),
    onSettled: () => invalidate(client, keys.tuTurno, keys.actionsAll, keys.actividadAll, keys.calendarioAll, keys.overview),
  });
}

/** Total stop / resume. 409 when OPERATOR_PAUSED comes from the environment. */
export function useSetControl() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ paused, reason }: { paused: boolean; reason: string }) => setControl(paused, reason),
    onSettled: () => invalidate(client, keys.overview, keys.tuTurno, keys.feed, keys.calendarioAll),
  });
}

export function useSetAccountPaused() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ accountId, paused, reason }: { accountId: string; paused: boolean; reason: string }) => setAccountPaused(accountId, paused, reason),
    onSettled: () => invalidate(client, keys.overview, keys.accounts, keys.tuTurno, keys.linkedin),
  });
}

/** Paid: queues the editorial circuit for the next free slot (ask for confirmation first). */
export function usePlanPiece() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (requestId?: string) => planPiece(requestId), onSettled: () => invalidate(client, keys.editorialAll, keys.calendarioAll, keys.actividadAll) });
}

// ================================================================ weekly summary (Resultados › Resumen de la semana)

/** GET /api/v1/resultados/resumen-semanal: the latest summary, the previous weeks and «Generar ahora». */
export function useResumenSemanal() {
  return useQuery({ queryKey: keys.resumenSemanal, queryFn: getResumenSemanal, refetchInterval: REFRESH.resultados });
}

export type ResumenDecision = 'visto' | 'aplicar' | 'descartar' | 'deshacer';
const DECISIONS = { visto: markResumenVisto, aplicar: aplicarResumen, descartar: descartarResumen, deshacer: deshacerResumen } as const;

/** Gustavo's decision on a summary. Applying or undoing also changes the orientation (Ajustes) and the Tu turno card. */
export function useResumenDecision() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ summaryId, decision }: { summaryId: string; decision: ResumenDecision }) => DECISIONS[decision](summaryId),
    onSettled: () => invalidate(client, keys.resumenSemanal, keys.orientacion, keys.ajustes, keys.tuTurno),
  });
}

/** Paid: queues the summary of the last week (ask for confirmation first, with the estimated cost). */
export function useGenerarResumen() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (requestId?: string) => generarResumen(requestId), onSettled: () => invalidate(client, keys.resumenSemanal) });
}
