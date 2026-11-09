import { ExternalLink } from '@/components/ui/ExternalLink';
import { useState } from 'react';
import { View } from 'react-native';
import { useReferentReviews } from '@compartido/api/referentes';
import { Button, ErrorRetry, T } from '@/components/ui';
export function ReferentHistory({ account }: { account: string }) {
  const query = useReferentReviews(account);
  const [open, setOpen] = useState(false);
  return <View>
    <Button onPress={() => setOpen(!open)}>{open ? 'Ocultar revisiones' : 'Revisiones y resultados'}</Button>
    <ErrorRetry error={query.error} onRetry={() => void query.refetch()} />
    {open ? query.data?.slice(0, 2).map(review => <View key={review.id}><T>Revisión {review.month} · {review.dossier.status ?? review.state}</T>
      <T>{review.dossier.summary}</T>
      {review.dossier.sources?.map(source => <View key={source.id}><ExternalLink href={source.url}>{source.title}</ExternalLink><T variant="detalle">{source.retrieved_at}</T></View>)}
      {review.changes.map(change => <T key={change.id}>{change.proposal.incoming?.display_name ?? 'Baja de referente'}: {change.state === 'aplicada_por_plazo' ? 'Aplicada por plazo autorizado' : change.state} {change.conflict} · {change.proposal.reason}</T>)}
      {review.experiments.map(exp => <View key={exp.id}><T>Experimento: {exp.results.final?.outcome ?? exp.state}</T>
        {exp.results.final ? <T>Personas con encaje por semana: base {exp.results.final.base_fit_week}, foco {exp.results.final.focus_fit_week}. {exp.results.final.limitations}</T> : null}</View>)}
    </View>) : null}
  </View>;
}
