// La semana GASP (estrategia.py, docs/plan-estrategia-semanal.md): the type of each day (G crecimiento, A autoridad,
// S venta, P personal), the idea the director planned for it, what the reader needs and the audience signal behind it.
// GET /api/v1/estrategia/semana?dia=, PATCH /api/v1/estrategia/dias/<dia>, POST /api/v1/estrategia/mover and the paid
// POST /api/v1/estrategia/planear.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { REFRESH } from './hooks';
import { keys } from './queryClient';
import type { CalendarGasp, GaspType, Job } from './types';

export type { CalendarGasp, GaspType };

export const GASP_TYPES: readonly GaspType[] = ['G', 'A', 'S', 'P'];

export const GASP_LABEL: Record<GaspType, string> = { G: 'Crecimiento', A: 'Autoridad', S: 'Venta', P: 'Personal' };

/** What the type of a day is for, in one line (the audience comes first). */
export const GASP_PURPOSE: Record<GaspType, string> = {
  G: 'Que lo descubra gente nueva',
  A: 'Que confíen en su criterio',
  S: 'Convertir atención en conversaciones',
  P: 'Lo humano de construir empresas',
};

export type AudienceSignalKind =
  | 'referent_outlier'
  | 'comment_question'
  | 'owner_capture'
  | 'results_by_type'
  | 'audience_question';

export const SIGNAL_LABEL: Record<AudienceSignalKind, string> = {
  referent_outlier: 'Un post de referente que superó su mediana',
  comment_question: 'Una pregunta en tus comentarios',
  owner_capture: 'Algo que contaste de un comprador',
  results_by_type: 'Lo que funcionó por tipo',
  audience_question: 'Lo que pregunta la audiencia de tu industria',
};

export interface AudienceEvidence {
  kind: AudienceSignalKind | string;
  ref: string;
  note: string;
}

export interface PlanDay {
  date: string;
  type: GaspType;
  label: string;
  type_reason: string;
  idea: string | null;
  reason: string | null;
  reader_need: string | null;
  audience_evidence: AudienceEvidence | null;
  evidence_ok: boolean;
  pillar: string | null;
  format: string | null;
  /** planned · discarded · capture (an idea of his took the day) · used (its post was prepared). */
  state: 'planned' | 'discarded' | 'capture' | 'used' | string;
  owner_edited: boolean;
  /** False once the day passed or its post is prepared. */
  editable: boolean;
  piece_id: string | null;
}

export interface KeptIdea {
  date: string;
  type: GaspType;
  idea: string;
  reader_need: string | null;
  audience_evidence: AudienceEvidence | null;
}

export interface WeekPlan {
  week_start: string;
  week_end: string;
  /** estructura: only the types (free) · planeada: the director planned the ideas. */
  state: 'estructura' | 'planeada';
  state_label: string;
  summary: string | null;
  warnings: string[];
  days: PlanDay[];
  kept_ideas: KeptIdea[];
  month_share: Record<GaspType, { posts: number; pct: number; target_pct: number }>;
  cost_usd: number | null;
  regenerate: { available: boolean; pending: boolean; estimated_usd: number; max_usd: number };
  enabled: boolean;
}

export const estrategiaKeys = {
  all: ['estrategia'] as const,
  week: (dia: string) => ['estrategia', 'semana', dia] as const,
};

export const getSemana = (dia: string) => api.get<WeekPlan>(`/api/v1/estrategia/semana?dia=${encodeURIComponent(dia)}`);
/** Changes a day's type (its planned idea waits in kept_ideas) or discards its idea. */
export const cambiarDia = (dia: string, body: { tipo?: GaspType; descartar_idea?: boolean }) =>
  api.patch<WeekPlan>(`/api/v1/estrategia/dias/${encodeURIComponent(dia)}`, body);
/** Two days of the same week swap type and idea. */
export const moverDias = (desde: string, hasta: string) => api.post<WeekPlan>('/api/v1/estrategia/mover', { desde, hasta });
/** Paid: one call of the director for this week or the next one; his changes are kept. */
export const planearSemana = (semana: string, requestId?: string) =>
  api.post<{ job: Job }>('/api/v1/estrategia/planear', requestId ? { semana, request_id: requestId } : { semana });

export function useSemana(dia: string) {
  return useQuery({ queryKey: estrategiaKeys.week(dia), queryFn: () => getSemana(dia), refetchInterval: REFRESH.calendario });
}

function useRefresh() {
  const client = useQueryClient();
  return () => Promise.all([client.invalidateQueries({ queryKey: estrategiaKeys.all }), client.invalidateQueries({ queryKey: keys.calendarioAll })]);
}

export function useCambiarDia() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: ({ dia, ...body }: { dia: string; tipo?: GaspType; descartar_idea?: boolean }) => cambiarDia(dia, body), onSettled: refresh });
}

export function useMoverDias() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: ({ desde, hasta }: { desde: string; hasta: string }) => moverDias(desde, hasta), onSettled: refresh });
}

export function usePlanearSemana() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: ({ semana, requestId }: { semana: string; requestId?: string }) => planearSemana(semana, requestId), onSettled: refresh });
}
