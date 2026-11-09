import type { ReferentChangeCard, ReferentProposal, ReferentExperimentCard } from '../api/referentes';
import { normalizeProfileUrl } from '../api/personas';

export function monthlyCountdown(deadline: string, now = Date.now()): string {
  const left = new Date(deadline).getTime() - now;
  const end = new Date(new Date(deadline).getTime() - 1).toLocaleDateString('es-CO', { timeZone: 'America/Bogota', day: 'numeric', month: 'long' });
  if (left <= 0) return `Plazo terminado: ${end}, 23:59 (America/Bogota)`;
  const hours = Math.ceil(left / 3_600_000);
  return `${hours >= 24 ? `Quedan ${Math.ceil(hours / 24)} días` : `Queda${hours === 1 ? '' : 'n'} ${hours} hora${hours === 1 ? '' : 's'}`} · hasta el ${end}, 23:59 (America/Bogota)`;
}
export function proposalTitle(p: ReferentProposal, outgoing = 'referente'): string {
  return p.kind === 'swap' ? `sale ${outgoing} · entra ${p.incoming?.display_name ?? 'referente'}`
    : p.kind === 'add' ? `Alta: ${p.incoming?.display_name ?? 'referente'}` : `Baja: ${outgoing}`;
}
export function editFields(card: ReferentChangeCard) {
  const p = card.proposal;
  return { reason: p.reason, outgoing: p.outgoing ?? '', name: p.incoming?.display_name ?? '',
    url: p.incoming?.profile_url ?? '', niche: p.incoming?.niche ?? '', audience: p.incoming?.audience ?? '',
    contribution: p.incoming?.contribution ?? '', source: '' };
}
export function editedProposal(card: ReferentChangeCard, fields: ReturnType<typeof editFields>): ReferentProposal {
  if (!fields.reason.trim()) throw new Error('El motivo es obligatorio.');
  const proposal = { ...card.proposal, reason: fields.reason.trim() };
  if (proposal.outgoing) proposal.outgoing = fields.outgoing;
  if (proposal.incoming) {
    const url = normalizeProfileUrl(fields.url);
    if (!url || !fields.name.trim() || !fields.niche.trim() || !fields.audience.trim() || !fields.contribution.trim()) {
      throw new Error('Completa el perfil, nicho, audiencia y aporte del candidato.');
    }
    const changed = url !== normalizeProfileUrl(proposal.incoming.profile_url);
    if (changed && !/^https:\/\//i.test(fields.source)) throw new Error('Añade una fuente pública para el nuevo perfil.');
    proposal.incoming = { ...proposal.incoming, profile_url: url, identifier: url.split('/in/')[1]!.replace(/\/$/, ''),
      display_name: fields.name.trim(), niche: fields.niche.trim(), audience: fields.audience.trim(), contribution: fields.contribution.trim(),
      ...(changed ? { top_voice: false, sources: [fields.source] } : {}) };
    if (fields.source) proposal.evidence = [...proposal.evidence, fields.source];
  }
  return proposal;
}
export function experimentLines(exp: ReferentExperimentCard): string[] {
  const date = (s: string) => new Date(s).toLocaleString('es-CO', { timeZone: 'America/Bogota' });
  const p = exp.plan;
  return [`Base: ${date(exp.starts_at)} → ${date(exp.focus_at)} (14 días)`,
    `Foco: ${date(exp.focus_at)} → ${date(exp.followup_at)} (28 días)`,
    `Seguimiento: ${date(exp.followup_at)} → ${date(exp.ends_at)} (7 días). America/Bogota.`,
    `Público: ${p.audience}`, `Comparación: ${p.comparison}`, `Criterio de encaje: ${p.fit_criterion}`,
    `Métrica: ${p.metric}. Denominador: ${p.denominator}.`,
    `Mínimo ${p.min_classified} personas clasificadas, ${Math.round(p.min_coverage * 100)} % de cobertura y ${p.min_fit_week} nuevas personas con encaje/semana, por encima de la base.`,
    `Hasta ${p.comments_week} comentarios útiles/semana dentro de BAR-15; mínimo ${p.min_exposure} publicados para evaluar. Un experimento a la vez.`,
    p.stop_rule, p.budget, p.confounders, p.limitations,
    'Los umbrales quedan fijados al aprobar. Aprobar no autoriza altas, bajas ni comentarios por adelantado.'];
}

export function evidenceSummary(card: ReferentChangeCard): string {
  const coverage = card.evidence.coverage as { observed?: number; classified?: number; fit?: number | null; fit_pct?: number | null } | undefined;
  if (!coverage || coverage.classified === undefined || coverage.observed === undefined) return 'Sin muestra suficiente para evaluar rendimiento; seguir midiendo.';
  const window = card.evidence.window as { start?: string; end?: string } | undefined;
  const period = window?.start && window?.end ? ` Ventana: ${window.start} → ${window.end}.` : '';
  return `Muestra: ${coverage.observed} personas observadas; cobertura ${coverage.classified}/${coverage.observed}; encaje ${coverage.fit ?? 'sin dato'}/${coverage.classified}${coverage.fit_pct != null ? ` (${coverage.fit_pct} %)` : ''}.${period}`;
}
