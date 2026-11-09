import type { Panel, ReaderAssessment } from '../api/types';

export function communityTrace(panel: Panel): string {
  const study = panel.community_study;
  return study?.study_id ? `${study.status} · ${study.study_id} · Versión ${study.version}` : 'Sin estudio vigente';
}

export function communityEffects(reader: ReaderAssessment): string[] {
  return (['variant_a', 'variant_b'] as const).flatMap((variant, index) =>
    (reader[variant]?.community ?? []).map((ref) =>
      `${index ? 'B' : 'A'} · ${ref.finding_id} · ${ref.basis === 'observed_in_sample' ? 'Observado en la muestra' : 'Hipótesis del lector'}: ${ref.effect} ${ref.uncertainty}`));
}
