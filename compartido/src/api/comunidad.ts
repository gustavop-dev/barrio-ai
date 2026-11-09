import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

export interface CommunityFinding {
  id: string;
  pattern: string;
  basis: 'observed' | 'declared' | 'hypothesis';
  people: number;
  counterexamples: number | null;
  counterexample_note?: string;
  examples?: { id: string; paraphrase: string }[];
  interpretation: string;
  uncertainty: string;
}

export interface CommunityReport {
  status: string;
  pending: boolean;
  study: null | {
    id: string; period: string; version: number; state: string;
    window_start: string; window_end: string; created_at: string; expires_at: string;
    positioning_version: string;
    coverage: { sample_size?: number; potential?: number; since?: string | null; limitations?: string[] };
    summary: { findings?: CommunityFinding[]; unknown_follow_reason?: number; uncertainties?: string[]; units?: string[] };
  };
  sources: { id: string; person: string; kind: string; text: string; url: string;
    event_at: string | null; observed_at: string; analysis: { follow_status?: string; follow_quote?: string } }[];
}

export const communityKey = ['comunidad'] as const;
export const communityCopy = {
  title: 'Estudio de comunidad',
  privacy: 'Solo perfiles y comentarios públicos. Los lectores reciben patrones sin nombres ni enlaces personales.',
  retention: 'Extractos: hasta 90 días. Resúmenes: hasta 180 días. El panel requiere un estudio de los últimos 45 días.',
  pending: 'Estudio en preparación',
  insufficient: 'Sin muestra suficiente',
  withdrawal: 'Retirar invalida el resumen y evita volver a recoger esta evidencia. Los contactos se conservan.',
};
export const findingBasis = (basis: CommunityFinding['basis']) =>
  basis === 'hypothesis' ? 'Hipótesis limitada' : basis === 'declared' ? 'Motivo declarado públicamente' : 'Observado en la muestra';

export function useCommunity(account: string) {
  return useQuery({ queryKey: [...communityKey, account], enabled: Boolean(account),
    queryFn: ({ signal }) => api.get<CommunityReport>(`/api/v1/comunidad?account=${encodeURIComponent(account)}`, signal),
    staleTime: 0, refetchInterval: (query) => query.state.data?.pending ? 5000 : false });
}

export function useRefreshCommunity() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (account: string) => api.post('/api/v1/comunidad', { account, refresh: true }),
    onSuccess: () => client.invalidateQueries({ queryKey: communityKey }) });
}

export function useWithdrawCommunity() {
  const client = useQueryClient();
  return useMutation({ mutationFn: ({ source, wholePerson = false, reason = 'excluded' }: {
    source: string; wholePerson?: boolean; reason?: 'excluded' | 'incorrect';
  }) => api.post(`/api/v1/comunidad/fuentes/${encodeURIComponent(source)}/retirar`, { whole_person: wholePerson, reason }),
    onSuccess: () => client.invalidateQueries({ queryKey: communityKey }) });
}
