import { useQuery } from '@tanstack/react-query';
import { api } from './client';

export interface ReferentCandidate {
  identifier: string; display_name: string; profile_url: string;
  niche: string; audience: string; contribution: string; top_voice: boolean; sources: string[];
}
export interface ReferentProposal {
  kind: 'add' | 'remove' | 'swap'; outgoing?: string; incoming?: ReferentCandidate;
  reason: string; evidence: string[]; experiment?: { hypothesis: string; days: number[]; comments_week: number; approval_required: boolean };
}
export interface ReferentSource { id: string; url: string; title: string; retrieved_at: string; quoted_text?: string }
export interface ReferentChangeCard {
  id: string; account: string; version: number; state: string; proposal: ReferentProposal;
  outgoing: { id: string; display_name: string; profile_url: string } | null;
  sources: ReferentSource[]; limitations: string[]; evidence: Record<string, unknown>;
  occupancy: { before: number; after: number; main: number; variables: number };
  can_decide: boolean; conflict: string; endpoint: string;
}
export interface ExperimentPlan {
  control_referent: string; confounders: string;
  base_days: number; focus_days: number; followup_days: number; comments_week: number;
  min_classified: number; min_coverage: number; min_fit_week: number; min_exposure: number;
  hypothesis: string; audience: string; comparison: string; fit_criterion: string;
  positioning_version: string; orientation_version: string; metric: string; denominator: string;
  stop_rule: string; budget: string; limitations: string;
}
export interface ReferentExperimentCard {
  id: string; version: number; state: string; plan: ExperimentPlan;
  starts_at: string; focus_at: string; followup_at: string; ends_at: string;
  can_decide: boolean; endpoint: string; results: Record<string, unknown>;
}
export interface ReferentReview {
  id: string; month: string; state: string; deadline: string;
  dossier: { summary?: string; status?: string; limitations?: string[]; sources?: ReferentSource[] };
  changes: { id: string; state: string; proposal: ReferentProposal; conflict: string }[];
  experiments: { id: string; state: string; plan: ExperimentPlan; results: { final?: { outcome: string; base_fit_week: number; focus_fit_week: number; limitations: string } } }[];
}
export function useReferentReviews(account: string) {
  return useQuery({ queryKey: ['referents', 'reviews', account], enabled: Boolean(account),
    queryFn: () => api.get<ReferentReview[]>(`/api/v1/referentes/revisiones?account=${encodeURIComponent(account)}`) });
}
