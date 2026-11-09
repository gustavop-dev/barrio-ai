import { useReferentReviews } from '../../../../compartido/src/api/referentes';
import { ErrorRetry, ExternalLink } from '../../components/ui';
export function ReferentHistory({ account }: { account: string }) {
  const query = useReferentReviews(account);
  return <div>
    <ErrorRetry error={query.error} onRetry={() => void query.refetch()} />
    {query.data?.slice(0, 2).map(review => <details key={review.id}><summary>Revisión {review.month} · {review.dossier.status ?? review.state}</summary>
      <p>{review.dossier.summary}</p>
      {review.dossier.sources?.map(source => <p key={source.id}><ExternalLink href={source.url}>{source.title}</ExternalLink> · {source.retrieved_at}</p>)}
      {review.changes.map(change => <p key={change.id}>{change.proposal.incoming?.display_name ?? 'Baja de referente'}: {change.state === 'aplicada_por_plazo' ? 'Aplicada por plazo autorizado' : change.state} {change.conflict} · {change.proposal.reason}</p>)}
      {review.experiments.map(exp => <div key={exp.id}><p>Experimento: {exp.results.final?.outcome ?? exp.state}</p>
        {exp.results.final ? <p>Personas con encaje por semana: base {exp.results.final.base_fit_week}, foco {exp.results.final.focus_fit_week}. {exp.results.final.limitations}</p> : null}</div>)}
    </details>)}
  </div>;
}
