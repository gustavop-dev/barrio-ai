import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { keys } from './queryClient';

export interface ProfileSection {
  id: string; title: string; action: 'change' | 'keep' | 'not_applicable' | 'missing';
  copy: string; audience: string; benefit: string; reason: string;
  citations: { unit_id: string; reason: string }[]; evidence: string[]; steps: string[];
  missing: { key: string; question: string; purpose: string }[]; issues?: string[];
  readiness: 'ready' | 'needs_input' | 'blocked'; decision: 'pending' | 'accepted' | 'declined';
  application: 'pending' | 'applied' | 'checked'; applied_at?: string; applied_text?: string; checked_at?: string;
  current: { text: string; source: string; at: string } | null; limit: number; limit_source: string;
}
export interface ProfileReview { ok: boolean; checks: { point: number; ok: boolean; reason: string }[]; identity_03: boolean; smile_01: boolean; clear_glasses: boolean }
export interface ProfileAsset {
  id: string; kind: string; width: number; height: number; url: string;
  review: { ok: boolean; options?: Record<string, ProfileReview> };
}
export interface ProfileProposal {
  id: string; version: number; revision: number; mode: string; state: string;
  sections: ProfileSection[]; photo_choice: '' | 'A' | 'B'; findings: string[];
  microphone_note: string; markdown: string; document_url: string; references_valid: boolean;
  assets: ProfileAsset[]; references: { id: string; role: string; note: string; version: number; url: string }[];
}
export type ProfileAction = 'accept' | 'adjust' | 'later' | 'decline' | 'applied' | 'changed' | 'choose_A' | 'choose_B' | 'verify';
export interface ProfileDecision { revision: number; section?: string; action: ProfileAction; note?: string }
const path = (id: string) => `/api/v1/perfil/${encodeURIComponent(id)}`;
export const profileKey = (id: string) => ['perfil', id] as const;
export const getProfile = (id: string) => api.get<ProfileProposal>(path(id));
export const decideProfile = (id: string, data: ProfileDecision) => api.post<ProfileProposal>(`${path(id)}/decision`, data);
export const profileDownload = (id: string, resource = 'documento') => api.post<{ url: string }>(`${path(id)}/descarga`, { resource });
export function useProfile(id: string, enabled = true) {
  return useQuery({ queryKey: profileKey(id), queryFn: () => getProfile(id), enabled,
    refetchInterval: (query) => ['queued', 'running'].includes(query.state.data?.state ?? '') ? 4000 : false });
}
export function useProfileDecision(id: string) {
  const client = useQueryClient();
  return useMutation({ mutationFn: (data: ProfileDecision) => decideProfile(id, data), networkMode: 'always',
    onSuccess: (data) => { client.setQueryData(profileKey(id), data); void client.invalidateQueries({ queryKey: keys.tuTurno }); },
    onError: () => { void client.invalidateQueries({ queryKey: profileKey(id) }); },
  });
}
